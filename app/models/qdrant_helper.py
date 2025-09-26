from qdrant_client import AsyncQdrantClient
from openai import AsyncOpenAI
from app.core.config import settings
import httpx
from app.core.logging import logger

class QdrantHelper:
    def __init__(self):
        self.qdrant_client = AsyncQdrantClient(url=settings.QDRANT_URL)
        
    async def embedder(self,query_str:str):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url=settings.EMBEDDING_URL,
                    headers={
                        "Content-Type":"application/json",
                        "Authorization":f"Bearer {settings.EMBEDDING_TOKEN}"
                    },
                    json={
                        "model":"text-1024",
                        "input":query_str
                    }
                )
                if response.status_code != 200:
                    raise ValueError("Jina3 embedding API returned {response.status_code}")
            response_dict = response.json()
            data = response_dict['data']
            embedding = data[0]['embedding']
            return embedding
        except Exception as e:
            logger.error(f"Jina3 embedding failed, using OpenAI: {e}")
            try:
                client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                response = await client.embeddings.create(
                    input=query_str,
                    model="text-embedding-3-small",
                    dimensions=1024
                )
                embedding = response.data[0].embedding
                return embedding
            except Exception as openai_error:
                logger.error(f"OpenAI embedding failed too: {openai_error}")
                raise RuntimeError("Both embedding providers failed")
            
            
    async def retrieve_context(self,query_str:str) -> str:
        query = await self.embedder(query_str=query_str)
        search_resullt = await self.qdrant_client.query_points(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            query=query,
            with_payload=True,
            limit=5
        )
        relevant_context = "".join([
            f"---\nCase_id: {point.id}\nMessages: {point.payload.get('content','')}\n\n" for point in search_resullt.points if point.payload is not None
        ])
        return relevant_context
    async def retrieve_labels(self,query_str:str) ->list[str]:
        labels:list[str] = []
        query = await self.embedder(query_str=query_str)
        
        search_result = await self.qdrant_client.query_points(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            query=query,
            with_payload=True,
            limit=5
        )
        
        for point in search_result.points:
            labels.append(point.payload.get('label_title',''))
    
        return labels
        

qdrant_helper = QdrantHelper()