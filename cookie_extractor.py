#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Douyin Cookie Auto Extractor
Automatically logs in with Playwright and extracts cookies
"""

import asyncio
import json
import os
import sys
import yaml
from pathlib import Path
from typing import Dict, Optional
import time

try:
    from playwright.async_api import async_playwright, Browser, Page
    from rich.console import Console
    from rich.prompt import Prompt, Confirm
    from rich.panel import Panel
    from rich import print as rprint
except ImportError:
    print("Please install required dependencies: pip install playwright rich pyyaml")
    print("Then run: playwright install chromium")
    sys.exit(1)

console = Console()


class CookieExtractor:
    """Cookie Extractor"""
    
    def __init__(self, config_path: str = "config_simple.yml"):
        self.config_path = config_path
        self.cookies = {}
        
    async def extract_cookies(self, headless: bool = False) -> Dict:
        """Extract cookies
        
        Args:
            headless: whether to run in headless mode
        """
        console.print(Panel.fit(
            "[bold cyan]Douyin Cookie Auto Extractor[/bold cyan]\n"
            "[dim]A browser will open automatically — please complete login there[/dim]",
            border_style="cyan"
        ))
        
        async with async_playwright() as p:
            # 启动浏览器
            browser = await p.chromium.launch(
                headless=headless,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            # 创建上下文（模拟真实浏览器）
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # 添加初始化脚本（隐藏自动化特征）
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            # 创建页面
            page = await context.new_page()
            page.set_default_timeout(600000)  # Set timeout to 600 seconds (10 minutes)
            
            try:
                # Open Douyin login page
                console.print("\n[cyan]Opening Douyin login page...[/cyan]")
                await page.goto('https://www.douyin.com', wait_until='load', timeout=120000)
                
                # Wait for user to log in
                console.print("\n[yellow]Please complete the login in the browser[/yellow]")
                console.print("[dim]Login methods:[/dim]")
                console.print("  1. Scan QR code (recommended)")
                console.print("  2. Phone number login")
                console.print("  3. Third-party account login")
                
                # 等待登录成功的标志
                logged_in = await self._wait_for_login(page)
                
                if logged_in:
                    console.print("\n[green]✅ Login successful! Extracting cookies...[/green]")
                    
                    # 提取Cookie
                    cookies = await context.cookies()
                    
                    # 转换为字典格式
                    cookie_dict = {}
                    cookie_string = ""
                    
                    for cookie in cookies:
                        cookie_dict[cookie['name']] = cookie['value']
                        cookie_string += f"{cookie['name']}={cookie['value']}; "
                    
                    self.cookies = cookie_dict
                    
                    # Show important cookies
                    console.print("\n[cyan]Key cookies extracted:[/cyan]")
                    important_cookies = ['sessionid', 'sessionid_ss', 'ttwid', 'passport_csrf_token', 'msToken']
                    for name in important_cookies:
                        if name in cookie_dict:
                            value = cookie_dict[name]
                            console.print(f"  • {name}: {value[:20]}..." if len(value) > 20 else f"  • {name}: {value}")
                    
                    # Save cookies
                    if Confirm.ask("\nSave cookies to the configuration file?"):
                        self._save_cookies(cookie_dict)
                        console.print("[green]✅ Cookies saved to configuration file[/green]")
                    
                    # Save full cookie string to file
                    with open('cookies.txt', 'w', encoding='utf-8') as f:
                        f.write(cookie_string.strip())
                    console.print("[green]✅ Full cookie string saved to cookies.txt[/green]")
                    
                    return cookie_dict
                else:
                    console.print("\n[red]❌ Login timed out or failed[/red]")
                    return {}
                    
            except Exception as e:
                console.print(f"\n[red]❌ Failed to extract cookies: {e}[/red]")
                return {}
            finally:
                await browser.close()
    
    async def _wait_for_login(self, page: Page, timeout: int = 300) -> bool:
        """Wait for user to log in
        
        Args:
            page: Page object
            timeout: timeout in seconds
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check if logged in (multiple heuristics)
            try:
                # Method 1: check for user avatar
                avatar = await page.query_selector('div[class*="avatar"]')
                if avatar:
                    await asyncio.sleep(2)  # 等待Cookie完全加载
                    return True
                
                # Method 2: URL contains user ID
                current_url = page.url
                if '/user/' in current_url:
                    await asyncio.sleep(2)
                    return True
                
                # Method 3: specific post‑login elements exist
                user_menu = await page.query_selector('[class*="user-info"]')
                if user_menu:
                    await asyncio.sleep(2)
                    return True
                
            except:
                pass
            
            await asyncio.sleep(2)
            
            # Show progress while waiting
            elapsed = int(time.time() - start_time)
            remaining = timeout - elapsed
            console.print(f"\r[dim]Waiting for login... (timeout in {remaining}s)[/dim]", end="")
        
        return False
    
    def _save_cookies(self, cookies: Dict):
        """Save cookies to configuration file"""
        # Read existing config
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
        else:
            config = {}
        
        # Update cookie config
        config['cookies'] = cookies
        
        # Save config
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
    
    async def quick_extract(self) -> Dict:
        """Quick extract (use an already logged‑in browser session)"""
        console.print("\n[cyan]Trying to extract cookies from an already open browser...[/cyan]")
        console.print("[dim]Please make sure you are logged into Douyin in the browser[/dim]")
        
        # You can connect via CDP to an already opened browser
        # The browser must be launched in debugging mode
        console.print("\n[yellow]Please follow these steps:[/yellow]")
        console.print("1. Close all Chrome instances")
        console.print("2. Start Chrome in debugging mode:")
        console.print("   Windows: chrome.exe --remote-debugging-port=9222")
        console.print("   Mac: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222")
        console.print("3. Log into Douyin in the opened browser")
        console.print("4. Press Enter to continue...")
        
        input()
        
        try:
            async with async_playwright() as p:
                # Connect to an already opened browser
                browser = await p.chromium.connect_over_cdp("http://localhost:9222")
                contexts = browser.contexts

                if contexts:
                    context = contexts[0]
                    pages = context.pages

                    # Find the Douyin page
                    douyin_page = None
                    for page in pages:
                        if 'douyin.com' in page.url:
                            douyin_page = page
                            break

                    if douyin_page:
                        # Extract cookies
                        cookies = await context.cookies()
                        cookie_dict = {}

                        for cookie in cookies:
                            if 'douyin.com' in cookie.get('domain', ''):
                                cookie_dict[cookie['name']] = cookie['value']

                        if cookie_dict:
                            console.print("[green]✅ Successfully extracted cookies![/green]")
                            self._save_cookies(cookie_dict)
                            return cookie_dict
                        else:
                            console.print("[red]Douyin cookies not found[/red]")
                    else:
                        console.print("[red]Douyin page not found — please visit douyin.com first[/red]")
                else:
                    console.print("[red]No browser context found[/red]")

        except Exception as e:
            console.print(f"[red]Failed to connect to browser: {e}[/red]")
            console.print("[yellow]Please ensure the browser is started in debugging mode[/yellow]")
        
        return {}


