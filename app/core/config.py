from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    LOG_LEVEL: str = "ERROR"
    LOG_FILENAME: str = ""
    OPENAI_API_KEY: str = ""
    OMNIDESK_DOMAIN: str = ""
    STAFF_ID: int | None = None
    USER_EMAIL: str = ""
    OMNIDESK_API_KEY: str = ""
    DB_URL: str
    DB_ECHO: bool = False 
    POSTGRES_USER:str 
    POSTGRES_PASSWORD:str
    POSTGRES_DB:str
    # redis
    REDIS_PASSWORD:str
    REDIS_USER:str
    REDIS_USER_PASSWORD:str
    REDIS_URL:str
    BUFFER_TIMEOUT:int
    
    # Qdrant
    QDRANT_URL:str
    QDRANT_COLLECTION_NAME:str
    EMBEDDING_URL:str
    EMBEDDING_TOKEN:str

    class Config:
        env_file = ".env"

settings = Settings()


    