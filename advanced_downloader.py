#!/usr/bin/env python3
"""
Advanced Douyin Downloader with X-Bogus signature support
This implementation includes manual API calls with anti-scraping bypass
"""

import re
import json
import time
import hashlib
import random
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlencode, urlparse, parse_qs

import httpx
from fake_useragent import UserAgent
from tqdm import tqdm

try:
    import browser_cookie3
    COOKIES_AVAILABLE = True
except ImportError:
    COOKIES_AVAILABLE = False
    print("⚠️  browser-cookie3 not available. Cookie extraction disabled.")


class XBogusGenerator:
    """
    X-Bogus signature generator for Douyin API
    This is a simplified version - the actual algorithm is more complex
    """
    
    @staticmethod
    def generate(url: str, user_agent: str) -> str:
        """
        Generate X-Bogus signature
        
        Note: This is a placeholder. The real X-Bogus algorithm is constantly
        updated by Douyin and requires reverse engineering their JavaScript.
        
        For production use, consider:
        1. Using yt-dlp which maintains the algorithm
        2. Using browser automation to bypass the signature
        3. Referencing open-source implementations like:
           https://github.com/B1gM8c/X-Bogus
        """
        # Simplified signature generation (NOT production-ready)
        timestamp = str(int(time.time() * 1000))
        random_str = ''.join(random.choices('0123456789abcdef', k=16))
        
        # Combine components
        sign_str = f"{url}|{user_agent}|{timestamp}|{random_str}"
        
        # Generate hash
        hash_obj = hashlib.md5(sign_str.encode())
        signature = hash_obj.hexdigest()
        
        return signature
    

