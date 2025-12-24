#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Auto Cookie Manager
Automatically fetch, refresh, and manage Douyin Cookies
"""

import asyncio
import json
import time
import logging
import pickle
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed, auto Cookie management unavailable")


@dataclass
class CookieInfo:
    """Cookie info"""
    cookies: List[Dict[str, Any]]
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    login_method: str = "manual"  # manual, qrcode, phone
    is_valid: bool = True
    
    def is_expired(self, max_age_hours: int = 24) -> bool:
        """Check if Cookie is expired"""
        age = time.time() - self.created_at
        return age > max_age_hours * 3600
    
    def to_dict(self) -> Dict:
        """Convert to dictionary format"""
        return {
            'cookies': self.cookies,
            'created_at': self.created_at,
            'last_used': self.last_used,
            'login_method': self.login_method,
            'is_valid': self.is_valid
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CookieInfo':
        """Create from dictionary"""
        return cls(**data)


class AutoCookieManager:
    """Auto Cookie Manager"""
    
    def __init__(
        self,
        cookie_file: str = "cookies.pkl",
        auto_refresh: bool = True,
        refresh_interval: int = 3600,
        headless: bool = False
    ):
        """
        Initialize Cookie manager
        
        Args:
            cookie_file: Cookie save file
            auto_refresh: Whether to auto-refresh
            refresh_interval: Refresh interval (seconds)
            headless: Whether browser is in headless mode
        """
        self.cookie_file = Path(cookie_file)
        self.auto_refresh = auto_refresh
        self.refresh_interval = refresh_interval
        self.headless = headless
        
        self.current_cookies: Optional[CookieInfo] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.playwright = None
        
        self._refresh_task = None
        self._lock = asyncio.Lock()
        
        # Load saved Cookies
        self._load_cookies()
    
    def _load_cookies(self):
        """Load Cookies from file"""
        if self.cookie_file.exists():
            try:
                with open(self.cookie_file, 'rb') as f:
                    data = pickle.load(f)
                    self.current_cookies = CookieInfo.from_dict(data)
                    logger.info(f"Loaded saved Cookies (Created at: {datetime.fromtimestamp(self.current_cookies.created_at)})")
            except Exception as e:
                logger.error(f"Failed to load Cookies: {e}")
                self.current_cookies = None
    
    def _save_cookies(self):
        """Save Cookies to file"""
        if self.current_cookies:
            try:
                with open(self.cookie_file, 'wb') as f:
                    pickle.dump(self.current_cookies.to_dict(), f)
                logger.info("Cookies saved")
            except Exception as e:
                logger.error(f"Failed to save Cookies: {e}")
    
    async def get_cookies(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get valid Cookies
        
        Returns:
            List of Cookies
        """
        async with self._lock:
            # Check if refresh is needed
            if self._need_refresh():
                await self._refresh_cookies()
            
            if self.current_cookies and self.current_cookies.is_valid:
                self.current_cookies.last_used = time.time()
                return self.current_cookies.cookies
            
            return None
    
    def _need_refresh(self) -> bool:
        """Determine if Cookies need refresh"""
        if not self.current_cookies:
            return True
        
        # Check if expired
        if self.current_cookies.is_expired(max_age_hours=24):
            logger.info("Cookies expired, need refresh")
            return True
        
        # Check if idle for too long
        idle_time = time.time() - self.current_cookies.last_used
        if idle_time > self.refresh_interval:
            logger.info(f"Cookies idle for {idle_time/3600:.1f} hours, need refresh")
            return True
        
        return False
    
    async def _refresh_cookies(self):
        """Login and get new Cookies"""
        logger.info("Need to re-login to get Cookies")
        
        try:
            browser = await self._get_browser()
            page = await browser.new_page()
            
            # Visit Douyin, relax wait conditions
            try:
                await page.goto("https://www.douyin.com", wait_until='domcontentloaded', timeout=120000)
                # Extra wait for page stability, allow time for captcha page to load
                await asyncio.sleep(10)
            except Exception as e:
                logger.warning(f"Page load timeout, continuing: {e}")
                # Continue even if timeout
            
            # Check login status
            is_logged_in = await self._check_login_status(page)
            
            if not is_logged_in:
                # Perform login flow
                login_method = await self._perform_login(page)
                
                if not login_method:
                    logger.error("Login failed")
                    await page.close()
                    return
            else:
                login_method = "already_logged_in"
            
            # Get Cookies
            cookies = await page.context.cookies()
            
            # Filter necessary Cookies
            filtered_cookies = self._filter_cookies(cookies)
            
            self.current_cookies = CookieInfo(
                cookies=filtered_cookies,
                login_method=login_method
            )
            
            self._save_cookies()
            logger.info(f"Successfully fetched Cookies (Login method: {login_method})")
            
            await page.close()
            
        except Exception as e:
            logger.error(f"Failed to login and fetch Cookies: {e}")

    async def _try_refresh_existing(self) -> bool:
        """Try to refresh existing Cookies"""
        try:
            browser = await self._get_browser()
            page = await browser.new_page()
            
            # Set existing Cookies
            await page.context.add_cookies(self.current_cookies.cookies)
            
            # Visit Douyin homepage
            await page.goto("https://www.douyin.com", wait_until='networkidle')
            
            # Check if still logged in
            is_logged_in = await self._check_login_status(page)
            
            if is_logged_in:
                # Get updated Cookies
                cookies = await page.context.cookies()
                self.current_cookies = CookieInfo(
                    cookies=cookies,
                    login_method="refresh"
                )
                self._save_cookies()
                logger.info("Cookies refreshed successfully")
                await page.close()
                return True
            
            await page.close()
            return False
            
        except Exception as e:
            logger.error(f"Failed to refresh Cookies: {e}")
            return False
    
    async def _login_and_get_cookies(self):
        """Login and get new Cookies"""
        logger.info("Need to re-login to get Cookies")
        
        try:
            browser = await self._get_browser()
            page = await browser.new_page()
            
            # Visit Douyin
            await page.goto("https://www.douyin.com", wait_until='networkidle')
            
            # Check login status
            is_logged_in = await self._check_login_status(page)
            
            if not is_logged_in:
                # Perform login flow
                login_method = await self._perform_login(page)
                
                if not login_method:
                    logger.error("Login failed")
                    await page.close()
                    return
            else:
                login_method = "already_logged_in"
            
            # Get Cookies
            cookies = await page.context.cookies()
            
            # Filter necessary Cookies
            filtered_cookies = self._filter_cookies(cookies)
            
            self.current_cookies = CookieInfo(
                cookies=filtered_cookies,
                login_method=login_method
            )
            
            self._save_cookies()
            logger.info(f"Successfully fetched Cookies (Login method: {login_method})")
            
            await page.close()
            
        except Exception as e:
            logger.error(f"Failed to login and fetch Cookies: {e}")
    
    async def _check_login_status(self, page: 'Page') -> bool:
        """Check login status"""
        try:
            # Look for user avatar or other login indicators
            selectors = [
                '[data-e2e="user-avatar"]',
                '.user-avatar',
                '[class*="avatar"]',
                '.login-success',
                '[class*="user"]',
                '[class*="profile"]',
                'img[alt*="头像"]',
                'img[alt*="avatar"]',
                '[data-e2e="profile"]',
                '.profile-info'
            ]
            
            for selector in selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=5000)
                    if element:
                        logger.info("Detected logged in")
                        return True
                except:
                    continue
            
            # Extra check: look for login button, if not found might be logged in
            try:
                login_indicators = [
                    '[data-e2e="login-button"]',
                    '.login-button',
                    'button:has-text("登录")',
                    'a:has-text("登录")'
                ]
                
                for indicator in login_indicators:
                    try:
                        element = await page.wait_for_selector(indicator, timeout=2000)
                        if element:
                            logger.info("Detected login button, not logged in")
                            return False
                    except:
                        continue
                
                # If login button not found, might be logged in
                logger.info("Login button not found, might be logged in")
                return True
                
            except Exception:
                pass
            
            return False
            
        except Exception as e:
            logger.warning(f"Failed to check login status: {e}")
            return False
    
    async def _perform_login(self, page: 'Page') -> Optional[str]:
        """Perform login flow"""
        logger.info("Starting login flow...")
        
        # Try QR code login first
        login_method = await self._qrcode_login(page)
        
        if not login_method:
            # If QR code login fails, try manual
            login_method = await self._manual_login(page)
        
        return login_method
    
    async def _qrcode_login(self, page: Page) -> Optional[str]:
        """QR code login"""
        try:
            logger.info("Attempting QR code login...")
            
            # Find and click login button
            login_button_selectors = [
                '[data-e2e="login-button"]',
                '.login-button',
                'button:has-text("登录")',
                'a:has-text("登录")',
                '[class*="login"]',
                'button:has-text("登入")',
                'a:has-text("登入")'
            ]
            
            for selector in login_button_selectors:
                try:
                    button = await page.wait_for_selector(selector, timeout=15000)
                    if button:
                        await button.click()
                        break
                except:
                    continue
            
            # Wait for login popup
            await asyncio.sleep(8)
            
            # Select QR code login
            qr_selectors = [
                '[data-e2e="qrcode-tab"]',
                '.qrcode-login',
                'text=扫码登录',
                'text=二维码登录',
                '[class*="qrcode"]',
                'text=二维码',
                'text=扫码'
            ]
            
            for selector in qr_selectors:
                try:
                    qr_tab = await page.wait_for_selector(selector, timeout=15000)
                    if qr_tab:
                        await qr_tab.click()
                        break
                except:
                    continue
            
            # Wait for QR code to appear
            qr_img_selectors = [
                '.qrcode-img', 
                '[class*="qrcode"] img', 
                'canvas',
                '[class*="qr"] img',
                'img[alt*="二维码"]',
                'img[alt*="QR"]'
            ]
            
            qr_found = False
            for selector in qr_img_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=20000)
                    qr_found = True
                    break
                except:
                    continue
            
            if not qr_found:
                logger.warning("QR code not found, continuing to wait...")
                # Continue waiting even if not found, page might still be loading
            
            if not self.headless:
                print("\n" + "="*60)
                print("Please use Douyin APP to scan QR code to login")
                print("If a captcha appears, please complete the verification")
                print("Waiting for login...")
                print("="*60 + "\n")
            
            # Wait for user to scan (max 300s, allow time for captcha)
            start_time = time.time()
            while time.time() - start_time < 300:
                is_logged_in = await self._check_login_status(page)
                if is_logged_in:
                    logger.info("QR code login successful")
                    return "qrcode"
                await asyncio.sleep(8)
            
            logger.warning("QR code login timeout")
            return None
            
        except Exception as e:
            logger.error(f"QR code login failed: {e}")
            return None
    
    async def _manual_login(self, page: Page) -> Optional[str]:
        """Manual login (wait for user action)"""
        if self.headless:
            logger.error("Manual login unavailable in headless mode")
            return None
        
        print("\n" + "="*60)
        print("Please complete login manually in the browser")
        print("If a captcha appears, please complete the verification")
        print("Will automatically continue after successful login...")
        print("="*60 + "\n")
        
        # Wait for manual login (max 600s, allow ample time for captcha)
        start_time = time.time()
        while time.time() - start_time < 600:
            is_logged_in = await self._check_login_status(page)
            if is_logged_in:
                logger.info("Manual login successful")
                return "manual"
            await asyncio.sleep(8)
        
        logger.warning("Manual login timeout")
        return None
    
    def _filter_cookies(self, cookies: List[Dict]) -> List[Dict]:
        """Filter necessary Cookies"""
        # Necessary Cookie names
        required_names = [
            'msToken',
            'ttwid', 
            'odin_tt',
            'passport_csrf_token',
            'sid_guard',
            'uid_tt',
            'sessionid',
            'sid_tt'
        ]
        
        filtered = []
        for cookie in cookies:
            # Keep necessary Cookies or all Cookies under Douyin domain
            if cookie['name'] in required_names or '.douyin.com' in cookie.get('domain', ''):
                filtered.append(cookie)
        
        logger.info(f"Kept {len(filtered)} Cookies after filtering")
        return filtered
    
    async def _get_browser(self) -> Browser:
        """Get browser instance"""
        if not self.browser:
            if not PLAYWRIGHT_AVAILABLE:
                raise ImportError("Playwright not installed")
            
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )
            
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='zh-CN'
            )
        
        return self.context
    
    async def start_auto_refresh(self):
        """Start auto-refresh task"""
        if self.auto_refresh and not self._refresh_task:
            self._refresh_task = asyncio.create_task(self._auto_refresh_loop())
            logger.info("Auto Cookie refresh started")
    
    async def stop_auto_refresh(self):
        """Stop auto-refresh task"""
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            self._refresh_task = None
            logger.info("Auto Cookie refresh stopped")
    
    async def _auto_refresh_loop(self):
        """Auto-refresh loop"""
        while True:
            try:
                await asyncio.sleep(self.refresh_interval)
                
                if self._need_refresh():
                    logger.info("Triggering auto Cookie refresh")
                    await self._refresh_cookies()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-refresh exception: {e}")
                await asyncio.sleep(60)  # Wait 1 minute after error before retrying
    
    async def cleanup(self):
        """Cleanup resources"""
        await self.stop_auto_refresh()
        
        if self.context:
            await self.context.close()
            self.context = None
        
        if self.browser:
            await self.browser.close()
            self.browser = None
        
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        
        logger.info("Cookie manager resources cleaned up")
    
    def get_cookie_dict(self) -> Optional[Dict[str, str]]:
        """Get Cookie dictionary format"""
        if not self.current_cookies:
            return None
        
        cookie_dict = {}
        for cookie in self.current_cookies.cookies:
            cookie_dict[cookie['name']] = cookie['value']
        
        return cookie_dict
    
    def get_cookie_string(self) -> Optional[str]:
        """Get Cookie string format"""
        cookie_dict = self.get_cookie_dict()
        if not cookie_dict:
            return None
        
        return '; '.join([f'{k}={v}' for k, v in cookie_dict.items()])
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.start_auto_refresh()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.cleanup()