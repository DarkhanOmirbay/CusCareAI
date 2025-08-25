from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import User,Chat,Message
from app.core.logging import logger
from sqlalchemy import select

async def get_or_create_user(session: AsyncSession, user_id: int, full_name: str = None):
    user = await session.get(User, user_id)
    if not user:
        user = User(user_id=user_id, full_name=full_name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user

async def get_or_create_chat(session: AsyncSession, chat_id: int, user_id: int):
    chat = await session.get(Chat, chat_id)
    if not chat:
        chat = Chat(chat_id=chat_id, user_id=user_id)
        session.add(chat)
        await session.commit()
        await session.refresh(chat)
    return chat

async def save_message(session:AsyncSession,user_id:str,chat_id:str,last_message:str,response:str):
    await get_or_create_user(session, user_id)
    await get_or_create_chat(session, chat_id, user_id)
    
    msg  = Message(
        user_id=user_id,
        chat_id = chat_id,
        message = last_message,
        response = response
    )
    
    logger.debug(f"message: {msg}")
    
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    
    return msg

async def get_chat_history(session:AsyncSession,chat_id:str,limit:int=10):
    result = await session.execute(
        select(Message).where(Message.chat_id==chat_id).order_by(Message.created_at.desc()).limit(limit=limit))
    
    messages = result.scalars().all()
    
    return list(reversed(messages))