import os
import logging
import asyncio
import yt_dlp
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

SUPPORTED_SITES = ["youtube.com", "youtu.be", "facebook.com", "fb.watch", "instagram.com", "twitter.com", "x.com", "tiktok.com"]

class VideoDownloader:
    def __init__(self):
        self.temp_dir = "temp_downloads"
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def is_supported(self, url):
        domain = urlparse(url).netloc.lower()
        return any(site in domain for site in SUPPORTED_SITES)
    
    async def get_info(self, url):
        try:
            ydl_opts = {'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(None, lambda: ydl.extract_info(url, download=False))
                return {'title': info.get('title', 'غير معروف'), 'duration': info.get('duration', 0), 'uploader': info.get('uploader', 'غير معروف')}
        except:
            return None
    
    async def download(self, url, quality='best'):
        try:
            filename = f"vid_{os.urandom(4).hex()}"
            format_map = {'best': 'best[height<=1080]', '720': 'best[height<=720]', '480': 'best[height<=480]', '360': 'best[height<=360]', 'audio': 'bestaudio/best'}
            format_select = format_map.get(quality, format_map['best'])
            ext = '.mp3' if quality == 'audio' else '.mp4'
            output_path = os.path.join(self.temp_dir, f"{filename}{ext}")
            ydl_opts = {'format': format_select, 'outtmpl': output_path, 'quiet': True, 'no_warnings': True}
            if quality == 'audio':
                ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await asyncio.get_event_loop().run_in_executor(None, lambda: ydl.download([url]))
            return output_path if os.path.exists(output_path) else None
        except Exception as e:
            logger.error(f"Download error: {e}")
            return None
