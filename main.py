import os
import logging
import asyncio
from pathlib import Path
from urllib.parse import urlparse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# ========================
# الاعدادات
# ========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DOWNLOAD_DIR = Path("/tmp/downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ========================
# خيارات yt-dlp لكل منصة
# ========================
def get_ydl_opts(url, quality='best'):
    """إعدادات محسنة حسب المنصة"""
    
    domain = urlparse(url).netloc.lower()
    
    # إعدادات أساسية
    opts = {
        'outtmpl': str(DOWNLOAD_DIR / '%(title).80s.%(ext)s'),
        'quiet': True,
        'no_warnings': False,  # خلينا نشوف الأخطاء
        'socket_timeout': 30,
        'retries': 5,
        'fragment_retries': 5,
        'extract_flat': False,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }
    
    # إعدادات خاصة بانستغرام
    if 'instagram.com' in domain:
        opts.update({
            'format': 'best',
            'extractor_args': {
                'instagram': {
                    'no_login': 'true',
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Cookie': '',  # فاضي للتحميل العام
            }
        })
    
    # إعدادات تيك توك
    elif 'tiktok.com' in domain:
        opts.update({
            'format': 'best',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.tiktok.com/',
            }
        })
    
    # إعدادات يوتيوب وبقية المنصات
    else:
        opts.update({
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
        })
    
    # للصوتيات
    if quality == 'audio':
        opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
        })
    
    return opts

# ========================
# دالة التحميل
# ========================
async def download_video(url, quality, update, context):
    """تحميل الفيديو وإرساله"""
    chat_id = update.effective_chat.id
    
    if update.callback_query:
        status_msg = await update.callback_query.message.reply_text("🔄 جاري التحميل...")
    else:
        status_msg = await context.bot.send_message(chat_id, "🔄 جاري التحميل...")
    
    try:
        ydl_opts = get_ydl_opts(url, quality)
        
        def sync_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                # تصحيح الامتداد للصوت
                if quality == 'audio':
                    filename = str(Path(filename).with_suffix('.mp3'))
                
                return filename, info
        
        # تشغيل في thread منفصل
        filepath, info = await asyncio.to_thread(sync_download)
        
        # البحث عن الملف إذا ما لقيناه
        if not os.path.exists(filepath):
            # يمكن الملف بامتداد مختلف
            base = Path(filepath).stem
            for ext in ['.mp4', '.mkv', '.webm', '.mp3']:
                alt_path = DOWNLOAD_DIR / f"{base}{ext}"
                if alt_path.exists():
                    filepath = str(alt_path)
                    break
        
        if not os.path.exists(filepath):
            # آخر محاولة - أي ملف جديد في المجلد
            files = sorted(DOWNLOAD_DIR.glob("*"), key=lambda f: f.stat().st_mtime, reverse=True)
            if files:
                filepath = str(files[0])
            else:
                raise FileNotFoundError("الملف غير موجود")
        
        # فحص الحجم
        file_size = os.path.getsize(filepath)
        max_size = 5000 * 1024 * 1024  # 50MB
        
        if file_size > max_size:
            await status_msg.edit_text(f"⚠️ الملف كبير: {file_size/1024/1024:.1f}MB - الحد 5000MB")
            os.remove(filepath)
            return
        
        if file_size == 0:
            await status_msg.edit_text("❌ الملف فارغ")
            os.remove(filepath)
            return
        
        # حذف رسالة الانتظار
        await status_msg.delete()
        
        # إرسال الملف
        title = info.get('title', Path(filepath).stem)[:100]
        
        if quality == 'audio':
            with open(filepath, 'rb') as f:
                await context.bot.send_audio(
                    chat_id,
                    f,
                    title=title,
                    performer=info.get('uploader', 'Unknown')
                )
        else:
            with open(filepath, 'rb') as f:
                await context.bot.send_video(
                    chat_id,
                    f,
                    supports_streaming=True,
                    caption=f"🎬 {title}" if len(title) < 100 else None
                )
        
        # حذف الملف
        os.remove(filepath)
        logger.info(f"✅ تم بنجاح: {title}")
        
    except Exception as e:
        # طباعة الخطأ كامل في السجلات
        logger.exception("خطأ في التحميل:")
        error_str = str(e)
        
        # رسائل مخصصة حسب الخطأ
        if "login" in error_str.lower() or "401" in error_str or "403" in error_str:
            await status_msg.edit_text(
                "🔒 إنستغرام يطلب تسجيل دخول لهذا الفيديو\n\n"
                "📌 الحلول:\n"
                "1️⃣ جرب فيديو من حساب عام مفتوح\n"
                "2️⃣ أضف حساب إنستغرام في إعدادات البوت\n\n"
                f"❌ الخطأ: {error_str[:150]}"
            )
        elif "rate limit" in error_str.lower() or "429" in error_str:
            await status_msg.edit_text("⏳ تم حظر مؤقت من إنستغرام. انتظر 5 دقائق وحاول مجدداً.")
        elif "not available" in error_str.lower():
            await status_msg.edit_text("❌ الفيديو غير متاح (خاص أو محذوف)")
        else:
            await status_msg.edit_text(f"❌ خطأ:\n{error_str[:200]}")

# ========================
# أوامر البوت
# ========================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 *بوت تحميل الفيديوهات*\n\n"
        "📥 المنصات المدعومة:\n"
        "• 📸 انستغرام\n"
        "• 🎵 تيك توك\n"
        "• 📺 يوتيوب\n"
        "• 🐦 تويتر/X\n"
        "• 👤 فيسبوك\n\n"
        "📤 فقط أرسل الرابط واختر الجودة!",
        parse_mode='Markdown'
    )

async def url_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ أرسل رابط صحيح يبدأ بـ http:// أو https://")
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
        await query.edit_message_text("❌ انتهت الجلسة، أرسل الرابط مجدداً")
        return
    
    quality_names = {
        '720p': '🎥 720p',
        '1080p': '🎥 1080p',
        'best': '🔥 أفضل جودة',
        'audio': '🎵 MP3'
    }
    
    await query.edit_message_text(f"⏳ جاري تحميل {quality_names.get(quality, quality)}...")
    await download_video(url, quality, update, context)

# ========================
# تشغيل البوت
# ========================
def main():
    if not BOT_TOKEN:
        logger.error("❌ أضف BOT_TOKEN في Railway Variables")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, url_handler))
    app.add_handler(CallbackQueryHandler(quality_handler))
    
    logger.info("🚀 البوت يعمل على Railway...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
