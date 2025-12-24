#!/usr/bin/env python3
"""
Douyin Video Downloader
Downloads high-quality Douyin videos without watermarks
"""

import re
import json
import time
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs

import httpx
from fake_useragent import UserAgent
from tqdm import tqdm

try:
    import browser_cookie3
    COOKIES_AVAILABLE = True
except ImportError:
    COOKIES_AVAILABLE = False


class DouyinDownloader:
    """Main class for downloading Douyin videos"""
    
    def __init__(self):
        self.ua = UserAgent()
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
        self.headers = self._get_headers()
        
    def _get_headers(self) -> Dict[str, str]:
        """Generate request headers with proper User-Agent and Referer"""
        return {
            'User-Agent': self.ua.chrome,
            'Referer': 'https://www.douyin.com/',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Origin': 'https://www.douyin.com',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }
    
    def extract_url(self, text: str) -> Optional[str]:
        """
        Extract Douyin URL from mixed Chinese/English text
        
        Args:
            text: Input text containing Douyin share link
            
        Returns:
            Extracted URL or None if not found
        """
        # Pattern to match v.douyin.com URLs
        pattern = r'https?://v\.douyin\.com/[A-Za-z0-9]+/?'
        match = re.search(pattern, text)
        
        if match:
            return match.group(0)
        
        # Alternative pattern for full URLs
        pattern2 = r'https?://(?:www\.)?douyin\.com/(?:video|note)/(\d+)'
        match2 = re.search(pattern2, text)
        
        if match2:
            return match2.group(0)
            
        return None
    
    def get_video_id(self, url: str) -> Optional[str]:
        """
        Follow redirects and extract video ID (aweme_id)
        
        Args:
            url: Short or full Douyin URL
            
        Returns:
            Video ID or None if extraction fails
        """
        try:
            print(f"🔗 Following redirects for: {url}")
            
            # Follow redirects
            response = self.session.get(url, headers=self.headers)
            final_url = str(response.url)
            
            print(f"✅ Final URL: {final_url}")
            
            # Extract video ID from final URL
            # Pattern 1: /video/1234567890
            match = re.search(r'/(?:video|note)/(\d+)', final_url)
            if match:
                return match.group(1)
            
            # Pattern 2: modal_id parameter
            parsed = urlparse(final_url)
            params = parse_qs(parsed.query)
            if 'modal_id' in params:
                return params['modal_id'][0]
                
            return None
            
        except Exception as e:
            print(f"❌ Error getting video ID: {e}")
            return None
    
    def get_video_info_ytdlp(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Get video info using yt-dlp (most reliable method)
        
        Args:
            url: Douyin video URL
            
        Returns:
            Video information dictionary
        """
        try:
            import yt_dlp
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
            
            print(f"📡 Fetching video info using yt-dlp...")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                return {
                    'title': info.get('title', 'Untitled'),
                    'video_id': info.get('id', ''),
                    'download_url': info.get('url', ''),
                    'duration': info.get('duration', 0),
                    'description': info.get('description', ''),
                    'author': info.get('uploader', 'Unknown'),
                }
                
        except ImportError:
            print("⚠️  yt-dlp not available, will try manual method")
            return None
        except Exception as e:
            print(f"❌ Error with yt-dlp: {e}")
            return None
    
    def sanitize_filename(self, filename: str) -> str:
        """
        Remove invalid characters from filename
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove invalid characters
        invalid_chars = r'[<>:"/\\|?*]'
        filename = re.sub(invalid_chars, '_', filename)
        
        # Limit length
        if len(filename) > 200:
            filename = filename[:200]
            
        return filename
    
    def download_video(self, url: str, output_path: Optional[str] = None) -> bool:
        """
        Download video with progress bar
        
        Args:
            url: Direct video download URL
            output_path: Output file path (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"⬇️  Starting download...")
            
            # Start download with streaming
            with self.session.stream('GET', url, headers=self.headers) as response:
                response.raise_for_status()
                
                # Get total size
                total_size = int(response.headers.get('content-length', 0))
                
                # Setup progress bar
                progress_bar = tqdm(
                    total=total_size,
                    unit='iB',
                    unit_scale=True,
                    desc='Downloading'
                )
                
                # Write to file
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        size = f.write(chunk)
                        progress_bar.update(size)
                
                progress_bar.close()
                
            print(f"✅ Video saved to: {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return False
    
    def extract_cookies_to_file(self, output_file: str = './douyin_cookies.txt') -> bool:
        """
        Extract cookies from browser and save to Netscape format for yt-dlp
        
        Args:
            output_file: Path to save cookies file
            
        Returns:
            True if successful
        """
        if not COOKIES_AVAILABLE:
            return False
            
        try:
            print("🍪 Extracting cookies from browser...")
            
            cookies = None
            # Try Chrome first
            try:
                cookies = browser_cookie3.chrome(domain_name='.douyin.com')
                print("✅ Found cookies from Chrome")
            except:
                pass
            
            # Try Edge
            if not cookies:
                try:
                    cookies = browser_cookie3.edge(domain_name='.douyin.com')
                    print("✅ Found cookies from Edge")
                except:
                    pass
            
            # Try Firefox
            if not cookies:
                try:
                    cookies = browser_cookie3.firefox(domain_name='.douyin.com')
                    print("✅ Found cookies from Firefox")
                except:
                    pass
            
            if not cookies:
                print("⚠️  No cookies found. Please log in to Douyin in your browser first.")
                return False
            
            # Write cookies in Netscape format
            with open(output_file, 'w') as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# This is a generated file! Do not edit.\n\n")
                
                for cookie in cookies:
                    f.write(f"{cookie.domain}\t")
                    f.write(f"{'TRUE' if cookie.domain.startswith('.') else 'FALSE'}\t")
                    f.write(f"{cookie.path}\t")
                    f.write(f"{'TRUE' if cookie.secure else 'FALSE'}\t")
                    f.write(f"{cookie.expires if cookie.expires else 0}\t")
                    f.write(f"{cookie.name}\t")
                    f.write(f"{cookie.value}\n")
            
            print(f"✅ Cookies saved to {output_file}")
            return True
            
        except Exception as e:
            print(f"⚠️  Error extracting cookies: {e}")
            return False
    
    def download_with_ytdlp(self, url: str, output_dir: str = './downloads') -> bool:
        """
        Download video using yt-dlp (recommended method)
        
        Args:
            url: Douyin video URL
            output_dir: Output directory
            
        Returns:
            True if successful
        """
        try:
            import yt_dlp
            
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            
            # Extract cookies for authentication
            cookies_file = './douyin_cookies.txt'
            has_cookies = self.extract_cookies_to_file(cookies_file)
            
            ydl_opts = {
                'outtmpl': f'{output_dir}/%(title)s_%(id)s.%(ext)s',
                'format': 'best',
                'quiet': False,
                'no_warnings': False,
                'progress_hooks': [self._ytdlp_progress_hook],
            }
            
            # Add cookies if available
            if has_cookies and Path(cookies_file).exists():
                ydl_opts['cookiefile'] = cookies_file
                print(f"🔐 Using cookies for authentication")
            else:
                print(f"⚠️  No cookies available - download may fail")
                print(f"💡 To fix: Open https://www.douyin.com in Chrome/Edge/Firefox and log in")
            
            print(f"🎬 Downloading video using yt-dlp...")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            print(f"✅ Download complete!")
            
            # Clean up cookies file
            try:
                if Path(cookies_file).exists():
                    Path(cookies_file).unlink()
            except:
                pass
            
            return True
            
        except ImportError:
            print("❌ yt-dlp is not installed. Install it with: pip install yt-dlp")
            return False
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return False
    
    def _ytdlp_progress_hook(self, d):
        """Progress hook for yt-dlp downloads"""
        if d['status'] == 'downloading':
            print(f"\r⬇️  {d.get('_percent_str', 'N/A')} | "
                  f"Speed: {d.get('_speed_str', 'N/A')} | "
                  f"ETA: {d.get('_eta_str', 'N/A')}", end='')
        elif d['status'] == 'finished':
            print(f"\n✅ Download finished, processing...")
    
    def process(self, text: str, output_dir: str = './downloads') -> bool:
        """
        Main processing pipeline: extract URL -> download video
        
        Args:
            text: Input text containing Douyin link
            output_dir: Output directory for downloaded videos
            
        Returns:
            True if successful
        """
        print("="*60)
        print("🎥 Douyin Video Downloader")
        print("="*60)
        
        # Step 1: Extract URL
        url = self.extract_url(text)
        if not url:
            print("❌ No Douyin URL found in the text")
            return False
        
        print(f"✅ Found URL: {url}")
        
        # Step 2: Download using yt-dlp (most reliable)
        success = self.download_with_ytdlp(url, output_dir)
        
        if not success:
            print("\n" + "="*60)
            print("❌ Download Failed - Troubleshooting Guide")
            print("="*60)
            print("\n📋 Common Issues:")
            print("1. Missing Cookies (most common)")
            print("   ➜ Open https://www.douyin.com in Chrome/Edge/Firefox")
            print("   ➜ Browse any video (no need to log in)")
            print("   ➜ Try the download again")
            print("\n2. Missing Dependencies")
            print("   ➜ Run: pip install browser-cookie3")
            print("\n3. Browser Not Supported")
            print("   ➜ Use Chrome, Edge, or Firefox")
            print("   ➜ Make sure browser is closed or restart it")
            print("\n4. Regional Restrictions")
            print("   ➜ Some videos may be region-locked")
            print("="*60)
        
        return success
    
    def close(self):
        """Close HTTP session"""
        self.session.close()


def main():
    """Main entry point"""
    import sys
    
    # Example input text
    example_text = """
    6.12 z@t.Rx RKW:/ 09/10 趣味英语故事《小狐狸的彩虹尾巴》🦊🌈 
    小狐狸想要一条彩虹尾巴，最后才发现——红色的自己，已经很漂亮❤️ 
    这是一则关于自我认同与接纳的温暖故事。
    https://v.douyin.com/xSQfKpWGib4/ 复制此链接，打开Dou音搜索，直接观看视频！
    """
    
    if len(sys.argv) > 1:
        # Use command line argument
        input_text = ' '.join(sys.argv[1:])
    else:
        # Use example or prompt user
        print("No input provided. Using example text...")
        input_text = example_text
    
    # Create downloader and process
    downloader = DouyinDownloader()
    
    try:
        downloader.process(input_text)
    finally:
        downloader.close()


if __name__ == '__main__':
    main()

