from qdrant_client import AsyncQdrantClient
from app.core.config import settings
import httpx

class QdrantHelper:
    def __init__(self):
        self.qdrant_client = AsyncQdrantClient(url=settings.QDRANT_URL)
        
    async def embedder(self,query_str:str):
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
        response_dict = response.json()
        data = response_dict['data']
        embedding = data[0]['embedding']
        return embedding
            
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
        
        

qdrant_helper = QdrantHelper()

# import asyncio
# async def test():
#     result = await qdrant_helper.retrieve_context(query_str="У меня смс код не приходит")
#     print(result)
# asyncio.run(test())