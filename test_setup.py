#!/usr/bin/env python3
"""
Test script to verify Douyin Downloader setup
Run this to check if all dependencies are properly installed
"""

import sys

def test_imports():
    """Test if all required packages can be imported"""
    print("="*60)
    print("🧪 Testing Douyin Downloader Setup")
    print("="*60)
    print()
    
    tests = {
        'httpx': 'HTTP client',
        'yt_dlp': 'Video downloader',
        'fake_useragent': 'User-Agent generator',
        'tqdm': 'Progress bars',
        'browser_cookie3': 'Cookie extraction',
    }
    
    results = {}
    
    for package, description in tests.items():
        try:
            __import__(package)
            results[package] = True
            print(f"✅ {package:20} - {description}")
        except ImportError as e:
            results[package] = False
            print(f"❌ {package:20} - {description} - NOT INSTALLED")
    
    print()
    print("="*60)
    
    # Summary
    passed = sum(results.values())
    total = len(results)
    
    if passed == total:
        print(f"✅ All tests passed! ({passed}/{total})")
        print()
        print("🎉 Your setup is ready to download Douyin videos!")
        return True
    else:
        print(f"⚠️  Some dependencies missing ({passed}/{total} installed)")
        print()
        print("📦 To install missing packages:")
        print("   pip install -r requirements.txt")
        print()
        
        # Show specific missing packages
        missing = [pkg for pkg, status in results.items() if not status]
        if missing:
            print("Or install individually:")
            for pkg in missing:
                print(f"   pip install {pkg}")
        
        return False


def test_browser_cookies():
    """Test browser cookie extraction"""
    print()
    print("="*60)
    print("🍪 Testing Browser Cookie Extraction")
    print("="*60)
    print()
    
    try:
        import browser_cookie3
        
        browsers = {
            'Chrome': browser_cookie3.chrome,
            'Edge': browser_cookie3.edge,
            'Firefox': browser_cookie3.firefox,
        }
        
        found_any = False
        
        for name, browser_func in browsers.items():
            try:
                cookies = list(browser_func(domain_name='.douyin.com'))
                if cookies:
                    print(f"✅ {name:15} - Found {len(cookies)} Douyin cookies")
                    found_any = True
                else:
                    print(f"⚠️  {name:15} - No Douyin cookies found")
            except Exception as e:
                print(f"⚠️  {name:15} - Cannot access ({str(e)[:30]}...)")
        
        print()
        
        if found_any:
            print("✅ Cookie extraction works!")
            print("   You should be able to download videos.")
        else:
            print("⚠️  No Douyin cookies found in any browser")
            print()
            print("💡 To fix this:")
            print("   1. Open https://www.douyin.com in Chrome/Edge/Firefox")
            print("   2. Browse any video (no need to log in)")
            print("   3. Close your browser completely")
            print("   4. Run this test again")
        
        return found_any
        
    except ImportError:
        print("❌ browser_cookie3 not installed")
        print("   Install it with: pip install browser-cookie3")
        return False


def test_ytdlp_version():
    """Check yt-dlp version"""
    print()
    print("="*60)
    print("📦 Checking yt-dlp Version")
    print("="*60)
    print()
    
    try:
        import yt_dlp
        version = yt_dlp.version.__version__
        print(f"✅ yt-dlp version: {version}")
        print()
        print("💡 Keep yt-dlp updated for best results:")
        print("   pip install --upgrade yt-dlp")
        return True
    except ImportError:
        print("❌ yt-dlp not installed")
        return False
    except:
        print("⚠️  yt-dlp installed but version unknown")
        return True


def main():
    """Run all tests"""
    
    # Test 1: Imports
    imports_ok = test_imports()
    
    if not imports_ok:
        print()
        print("="*60)
        print("❌ Please install missing dependencies first")
        print("="*60)
        sys.exit(1)
    
    # Test 2: Browser cookies
    cookies_ok = test_browser_cookies()
    
    # Test 3: yt-dlp version
    ytdlp_ok = test_ytdlp_version()
    
    # Final summary
    print()
    print("="*60)
    print("📊 Final Summary")
    print("="*60)
    print()
    
    if imports_ok and cookies_ok:
        print("🎉 Everything looks good!")
        print("   You're ready to download Douyin videos.")
        print()
        print("🚀 Try it now:")
        print('   python douyin_downloader.py "https://v.douyin.com/YOUR_LINK/"')
    elif imports_ok and not cookies_ok:
        print("⚠️  Dependencies OK, but no cookies found")
        print("   Visit https://www.douyin.com in your browser first")
        print("   Then try downloading")
    else:
        print("❌ Setup incomplete")
        print("   Install missing dependencies with:")
        print("   pip install -r requirements.txt")
    
    print()


if __name__ == '__main__':
    main()