class AdvancedDouyinDownloader:
    """Advanced downloader with manual API calls and signature generation"""
    
    API_BASE = "https://www.douyin.com/aweme/v1/web/aweme/detail/"
    
    def __init__(self):
        self.ua = UserAgent()
        self.user_agent = self.ua.chrome
        # Try HTTP/2, fallback to HTTP/1.1 if h2 not installed
        try:
            self.session = httpx.Client(
                http2=True,
                follow_redirects=True,
                timeout=30.0
            )
        except ImportError:
            print("⚠️  HTTP/2 not available, using HTTP/1.1")
            self.session = httpx.Client(
                follow_redirects=True,
                timeout=30.0
            )
        self.cookies = self._get_browser_cookies()
        self.headers = self._get_headers()
        
    def _get_browser_cookies(self) -> Dict[str, str]:
        """Extract cookies from browser using browser-cookie3"""
        if not COOKIES_AVAILABLE:
            return {}
        
        try:
            print("🍪 Extracting cookies from browser...")
            
            # Try Chrome first
            try:
                cookies = browser_cookie3.chrome(domain_name='douyin.com')
                cookie_dict = {cookie.name: cookie.value for cookie in cookies}
                if cookie_dict:
                    print(f"✅ Found {len(cookie_dict)} cookies from Chrome")
                    return cookie_dict
            except:
                pass
            
            # Try Firefox
            try:
                cookies = browser_cookie3.firefox(domain_name='douyin.com')
                cookie_dict = {cookie.name: cookie.value for cookie in cookies}
                if cookie_dict:
                    print(f"✅ Found {len(cookie_dict)} cookies from Firefox")
                    return cookie_dict
            except:
                pass
            
            print("⚠️  No cookies found in browser")
            return {}
            
        except Exception as e:
            print(f"⚠️  Error extracting cookies: {e}")
            return {}
    
    def _get_headers(self) -> Dict[str, str]:
        """Generate request headers with device fingerprint"""
        return {
            'User-Agent': self.user_agent,
            'Referer': 'https://www.douyin.com/',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Origin': 'https://www.douyin.com',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        }
    
    def get_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from Douyin URL"""
        try:
            print(f"🔗 Resolving URL: {url}")
            
            response = self.session.get(url, headers=self.headers)
            final_url = str(response.url)
            
            # Extract aweme_id
            match = re.search(r'/(?:video|note)/(\d+)', final_url)
            if match:
                video_id = match.group(1)
                print(f"✅ Video ID: {video_id}")
                return video_id
            
            # Try modal_id parameter
            parsed = urlparse(final_url)
            params = parse_qs(parsed.query)
            if 'modal_id' in params:
                video_id = params['modal_id'][0]
                print(f"✅ Video ID: {video_id}")
                return video_id
            
            return None
            
        except Exception as e:
            print(f"❌ Error resolving URL: {e}")
            return None
    
    def get_video_info(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch video info from Douyin API with X-Bogus signature
        
        Args:
            video_id: Douyin video ID (aweme_id)
            
        Returns:
            Video information or None
        """
        try:
            # Build request parameters
            params = {
                'aweme_id': video_id,
                'device_platform': 'webapp',
                'aid': '6383',
                'channel': 'channel_pc_web',
                'pc_client_type': '1',
                'version_code': '170400',
                'version_name': '17.4.0',
                'cookie_enabled': 'true',
                'screen_width': '1920',
                'screen_height': '1080',
                'browser_language': 'zh-CN',
                'browser_platform': 'Win32',
                'browser_name': 'Chrome',
                'browser_version': '120.0.0.0',
                'browser_online': 'true',
                'engine_name': 'Blink',
                'engine_version': '120.0.0.0',
                'os_name': 'Windows',
                'os_version': '10',
                'cpu_core_num': '8',
                'device_memory': '8',
                'platform': 'PC',
            }
            
            # Generate X-Bogus signature
            query_string = urlencode(params)
            full_url = f"{self.API_BASE}?{query_string}"
            x_bogus = XBogusGenerator.generate(full_url, self.user_agent)
            
            params['X-Bogus'] = x_bogus
            
            print(f"📡 Fetching video info from API...")
            print(f"   X-Bogus: {x_bogus[:20]}...")
            
            # Make API request
            response = self.session.get(
                self.API_BASE,
                params=params,
                headers=self.headers,
                cookies=self.cookies
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Parse response
            if data.get('status_code') == 0 and 'aweme_detail' in data:
                aweme = data['aweme_detail']
                
                # Extract video info
                video_info = {
                    'title': aweme.get('desc', 'Untitled'),
                    'video_id': video_id,
                    'author': aweme.get('author', {}).get('nickname', 'Unknown'),
                    'duration': aweme.get('duration', 0),
                    'create_time': aweme.get('create_time', 0),
                }
                
                # Extract download URL (without watermark)
                video_data = aweme.get('video', {})
                
                # Priority: download_addr > play_addr
                if 'download_addr' in video_data:
                    video_info['download_url'] = video_data['download_addr'].get('url_list', [None])[0]
                elif 'play_addr' in video_data:
                    video_info['download_url'] = video_data['play_addr'].get('url_list', [None])[0]
                else:
                    video_info['download_url'] = None
                
                print(f"✅ Got video info: {video_info['title']}")
                return video_info
            else:
                print(f"❌ API returned error: {data.get('status_msg', 'Unknown error')}")
                return None
                
        except Exception as e:
            print(f"❌ Error fetching video info: {e}")
            return None
    
    def download_video(self, video_url: str, output_path: str) -> bool:
        """Download video with progress bar and retry logic"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"🔄 Retry attempt {attempt + 1}/{max_retries}")
                
                print(f"⬇️  Starting download...")
                
                # Stream download
                with self.session.stream('GET', video_url, headers=self.headers) as response:
                    response.raise_for_status()
                    
                    total_size = int(response.headers.get('content-length', 0))
                    
                    progress_bar = tqdm(
                        total=total_size,
                        unit='iB',
                        unit_scale=True,
                        desc='Progress'
                    )
                    
                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            size = f.write(chunk)
                            progress_bar.update(size)
                    
                    progress_bar.close()
                
                print(f"✅ Downloaded: {output_path}")
                return True
                
            except Exception as e:
                print(f"❌ Download error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return False
        
        return False
    
    def sanitize_filename(self, filename: str) -> str:
        """Remove invalid characters from filename"""
        invalid_chars = r'[<>:"/\\|?*]'
        filename = re.sub(invalid_chars, '_', filename)
        if len(filename) > 200:
            filename = filename[:200]
        return filename
    
    def process_manual(self, text: str, output_dir: str = './downloads') -> bool:
        """
        Process video download using manual API calls
        
        This method demonstrates the technical implementation but may fail
        due to X-Bogus signature validation. For production use, prefer yt-dlp.
        """
        print("="*60)
        print("🎥 Advanced Douyin Downloader (Manual Mode)")
        print("="*60)
        
        # Extract URL
        pattern = r'https?://v\.douyin\.com/[A-Za-z0-9]+/?'
        match = re.search(pattern, text)
        
        if not match:
            print("❌ No Douyin URL found")
            return False
        
        url = match.group(0)
        print(f"✅ Found URL: {url}")
        
        # Get video ID
        video_id = self.get_video_id(url)
        if not video_id:
            print("❌ Failed to extract video ID")
            return False
        
        # Get video info
        video_info = self.get_video_info(video_id)
        if not video_info or not video_info.get('download_url'):
            print("❌ Failed to get video download URL")
            print("💡 The X-Bogus signature may be invalid.")
            print("💡 Recommendation: Use yt-dlp instead (see douyin_downloader.py)")
            return False
        
        # Prepare output
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        safe_title = self.sanitize_filename(video_info['title'])
        output_path = Path(output_dir) / f"{safe_title}_{video_id}.mp4"
        
        # Download
        success = self.download_video(video_info['download_url'], str(output_path))
        
        return success
    
    def close(self):
        """Close HTTP session"""
        self.session.close()


def main():
    """Main entry point for advanced downloader"""
    import sys
    
    example_text = """
    https://v.douyin.com/xSQfKpWGib4/
    """
    
    if len(sys.argv) > 1:
        input_text = ' '.join(sys.argv[1:])
    else:
        print("⚠️  Using example URL...")
        input_text = example_text
    
    downloader = AdvancedDouyinDownloader()
    
    try:
        print("\n⚠️  NOTE: Manual API mode may fail due to X-Bogus validation.")
        print("⚠️  For reliable downloads, use douyin_downloader.py with yt-dlp\n")
        
        downloader.process_manual(input_text)
    finally:
        downloader.close()


if __name__ == '__main__':
    main()

