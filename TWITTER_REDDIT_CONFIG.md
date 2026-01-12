# Enhanced Twitter and Reddit Download Configuration

## Overview

The Video Share platform now includes enhanced support for Twitter/X and Reddit video downloads with multiple fallback strategies and improved reliability.

## New Features

### 1. Platform-Specific Download Handlers
- **Twitter/X**: Direct page scraping + yt-dlp fallback
- **Reddit**: JSON API extraction + direct HTTP download + yt-dlp fallback
- **Enhanced Headers**: Better user agents and request headers for all platforms

### 2. Multiple Fallback Strategies
Each platform now tries multiple methods in order:
1. Direct platform-specific extraction
2. Enhanced yt-dlp with platform-specific parameters
3. Fallback to standard yt-dlp

### 3. New Configuration Options

#### Environment Variables
```bash
# Proxy settings (optional) - useful for bypassing restrictions
YT_DLP_PROXY=http://proxy.example.com:8080
YT_DLP_PROXY=socks5://proxy.example.com:1080

# Rate limiting (optional) - helps avoid being blocked
YT_DLP_RATE_LIMIT=1M  # 1MB/s
YT_DLP_RATE_LIMIT=500K  # 500KB/s

# Maximum video duration in seconds (default: 3600 = 1 hour)
YT_DLP_MAX_DURATION=3600

# Cookies file path (optional) - for authenticated requests
YT_DLP_COOKIES=/path/to/cookies.txt

# Custom user agent (optional) - for specific platform compatibility
YT_DLP_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
```

## Platform-Specific Tips

### Twitter/X Downloads
1. **Rate Limiting**: Twitter often blocks automated downloads. Use `YT_DLP_RATE_LIMIT=500K` to slow down requests
2. **Proxy Support**: Consider using a proxy (`YT_DLP_PROXY`) to bypass IP-based restrictions
3. **Cookies**: Use cookies from a logged-in browser session (`YT_DLP_COOKIES`) for better success rates
4. **User Agent**: The system now uses enhanced headers that mimic real browsers

### Reddit Downloads
1. **Stream Merging**: Reddit videos often have separate audio/video streams that are automatically merged
2. **API Access**: The system tries Reddit's JSON API first for better reliability
3. **Rate Limiting**: Use `YT_DLP_RATE_LIMIT=1M` to avoid being blocked
4. **Direct Download**: Falls back to direct HTTP download if yt-dlp fails

## Troubleshooting

### Common Issues

1. **Downloads Fail on Cloud Platforms**
   - Twitter and Reddit often block cloud hosting providers
   - Solution: Use a proxy or self-host the application

2. **Rate Limiting Errors**
   - Platforms detect automated downloads
   - Solution: Increase `YT_DLP_RATE_LIMIT` or use `YT_DLP_PROXY`

3. **Authentication Required**
   - Some content requires login
   - Solution: Export cookies from browser and use `YT_DLP_COOKIES`

### Getting Cookies for Twitter/Reddit

1. **Chrome/Edge**:
   - Install "Get cookies.txt" extension
   - Visit Twitter/Reddit and login
   - Click extension and download cookies.txt
   - Set `YT_DLP_COOKIES=/path/to/cookies.txt`

2. **Firefox**:
   - Install "cookies.txt" extension
   - Visit Twitter/Reddit and login
   - Click extension and download cookies.txt
   - Set `YT_DLP_COOKIES=/path/to/cookies.txt`

## Self-Hosting Benefits

The enhanced download system works best in self-hosted environments because:
- No cloud platform restrictions
- Full control over network configuration
- Ability to use proxies and VPNs
- Better success rates for Twitter and Reddit downloads

## Technical Details

### Enhanced Headers
The system now uses comprehensive browser headers:
```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8
Accept-Language: en-US,en;q=0.9
DNT: 1
```

### Platform-Specific Parameters
- **Twitter**: Referer header, optimized fragment handling
- **Reddit**: Enhanced format detection, DASH stream support
- **YouTube**: Concurrent fragment downloads

### Error Handling
- Graceful fallback between methods
- Detailed logging for troubleshooting
- User-friendly error messages
- Platform-specific error explanations
