import uuid
from sqlalchemy import Column,String,ForeignKey,Text,DateTime
from sqlalchemy.dialects.postgresql import BIGINT,INTEGER
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.db_helper import Base

class User(Base):
    __tablename__ = "users"
    
    user_id = Column(BIGINT,primary_key=True)
    full_name = Column(String(255),nullable=True)
    email = Column(String(255),unique=True,nullable=True)
    phone = Column(String(50),nullable=True)
    
    chats = relationship("Chat",back_populates="user")

class Chat(Base):
    __tablename__ = "chats"
    
    chat_id = Column(String,primary_key=True)
    user_id = Column(BIGINT,ForeignKey("users.user_id",ondelete="CASCADE"))
    created_at = Column(DateTime(timezone=True),server_default=func.now())
    
    user = relationship("User",back_populates="chats")
    messages = relationship("Message",back_populates="chat")
    
class Message(Base):
    __tablename__ = "messages"
    
    message_id = Column(INTEGER,primary_key=True,autoincrement=True)
    chat_id = Column(String,ForeignKey("chats.chat_id",ondelete="CASCADE"))
    user_id = Column(BIGINT,ForeignKey("users.user_id",ondelete="CASCADE"))
    message = Column(Text,nullable=True)
    response = Column(Text,nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chat = relationship("Chat",back_populates="messages")
    