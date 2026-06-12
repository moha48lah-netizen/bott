import os
import logging
import asyncio

logger = logging.getLogger(__name__)

class AudioSeparator:
    def __init__(self):
        self.temp_dir = "temp_audio"
        os.makedirs(self.temp_dir, exist_ok=True)
    
    async def separate(self, audio_path):
        try:
            output_dir = os.path.join(self.temp_dir, f"sep_{os.urandom(4).hex()}")
            os.makedirs(output_dir, exist_ok=True)
            cmd = ['spleeter', 'separate', '-p', 'spleeter:2stems', '-o', output_dir, audio_path]
            process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                return None, "❌ فشل فصل الصوت"
            result = {}
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    if 'vocals' in file:
                        result['vocals'] = os.path.join(root, file)
                    elif 'accompaniment' in file:
                        result['music'] = os.path.join(root, file)
            return result, None
        except Exception as e:
            logger.error(f"Separator error: {e}")
            return None, f"❌ خطأ: {str(e)}"
