# Douyin Downloader – Bulk No‑Watermark Tool

![douyin-downloader](https://socialify.git.ci/jiji262/douyin-downloader/image?custom_description=%E6%8A%96%E9%9F%B3%E6%89%B9%E9%87%8F%E4%B8%8B%E8%BD%BD%E5%B7%A5%E5%85%B7%EF%BC%8C%E5%8E%BB%E6%B0%B4%E5%8D%B0%EF%BC%8C%E6%94%AF%E6%8C%81%E8%A7%86%E9%A2%91%E3%80%81%E5%9B%BE%E9%9B%86%E3%80%81%E5%90%88%E9%9B%86%E3%80%81%E9%9F%B3%E4%B9%90%28%E5%8E%9F%E5%A3%B0%29%E3%80%82%0A%E5%85%8D%E8%B4%B9%EF%BC%81%E5%85%8D%E8%B4%B9%EF%BC%81%E5%85%8D%E8%B4%B9%EF%BC%81&description=1&font=Jost&forks=1&logo=https%3A%2F%2Fraw.githubusercontent.com%2Fjiji262%2Fdouyin-downloader%2Frefs%2Fheads%2Fmain%2Fimg%2Flogo.png&name=1&owner=1&pattern=Circuit+Board&pulls=1&stargazers=1&theme=Light)

A powerful bulk downloader for Douyin content. Supports videos, image albums, music (original sound), and live streams. Two versions are available: V1.0 (Stable) and V2.0 (Enhanced).

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Version Overview](#-version-overview)
- [V1.0 Guide](#-v10-guide)
- [V2.0 Guide](#-v20-guide)
- [Cookie Tools](#-cookie-tools)
- [Supported Link Types](#-supported-link-types)
- [FAQ](#-faq)
- [Changelog](#-changelog)

## ⚡ Quick Start

![qun](./img/fuye.jpg)

### Requirements

- Python 3.9+
- OS: Windows, macOS, or Linux

### Installation

1. Clone the repo
```bash
git clone https://github.com/jiji262/douyin-downloader.git
cd douyin-downloader
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Configure Cookies (required for first use)
```bash
# Method 1: Automatic (recommended)
python cookie_extractor.py

# Method 2: Manual
python get_cookies_manual.py
```

## 📦 Version Overview

### V1.0 (DouYinCommand.py) – Stable
- ✅ Proven stability: battle‑tested
- ✅ Simple to use: config‑driven
- ✅ Feature complete: supports all content types
- ✅ Single‑video downloads: fully working
- ⚠️ Manual setup: requires manual cookie acquisition and configuration

### V2.0 (downloader.py) – Enhanced
- 🚀 Automatic cookie management: auto‑acquire and refresh
- 🚀 Unified entry point: everything in one script
- 🚀 Async architecture: faster, concurrent downloads
- 🚀 Smart retries: automatic retry and recovery
- 🚀 Incremental downloads: avoid duplicates
- ⚠️ Single‑video downloads: API returns empty response (known issue)
- ✅ User profile downloads: fully working

## 🎯 V1.0 Guide

### Configure via file

1. Create and edit config
```bash
cp config.example.yml config.yml
# then edit config.yml
```

2. Example configuration
```yaml
# Links to download
link:
  - https://v.douyin.com/xxxxx/                    # single video
  - https://www.douyin.com/user/xxxxx              # user profile
  - https://www.douyin.com/collection/xxxxx        # collection

# Save path
path: ./Downloaded/

# Cookie configuration (required)
cookies:
  msToken: YOUR_MS_TOKEN_HERE
  ttwid: YOUR_TTWID_HERE
  odin_tt: YOUR_ODIN_TT_HERE
  passport_csrf_token: YOUR_PASSPORT_CSRF_TOKEN_HERE
  sid_guard: YOUR_SID_GUARD_HERE

# Download options
music: True    # download music
cover: True    # download cover
avatar: True   # download avatar
json: True     # save JSON data

# Modes
mode:
  - post       # download published posts
  # - like     # download liked posts
  # - mix      # download collections

# Download counts (0 = all)
number:
  post: 0      # number of published posts
  like: 0      # number of liked posts
  allmix: 0    # number of collections
  mix: 0       # items per single collection

# Other settings
thread: 5      # number of download threads
database: True # record to database
```

### Run

```bash
# Run with config file
python DouYinCommand.py

# Or via command line args
python DouYinCommand.py --cmd False
```

### Examples

```bash
# Download a single video
# Set link to a video URL in config.yml
python DouYinCommand.py

# Download a user profile
# Set link to a user profile URL in config.yml
python DouYinCommand.py

# Download a collection
# Set link to a collection URL in config.yml
python DouYinCommand.py
```

## 🚀 V2.0 Guide

### Command line usage

```bash
# Download a single video (cookies required beforehand)
python downloader.py -u "https://v.douyin.com/xxxxx/"

# Download a user profile (recommended)
python downloader.py -u "https://www.douyin.com/user/xxxxx"

# Auto‑acquire cookies and download
python downloader.py --auto-cookie -u "https://www.douyin.com/user/xxxxx"

# Specify save path
python downloader.py -u "URL" --path "./my_videos/"

# Use configuration file
python downloader.py --config
```

### Configuration file usage

1. Create config file
```bash
cp config.example.yml config_simple.yml
```

2. Example configuration
```yaml
# Links to download
link:
  - https://www.douyin.com/user/xxxxx

# Save path
path: ./Downloaded/

# Automatic cookie management
auto_cookie: true

# Download options
music: true
cover: true
avatar: true
json: true

# Modes
mode:
  - post

# Download counts
number:
  post: 10

# Incremental download
increase:
  post: false

# Database
database: true
```

3. Run
```bash
python downloader.py --config
```

### Command line options

```bash
python downloader.py [OPTIONS] [URL...]

Options:
  -u, --url URL          Download link
  -p, --path PATH        Save path
  -c, --config           Use configuration file
  --auto-cookie          Automatically acquire cookies
  --cookies COOKIES      Provide cookies manually
  -h, --help             Show help
```

## 🍪 Cookie Tools

### 1) cookie_extractor.py – Automatic

Purpose: Use Playwright to open a browser and automatically acquire cookies.

Usage:
```bash
# Install Playwright
pip install playwright
playwright install chromium

# Run auto acquisition
python cookie_extractor.py
```

Highlights:
- ✅ Automatically opens a browser
- ✅ Supports QR login
- ✅ Detects login state
- ✅ Saves to configuration file
- ✅ Supports multiple login methods

Steps:
1. Run `python cookie_extractor.py`
2. Choose an extraction method (recommend 1)
3. Complete login in the opened browser
4. The program extracts and saves cookies automatically

### 2) get_cookies_manual.py – Manual

Purpose: Acquire cookies manually via browser DevTools.

Usage:
```bash
python get_cookies_manual.py
```

Highlights:
- ✅ No Playwright required
- ✅ Detailed step‑by‑step instructions
- ✅ Cookie validation
- ✅ Auto save to configuration
- ✅ Backup and restore support

Steps:
1. Run `python get_cookies_manual.py`
2. Choose "Get new cookies"
3. Follow the tutorial to acquire cookies in your browser
4. Paste the cookie content
5. The program parses and saves automatically

### Cookie acquisition guide

#### Method A: Browser DevTools

1. Open your browser and visit [Douyin Web](https://www.douyin.com)
2. Log in to your Douyin account
3. Press `F12` to open DevTools
4. Switch to the `Network` tab
5. Refresh the page and pick any request
6. Find the `Cookie` header
7. Copy the following cookie keys:
   - `msToken`
   - `ttwid`
   - `odin_tt`
   - `passport_csrf_token`
   - `sid_guard`

#### Method B: Automatic tool

```bash
# Recommended
python cookie_extractor.py
```

## 📋 Supported Link Types

### 🎬 Video content
- Single video share link: `https://v.douyin.com/xxxxx/`
- Single video direct link: `https://www.douyin.com/video/xxxxx`
- Image album (note): `https://www.douyin.com/note/xxxxx`

### 👤 User content
- User profile: `https://www.douyin.com/user/xxxxx`
  - Download all posts published by the user
  - Download user likes (may require permissions)

### 📚 Collections
- User collections: `https://www.douyin.com/collection/xxxxx`
- Music collections: `https://www.douyin.com/music/xxxxx`

### 🔴 Live
- Live room: `https://live.douyin.com/xxxxx`

## 🔧 FAQ

### Q: Why does single‑video download fail?
A:
- V1.0: Check that cookies are valid and include the required fields
- V2.0: Known issue – API returns empty response; use profile downloads instead

### Q: What if cookies expire?
A:
- Re‑acquire via `python cookie_extractor.py`
- Or acquire manually via `python get_cookies_manual.py`

### Q: How to improve download speed?
A:
- Increase concurrency by adjusting `thread`
- Check your network connection
- Avoid downloading too much at once

### Q: How to batch download?
A:
- V1.0: Add multiple links in `config.yml`
- V2.0: Pass multiple links via CLI or use a config file

### Q: What formats are supported?
A:
- Video: MP4 (no watermark)
- Images: JPG
- Audio: MP3
- Data: JSON

## 📝 Changelog

### V2.0 (2025‑08)
- ✅ Unified entry: all features in `downloader.py`
- ✅ Automatic cookie management: acquire and refresh
- ✅ Async architecture: performance optimized, concurrent downloads
- ✅ Smart retries: auto retry and recovery
- ✅ Incremental downloads
- ✅ User profile downloads: fully working
- ⚠️ Single‑video downloads: API returns empty response (known issue)

### V1.0 (2024‑12)
- ✅ Stable and reliable: heavily tested
- ✅ Feature complete: all content types
- ✅ Single‑video downloads: fully working
- ✅ Config‑driven: simple to use
- ✅ Database support: keeps download history

## ⚖️ Legal Notice

- For learning and communication purposes only
- Follow relevant laws and platform terms
- Do not use for commercial purposes or rights infringement
- Respect original authors' copyrights for downloaded content

## 🤝 Contributing

Issues and PRs are welcome!

### Report problems
- Use [Issues](https://github.com/jiji262/douyin-downloader/issues) to report bugs
- Provide detailed error messages and reproduction steps

### Feature requests
- Propose new features in Issues
- Describe requirements and usage scenarios clearly

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

<div align="center">

**If this project helps you, please ⭐ Star it!**

[🐛 Report an issue](https://github.com/jiji262/douyin-downloader/issues) • [💡 Request a feature](https://github.com/jiji262/douyin-downloader/issues) • [📖 Read the docs](https://github.com/jiji262/douyin-downloader/wiki)

Made with ❤️ by [jiji262](https://github.com/jiji262)

</div>
