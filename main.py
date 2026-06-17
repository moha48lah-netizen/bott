import os
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# ========================
# 1. الاعدادات الأساسية
# ========================
BOT_TOKEN = "TOKEN_HERE"  # ضع التوكن هنا
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ========================
# 2. خيارات الجودة لـ yt-dlp
# ========================
def get_ydl_opts(quality: str):
    """إعدادات التحميل حسب الجودة المطلوبة"""
    if quality == "audio":
        return {
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }],
            "outtmpl": str(DOWNLOAD_DIR / "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
        }
    
    formats = {
        "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "best": "bestvideo+bestaudio/best",
    }
    
    return {
        "format": formats.get(quality, "best"),
        "merge_output_format": "mp4",
        "outtmpl": str(DOWNLOAD_DIR / "%(title)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
    }

# ========================
# 3. دالة التحميل الأساسية
# ========================
async def download_video(url: str, quality: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحميل الفيديو وإرساله للمستخدم ثم حذفه فوراً"""
    chat_id = update.effective_chat.id
    temp_msg = await context.bot.send_message(chat_id, "🔄 جاري التحميل... يرجى الانتظار ⏳")

    try:
        ydl_opts = get_ydl_opts(quality)
        
        def sync_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)

        # التحميل في thread منفصل حتى لا نعلق البوت
        file_path = await asyncio.to_thread(sync_download)
        
        if not os.path.exists(file_path):
            await temp_msg.edit_text("❌ فشل التحميل، الملف غير موجود.")
            return

        # إرسال الفيديو أو الصوت
        await temp_msg.delete()
        if quality == "audio":
            with open(file_path, "rb") as f:
                await context.bot.send_audio(chat_id, f, title=os.path.basename(file_path))
        else:
            with open(file_path, "rb") as f:
                await context.bot.send_video(chat_id, f, supports_streaming=True)

        # 🧹 حذف الملف فوراً بعد الإرسال
        os.remove(file_path)
        logging.info(f"تم حذف الملف: {file_path}")

    except Exception as e:
        await temp_msg.edit_text(f"❌ حدث خطأ: {str(e)[:200]}")
        logging.error(f"خطأ في التحميل: {e}")

# ========================
# 4. أوامر البوت
# ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 مرحباً! أرسل لي رابط فيديو من أي منصة (يوتيوب، انستغرام، تيك توك، تويتر، فيسبوك...)\n"
        "سأعطيك خيارات الجودة ثم أرسل لك الفيديو 🚀\n\n"
        "📌 البوت لا يخزن الملفات، يتم حذفها فور الإرسال."
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    context.user_data["url"] = url
    
    keyboard = [
        [InlineKeyboardButton("🎥 720p", callback_data="720p"),
         InlineKeyboardButton("🎥 1080p", callback_data="1080p")],
        [InlineKeyboardButton("🔥 أفضل جودة (Best)", callback_data="best"),
         InlineKeyboardButton("🎵 MP3 فقط", callback_data="audio")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "✅ تم استلام الرابط، اختر الجودة:",
        reply_markup=reply_markup
    )

async def quality_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    quality = query.data
    url = context.user_data.get("url")
    
    if not url:
        await query.edit_message_text("❌ الرابط غير موجود، أرسل الرابط مجدداً.")
        return
    
    await query.edit_message_text(f"⏳ جاري تحميل الفيديو بجودة {quality}...")
    
    # تشغيل التحميل
    await download_video(url, quality, update, context)

# ========================
# 5. تشغيل البوت
# ========================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(quality_callback))

    logging.info("🚀 البوت يعمل...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
