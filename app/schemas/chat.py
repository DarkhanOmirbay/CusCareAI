from pydantic import BaseModel

class ChatRequest(BaseModel):
    chat_id:str
    last_message:str
    user_id:str
    
    

# user_id -> users(user_id PK int,full_name, user_email,user_phone,user_company_id FK)
# company_id -> companies(company_id,name etc)
# user_message , answer_from_ai I should store -> (user_id FK,chat_id,user_message,answer_to_the_message)


    


