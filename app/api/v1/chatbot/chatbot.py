from fastapi import APIRouter,status,BackgroundTasks,Response
from app.schemas.chat import ChatRequest,WebhookRequest
from app.core.logging import logger
from app.core.langgraph.graph import agent,client
from app.core.omnidesk.omnidesk_api import omnidesk_api
from app.api.v1.chatbot.helper import get_message_type,is_working_hours
from langchain_core.messages import HumanMessage,AIMessage
import io
from app.models.redis_helper import redis_helper
from datetime import datetime, timedelta, timezone

from app.api.v1.chatbot.labels import OUTSIDE_WORKING_HOURS_RESPONSE


router = APIRouter()

ALMATY_TZ = timezone(timedelta(hours=5))

@router.post("/chat")
async def chat(chat_request:ChatRequest,bg:BackgroundTasks):
    now = datetime.now(ALMATY_TZ)
    if not is_working_hours(now):
        logger.info(f"chat_request {chat_request.chat_id} received outside working hours")
        try:
            code = await omnidesk_api.send_message(content=OUTSIDE_WORKING_HOURS_RESPONSE, chat_id=chat_request.chat_id)
            logger.info(f"message sended {code}")
        except Exception as e:
            import traceback
            logger.error(f"ERROR SEND MESSAGE {str(e)}")
            logger.error(traceback.format_exc())
            
        return Response("outside working hours",status_code=status.HTTP_200_OK)
    else:    
        logger.info(f"chat_request {chat_request.chat_id} added to Background task")
        bg.add_task(chat_process,chat_request)
        return Response("accepted",status_code=status.HTTP_200_OK)
    


@router.post("/webhook")
async def recieve_webhook(webhook_request:WebhookRequest): 
    logger.info(f"JSON STRUCTURE : {webhook_request.model_dump()}")
    return Response("accepted",status_code=status.HTTP_200_OK)


async def get_content_by_msg_type(msg_type:str,chat_request:ChatRequest):
    if msg_type == "text":
        return chat_request.last_message
    
    elif msg_type == "image":
        image_data = await omnidesk_api.download_image(last_message=chat_request.last_message)
        message = HumanMessage(content=[
                {"type": "text", "text": "Опиши прикрепленную image"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
            ]) 
        system_message = AIMessage(
                content="ТЫ ИИ АССИСТЕНТ КОТОРЫЙ ПРИНИМАЕТ ФОТОГРАФИЙ , КАРТИНКИ , СКРИНШОТЫ\n\n ТВОЯ ЗАДАЧА ДАТЬ ОПИСАНИЕ КАРТИНКИ по шаблону : на image показан ... итд"
            )
        result = await agent.ainvoke({"last_message": message,"system_message":system_message})
        content = result["response"]
        return content
        
    elif msg_type == "audio":
        audio_data = await omnidesk_api.download_audio(last_message=chat_request.last_message)
            
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "audio.mp3"
            
        transcription = await client.audio.transcriptions.create(
                model = "gpt-4o-transcribe",
                file=audio_file
            )
        
        return transcription.text                    
    
async def chat_process(chat_request:ChatRequest):
    logger.info(f"chat_process started for chat_request {chat_request.chat_id} ")
    
    messageType = await get_message_type(last_message=chat_request.last_message)
    
    logger.info(f"Message type is {messageType} for chat_request {chat_request.chat_id}")
    
    content = await get_content_by_msg_type(msg_type=messageType,chat_request=chat_request)
    
    logger.info(f"Content is {content} for chat_request {chat_request.chat_id}")

    await redis_helper.add_message_to_buffer(chat_request=chat_request,content=content)
    
    
    

    
    
    
    
    