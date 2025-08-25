import httpx
from app.core.config import settings

class OmnideskAPI:
    def __init__(self):
        self.OMNIDESK_DOMAIN:str = settings.OMNIDESK_DOMAIN
        self.STAFF_ID:int = settings.STAFF_ID
        self.auth = (settings.USER_EMAIL,settings.OMNIDESK_API_KEY)
        
        
    def send_message(self,content:str,chat_id:str):
        data = {
            "message":{
                "content":content,
                "staff_id":self.STAFF_ID # сотрудник
            }
        }
        response = httpx.post(auth=self.auth,url=f"{self.OMNIDESK_DOMAIN}/cases/{chat_id}/messages.json",json=data)
        
        return response.status_code
        
        
omnidesk_api = OmnideskAPI()




            