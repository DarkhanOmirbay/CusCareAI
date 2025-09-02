import re
import httpx
from app.models.models import Message
from datetime import datetime,timezone

async def get_message_type(last_message:str) -> str:
    """
    Классифицирует сообщение:
    - text
    - image
    - audio
    """
    
    urls = re.findall(r'https?://\S+',last_message)
    
    for url in urls:
        if "attachment/download/chat/" in url:
            if url.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")):
                return "image"
            elif url.lower().endswith((".mp3", ".mpeg", ".wav", ".ogg", ".m4a",".opus")):
                return "audio"    
            else: 
                return "text"    


