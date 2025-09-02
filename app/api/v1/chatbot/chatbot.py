from fastapi import APIRouter,HTTPException,status,Depends,BackgroundTasks
from app.schemas.chat import ChatRequest
from app.core.logging import logger
from app.core.langgraph.graph import agent,client
from app.core.omnidesk.omnidesk_api import omnidesk_api
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db_helper import db_helper
from app.api.v1.chatbot import crud
from app.api.v1.chatbot.helper import get_message_type
from langchain_core.messages import HumanMessage,AIMessage
import io
from app.api.v1.chatbot.labels import LABELS,SUCCESS_ID,SUPPORT_ID,SYSTEM_PROMPT,SYSTEM_PROMPT_V2
import json
from datetime import datetime

from zoneinfo import ZoneInfo

router = APIRouter()

 
@router.post("/chat")
async def chat(chat_request:ChatRequest,session:AsyncSession = Depends(db_helper.scoped_session_dependency)):
    # logger.info(f" chat view (chat_request): {chat_request}")
    
    try:
        history = await crud.get_chat_history(session=session,chat_id=chat_request.chat_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"ERROR GET CHAT HISTORY {str(e)}")
    
    
    messageType = await get_message_type(last_message=chat_request.last_message)
    
    if messageType == "image":
        image_data = await omnidesk_api.download_image(last_message=chat_request.last_message)
        conversation = ""
        for msg in history:
            local_time = msg.created_at.astimezone(ZoneInfo("Asia/Almaty"))
            conversation += f"User({local_time.strftime('%Y-%m-%d %H:%M:%S %z')}): {msg.message}\n"
            if msg.response:
                last_message_time = datetime.now()
                local_time_last_msg = last_message_time.astimezone(ZoneInfo("Asia/Almaty"))
                conversation += f"Bot: {msg.response}\n"
        conversation += f"User({local_time.strftime('%Y-%m-%d %H:%M:%S %z')}): {msg.message})(message with image): {chat_request.last_message}\nBot:"

        message = HumanMessage(content=[
            {"type": "text", "text": conversation},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
        ])
    elif messageType == "audio":
        audio_data = await omnidesk_api.download_audio(last_message=chat_request.last_message)
        
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "audio.mp3"
        
        transcription = await client.audio.transcriptions.create(
            model = "gpt-4o-transcribe",
            file=audio_file
        )
        # ADD PROMPT FOR TRUSTME rules
        conversation = ""
        for msg in history:
            local_time = msg.created_at.astimezone(ZoneInfo("Asia/Almaty"))
            conversation += f"User({local_time.strftime('%Y-%m-%d %H:%M:%S %z')}): {msg.message}\n"
            if msg.response:
                last_message_time = datetime.now()
                local_time_last_msg = last_message_time.astimezone(ZoneInfo("Asia/Almaty"))
                conversation += f"Bot: {msg.response}\n"
        conversation += f"User({local_time_last_msg.strftime('%Y-%m-%d %H:%M:%S %z')}): {chat_request.last_message}\nUser's Audio transcription: {transcription.text}\nBot:"
        
        message = HumanMessage(content=[
            {"type": "text", "text": conversation},
        ])
        
        
    else:
        conversation = ""
        for msg in history:
            local_time = msg.created_at.astimezone(ZoneInfo("Asia/Almaty"))
            conversation += f"User({local_time.strftime('%Y-%m-%d %H:%M:%S %z')}): {msg.message}\n"
            if msg.response:
                conversation += f"Bot: {msg.response}\n"
        last_message_time = datetime.now()
        local_time_last_msg = last_message_time.astimezone(ZoneInfo("Asia/Almaty"))
        conversation += f"User({local_time_last_msg.strftime('%Y-%m-%d %H:%M:%S %z')}): {chat_request.last_message}\nBot:"
        
        message = HumanMessage(content=conversation)
    
    try:
        system_message = AIMessage(
            content=SYSTEM_PROMPT_V2
        )
        result = await agent.ainvoke({"last_message": message,"system_message":system_message})
        response_invoke = result["response"]
        tokens_1 = result["tokens"]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ERROR AINVOKE {str(e)}"
        )
    
    if messageType == "audio":
        try:
            saved = await crud.save_message(session=session,user_id=int(chat_request.user_id),
                                  chat_id=chat_request.chat_id,last_message=transcription.text,response=response_invoke)
        except Exception as e:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"ERROR SAVE MESSAGE {str(e)}")
    else:
        try:
            saved = await crud.save_message(session=session,user_id=int(chat_request.user_id),
                                  chat_id=chat_request.chat_id,last_message=chat_request.last_message,response=response_invoke)
        except Exception as e:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"ERROR SAVE MESSAGE {str(e)}")
           
    try:
        code = await omnidesk_api.send_message(content=response_invoke,chat_id=chat_request.chat_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"ERROR SEND MESSAGE {str(e)}")
    
    last_ten_msg = await crud.get_chat_history(session=session,chat_id=chat_request.chat_id)
    chat = await crud.get_chat_by_id(session=session,chat_id=chat_request.chat_id)

 
    if len(last_ten_msg) ==10:
        if not chat.labels_and_group:
            prompt = f"""
            Ты — классификатор чата.

            Твоя задача:
            1. Проанализировать последние 10 сообщений чата.
            2. Определить список релевантных меток (labels).
            3. Определить группу (group) по следующим правилам:
            - Если клиент новый → вернуть "Success_ID".
            - Если клиент взаимодействует меньше 2 месяцев → вернуть "Success_ID".
            - Если клиент не новый и взаимодействует больше 2 месяцев → вернуть "Support_ID".

            Важно:
            - Ответь строго в формате **валидного JSON**.
            - Не добавляй никаких пояснений или текста вне JSON.
            - Используй только указанные ID меток и групп.

            Сообщения чата:
            {last_ten_msg}

            Список доступных меток:
            {LABELS}

            Список доступных групп:
            Success_ID = {SUCCESS_ID}
            Support_ID = {SUPPORT_ID}

            Формат ответа (пример):
            {{
                "labels": [id_label_1, id_label_2],
                "group": "96756"
            }}
            """

            response= await client.chat.completions.create(
                model="gpt-4o",
                response_format={
                    "type":"json_object"
                },
                messages=[
                    {"role": "system", "content": "Ты помощник-классификатор. Отвечай строго в JSON формате."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0
            )
            result_labels_and_group = json.loads(response.choices[0].message.content)
            tokens_2 = response.usage.total_tokens
            logger.debug(F"labels and group: {result}")
            logger.debug(f"labels: {result_labels_and_group['labels']}, group {result_labels_and_group['group']}")
            print(f"labels: {result_labels_and_group['labels']}, group {result_labels_and_group['group']}")
            
            try:
                request_set_label = await omnidesk_api.set_labels_and_group(
                    chat_id=chat_request.chat_id,
                    labels=result_labels_and_group['labels'],
                    group=result_labels_and_group['group'])
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"ERROR SETTING LABELS AND GROUP {str(e)}")
            
            
            try:
                set_true = await crud.set_labels_group(session=session,
                    chat_id = chat_request.chat_id)
            except Exception as e:
                raise HTTPException(status_code=
                                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    detail = f"ERROR SET LABELS AND GROUP {str(e)}")

    
    return {
        "response":response_invoke,
        "prompt sended":system_message,
        # "tokens_used":tokens_1+tokens_2,
        "conversation":conversation,
        "saved":saved,
        "code":code,
        # "labels_and_group":result_labels_and_group,
        # "request_set_label_code":request_set_label,
        # "set_true":set_true
    }    
  
