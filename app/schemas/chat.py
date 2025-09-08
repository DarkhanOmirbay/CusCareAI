from pydantic import BaseModel

class ChatRequest(BaseModel):
    chat_id:str
    last_message:str 
    user_id:str
    
    
class WebhookRequest(BaseModel):
    case_id:str
    case_number:str
    case_description:str
    last_message:str 
    last_message_id:str
    user_id:str
    




