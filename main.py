import os
import logging
import asyncio
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# ========================
# 1. الاعدادات
# ========================
BOT_TOKEN = "8940243101:AAGk3kzx9hDpp3CFV2owD2UT52XfaRTEMI0"  # ضع التوكن هنا
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# إعدادات التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========================
# 2. إعدادات التحميل المحسنة
# ========================
def get_ydl_opts(quality: str):
    """إعدادات yt-dlp مع أفضل توافق"""
    
    # الإعدادات الأساسية
    base_opts = {
        'outtmpl': str(DOWNLOAD_DIR / '%(title).100s.%(ext)s'),  # تقييد طول الاسم
        'quiet': True,
        'no_warnings': False,
        'extract_flat': False,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
        },
        # خيارات مهمة للسيرفر
        'socket_timeout': 30,
        'retries': 3,
        'fragment_retries': 3,
        'skip_download': False,
        'trim_file_name': 100,
    }
    
    if quality == "audio":
        return {
            **base_opts,
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
        }
    
    # إعدادات الفيديو حسب الجودة
    format_map = {
        "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
        "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]",
        "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    }
    
    return {
        **base_opts,
        'format': format_map.get(quality, "best"),
        'merge_output_format': 'mp4',
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
    }

# ========================
# 3. دالة التحميل
# ========================
async def download_media(url: str, quality: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحميل وإرسال الوسائط"""
    chat_id = update.effective_chat.id
    
    # إرسال رسالة انتظار
    if update.callback_query:
        status_msg = await update.callback_query.message.reply_text("🔄 جاري التحميل... ⏳")
    else:
        status_msg = await context.bot.send_message(chat_id, "🔄 جاري التحميل... ⏳")
    
    try:
        # إنشاء خيارات التحميل
        ydl_opts = get_ydl_opts(quality)
        
        # تنفيذ التحميل في thread منفصل
        def download_sync():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                # إذا كان صوت، نغير الامتداد
                if quality == "audio":
                    filename = str(Path(filename).with_suffix('.mp3'))
                
                return filename, info
        
        filepath, info = await asyncio.to_thread(download_sync)
        
        # التأكد من وجود الملف
        if not os.path.exists(filepath):
            # البحث في مجلد التحميلات
            files = sorted(DOWNLOAD_DIR.glob("*"), key=os.path.getmtime, reverse=True)
            if files:
                filepath = str(files[0])
            else:
                raise FileNotFoundError("الملف غير موجود")
        
        # فحص حجم الملف
        file_size = os.path.getsize(filepath)
        max_size = 50 * 1024 * 1024  # 50 ميجابايت
        
        if file_size > max_size:
            await status_msg.edit_text(f"⚠️ حجم الملف كبير جداً: {file_size / (1024*1024):.1f}MB")
            os.remove(filepath)
            return
        
        # حذف رسالة الانتظار
        await status_msg.delete()
        
        # إرسال الملف
        title = info.get('title', Path(filepath).stem)[:100]
        
        if quality == "audio":
            with open(filepath, 'rb') as audio:
                await context.bot.send_audio(
                    chat_id, 
                    audio, 
                    title=title,
                    performer=info.get('uploader', 'Unknown')
                )
        else:
            with open(filepath, 'rb') as video:
                await context.bot.send_video(
                    chat_id, 
                    video,
                    supports_streaming=True,
                    caption=f"🎬 {title}" if len(title) < 100 else None
                )
        
        # حذف الملف
        os.remove(filepath)
        logger.info(f"✅ تم تحميل وإرسال: {title}")
        
    except Exception as e:
        error_msg = str(e)[:200]
        logger.error(f"❌ خطأ: {error_msg}")
        
        # رسائل خطأ مخصصة
        if "HTTP Error 429" in error_msg:
            await status_msg.edit_text("⏳ كثرة الطلبات. انتظر دقيقة وحاول مجدداً.")
        elif "Private video" in error_msg or "login" in error_msg.lower():
            await status_msg.edit_text("🔒 هذا المحتوى خاص أو يحتاج تسجيل دخول.")
        elif "Video unavailable" in error_msg:
            await status_msg.edit_text("❌ الفيديو غير متاح أو محذوف.")
        else:
            await status_msg.edit_text(f"❌ خطأ: {error_msg}")

# ========================
# 4. معالجات البوت
# ========================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /start"""
    await update.message.reply_text(
        "🎬 *مرحباً بك في بوت تحميل الفيديوهات!*\n\n"
        "📥 *المنصات المدعومة:*\n"
        "• 📺 يوتيوب\n"
        "• 📸 انستغرام\n"
        "• 🎵 تيك توك\n"
        "• 🐦 تويتر/X\n"
        "• 👤 فيسبوك\n"
        "• 🎬 Vimeo\n"
        "• وغيرها الكثير...\n\n"
        "📤 *طريقة الاستخدام:*\n"
        "1️⃣ أرسل رابط الفيديو\n"
        "2️⃣ اختر الجودة\n"
        "3️⃣ استلم الفيديو\n\n"
        "⚡️ *الميزات:*\n"
        "• تحميل سريع\n"
        "• جودة تصل إلى 1080p\n"
        "• دعم الصوت MP3\n"
        "• حذف تلقائي للملفات\n\n"
        "👨‍💻 *المطور:* @yourusername",
        parse_mode='Markdown'
    )

async def url_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الروابط"""
    url = update.message.text.strip()
    
    # التحقق من صحة الرابط
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ من فضلك أرسل رابط صحيح يبدأ بـ http:// أو https://")
        return
    
    # تخزين الرابط
    context.user_data['url'] = url
    
    # إنشاء لوحة المفاتيح
    keyboard = [
        [
            InlineKeyboardButton("🎥 720p", callback_data="720p"),
            InlineKeyboardButton("🎥 1080p", callback_data="1080p")
        ],
        [
            InlineKeyboardButton("🔥 أفضل جودة", callback_data="best"),
            InlineKeyboardButton("🎵 MP3", callback_data="audio")
        ]
    ]
    
    await update.message.reply_text(
        "✅ *تم استلام الرابط*\n\nاختر جودة التحميل:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def quality_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار الجودة"""
    query = update.callback_query
    await query.answer()
    
    quality = query.data
    url = context.user_data.get('url')
    
    if not url:
        await query.edit_message_text("❌ انتهت الجلسة. أرسل الرابط مجدداً.")
        return
    
    # رسالة الجودة
    quality_names = {
        '720p': '🎥 720p',
        '1080p': '🎥 1080p',
        'best': '🔥 أفضل جودة',
        'audio': '🎵 MP3'
    }
    
    await query.edit_message_text(f"⏳ جاري تحميل {quality_names.get(quality, quality)}...")
    
    # بدء التحميل
    await download_media(url, quality, update, context)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأخطاء العامة"""
    logger.error(f"Update {update} caused error {context.error}")
    try:
        if update and update.effective_chat:
            await context.bot.send_message(
                update.effective_chat.id,
                "❌ حدث خطأ غير متوقع. جرب مرة أخرى."
            )
    except:
        pass

# ========================
# 5. تشغيل البوت
# ========================
def main():
    """الدالة الرئيسية"""
    
    # التحقق من وجود التوكن
    if BOT_TOKEN == "TOKEN_HERE":
        logger.error("❌ الرجاء وضع توكن البوت في المتغير BOT_TOKEN")
        return
    
    # إنشاء التطبيق
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, url_handler))
    application.add_handler(CallbackQueryHandler(quality_handler))
    
    # معالج الأخطاء
    application.add_error_handler(error_handler)
    
    # تشغيل البوت
    logger.info("🚀 البوت يعمل الآن...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
