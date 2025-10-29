import httpx
from app.core.config import settings
import re
import base64
from typing import List


class OmnideskAPI:
    def __init__(self):
        self.OMNIDESK_DOMAIN: str = settings.OMNIDESK_DOMAIN
        self.STAFF_ID: int = settings.STAFF_ID
        self.auth = (settings.USER_EMAIL, settings.OMNIDESK_API_KEY)

    async def send_message(self, content: str, chat_id: str):
        data = {"message": {"content": content, "staff_id": self.STAFF_ID}}  # сотрудник
        async with httpx.AsyncClient() as client:
            response = await client.post(
                auth=self.auth,
                url=f"{self.OMNIDESK_DOMAIN}/cases/{chat_id}/messages.json",
                json=data,
            )
        # response = httpx.post(auth=self.auth,url=f"{self.OMNIDESK_DOMAIN}/cases/{chat_id}/messages.json",json=data)

        return response.status_code

    async def download_image(self, last_message: str):
        urls = re.findall(r"https?://\S+", last_message)
        for url in urls:
            async with httpx.AsyncClient() as client:
                result = await client.get(auth=self.auth, url=url)
            # result = httpx.get(auth=self.auth,url=url)
        image_data = base64.b64encode(result.content).decode(encoding="utf-8")
        return image_data

    async def download_audio(self, last_message: str):
        urls = re.findall(r"https?://\S+", last_message)
        for url in urls:
            async with httpx.AsyncClient() as client:
                result = await client.get(auth=self.auth, url=url)
            # result = httpx.get(auth=self.auth,url=url)
        # audio_data = base64.b64encode(result.content).decode(encoding="utf-8")
        # return audio_data
        return result.content

    async def set_labels_and_group(self, chat_id: str, labels: List[int], group: str):
        data = {"case": {"group_id": group, "add_labels": labels}}

        async with httpx.AsyncClient() as client:
            result = await client.put(
                auth=self.auth,
                url=f"{self.OMNIDESK_DOMAIN}/cases/{chat_id}.json",
                json=data,
            )
        return result.status_code

    async def call_human(self, chat_id: str, user_id: int, message: str = "ВЫЗОВ МЕНЕДЖЕРА"):
        data = {"message": {"content": message, "user_id": user_id}}
        async with httpx.AsyncClient() as client:
            result = await client.post(
                auth=self.auth,
                url=f"{self.OMNIDESK_DOMAIN}/cases/{chat_id}/messages.json",
                json=data,
            )
            return result.status_code


omnidesk_api = OmnideskAPI()
