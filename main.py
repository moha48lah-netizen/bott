import os
import logging
import asyncio
import re
from pathlib import Path
from urllib.parse import urlparse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import requests

# ========================
# الاعدادات من Railway
# ========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DOWNLOAD_DIR = Path("/tmp/downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ========================
# دوال التحميل
# ========================
def extract_instagram(url):
    """تحميل انستغرام"""
    try:
        if '/reel/' in url:
            post_id = url.split('/reel/')[1].split('/')[0].split('?')[0]
        elif '/p/' in url:
            post_id = url.split('/p/')[1].split('/')[0].split('?')[0]
        else:
            return None
        
        # طريقة 1: API مباشر
        api_url = f"https://www.instagram.com/p/{post_id}/?__a=1&__d=1"
        headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'}
        
        response = requests.get(api_url, headers=headers, timeout=15)
        if response.status_code == 200:
            try:
                data = response.json()
                video_url = data['graphql']['shortcode_media']['video_url']
                video_response = requests.get(video_url, headers=headers, timeout=30)
                if video_response.status_code == 200:
                    filepath = DOWNLOAD_DIR / f"ig_{post_id}.mp4"
                    with open(filepath, 'wb') as f:
                        f.write(video_response.content)
                    return str(filepath)
            except:
                pass
        
        # طريقة 2: snapinsta
        snap_url = "https://snapinsta.app/action2.php"
        data = {'url': url, 'action': 'post'}
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        response = requests.post(snap_url, data=data, headers=headers, timeout=15)
        if response.status_code == 200:
            video_match = re.search(r'href="(https://[^"]*\.mp4[^"]*)"', response.text)
            if video_match:
                video_url = video_match.group(1).replace('&amp;', '&')
                video_response = requests.get(video_url, headers=headers, timeout=30)
                if video_response.status_code == 200:
                    filepath = DOWNLOAD_DIR / f"ig_{post_id}.mp4"
                    with open(filepath, 'wb') as f:
                        f.write(video_response.content)
                    return str(filepath)
        return None
    except Exception as e:
        logger.error(f"Instagram error: {e}")
        return None

def extract_tiktok(url):
    """تحميل تيك توك"""
    try:
        api_url = "https://www.tikwm.com/api/"
        params = {'url': url, 'hd': 1}
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        response = requests.get(api_url, params=params, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 0:
                video_url = data['data'].get('hdplay') or data['data'].get('play')
                if video_url:
                    video_response = requests.get(video_url, headers=headers, timeout=30)
                    if video_response.status_code == 200:
                        video_id = data['data']['id']
                        filepath = DOWNLOAD_DIR / f"tt_{video_id}.mp4"
                        with open(filepath, 'wb') as f:
                            f.write(video_response.content)
                        return str(filepath)
        return None
    except Exception as e:
        logger.error(f"TikTok error: {e}")
        return None

def extract_youtube(url, quality='best'):
    """تحميل يوتيوب"""
    try:
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': str(DOWNLOAD_DIR / '%(title).50s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            'socket_timeout': 30,
            'retries': 3,
        }
        
        if quality == 'audio':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '320'}],
            })
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if quality == 'audio':
                filename = str(Path(filename).with_suffix('.mp3'))
            return filename
    except Exception as e:
        logger.error(f"YouTube error: {e}")
        return None

def extract_other(url):
    """تحميل المنصات الأخرى"""
    try:
        ydl_opts = {
            'format': 'best',
            'outtmpl': str(DOWNLOAD_DIR / '%(title).50s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        logger.error(f"Other error: {e}")
        return None

# ========================
# دالة التحميل الذكية
# ========================
async def smart_download(url, quality, update, context):
    """توجيه التحميل حسب المنصة"""
    chat_id = update.effective_chat.id
    
    if update.callback_query:
        status_msg = await update.callback_query.message.reply_text("🔄 جاري التحميل...")
    else:
        status_msg = await context.bot.send_message(chat_id, "🔄 جاري التحميل...")
    
    try:
        domain = urlparse(url).netloc.lower()
        filepath = None
        
        if 'instagram.com' in domain:
            filepath = await asyncio.to_thread(extract_instagram, url)
        elif 'tiktok.com' in domain:
            filepath = await asyncio.to_thread(extract_tiktok, url)
        elif 'youtube.com' in domain or 'youtu.be' in domain:
            filepath = await asyncio.to_thread(extract_youtube, url, quality)
        else:
            filepath = await asyncio.to_thread(extract_other, url)
        
        if filepath and os.path.exists(filepath):
            file_size = os.path.getsize(filepath)
            
            if file_size > 50 * 1024 * 1024:
                await status_msg.edit_text("⚠️ حجم الملف كبير جداً (>50MB)")
                os.remove(filepath)
                return
            
            await status_msg.delete()
            
            if quality == 'audio':
                with open(filepath, 'rb') as f:
                    await context.bot.send_audio(chat_id, f, title=Path(filepath).stem)
            else:
                with open(filepath, 'rb') as f:
                    await context.bot.send_video(chat_id, f, supports_streaming=True)
            
            os.remove(filepath)
            logger.info(f"✅ تم التحميل: {filepath}")
        else:
            await status_msg.edit_text("❌ فشل التحميل\nجرب فيديو آخر")
    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text(f"❌ خطأ: {str(e)[:200]}")

# ========================
# أوامر البوت
# ========================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 بوت تحميل الفيديوهات\n\n"
        "📥 أرسل رابط الفيديو للتحميل\n"
        "📺 يوتيوب | 📸 انستغرام | 🎵 تيك توك | 🐦 تويتر | 👤 فيسبوك"
    )

async def url_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ أرسل رابط صحيح")
        return
    
    context.user_data['url'] = url
    
    keyboard = [
        [InlineKeyboardButton("🎥 720p", callback_data="720p"),
         InlineKeyboardButton("🎥 1080p", callback_data="1080p")],
        [InlineKeyboardButton("🔥 أفضل جودة", callback_data="best"),
         InlineKeyboardButton("🎵 MP3", callback_data="audio")]
    ]
    
    await update.message.reply_text(
        "✅ تم استلام الرابط\nاختر الجودة:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def quality_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    quality = query.data
    url = context.user_data.get('url')
    
    if not url:
        await query.edit_message_text("❌ انتهت الجلسة")
        return
    
    await query.edit_message_text(f"⏳ جاري التحميل...")
    await smart_download(url, quality, update, context)

# ========================
# تشغيل البوت
# ========================
def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير موجود في المتغيرات البيئية")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, url_handler))
    app.add_handler(CallbackQueryHandler(quality_handler))
    
    logger.info("🚀 البوت يعمل...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
