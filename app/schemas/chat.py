from pydantic import BaseModel

class ChatRequest(BaseModel):
    chat_id:str
    last_message:str 
    user_id:str
    
    




