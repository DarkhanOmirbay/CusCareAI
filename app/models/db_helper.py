from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    async_scoped_session,
    AsyncSession
)
from asyncio import current_task
from app.core.config import settings
from sqlalchemy.orm import declarative_base

class DatabaseHelper:
    def __init__(self,url:str,echo:bool=False):
        self.engine = create_async_engine(
            url = url,
            echo = echo
        )
        self.session_factory = async_sessionmaker(
            bind = self.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        self.base = declarative_base()
    
    def get_scoped_session(self):
        session = async_scoped_session(
            session_factory=self.session_factory,
            scopefunc=current_task,
        )
        return session
    
    async def scoped_session_dependency(self)->AsyncSession:
        session = self.get_scoped_session()
        yield session
        await session.close()
        


db_helper = DatabaseHelper(url=settings.DB_URL,echo=settings.DB_ECHO)

Base = db_helper.base
