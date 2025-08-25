from fastapi import APIRouter,HTTPException,status,Depends
from app.schemas.chat import ChatRequest
from app.core.logging import logger
from app.core.langgraph.graph import agent
from app.core.omnidesk.omnidesk_api import omnidesk_api
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db_helper import db_helper
from app.api.v1.chatbot import crud

router = APIRouter()

 
@router.post("/chat")
async def chat(chat_request:ChatRequest,session:AsyncSession = Depends(db_helper.scoped_session_dependency)):
    logger.info(f" chat view (chat_request): {chat_request}")
    
    try:
        history = await crud.get_chat_history(session=session,chat_id=chat_request.chat_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"ERROR GET CHAT HISTORY {str(e)}")
    
    conversation = ""
    for msg in history:
        conversation += f"User: {msg.message}\n"
        if msg.response:
            conversation += f"Bot: {msg.response}\n"
    conversation += f"User: {chat_request.last_message}\nBot:"
    
    try:
        result = await agent.ainvoke({"last_message":conversation})
        response = result["response"]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"ERROR AINVOKE {str(e)}")
    
    try:
        saved = await crud.save_message(session=session,user_id=int(chat_request.user_id),
                                  chat_id=chat_request.chat_id,last_message=chat_request.last_message,response=response)
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"ERROR SAVE MESSAGE {str(e)}")
    
    try:
        code = omnidesk_api.send_message(content=response,chat_id=chat_request.chat_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"ERROR SEND MESSAGE {str(e)}")
    
    return {"answer":result["response"],
            "message":saved}
   
     
