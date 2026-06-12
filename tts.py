import os
import logging
import asyncio
from gtts import gTTS

logger = logging.getLogger(__name__)

VOICES = {
    'ar_female': {'lang': 'ar', 'tld': 'com'},
    'ar_male': {'lang': 'ar', 'tld': 'com'},
    'en_female': {'lang': 'en', 'tld': 'co.uk'},
    'en_male': {'lang': 'en', 'tld': 'com'},
    'en_us_female': {'lang': 'en', 'tld': 'us'},
    'en_us_male': {'lang': 'en', 'tld': 'us'},
}

class TextToSpeech:
    def __init__(self):
        self.temp_dir = "temp_tts"
        os.makedirs(self.temp_dir, exist_ok=True)
    
    async def convert(self, text, voice='ar_female', speed='normal'):
        try:
            if len(text) > 500:
                return None, "❌ النص طويل جداً (الحد الأقصى 500 حرف)"
            voice_config = VOICES.get(voice, VOICES['ar_female'])
            slow = speed == 'slow'
            filename = f"tts_{os.urandom(4).hex()}.mp3"
            output_path = os.path.join(self.temp_dir, filename)
            tts = gTTS(text=text, lang=voice_config['lang'], tld=voice_config['tld'], slow=slow)
            await asyncio.get_event_loop().run_in_executor(None, lambda: tts.save(output_path))
            return output_path if os.path.exists(output_path) else None, None
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return None, f"❌ خطأ: {str(e)}"
