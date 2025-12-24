# 🎥 Douyin Video Downloader

A Python-based tool to download high-quality Douyin (抖音) videos without watermarks.

## ✨ Features

- 📝 Extract Douyin URLs from mixed Chinese/English text
- 🎬 Download videos without watermarks
- 📊 Progress bar during download
- 🔄 Automatic retry on failure
- 🛡️ Anti-scraping bypass (User-Agent, headers, cookies)
- 🎯 Multiple implementation methods

## 🚀 Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

### Basic Usage

**Method 1: Using the Recommended Downloader (yt-dlp)**

```bash
python douyin_downloader.py "https://v.douyin.com/xSQfKpWGib4/"
```

Or with full text:

```bash
python douyin_downloader.py "6.12 z@t.Rx RKW:/ 趣味英语故事 https://v.douyin.com/xSQfKpWGib4/ 复制此链接"
```

**Method 2: Using Advanced Downloader (Manual API)**

```bash
python advanced_downloader.py "https://v.douyin.com/xSQfKpWGib4/"
```

### Python API Usage

```python
from douyin_downloader import DouyinDownloader

# Create downloader instance
downloader = DouyinDownloader()

# Input text with Douyin share link
text = """
6.12 z@t.Rx RKW:/ 09/10 趣味英语故事《小狐狸的彩虹尾巴》🦊🌈
https://v.douyin.com/xSQfKpWGib4/ 复制此链接，打开Dou音搜索，直接观看视频！
"""

# Process and download
try:
    downloader.process(text, output_dir='./downloads')
finally:
    downloader.close()
```

## 📦 Technology Stack

| Library | Purpose |
|---------|---------|
| `httpx` | Async HTTP client with HTTP/2 support |
| `yt-dlp` | Video download engine (handles anti-scraping) |
| `fake-useragent` | Generate realistic User-Agent strings |
| `browser-cookie3` | Extract browser cookies for authentication |
| `regex` | URL pattern matching |
| `tqdm` | Download progress bars |

## 🔧 Implementation Details

### Architecture

This project includes two implementations:

1. **`douyin_downloader.py`** (Recommended)
   - Uses `yt-dlp` for reliable downloads
   - Handles X-Bogus signature automatically
   - Best for production use

2. **`advanced_downloader.py`** (Educational)
   - Manual API calls with anti-scraping bypass
   - Shows technical implementation details
   - Demonstrates X-Bogus signature generation
   - May fail due to signature validation

### Core Components

#### 1. URL Extraction
```python
def extract_url(self, text: str) -> Optional[str]:
    # Regex patterns for v.douyin.com and full URLs
    pattern = r'https?://v\.douyin\.com/[A-Za-z0-9]+/?'
    match = re.search(pattern, text)
    return match.group(0) if match else None
```

#### 2. Redirect Resolution
```python
def get_video_id(self, url: str) -> Optional[str]:
    # Follow redirects to get final URL
    response = self.session.get(url, headers=self.headers)
    final_url = str(response.url)
    
    # Extract video ID (aweme_id)
    match = re.search(r'/(?:video|note)/(\d+)', final_url)
    return match.group(1) if match else None
```

#### 3. Anti-Scraping Bypass

**Headers Configuration:**
```python
headers = {
    'User-Agent': user_agent.chrome,
    'Referer': 'https://www.douyin.com/',
    'Accept': 'application/json, text/plain, */*',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120"',
}
```

**X-Bogus Signature:**
- Complex algorithm that combines URL, User-Agent, timestamp, and parameters
- Constantly updated by Douyin
- `yt-dlp` maintains the implementation
- Manual implementation in `advanced_downloader.py` is simplified (for demonstration)

#### 4. Video Download

```python
def download_video(self, url: str, output_path: str) -> bool:
    with self.session.stream('GET', url) as response:
        total_size = int(response.headers.get('content-length', 0))
        
        with tqdm(total=total_size, unit='iB', unit_scale=True) as pbar:
            with open(output_path, 'wb') as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
                    pbar.update(len(chunk))
```

## 🎯 Use Cases

### Example 1: Single Video Download
```python
from douyin_downloader import DouyinDownloader

downloader = DouyinDownloader()
text = "Check this out: https://v.douyin.com/xSQfKpWGib4/"
downloader.process(text)
downloader.close()
```

### Example 2: Batch Processing
```python
from douyin_downloader import DouyinDownloader

urls = [
    "https://v.douyin.com/xSQfKpWGib4/",
    "https://v.douyin.com/xABcDefGHi/",
    "https://v.douyin.com/xJKLmNoPQr/",
]

downloader = DouyinDownloader()
try:
    for url in urls:
        downloader.process(url, output_dir='./batch_downloads')
finally:
    downloader.close()
```

### Example 3: Extract URL Only
```python
from douyin_downloader import DouyinDownloader

text = "看这个视频：https://v.douyin.com/xSQfKpWGib4/ 很有趣！"
downloader = DouyinDownloader()
url = downloader.extract_url(text)
print(f"Extracted URL: {url}")
```

## ⚠️ Known Limitations

1. **X-Bogus Signature**
   - The signature algorithm is proprietary and frequently updated
   - Manual implementation may become outdated
   - Use `yt-dlp` for production reliability

2. **Cookie Requirements**
   - Some videos may require valid browser cookies
   - Install `browser-cookie3` and log in to Douyin in your browser

3. **Rate Limiting**
   - Douyin may rate-limit excessive requests
   - Add delays between batch downloads

4. **Regional Restrictions**
   - Some videos may be region-locked
   - Consider using appropriate proxies if needed

## 🛠️ Troubleshooting

### Problem: "yt-dlp is not installed"
```bash
pip install yt-dlp
```

### Problem: "No cookies found in browser"
- Make sure you're logged in to Douyin in Chrome or Firefox
- Install browser-cookie3: `pip install browser-cookie3`

### Problem: "X-Bogus signature invalid"
- This is expected with the manual method
- Use `douyin_downloader.py` with yt-dlp instead

### Problem: Download fails with 403 Forbidden
- Check if cookies are properly extracted
- Update User-Agent string
- Verify video is publicly accessible

## 📚 API Reference

### DouyinDownloader

Main class for downloading Douyin videos.

#### Methods

- `extract_url(text: str) -> Optional[str]`
  - Extract Douyin URL from text
  
- `get_video_id(url: str) -> Optional[str]`
  - Get video ID from URL
  
- `download_with_ytdlp(url: str, output_dir: str) -> bool`
  - Download video using yt-dlp
  
- `process(text: str, output_dir: str) -> bool`
  - Complete pipeline: extract → download
  
- `close()`
  - Close HTTP session

## 📄 License

This project is for educational purposes only. Respect content creators' rights and Douyin's Terms of Service.

## 🤝 Contributing

Contributions are welcome! Areas for improvement:

- Better X-Bogus signature generation
- Support for playlists/channels
- GUI interface
- Batch processing optimization
- Additional anti-scraping techniques

## 🔗 References

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Universal video downloader
- [X-Bogus Algorithm](https://github.com/B1gM8c/X-Bogus) - Signature generation
- [Douyin API Documentation](https://developer.open-douyin.com/) - Official API docs

## ⚡ Performance Tips

1. **Use yt-dlp method** for best reliability
2. **Enable HTTP/2** (already enabled via httpx)
3. **Adjust chunk size** based on your network (default: 8192 bytes)
4. **Add delays** between downloads to avoid rate limiting
5. **Use async** for batch downloads (future improvement)

---

**Note:** This tool is for personal use and educational purposes. Always respect copyright and content creators' rights.

