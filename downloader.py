#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Douyin Downloader - Unified Enhanced Version
Supports batch downloading of videos, images, user homepages, collections, and more.
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse
import argparse
import yaml

# Third-party libraries
try:
    import aiohttp
    import requests
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
    from rich.table import Table
    from rich.panel import Panel
    from rich.live import Live
    from rich import print as rprint
except ImportError as e:
    print(f"Please install necessary dependencies: pip install aiohttp requests rich pyyaml")
    sys.exit(1)

# Add project path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import project modules
from apiproxy.douyin import douyin_headers
from apiproxy.douyin.urls import Urls
from apiproxy.douyin.result import Result
from apiproxy.common.utils import Utils
from apiproxy.douyin.auth.cookie_manager import AutoCookieManager
from apiproxy.douyin.database import DataBase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('downloader.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Rich console
console = Console()


class ContentType:
    """Content type enumeration"""
    VIDEO = "video"
    IMAGE = "image" 
    USER = "user"
    MIX = "mix"
    MUSIC = "music"
    LIVE = "live"


class DownloadStats:
    """Download statistics"""
    def __init__(self):
        self.total = 0
        self.success = 0
        self.failed = 0
        self.skipped = 0
        self.start_time = time.time()
    
    @property
    def success_rate(self):
        return (self.success / self.total * 100) if self.total > 0 else 0
    
    @property
    def elapsed_time(self):
        return time.time() - self.start_time
    
    def to_dict(self):
        return {
            'total': self.total,
            'success': self.success,
            'failed': self.failed,
            'skipped': self.skipped,
            'success_rate': f"{self.success_rate:.1f}%",
            'elapsed_time': f"{self.elapsed_time:.1f}s"
        }


class RateLimiter:
    """Rate limiter"""
    def __init__(self, max_per_second: float = 2):
        self.max_per_second = max_per_second
        self.min_interval = 1.0 / max_per_second
        self.last_request = 0
    
    async def acquire(self):
        """Acquire permission"""
        current = time.time()
        time_since_last = current - self.last_request
        if time_since_last < self.min_interval:
            await asyncio.sleep(self.min_interval - time_since_last)
        self.last_request = time.time()


class RetryManager:
    """Retry manager"""
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.retry_delays = [1, 2, 5]  # Retry delays
    
    async def execute_with_retry(self, func, *args, **kwargs):
        """Execute function and auto-retry"""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                    logger.warning(f"Attempt {attempt + 1} failed: {e}, retrying in {delay}s...")
                    await asyncio.sleep(delay)
        raise last_error


class UnifiedDownloader:
    """Unified Downloader"""
    
    def __init__(self, config_path: str = "config.yml"):
        self.config = self._load_config(config_path)
        self.urls_helper = Urls()
        self.result_helper = Result()
        self.utils = Utils()
        
        # Component initialization
        self.stats = DownloadStats()
        self.rate_limiter = RateLimiter(max_per_second=2)
        self.retry_manager = RetryManager(max_retries=self.config.get('retry_times', 3))
        
        # Cookie and headers (lazy initialization, supports auto-fetch)
        self.cookies = self.config.get('cookies') if 'cookies' in self.config else self.config.get('cookie')
        self.auto_cookie = bool(self.config.get('auto_cookie')) or (isinstance(self.config.get('cookie'), str) and self.config.get('cookie') == 'auto') or (isinstance(self.config.get('cookies'), str) and self.config.get('cookies') == 'auto')
        self.headers = {**douyin_headers}
        # Avoid server using brotli causing aiohttp decompression failure (empty response if brotli library not installed)
        self.headers['accept-encoding'] = 'gzip, deflate'
        # Incremental download and database
        self.increase_cfg: Dict[str, Any] = self.config.get('increase', {}) or {}
        self.enable_database: bool = bool(self.config.get('database', True))
        self.db: Optional[DataBase] = DataBase() if self.enable_database else None
        
        # Save path
        self.save_path = Path(self.config.get('path', './Downloaded'))
        self.save_path.mkdir(parents=True, exist_ok=True)
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration file"""
        if not os.path.exists(config_path):
            # Compatible config naming: priority config.yml, then config_simple.yml
            alt_path = 'config_simple.yml'
            if os.path.exists(alt_path):
                config_path = alt_path
            else:
                # Return empty config, determined by CLI arguments
                return {}
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Simplify config compatibility: links/link, output_dir/path, cookie/cookies
        if 'links' in config and 'link' not in config:
            config['link'] = config['links']
        if 'output_dir' in config and 'path' not in config:
            config['path'] = config['output_dir']
        if 'cookie' in config and 'cookies' not in config:
            config['cookies'] = config['cookie']
        if isinstance(config.get('cookies'), str) and config.get('cookies') == 'auto':
            config['auto_cookie'] = True
        
        # Allow no link (passed via CLI)
        # If both are missing, prompt later at runtime
        
        return config
    
    def _build_cookie_string(self) -> str:
        """Build Cookie string"""
        if isinstance(self.cookies, str):
            return self.cookies
        elif isinstance(self.cookies, dict):
            return '; '.join([f'{k}={v}' for k, v in self.cookies.items()])
        elif isinstance(self.cookies, list):
            # Support cookies list from AutoCookieManager
            try:
                kv = {c.get('name'): c.get('value') for c in self.cookies if c.get('name') and c.get('value')}
                return '; '.join([f'{k}={v}' for k, v in kv.items()])
            except Exception:
                return ''
        return ''

    async def _initialize_cookies_and_headers(self):
        """Initialize Cookie and headers (supports auto-fetch)"""
        # If config is 'auto', treat as not provided, trigger auto-fetch
        if isinstance(self.cookies, str) and self.cookies.strip().lower() == 'auto':
            self.cookies = None
        
        # If cookies explicitly provided, use directly
        cookie_str = self._build_cookie_string()
        if cookie_str:
            self.headers['Cookie'] = cookie_str
            # Also set to global douyin_headers to ensure all API requests use it
            from apiproxy.douyin import douyin_headers
            douyin_headers['Cookie'] = cookie_str
            return
        
        # Auto-fetch Cookie
        if self.auto_cookie:
            try:
                console.print("[cyan]🔐 Automatically fetching Cookie...[/cyan]")
                async with AutoCookieManager(cookie_file='cookies.pkl', headless=False) as cm:
                    cookies_list = await cm.get_cookies()
                    if cookies_list:
                        self.cookies = cookies_list
                        cookie_str = self._build_cookie_string()
                        if cookie_str:
                            self.headers['Cookie'] = cookie_str
                            # Also set to global douyin_headers to ensure all API requests use it
                            from apiproxy.douyin import douyin_headers
                            douyin_headers['Cookie'] = cookie_str
                            console.print("[green]✅ Cookie fetched successfully[/green]")
                            return
                console.print("[yellow]⚠️ Auto-fetch Cookie failed or empty, continuing in no-Cookie mode[/yellow]")
            except Exception as e:
                logger.warning(f"Auto-fetch Cookie failed: {e}")
                console.print("[yellow]⚠️ Auto-fetch Cookie failed, continuing in no-Cookie mode[/yellow]")
        
        # If failed to get Cookie, don't set it, use default headers
    
    def detect_content_type(self, url: str) -> ContentType:
        """Detect URL content type"""
        if '/user/' in url:
            return ContentType.USER
        elif '/video/' in url or 'v.douyin.com' in url:
            return ContentType.VIDEO
        elif '/note/' in url:
            return ContentType.IMAGE
        elif '/collection/' in url or '/mix/' in url:
            return ContentType.MIX
        elif '/music/' in url:
            return ContentType.MUSIC
        elif 'live.douyin.com' in url:
            return ContentType.LIVE
        else:
            return ContentType.VIDEO  # Default to video
    
    async def resolve_short_url(self, url: str) -> str:
        """Resolve short URL"""
        if 'v.douyin.com' in url:
            try:
                # Use synchronous request to get redirect
                response = requests.get(url, headers=self.headers, allow_redirects=True, timeout=10)
                final_url = response.url
                logger.info(f"Resolve short URL: {url} -> {final_url}")
                return final_url
            except Exception as e:
                logger.warning(f"Failed to resolve short URL: {e}")
        return url
    
    def extract_id_from_url(self, url: str, content_type: ContentType = None) -> Optional[str]:
        """Extract ID from URL
        
        Args:
            url: URL to parse
            content_type: Content type (optional, used to guide extraction)
        """
        # If known as user page, extract user ID directly
        if content_type == ContentType.USER or '/user/' in url:
            user_patterns = [
                r'/user/([\w-]+)',
                r'sec_uid=([\w-]+)'
            ]
            
            for pattern in user_patterns:
                match = re.search(pattern, url)
                if match:
                    user_id = match.group(1)
                    logger.info(f"Extracted user ID: {user_id}")
                    return user_id
        
        # Video ID patterns (priority)
        video_patterns = [
            r'/video/(\d+)',
            r'/note/(\d+)',
            r'modal_id=(\d+)',
            r'aweme_id=(\d+)',
            r'item_id=(\d+)'
        ]
        
        for pattern in video_patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                logger.info(f"Extracted video ID: {video_id}")
                return video_id
        
        # Other patterns
        other_patterns = [
            r'/collection/(\d+)',
            r'/music/(\d+)'
        ]
        
        for pattern in other_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # Try to extract numeric ID from URL
        number_match = re.search(r'(\d{15,20})', url)
        if number_match:
            video_id = number_match.group(1)
            logger.info(f"Extracted numeric ID from URL: {video_id}")
            return video_id
        
        logger.error(f"Unable to extract ID from URL: {url}")
        return None

    def _get_aweme_id_from_info(self, info: Dict) -> Optional[str]:
        """Extract aweme_id from aweme info"""
        try:
            if 'aweme_id' in info:
                return str(info.get('aweme_id'))
            # aweme_detail structure
            return str(info.get('aweme', {}).get('aweme_id') or info.get('aweme_id'))
        except Exception:
            return None

    def _get_sec_uid_from_info(self, info: Dict) -> Optional[str]:
        """Extract author sec_uid from aweme info"""
        try:
            return info.get('author', {}).get('sec_uid')
        except Exception:
            return None

    def _should_skip_increment(self, context: str, info: Dict, mix_id: Optional[str] = None, music_id: Optional[str] = None, sec_uid: Optional[str] = None) -> bool:
        """Determine whether to skip download based on incremental config and database records"""
        if not self.db:
            return False
        aweme_id = self._get_aweme_id_from_info(info)
        if not aweme_id:
            return False

        try:
            if context == 'post' and self.increase_cfg.get('post', False):
                sec = sec_uid or self._get_sec_uid_from_info(info) or ''
                return bool(self.db.get_user_post(sec, int(aweme_id)) if aweme_id.isdigit() else None)
            if context == 'like' and self.increase_cfg.get('like', False):
                sec = sec_uid or self._get_sec_uid_from_info(info) or ''
                return bool(self.db.get_user_like(sec, int(aweme_id)) if aweme_id.isdigit() else None)
            if context == 'mix' and self.increase_cfg.get('mix', False):
                sec = sec_uid or self._get_sec_uid_from_info(info) or ''
                mid = mix_id or ''
                return bool(self.db.get_mix(sec, mid, int(aweme_id)) if aweme_id.isdigit() else None)
            if context == 'music' and self.increase_cfg.get('music', False):
                mid = music_id or ''
                return bool(self.db.get_music(mid, int(aweme_id)) if aweme_id.isdigit() else None)
        except Exception:
            return False
        return False

    def _record_increment(self, context: str, info: Dict, mix_id: Optional[str] = None, music_id: Optional[str] = None, sec_uid: Optional[str] = None):
        """Write database record after successful download"""
        if not self.db:
            return
        aweme_id = self._get_aweme_id_from_info(info)
        if not aweme_id or not aweme_id.isdigit():
            return
        try:
            if context == 'post':
                sec = sec_uid or self._get_sec_uid_from_info(info) or ''
                self.db.insert_user_post(sec, int(aweme_id), info)
            elif context == 'like':
                sec = sec_uid or self._get_sec_uid_from_info(info) or ''
                self.db.insert_user_like(sec, int(aweme_id), info)
            elif context == 'mix':
                sec = sec_uid or self._get_sec_uid_from_info(info) or ''
                mid = mix_id or ''
                self.db.insert_mix(sec, mid, int(aweme_id), info)
            elif context == 'music':
                mid = music_id or ''
                self.db.insert_music(mid, int(aweme_id), info)
        except Exception:
            pass
    
    async def download_single_video(self, url: str, progress=None) -> bool:
        """Download single video/image set"""
        try:
            # Resolve short URL
            url = await self.resolve_short_url(url)
            
            # Extract ID
            video_id = self.extract_id_from_url(url, ContentType.VIDEO)
            if not video_id:
                logger.error(f"Unable to extract ID from URL: {url}")
                return False
            
            # If video ID not extracted, try using it directly as video ID
            if not video_id and '/user/' not in url:
                # Short URL might contain video ID directly
                video_id = url.split('/')[-2] if url.endswith('/') else url.split('/')[-1]
                logger.info(f"Attempting to extract ID from short URL path: {video_id}")
            
            if not video_id:
                logger.error(f"Unable to extract video ID from URL: {url}")
                return False
            
            # Rate limit
            await self.rate_limiter.acquire()
            
            # Get video info
            if progress:
                progress.update(task_id=progress.task_ids[-1], description="Fetching video info...")
            
            video_info = await self.retry_manager.execute_with_retry(
                self._fetch_video_info, video_id
            )
            
            if not video_info:
                logger.error(f"Unable to fetch video info: {video_id}")
                self.stats.failed += 1
                return False
            
            # Download media files
            if progress:
                progress.update(task_id=progress.task_ids[-1], description="Downloading media files...")
            
            success = await self._download_media_files(video_info, progress)
            
            if success:
                self.stats.success += 1
                logger.info(f"✅ Download successful: {url}")
            else:
                self.stats.failed += 1
                logger.error(f"❌ Download failed: {url}")
            
            return success
            
        except Exception as e:
            logger.error(f"Exception downloading video {url}: {e}")
            self.stats.failed += 1
            return False
        finally:
            self.stats.total += 1
    
    async def _fetch_video_info(self, video_id: str) -> Optional[Dict]:
        """Fetch video info - Using Playwright for bot bypass"""
        
        # Try Playwright method first (most reliable for bypassing bot detection)
        playwright_result = await self._fetch_video_info_playwright(video_id)
        if playwright_result:
            return playwright_result
        
        # Fallback to API methods
        try:
            # Use Douyin class from douyin.py
            from apiproxy.douyin.douyin import Douyin
            
            # Create Douyin instance
            dy = Douyin(database=False)
            
            # Set our cookies to douyin_headers
            if hasattr(self, 'cookies') and self.cookies:
                cookie_str = self._build_cookie_string()
                if cookie_str:
                    from apiproxy.douyin import douyin_headers
                    douyin_headers['Cookie'] = cookie_str
                    logger.info(f"Setting Cookie to Douyin class: {cookie_str[:100]}...")
            
            try:
                # Use existing successful implementation
                result = dy.getAwemeInfo(video_id)
                if result:
                    logger.info(f"Douyin class successfully fetched video info: {result.get('desc', '')[:30]}")
                    return result
                else:
                    logger.error("Douyin class returned empty result")
                    
            except Exception as e:
                logger.error(f"Douyin class failed to fetch video info: {e}")
                
        except Exception as e:
            logger.error(f"Failed to import or use Douyin class: {e}")
            import traceback
            traceback.print_exc()
        
        # If Douyin class fails, try fallback interface (iesdouyin, no X-Bogus required)
        try:
            fallback_url = f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={video_id}"
            logger.info(f"Attempting fallback interface to fetch video info: {fallback_url}")
            
            # Set more complete headers to mimic real browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': f'https://www.douyin.com/video/{video_id}',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin'
            }
            
            # Add cookies to fallback request
            cookie_str = self._build_cookie_string()
            if cookie_str:
                headers['Cookie'] = cookie_str
            
            async with aiohttp.ClientSession() as session:
                async with session.get(fallback_url, headers=headers, timeout=15) as response:
                    logger.info(f"Fallback interface response status: {response.status}")
                    if response.status != 200:
                        logger.error(f"Fallback interface request failed, status code: {response.status}")
                    else:
                        text = await response.text()
                        logger.info(f"Fallback interface response content length: {len(text)}")
                        
                        if text:
                            try:
                                data = json.loads(text)
                                logger.info(f"Fallback interface returned data keys: {list(data.keys()) if data else 'empty'}")
                                
                                item_list = (data or {}).get('item_list') or []
                                if item_list:
                                    aweme_detail = item_list[0]
                                    logger.info("Fallback interface successfully fetched video info")
                                    return aweme_detail
                                    
                            except json.JSONDecodeError as e:
                                logger.error(f"Fallback interface JSON parsing failed: {e}")
                        
        except Exception as e:
            logger.error(f"Fallback interface failed to fetch video info: {e}")
        
        # Try alternative web share API (more stable for single videos)
        try:
            share_api_url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={video_id}&aid=6383&device_platform=webapp"
            logger.info(f"Attempting web share API: {share_api_url[:100]}...")
            
            headers_share = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': f'https://www.douyin.com/video/{video_id}',
                'Accept': 'application/json',
            }
            
            cookie_str = self._build_cookie_string()
            if cookie_str:
                headers_share['Cookie'] = cookie_str
            
            async with aiohttp.ClientSession() as session:
                async with session.get(share_api_url, headers=headers_share, timeout=15) as response:
                    if response.status == 200:
                        text = await response.text()
                        if text:
                            try:
                                data = json.loads(text)
                                aweme_detail = data.get('aweme_detail')
                                if aweme_detail:
                                    logger.info("Web share API successfully fetched video info")
                                    return aweme_detail
                            except json.JSONDecodeError:
                                pass
                                
        except Exception as e:
            logger.error(f"Web share API failed: {e}")
        
        # Try mobile API endpoint (often less protected)
        try:
            # Use mobile endpoint which requires less strict cookie validation
            mobile_api_url = f"https://m.douyin.com/web/api/v2/aweme/iteminfo/?item_ids={video_id}"
            logger.info(f"Attempting mobile API: {mobile_api_url}")
            
            headers_mobile = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.32',
                'Referer': 'https://m.douyin.com/',
                'Accept': 'application/json',
            }
            
            cookie_str = self._build_cookie_string()
            if cookie_str:
                headers_mobile['Cookie'] = cookie_str
            
            async with aiohttp.ClientSession() as session:
                async with session.get(mobile_api_url, headers=headers_mobile, timeout=15) as response:
                    if response.status == 200:
                        text = await response.text()
                        if text:
                            try:
                                data = json.loads(text)
                                item_list = data.get('item_list') or []
                                if item_list and len(item_list) > 0:
                                    logger.info("Mobile API successfully fetched video info")
                                    return item_list[0]
                            except json.JSONDecodeError:
                                pass
                                
        except Exception as e:
            logger.error(f"Mobile API failed: {e}")
        
        # Final ultimate fallback: yt-dlp
        logger.info("🚨 All methods failed, trying yt-dlp as last resort...")
        ytdlp_result = await self._fetch_video_info_ytdlp(video_id)
        if ytdlp_result:
            return ytdlp_result
        
        return None
    
    async def _fetch_video_info_playwright(self, video_id: str) -> Optional[Dict]:
        """Fetch video info using Playwright to bypass bot detection"""
        try:
            from playwright.async_api import async_playwright
            
            logger.info(f"🎭 Using Playwright to fetch video {video_id}...")
            
            video_url = f"https://www.douyin.com/video/{video_id}"
            
            async with async_playwright() as p:
                # Launch browser with stealth mode
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process'
                    ]
                )
                
                # Create context with realistic settings
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='zh-CN',
                    timezone_id='Asia/Shanghai',
                    permissions=['geolocation'],
                    geolocation={'latitude': 31.2304, 'longitude': 121.4737},  # Shanghai
                )
                
                # Add stealth scripts
                await context.add_init_script("""
                    // Overwrite the `navigator.webdriver` property
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined,
                    });
                    
                    // Mock plugins
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5],
                    });
                    
                    // Mock languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['zh-CN', 'zh', 'en'],
                    });
                """)
                
                # Set cookies if available
                if hasattr(self, 'cookies') and self.cookies:
                    if isinstance(self.cookies, list):
                        await context.add_cookies(self.cookies)
                    elif isinstance(self.cookies, dict):
                        cookies_list = [
                            {'name': k, 'value': v, 'domain': '.douyin.com', 'path': '/'}
                            for k, v in self.cookies.items()
                        ]
                        await context.add_cookies(cookies_list)
                
                page = await context.new_page()
                
                # Intercept API responses
                video_data = {}
                video_data_found = asyncio.Event()
                
                async def handle_response(response):
                    """Capture video detail API responses"""
                    try:
                        url = response.url
                        # More precise filtering for video detail APIs
                        if (('aweme/detail' in url or 'aweme/v1/web/aweme/detail' in url) 
                            and response.status == 200):
                            try:
                                data = await response.json()
                                if data and isinstance(data, dict):
                                    logger.info(f"✅ Intercepted video detail API: {url[:80]}...")
                                    # Extract aweme_detail
                                    if 'aweme_detail' in data:
                                        video_data['aweme'] = data['aweme_detail']
                                        video_data_found.set()
                                        logger.info("🎉 Successfully captured video detail from API")
                            except Exception as e:
                                logger.debug(f"Failed to parse response: {e}")
                    except Exception:
                        pass
                
                page.on('response', handle_response)
                
                # Navigate to video page (don't wait for networkidle, too slow)
                try:
                    logger.info(f"📡 Navigating to {video_url}")
                    await page.goto(video_url, wait_until='domcontentloaded', timeout=15000)
                    
                    # Wait a bit for API calls to complete
                    logger.info("⏳ Waiting for video detail API...")
                    try:
                        await asyncio.wait_for(video_data_found.wait(), timeout=10)
                    except asyncio.TimeoutError:
                        logger.warning("⚠️ Timeout waiting for API, trying page extraction...")
                    
                    # Small delay for any remaining requests
                    await asyncio.sleep(1)
                    
                    # If we captured data from network, use it
                    if video_data.get('aweme'):
                        logger.info("✅ Successfully captured video data from network requests")
                        await browser.close()
                        return video_data['aweme']
                    
                    # Otherwise, try to extract from page content
                    logger.info("🔍 Attempting to extract data from page content...")
                    
                    # Scroll to trigger lazy loading
                    await page.evaluate("window.scrollBy(0, 500)")
                    await asyncio.sleep(0.5)
                    
                    # Method 1: Try all possible window variables
                    page_data = await page.evaluate("""
                        () => {
                            // Try multiple sources
                            const sources = [
                                window.__RENDER_DATA__,
                                window.RENDER_DATA,
                                window.__INITIAL_STATE__,
                                window.__INIT_PROPS__,
                            ];
                            
                            for (const source of sources) {
                                if (source) return { type: 'window', data: source };
                            }
                            
                            // Try RENDER_DATA script tag
                            const script = document.getElementById('RENDER_DATA');
                            if (script && script.textContent) {
                                return { type: 'script', data: script.textContent };
                            }
                            
                            return null;
                        }
                    """)
                    
                    if page_data:
                        try:
                            if page_data['type'] == 'script':
                                # URL decode and parse
                                import urllib.parse
                                decoded = urllib.parse.unquote(page_data['data'])
                                data = json.loads(decoded)
                            else:
                                data = page_data['data']
                            
                            logger.info(f"📦 Got page data, type: {page_data['type']}")
                            
                            # Navigate complex nested structure to find aweme_detail
                            def find_aweme_detail(obj, depth=0):
                                """Recursively search for aweme detail in nested dict"""
                                if depth > 5 or not isinstance(obj, dict):
                                    return None
                                
                                # Direct keys
                                if 'aweme_detail' in obj:
                                    return obj['aweme_detail']
                                if 'aweme' in obj and isinstance(obj['aweme'], dict):
                                    if 'aweme_id' in obj['aweme']:
                                        return obj['aweme']
                                
                                # Search recursively
                                for key, value in obj.items():
                                    if isinstance(value, dict):
                                        result = find_aweme_detail(value, depth + 1)
                                        if result:
                                            return result
                                
                                return None
                            
                            aweme = find_aweme_detail(data)
                            if aweme and 'aweme_id' in aweme:
                                logger.info("✅ Successfully extracted video data from page content")
                                await browser.close()
                                return aweme
                            else:
                                logger.warning("⚠️ Found data but no valid aweme_detail")
                        
                        except Exception as e:
                            logger.error(f"Failed to parse page data: {e}")
                    
                    logger.warning("⚠️ Could not extract video data from page")
                    
                except Exception as e:
                    logger.error(f"Error during page navigation: {e}")
                
                await browser.close()
                
        except ImportError:
            logger.warning("⚠️ Playwright not installed. Install with: pip install playwright && playwright install chromium")
        except Exception as e:
            logger.error(f"Playwright method failed: {e}")
        
        return None
    
    async def _fetch_video_info_ytdlp(self, video_id: str) -> Optional[Dict]:
        """Ultimate fallback: Use yt-dlp to extract video info"""
        try:
            import subprocess
            
            logger.info(f"🔄 Attempting yt-dlp fallback for video {video_id}...")
            
            video_url = f"https://www.douyin.com/video/{video_id}"
            
            # Try yt-dlp command
            cmd = [
                'yt-dlp',
                '--dump-json',
                '--no-download',
                video_url
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and result.stdout:
                try:
                    data = json.loads(result.stdout)
                    logger.info("✅ yt-dlp successfully extracted video info")
                    
                    # Convert yt-dlp format to douyin format
                    aweme_detail = {
                        'aweme_id': video_id,
                        'desc': data.get('description', ''),
                        'create_time': data.get('timestamp', 0),
                        'author': {
                            'nickname': data.get('uploader', 'unknown'),
                            'sec_uid': data.get('uploader_id', '')
                        },
                        'video': {
                            'play_addr': {
                                'url_list': [data.get('url', '')]
                            },
                            'cover': {
                                'url_list': [data.get('thumbnail', '')]
                            }
                        },
                        'music': {
                            'play_url': {
                                'url_list': []
                            }
                        }
                    }
                    
                    return aweme_detail
                    
                except json.JSONDecodeError:
                    logger.error("Failed to parse yt-dlp output")
            else:
                logger.warning(f"yt-dlp failed: {result.stderr[:200]}")
                
        except FileNotFoundError:
            logger.info("ℹ️ yt-dlp not installed. Install with: pip install yt-dlp")
        except subprocess.TimeoutExpired:
            logger.error("yt-dlp timeout")
        except Exception as e:
            logger.error(f"yt-dlp fallback failed: {e}")
        
        return None
    
    def _build_detail_params(self, aweme_id: str) -> str:
        """Build detail API parameters"""
        # Use same parameter format as existing douyinapi.py
        params = [
            f'aweme_id={aweme_id}',
            'device_platform=webapp',
            'aid=6383'
        ]
        return '&'.join(params)
    
    async def _download_media_files(self, video_info: Dict, progress=None) -> bool:
        """Download media files"""
        try:
            # Determine type
            is_image = bool(video_info.get('images'))
            
            # Build save path
            author_name = video_info.get('author', {}).get('nickname', 'unknown')
            desc = video_info.get('desc', '')[:50].replace('/', '_')
            # Compatible with create_time as timestamp or formatted string
            raw_create_time = video_info.get('create_time')
            dt_obj = None
            if isinstance(raw_create_time, (int, float)):
                dt_obj = datetime.fromtimestamp(raw_create_time)
            elif isinstance(raw_create_time, str) and raw_create_time:
                for fmt in ('%Y-%m-%d %H.%M.%S', '%Y-%m-%d_%H-%M-%S', '%Y-%m-%d %H:%M:%S'):
                    try:
                        dt_obj = datetime.strptime(raw_create_time, fmt)
                        break
                    except Exception:
                        pass
            if dt_obj is None:
                dt_obj = datetime.fromtimestamp(time.time())
            create_time = dt_obj.strftime('%Y-%m-%d_%H-%M-%S')
            
            folder_name = f"{create_time}_{desc}" if desc else create_time
            save_dir = self.save_path / author_name / folder_name
            save_dir.mkdir(parents=True, exist_ok=True)
            
            success = True
            
            if is_image:
                # Download image set (no watermark)
                images = video_info.get('images', [])
                for i, img in enumerate(images):
                    img_url = self._get_best_quality_url(img.get('url_list', []))
                    if img_url:
                        file_path = save_dir / f"image_{i+1}.jpg"
                        if await self._download_file(img_url, file_path):
                            logger.info(f"Downloaded image {i+1}/{len(images)}: {file_path.name}")
                        else:
                            success = False
            else:
                # Download video (no watermark)
                video_url = self._get_no_watermark_url(video_info)
                if video_url:
                    file_path = save_dir / f"{folder_name}.mp4"
                    if await self._download_file(video_url, file_path):
                        logger.info(f"Downloaded video: {file_path.name}")
                    else:
                        success = False
                
                # Download audio
                if self.config.get('music', True):
                    music_url = self._get_music_url(video_info)
                    if music_url:
                        file_path = save_dir / f"{folder_name}_music.mp3"
                        await self._download_file(music_url, file_path)
            
            # Download cover
            if self.config.get('cover', True):
                cover_url = self._get_cover_url(video_info)
                if cover_url:
                    file_path = save_dir / f"{folder_name}_cover.jpg"
                    await self._download_file(cover_url, file_path)
            
            # Save JSON data
            if self.config.get('json', True):
                json_path = save_dir / f"{folder_name}_data.json"
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(video_info, f, ensure_ascii=False, indent=2)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to download media files: {e}")
            return False
    
    def _get_no_watermark_url(self, video_info: Dict) -> Optional[str]:
        """Get no-watermark video URL"""
        try:
            # Priority use play_addr_h264
            play_addr = video_info.get('video', {}).get('play_addr_h264') or \
                       video_info.get('video', {}).get('play_addr')
            
            if play_addr:
                url_list = play_addr.get('url_list', [])
                if url_list:
                    # Replace URL to get no-watermark version
                    url = url_list[0]
                    url = url.replace('playwm', 'play')
                    url = url.replace('720p', '1080p')
                    return url
            
            # Fallback: download_addr
            download_addr = video_info.get('video', {}).get('download_addr')
            if download_addr:
                url_list = download_addr.get('url_list', [])
                if url_list:
                    return url_list[0]
                    
        except Exception as e:
            logger.error(f"Failed to get no-watermark URL: {e}")
        
        return None
    
    def _get_best_quality_url(self, url_list: List[str]) -> Optional[str]:
        """Get highest quality URL"""
        if not url_list:
            return None
        
        # Priority select URL containing specific keywords
        for keyword in ['1080', 'origin', 'high']:
            for url in url_list:
                if keyword in url:
                    return url
        
        # Return first one
        return url_list[0]
    
    def _get_music_url(self, video_info: Dict) -> Optional[str]:
        """Get music URL"""
        try:
            music = video_info.get('music', {})
            play_url = music.get('play_url', {})
            url_list = play_url.get('url_list', [])
            return url_list[0] if url_list else None
        except:
            return None
    
    def _get_cover_url(self, video_info: Dict) -> Optional[str]:
        """Get cover URL"""
        try:
            cover = video_info.get('video', {}).get('cover', {})
            url_list = cover.get('url_list', [])
            return self._get_best_quality_url(url_list)
        except:
            return None
    
    async def _download_file(self, url: str, save_path: Path) -> bool:
        """Download file"""
        try:
            if save_path.exists():
                logger.info(f"File already exists, skipping: {save_path.name}")
                return True
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(save_path, 'wb') as f:
                            f.write(content)
                        return True
                    else:
                        logger.error(f"Download failed, status code: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Failed to download file {url}: {e}")
            return False
    
    async def download_user_page(self, url: str) -> bool:
        """Download user homepage content"""
        try:
            # Extract user ID
            user_id = self.extract_id_from_url(url, ContentType.USER)
            if not user_id:
                logger.error(f"Unable to extract user ID from URL: {url}")
                return False
            
            console.print(f"\n[cyan]Fetching work list for user {user_id}...[/cyan]")
            
            # Download different types of content based on config
            mode = self.config.get('mode', ['post'])
            if isinstance(mode, str):
                mode = [mode]
            
            # Increase total task count statistics
            total_posts = 0
            if 'post' in mode:
                total_posts += self.config.get('number', {}).get('post', 0) or 1
            if 'like' in mode:
                total_posts += self.config.get('number', {}).get('like', 0) or 1
            if 'mix' in mode:
                total_posts += self.config.get('number', {}).get('allmix', 0) or 1
            
            self.stats.total += total_posts
            
            for m in mode:
                if m == 'post':
                    await self._download_user_posts(user_id)
                elif m == 'like':
                    await self._download_user_likes(user_id)
                elif m == 'mix':
                    await self._download_user_mixes(user_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to download user homepage: {e}")
            return False
    
    async def _download_user_posts(self, user_id: str):
        """Download user's posted works"""
        max_count = self.config.get('number', {}).get('post', 0)
        cursor = 0
        downloaded = 0
        
        console.print(f"\n[green]Starting download of user's posted works...[/green]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            
            while True:
                # Rate limit
                await self.rate_limiter.acquire()
                
                # Get work list
                posts_data = await self._fetch_user_posts(user_id, cursor)
                if not posts_data:
                    break
                
                aweme_list = posts_data.get('aweme_list', [])
                if not aweme_list:
                    break
                
                # Download works
                for aweme in aweme_list:
                    if max_count > 0 and downloaded >= max_count:
                        console.print(f"[yellow]Reached download count limit: {max_count}[/yellow]")
                        return
                    
                    # Time filter
                    if not self._check_time_filter(aweme):
                        continue
                    
                    # Create download task
                    task_id = progress.add_task(
                        f"Downloading work {downloaded + 1}", 
                        total=100
                    )
                    
                    # Incremental check
                    if self._should_skip_increment('post', aweme, sec_uid=user_id):
                        continue
                    
                    # Download
                    success = await self._download_media_files(aweme, progress)
                    
                    if success:
                        downloaded += 1
                        self.stats.success += 1  # Increase success count
                        progress.update(task_id, completed=100)
                        self._record_increment('post', aweme, sec_uid=user_id)
                    else:
                        self.stats.failed += 1  # Increase failed count
                        progress.update(task_id, description="[red]Download failed[/red]")
                
                # Check if there's more
                if not posts_data.get('has_more'):
                    break
                
                cursor = posts_data.get('max_cursor', 0)
        
        console.print(f"[green]✅ User works download complete, total downloaded: {downloaded}[/green]")
    
    async def _fetch_user_posts(self, user_id: str, cursor: int = 0) -> Optional[Dict]:
        """Fetch user's work list"""
        try:
            # Use getUserInfo method from Douyin class
            from apiproxy.douyin.douyin import Douyin
            
            # Create Douyin instance
            dy = Douyin(database=False)
            
            # Get user work list
            result = dy.getUserInfo(
                user_id, 
                "post", 
                35, 
                0,  # No limit
                False,  # No incremental
                "",  # start_time
                ""   # end_time
            )
            
            if result:
                logger.info(f"Douyin class successfully fetched user work list, total {len(result)} works")
                # Convert to expected format
                return {
                    'status_code': 0,
                    'aweme_list': result,
                    'max_cursor': cursor,
                    'has_more': False
                }
            else:
                logger.error("Douyin class returned empty result")
                return None
                
        except Exception as e:
            logger.error(f"Failed to fetch user work list: {e}")
            import traceback
            traceback.print_exc()
        
        return None
    
    async def _download_user_likes(self, user_id: str):
        """Download user's liked works"""
        max_count = 0
        try:
            max_count = int(self.config.get('number', {}).get('like', 0))
        except Exception:
            max_count = 0
        cursor = 0
        downloaded = 0

        console.print(f"\n[green]Starting download of user's liked works...[/green]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console
        ) as progress:

            while True:
                # Rate limit
                await self.rate_limiter.acquire()

                # Get liked list
                likes_data = await self._fetch_user_likes(user_id, cursor)
                if not likes_data:
                    break

                aweme_list = likes_data.get('aweme_list', [])
                if not aweme_list:
                    break

                # Download works
                for aweme in aweme_list:
                    if max_count > 0 and downloaded >= max_count:
                        console.print(f"[yellow]Reached download count limit: {max_count}[/yellow]")
                        return

                    if not self._check_time_filter(aweme):
                        continue

                    task_id = progress.add_task(
                        f"Downloading liked {downloaded + 1}",
                        total=100
                    )

                    # Incremental check
                    if self._should_skip_increment('like', aweme, sec_uid=user_id):
                        continue

                    success = await self._download_media_files(aweme, progress)

                    if success:
                        downloaded += 1
                        progress.update(task_id, completed=100)
                        self._record_increment('like', aweme, sec_uid=user_id)
                    else:
                        progress.update(task_id, description="[red]Download failed[/red]")

                # Pagination
                if not likes_data.get('has_more'):
                    break
                cursor = likes_data.get('max_cursor', 0)

        console.print(f"[green]✅ Liked works download complete, total downloaded: {downloaded}[/green]")

    async def _fetch_user_likes(self, user_id: str, cursor: int = 0) -> Optional[Dict]:
        """Fetch user's liked works list"""
        try:
            params_list = [
                f'sec_user_id={user_id}',
                f'max_cursor={cursor}',
                'count=35',
                'aid=6383',
                'device_platform=webapp',
                'channel=channel_pc_web',
                'pc_client_type=1',
                'version_code=170400',
                'version_name=17.4.0',
                'cookie_enabled=true',
                'screen_width=1920',
                'screen_height=1080',
                'browser_language=zh-CN',
                'browser_platform=MacIntel',
                'browser_name=Chrome',
                'browser_version=122.0.0.0',
                'browser_online=true'
            ]
            params = '&'.join(params_list)

            api_url = self.urls_helper.USER_FAVORITE_A

            try:
                xbogus = self.utils.getXbogus(params)
                full_url = f"{api_url}{params}&X-Bogus={xbogus}"
            except Exception as e:
                logger.warning(f"Failed to get X-Bogus: {e}, attempting without X-Bogus")
                full_url = f"{api_url}{params}"

            logger.info(f"Requesting user liked list: {full_url[:100]}...")

            async with aiohttp.ClientSession() as session:
                async with session.get(full_url, headers=self.headers, timeout=10) as response:
                    if response.status != 200:
                        logger.error(f"Request failed, status code: {response.status}")
                        return None

                    text = await response.text()
                    if not text:
                        logger.error("Response content is empty")
                        return None

                    data = json.loads(text)
                    if data.get('status_code') == 0:
                        return data
                    else:
                        logger.error(f"API returned error: {data.get('status_msg', 'Unknown error')}")
                        return None
        except Exception as e:
            logger.error(f"Failed to fetch user liked list: {e}")
        return None

    async def _download_user_mixes(self, user_id: str):
        """Download all user collections (limit count based on config)"""
        max_allmix = 0
        try:
            # Compatible with old key names allmix or mix
            number_cfg = self.config.get('number', {}) or {}
            max_allmix = int(number_cfg.get('allmix', number_cfg.get('mix', 0)) or 0)
        except Exception:
            max_allmix = 0

        cursor = 0
        fetched = 0

        console.print(f"\n[green]Starting to fetch user collection list...[/green]")
        while True:
            await self.rate_limiter.acquire()
            mix_list_data = await self._fetch_user_mix_list(user_id, cursor)
            if not mix_list_data:
                break

            mix_infos = mix_list_data.get('mix_infos') or []
            if not mix_infos:
                break

            for mix in mix_infos:
                if max_allmix > 0 and fetched >= max_allmix:
                    console.print(f"[yellow]Reached collection count limit: {max_allmix}[/yellow]")
                    return
                mix_id = mix.get('mix_id')
                mix_name = mix.get('mix_name', '')
                console.print(f"[cyan]Downloading collection[/cyan]: {mix_name} ({mix_id})")
                await self._download_mix_by_id(mix_id)
                fetched += 1

            if not mix_list_data.get('has_more'):
                break
            cursor = mix_list_data.get('cursor', 0)

        console.print(f"[green]✅ User collections download complete, total processed: {fetched}[/green]")

    async def _fetch_user_mix_list(self, user_id: str, cursor: int = 0) -> Optional[Dict]:
        """Fetch user collection list"""
        try:
            params_list = [
                f'sec_user_id={user_id}',
                f'cursor={cursor}',
                'count=35',
                'aid=6383',
                'device_platform=webapp',
                'channel=channel_pc_web',
                'pc_client_type=1',
                'version_code=170400',
                'version_name=17.4.0',
                'cookie_enabled=true',
                'screen_width=1920',
                'screen_height=1080',
                'browser_language=zh-CN',
                'browser_platform=MacIntel',
                'browser_name=Chrome',
                'browser_version=122.0.0.0',
                'browser_online=true'
            ]
            params = '&'.join(params_list)

            api_url = self.urls_helper.USER_MIX_LIST
            try:
                xbogus = self.utils.getXbogus(params)
                full_url = f"{api_url}{params}&X-Bogus={xbogus}"
            except Exception as e:
                logger.warning(f"Failed to get X-Bogus: {e}, attempting without X-Bogus")
                full_url = f"{api_url}{params}"

            logger.info(f"Requesting user collection list: {full_url[:100]}...")
            async with aiohttp.ClientSession() as session:
                async with session.get(full_url, headers=self.headers, timeout=10) as response:
                    if response.status != 200:
                        logger.error(f"Request failed, status code: {response.status}")
                        return None
                    text = await response.text()
                    if not text:
                        logger.error("Response content is empty")
                        return None
                    data = json.loads(text)
                    if data.get('status_code') == 0:
                        return data
                    else:
                        logger.error(f"API returned error: {data.get('status_msg', 'Unknown error')}")
                        return None
        except Exception as e:
            logger.error(f"Failed to fetch user collection list: {e}")
        return None

    async def download_mix(self, url: str) -> bool:
        """Download all works in a collection based on collection link"""
        try:
            mix_id = None
            for pattern in [r'/collection/(\d+)', r'/mix/detail/(\d+)']:
                m = re.search(pattern, url)
                if m:
                    mix_id = m.group(1)
                    break
            if not mix_id:
                logger.error(f"Unable to extract ID from collection link: {url}")
                return False
            await self._download_mix_by_id(mix_id)
            return True
        except Exception as e:
            logger.error(f"Failed to download collection: {e}")
            return False

    async def _download_mix_by_id(self, mix_id: str):
        """Download all works by collection ID"""
        cursor = 0
        downloaded = 0

        console.print(f"\n[green]Starting download of collection {mix_id} ...[/green]")

        while True:
            await self.rate_limiter.acquire()
            data = await self._fetch_mix_awemes(mix_id, cursor)
            if not data:
                break

            aweme_list = data.get('aweme_list') or []
            if not aweme_list:
                break

            for aweme in aweme_list:
                success = await self._download_media_files(aweme)
                if success:
                    downloaded += 1

            if not data.get('has_more'):
                break
            cursor = data.get('cursor', 0)

        console.print(f"[green]✅ Collection download complete, total downloaded: {downloaded}[/green]")

    async def _fetch_mix_awemes(self, mix_id: str, cursor: int = 0) -> Optional[Dict]:
        """Fetch work list under a collection"""
        try:
            params_list = [
                f'mix_id={mix_id}',
                f'cursor={cursor}',
                'count=35',
                'aid=6383',
                'device_platform=webapp',
                'channel=channel_pc_web',
                'pc_client_type=1',
                'version_code=170400',
                'version_name=17.4.0',
                'cookie_enabled=true',
                'screen_width=1920',
                'screen_height=1080',
                'browser_language=zh-CN',
                'browser_platform=MacIntel',
                'browser_name=Chrome',
                'browser_version=122.0.0.0',
                'browser_online=true'
            ]
            params = '&'.join(params_list)

            api_url = self.urls_helper.USER_MIX
            try:
                xbogus = self.utils.getXbogus(params)
                full_url = f"{api_url}{params}&X-Bogus={xbogus}"
            except Exception as e:
                logger.warning(f"Failed to get X-Bogus: {e}, attempting without X-Bogus")
                full_url = f"{api_url}{params}"

            logger.info(f"Requesting collection work list: {full_url[:100]}...")
            async with aiohttp.ClientSession() as session:
                async with session.get(full_url, headers=self.headers, timeout=10) as response:
                    if response.status != 200:
                        logger.error(f"Request failed, status code: {response.status}")
                        return None
                    text = await response.text()
                    if not text:
                        logger.error("Response content is empty")
                        return None
                    data = json.loads(text)
                    # USER_MIX returns without unified status_code, return directly here
                    return data
        except Exception as e:
            logger.error(f"Failed to fetch collection works: {e}")
        return None

    async def download_music(self, url: str) -> bool:
        """Download all works under a music page based on music link (supports incremental)"""
        try:
            # Extract music_id
            music_id = None
            m = re.search(r'/music/(\d+)', url)
            if m:
                music_id = m.group(1)
            if not music_id:
                logger.error(f"Unable to extract ID from music link: {url}")
                return False

            cursor = 0
            downloaded = 0
            limit_num = 0
            try:
                limit_num = int((self.config.get('number', {}) or {}).get('music', 0))
            except Exception:
                limit_num = 0

            console.print(f"\n[green]Starting download of works under music {music_id} ...[/green]")

            while True:
                await self.rate_limiter.acquire()
                data = await self._fetch_music_awemes(music_id, cursor)
                if not data:
                    break
                aweme_list = data.get('aweme_list') or []
                if not aweme_list:
                    break

                for aweme in aweme_list:
                    if limit_num > 0 and downloaded >= limit_num:
                        console.print(f"[yellow]Reached music download count limit: {limit_num}[/yellow]")
                        return True
                    if self._should_skip_increment('music', aweme, music_id=music_id):
                        continue
                    success = await self._download_media_files(aweme)
                    if success:
                        downloaded += 1
                        self._record_increment('music', aweme, music_id=music_id)

                if not data.get('has_more'):
                    break
                cursor = data.get('cursor', 0)

            console.print(f"[green]✅ Music works download complete, total downloaded: {downloaded}[/green]")
            return True
        except Exception as e:
            logger.error(f"Failed to download music page: {e}")
            return False

    async def _fetch_music_awemes(self, music_id: str, cursor: int = 0) -> Optional[Dict]:
        """Fetch work list under a music"""
        try:
            params_list = [
                f'music_id={music_id}',
                f'cursor={cursor}',
                'count=35',
                'aid=6383',
                'device_platform=webapp',
                'channel=channel_pc_web',
                'pc_client_type=1',
                'version_code=170400',
                'version_name=17.4.0',
                'cookie_enabled=true',
                'screen_width=1920',
                'screen_height=1080',
                'browser_language=zh-CN',
                'browser_platform=MacIntel',
                'browser_name=Chrome',
                'browser_version=122.0.0.0',
                'browser_online=true'
            ]
            params = '&'.join(params_list)

            api_url = self.urls_helper.MUSIC
            try:
                xbogus = self.utils.getXbogus(params)
                full_url = f"{api_url}{params}&X-Bogus={xbogus}"
            except Exception as e:
                logger.warning(f"Failed to get X-Bogus: {e}, attempting without X-Bogus")
                full_url = f"{api_url}{params}"

            logger.info(f"Requesting music work list: {full_url[:100]}...")
            async with aiohttp.ClientSession() as session:
                async with session.get(full_url, headers=self.headers, timeout=10) as response:
                    if response.status != 200:
                        logger.error(f"Request failed, status code: {response.status}")
                        return None
                    text = await response.text()
                    if not text:
                        logger.error("Response content is empty")
                        return None
                    data = json.loads(text)
                    return data
        except Exception as e:
            logger.error(f"Failed to fetch music works: {e}")
        return None
    
    def _check_time_filter(self, aweme: Dict) -> bool:
        """Check time filter"""
        start_time = self.config.get('start_time')
        end_time = self.config.get('end_time')
        
        if not start_time and not end_time:
            return True
        
        raw_create_time = aweme.get('create_time')
        if not raw_create_time:
            return True
        
        create_date = None
        if isinstance(raw_create_time, (int, float)):
            try:
                create_date = datetime.fromtimestamp(raw_create_time)
            except Exception:
                create_date = None
        elif isinstance(raw_create_time, str):
            for fmt in ('%Y-%m-%d %H.%M.%S', '%Y-%m-%d_%H-%M-%S', '%Y-%m-%d %H:%M:%S'):
                try:
                    create_date = datetime.strptime(raw_create_time, fmt)
                    break
                except Exception:
                    pass
        
        if create_date is None:
            return True
        
        if start_time:
            start_date = datetime.strptime(start_time, '%Y-%m-%d')
            if create_date < start_date:
                return False
        
        if end_time:
            end_date = datetime.strptime(end_time, '%Y-%m-%d')
            if create_date > end_date:
                return False
        
        return True
    
    async def run(self):
        """Run downloader"""
        # Display startup info
        console.print(Panel.fit(
            "[bold cyan]Douyin Downloader v3.0 - Unified Enhanced Version[/bold cyan]\n"
            "[dim]Supports batch downloading of videos, images, user homepages, and collections[/dim]",
            border_style="cyan"
        ))
        
        # Initialize Cookie and headers
        await self._initialize_cookies_and_headers()
        
        # Get URL list
        urls = self.config.get('link', [])
        # Compatible: single string
        if isinstance(urls, str):
            urls = [urls]
        if not urls:
            console.print("[red]No links found to download![/red]")
            return
        
        # Analyze URL types
        console.print(f"\n[cyan]📊 Link Analysis[/cyan]")
        url_types = {}
        for url in urls:
            content_type = self.detect_content_type(url)
            url_types[url] = content_type
            console.print(f"  • {content_type.upper()}: {url[:50]}...")
        
        # Start download
        console.print(f"\n[green]⏳ Starting download of {len(urls)} links...[/green]\n")
        
        for i, url in enumerate(urls, 1):
            content_type = url_types[url]
            console.print(f"[{i}/{len(urls)}] Processing: {url}")
            
            if content_type == ContentType.VIDEO or content_type == ContentType.IMAGE:
                await self.download_single_video(url)
            elif content_type == ContentType.USER:
                await self.download_user_page(url)
                # If config includes like or mix, process them as well
                modes = self.config.get('mode', ['post'])
                if 'like' in modes:
                    user_id = self.extract_id_from_url(url, ContentType.USER)
                    if user_id:
                        await self._download_user_likes(user_id)
                if 'mix' in modes:
                    user_id = self.extract_id_from_url(url, ContentType.USER)
                    if user_id:
                        await self._download_user_mixes(user_id)
            elif content_type == ContentType.MIX:
                await self.download_mix(url)
            elif content_type == ContentType.MUSIC:
                await self.download_music(url)
            else:
                console.print(f"[yellow]Unsupported content type: {content_type}[/yellow]")
            
            # Display progress
            console.print(f"Progress: {i}/{len(urls)} | Success: {self.stats.success} | Failed: {self.stats.failed}")
            console.print("-" * 60)
        
        # Show statistics
        self._show_stats()
    
    def _show_stats(self):
        """Show download statistics"""
        console.print("\n" + "=" * 60)
        
        # Create statistics table
        table = Table(title="📊 Download Statistics", show_header=True, header_style="bold magenta")
        table.add_column("Item", style="cyan", width=12)
        table.add_column("Value", style="green")
        
        stats = self.stats.to_dict()
        table.add_row("Total Tasks", str(stats['total']))
        table.add_row("Success", str(stats['success']))
        table.add_row("Failed", str(stats['failed']))
        table.add_row("Skipped", str(stats['skipped']))
        table.add_row("Success Rate", stats['success_rate'])
        table.add_row("Time Elapsed", stats['elapsed_time'])
        
        console.print(table)
        console.print("\n[bold green]✅ Download tasks complete![/bold green]")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Douyin Downloader - Unified Enhanced Version',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '-c', '--config',
        default='config.yml',
        help='Config file path (default: config.yml, auto-compatible with config_simple.yml)'
    )
    
    parser.add_argument(
        '-u', '--url',
        nargs='+',
        help='Directly specify URLs to download'
    )
    parser.add_argument(
        '-p', '--path',
        default=None,
        help='Save path (overrides config file)'
    )
    parser.add_argument(
        '--auto-cookie',
        action='store_true',
        help='Auto-fetch Cookie (requires Playwright installed)'
    )
    parser.add_argument(
        '--cookie',
        help='Manually specify Cookie string, e.g., "msToken=xxx; ttwid=yyy"'
    )
    
    args = parser.parse_args()
    
    # Combine config sources: priority CLI
    temp_config = {}
    if args.url:
        temp_config['link'] = args.url
    
    # Override save path
    if args.path:
        temp_config['path'] = args.path
    
    # Cookie config
    if args.auto_cookie:
        temp_config['auto_cookie'] = True
        temp_config['cookies'] = 'auto'
    if args.cookie:
        temp_config['cookies'] = args.cookie
        temp_config['auto_cookie'] = False
    
    # If temporary config exists, generate a temporary file for existing constructor
    if temp_config:
        # Merge file config (if exists)
        file_config = {}
        if os.path.exists(args.config):
            try:
                with open(args.config, 'r', encoding='utf-8') as f:
                    file_config = yaml.safe_load(f) or {}
            except Exception:
                file_config = {}
        
        # Compatible simplified key names
        if 'links' in file_config and 'link' not in file_config:
            file_config['link'] = file_config['links']
        if 'output_dir' in file_config and 'path' not in file_config:
            file_config['path'] = file_config['output_dir']
        if 'cookie' in file_config and 'cookies' not in file_config:
            file_config['cookies'] = file_config['cookie']
        
        merged = {**(file_config or {}), **temp_config}
        with open('temp_config.yml', 'w', encoding='utf-8') as f:
            yaml.dump(merged, f, allow_unicode=True)
        config_path = 'temp_config.yml'
    else:
        config_path = args.config
    
    # Run downloader
    try:
        downloader = UnifiedDownloader(config_path)
        asyncio.run(downloader.run())
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ User interrupted download[/yellow]")
    except Exception as e:
        console.print(f"\n[red]❌ Program exception: {e}[/red]")
        logger.exception("Program exception")
    finally:
        # Clean up temporary config
        if args.url and os.path.exists('temp_config.yml'):
            os.remove('temp_config.yml')


if __name__ == '__main__':
    main()