async def main():
    """Main entrypoint"""
    extractor = CookieExtractor()
    
    console.print("\n[cyan]Choose extraction method:[/cyan]")
    console.print("1. Automatic login extraction (recommended)")
    console.print("2. Extract from an already logged‑in browser")
    console.print("3. Enter cookies manually")
    
    choice = Prompt.ask("Select", choices=["1", "2", "3"], default="1")
    
    if choice == "1":
        # Automatic login extraction
        headless = not Confirm.ask("Show browser UI?", default=True)
        cookies = await extractor.extract_cookies(headless=headless)
        
    elif choice == "2":
        # Extract from already logged‑in browser
        cookies = await extractor.quick_extract()
        
    else:
        # Manual input
        console.print("\n[cyan]Enter cookie string:[/cyan]")
        console.print("[dim]Format: name1=value1; name2=value2; ...[/dim]")
        cookie_string = Prompt.ask("Cookies")
        
        cookies = {}
        for item in cookie_string.split(';'):
            if '=' in item:
                key, value = item.strip().split('=', 1)
                cookies[key] = value
        
        if cookies:
            extractor._save_cookies(cookies)
            console.print("[green]✅ Cookies saved[/green]")
    
    if cookies:
        console.print("\n[green]✅ Cookie extraction completed![/green]")
        console.print("[dim]You can now run the downloader:[/dim]")
        console.print("python3 downloader.py -c config_simple.yml")
    else:
        console.print("\n[red]❌ Failed to extract cookies[/red]")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]User cancelled operation[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Program error: {e}[/red]")