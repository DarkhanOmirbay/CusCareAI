import redis.asyncio as redis
from app.core.config import settings
from app.schemas.chat import ChatRequest
from typing import Optional, List, Dict
import asyncio
from app.core.logging import logger
from datetime import datetime, timedelta
import json
from app.models.db_helper import db_helper
from app.api.v1.chatbot import crud
from zoneinfo import ZoneInfo
from langchain_core.messages import HumanMessage, AIMessage
from app.api.v1.chatbot.labels import (
    SYSTEM_PROMPT_V2,
    LABELS,
    SUCCESS_ID,
    SUPPORT_ID,
    SYSTEM_PROMPT_V3,
    SYSTEM_PROMPT_V4,
)
from app.core.langgraph.graph import agent, client
from app.core.omnidesk.omnidesk_api import omnidesk_api
from app.models.qdrant_helper import qdrant_helper


class RedisHelper:
    """Redis Helper class"""

    def __init__(self, redis_url: str, buffer_timeout: int = 90):
        self.redis_url = redis_url
        self.buffer_timeout = buffer_timeout
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.background_task: Optional[asyncio.Task] = None
        self.shutdown = False

        # redis key patterns
        self.BUFFER_KEY = "buffer_id:{chat_id}"
        self.TIMER_KEY = "timer:{chat_id}"
        self.PROCESSING_KEY = "lock:{chat_id}"

    async def start(self):
        """Start function"""
        try:
            await self.redis_client.ping()
            logger.info("redis connected successfully")

            if self.background_task is None or self.background_task.done():
                self.background_task = asyncio.create_task(self.background_processor())
                logger.info("Background processor started")

        except Exception as e:
            logger.error(f"Redis connection failed : {str(e)}")
            raise

    async def stop(self):
        """Stop function"""
        self.shutdown = True

        if self.background_task and not self.background_task.done():
            self.background_task.cancel()
        await self.redis_client.close()
        logger.info("Redis buffer manager stopped")

    async def background_processor(self) -> int:
        """Background processor function"""
        while not self.shutdown:
            try:
                processed_count = await self.process_expired_buffers()
                if processed_count > 0:
                    logger.info(f"Processed {processed_count} expired chat buffers")
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background processor error: {str(e)}")
                await asyncio.sleep(30)

    async def process_expired_buffers(self) -> bool:
        """Process expired buffers function"""
        processed_count = 0
        now = datetime.now()

        try:
            async for timer_key in self.redis_client.scan_iter(match="timer:*"):
                try:
                    expire_time_str = await self.redis_client.get(name=timer_key)
                    if not expire_time_str:
                        continue

                    expire_time = datetime.fromisoformat(expire_time_str)

                    if (
                        expire_time <= now
                    ):  # 1 case : 10h:48m:30s < 10h:48m:15s => false // 2 case : 10h:48m:30s <= 10h:48m:31s
                        chat_id = timer_key.split(":", 1)[1]

                        if await self.process_chat_buffer(chat_id=chat_id):
                            processed_count += 1

                except Exception as e:
                    logger.error(f"Error processing timer {timer_key}: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"Error scanning expired buffers: {str(e)}")
        return processed_count

    async def process_chat_buffer(self, chat_id: str):
        """process_chat_buffer function"""
        buffer_key = self.BUFFER_KEY.format(chat_id=chat_id)
        timer_key = self.TIMER_KEY.format(chat_id=chat_id)
        processing_key = self.PROCESSING_KEY.format(chat_id=chat_id)

        try:
            lock_aquired = await self.redis_client.set(
                name=processing_key,
                value="processing",
                nx=True,
                ex=300,  # I should think about time !
            )

            if not lock_aquired:
                logger.debug(f"Chat {chat_id} already being processed")
                return False
            messages_json = await self.redis_client.lrange(
                name=buffer_key, start=0, end=-1
            )

            if not messages_json:
                await self.cleanup_redis_keys(chat_id=chat_id)
                return False

            messages = []

            for msg_json in reversed(messages_json):
                try:
                    messages.append(json.loads(msg_json))

                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing message: {str(e)}")

            if not messages:
                await self.cleanup_redis_keys(chat_id=chat_id)
                return False

            logger.info(
                f"Processing {len(messages)} buffered messages for chat {chat_id}"
            )

            success = await self.concatenate_process_and_save(
                messages=messages
            )  # MY BACKEND LOGIC SHOULD BE HERE PROCESSING Q&A

            if success:
                await self.cleanup_redis_keys(chat_id=chat_id)
                logger.info(
                    f"Successfully processed and saved buffer for chat {chat_id}"
                )
                return True
            else:
                logger.error(f"Failed to process buffer for chat {chat_id}")
                return False

        except Exception as e:
            logger.error(f"Error processing chat buffer {chat_id}: {str(e)}")
            return False
        finally:
            await self.redis_client.delete(processing_key)

    async def cleanup_redis_keys(self, chat_id: str):
        """cleanup_redis_key function"""
        buffer_key = self.BUFFER_KEY.format(chat_id=chat_id)
        timer_key = self.TIMER_KEY.format(chat_id=chat_id)
        processing_key = self.PROCESSING_KEY.format(chat_id=chat_id)

        pipe = self.redis_client.pipeline()
        pipe.delete(buffer_key, timer_key, processing_key)
        await pipe.execute()

        logger.debug(f"Cleaned up Redis keys for chat {chat_id}")

    async def concatenate_process_and_save(self, messages: List[Dict]) -> bool:
        if not messages:
            return False

        chat_id = messages[0]["chat_id"]
        user_id = messages[0]["user_id"]

        concatenated_messages = " ".join([msg["message"] for msg in messages])
        try:
            retrieved_context, point_ids = await qdrant_helper.retrieve_context(
                concatenated_messages
            )

            async with db_helper.session_factory() as session:
                try:
                    history = await crud.get_chat_history( ## first query to db
                        session=session, chat_id=chat_id
                    )
                except Exception as e:
                    logger.error(f"Error getting chat history: {str(e)}")
                    history = []

                history_lines = []
                for msg in history[-10:]:
                    local_time = msg.created_at.astimezone(ZoneInfo("Asia/Almaty"))
                    history_lines.append(
                        f"User({local_time.strftime('%Y-%m-%d %H:%M:%S %z')}): {msg.message}"
                    )
                    if msg.response:
                        history_lines.append(f"Bot: {msg.response}")

                formatted_history = "\n".join(history_lines)

                current_time = datetime.now().astimezone(ZoneInfo("Asia/Almaty"))

                greeting_words = [
                    "привет",
                    "здравствуйте",
                    "здравствуй",
                    "доброе утро",
                    "добрый день",
                    "добрый вечер",
                    "хай",
                    "hello",
                    "hi","сәлем","сәлеметсізбе","салеметсизбе","кайырлы кун","қайырлы күн"
                ]
                recent_threshold = current_time - timedelta(hours=1)
                found_recent_greeting = False
                for msg in history[-10:]:
                    try:
                        msg_time = msg.created_at.astimezone(ZoneInfo("Asia/Almaty"))
                    except Exception:
                        msg_time = current_time
                    if msg_time >= recent_threshold:
                        text = (msg.message or "").lower()
                        response_text = (msg.response or "").lower()
                        if any(g in text for g in greeting_words) or any(
                            g in response_text for g in greeting_words
                        ):
                            found_recent_greeting = True
                            break

                prompt = f"""
                    --- Chat History (last 10 messages) ---
                    {formatted_history}

                    --- Retrieved Context (top 5 results) ---
                    {retrieved_context}

                    --- User Query (current message) ---
                    User({current_time.strftime('%Y-%m-%d %H:%M:%S %z')}): {concatenated_messages}

                    """
                llm_message = HumanMessage(content=prompt)
                try:
                    system_message = AIMessage(content=SYSTEM_PROMPT_V3)
                    result = await agent.ainvoke(
                        {"last_message": llm_message, "system_message": system_message}
                    )
                    response_invoke = result["response"]
                    tokens_used = result["tokens"]

                    logger.info(
                        f"LLM responded for chat {chat_id}, tokens used: {tokens_used}"
                    )
                except Exception as e:
                    logger.error(f"LLM processing failed: {str(e)}")
                    return False

                try:
                    if found_recent_greeting:
                        system_instr = (
                            "Ты текстовый фильтр. Удали приветствия в начале текста "
                            "(например 'Здравствуйте', 'Добрый день', 'Привет' и т.п.). "
                            "Не добавляй ничего взамен. Не объясняй свои действия. "
                            "Верни только очищенный текст."
                            "Не используйте звёздочки в любом виде: никаких **жирных**, *курсива* и обрамления текста звёздочками. Для списков применяйте нумерацию «1., 2.» или тире «-» без звёздочек."
                        )
                    else:
                        system_instr = (
                            "Ты текстовый фильтр. Если в тексте нет приветствия, добавь одно короткое уместное "
                            "приветствие в начале (например 'Здравствуйте!'), затем оставь текст без изменений. "
                            "Не объясняй свои действия. Верни только финальный текст."
                            "Не используйте звёздочки в любом виде: никаких **жирных**, *курсива* и обрамления текста звёздочками. Для списков применяйте нумерацию «1., 2.» или тире «-» без звёздочек."
                        )

                    cleaned_response = await client.chat.completions.create(
                        model="gpt-4o",
                        response_format={"type": "text"},
                        messages=[
                            {"role": "system", "content": system_instr},
                            {"role": "user", "content": response_invoke},
                        ],
                        temperature=0,
                    )
                    response_invoke = cleaned_response.choices[0].message.content
                    logger.debug(f"Cleaned response: {response_invoke}")
                except Exception as e:
                    logger.error(f"Error cleaning response: {str(e)}")

                try:
                    saved = await crud.save_message( ## second query to db
                        session=session,
                        user_id=int(user_id),
                        chat_id=chat_id,
                        last_message=concatenated_messages,
                        response=response_invoke,
                        retrieved=point_ids,
                    )
                except Exception as e:
                    logger.error(f"ERROR SAVE MESSAGE {str(e)}")
                

                try:
                    code = await omnidesk_api.send_message(
                        content=response_invoke, chat_id=chat_id
                    )
                    logger.info(f"message sended {code}")
                except Exception as e:
                    import traceback
                    logger.error(f"ERROR SEND MESSAGE {str(e)}")
                    logger.error(traceback.format_exc())

                try:
                    prompt_human_help = f"""
                            --- История чата (последние 10 сообщений) ---
                            {formatted_history}

                            --- Запрос клиента (текущее сообщение) ---
                            Пользователь({current_time.strftime('%Y-%m-%d %H:%M:%S %z')}): {concatenated_messages}

                            Ответ на текущее сообщение от ИИ, используя RAG: {response_invoke}

                            --- Классификация запроса: ---
                            Проанализируй запрос. Верни `True`, если нужен реальный человек для ответа, и `False`, если ИИ может ответить самостоятельно, используя доступные данные или RAG.

                            Важно:
                            1. Если вопрос связан с тарифами, пакетами или стоимостью услуг — сразу возвращай `response_required: true`, даже если есть данные в RAG.
                            2. Если запрос общий и ИИ может ответить сам — возвращай `response_required: false`.
                            3. Ответ должен быть строго в формате JSON, например:

                            Формат ответа (пример):
                            {{
                            "response_required": true
                            }}
                        """
                    response_human_help = await client.chat.completions.create(
                        model="gpt-4o",
                        response_format={"type": "json_object"},
                        messages=[{"role": "user", "content": prompt_human_help}],
                        temperature=0,
                    )
                    need_human_help = json.loads(
                        response_human_help.choices[0].message.content
                    )
                    logger.debug(f"response from llm human help : {need_human_help}")
                except Exception as e:
                    logger.error(f"Error llm call for human_help : {str(e)}")

                if need_human_help and need_human_help.get("response_required"):
                    try:
                        result = await omnidesk_api.call_human(
                            chat_id=chat_id, user_id=user_id, message="ВЫЗОВ МЕНЕДЖЕРА"
                        )
                        logger.debug(f"Result from call_human() : {result}")
                    except Exception as e:
                        logger.error(f"Error call human : {str(e)}")

                last_ten_msg = await crud.get_chat_history(session=session, chat_id=chat_id) ## 3
                chat = await crud.get_chat_by_id(session=session, chat_id=chat_id) ## 4

                if len(last_ten_msg) == 10:
                    if not chat.labels_and_group:
                        messages_for_label = ""
                        labels: list[str] = []

                        for m in last_ten_msg:
                            messages_for_label += (
                                f"User message:{m.message}\n Bot response:{m.response}\n"
                            )
                            retrieved_labels = await qdrant_helper.retrieve_labels(
                                query_str=m.message
                            )
                            labels.extend(retrieved_labels)

                        labels_str = ", ".join(labels)
                        logger.debug(f"RETRIEVED LABELS {labels_str}")

                        prompt = f"""
                        Ты — классификатор чата.

                        Твоя задача:
                        1. Проанализировать последние 10 сообщений чата.
                        2. Определить список релевантных меток (labels) анализируя Сообщения чата и Retrieved labels со списком доступных меток.
                        3. Определить группу (group) по следующим правилам:
                        - Если клиент новый → вернуть "Success_ID".
                        - Если клиент взаимодействует меньше 2 месяцев → вернуть "Success_ID".
                        - Если клиент не новый и взаимодействует больше 2 месяцев → вернуть "Support_ID".

                        Важно:
                        - Ответь строго в формате **валидного JSON**.
                        - Не добавляй никаких пояснений или текста вне JSON.
                        - Используй только указанные ID меток и групп.

                        Сообщения чата:
                        {messages_for_label}
                        
                        Retrieved labels using knowledge base:
                        {labels_str}

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

                        response = await client.chat.completions.create(
                            model="gpt-4o",
                            response_format={"type": "json_object"},
                            messages=[
                                {
                                    "role": "system",
                                    "content": "Ты помощник-классификатор. Отвечай строго в JSON формате.",
                                },
                                {"role": "user", "content": prompt},
                            ],
                            temperature=0,
                        )
                        result_labels_and_group = json.loads(
                            response.choices[0].message.content
                        )
                        tokens_2 = response.usage.total_tokens
                        logger.debug(f"labels and group: {result}")
                        logger.debug(
                            f"labels: {result_labels_and_group['labels']}, group {result_labels_and_group['group']}"
                        )
                        print(
                            f"labels: {result_labels_and_group['labels']}, group {result_labels_and_group['group']}"
                        )

                        try:
                            request_set_label = await omnidesk_api.set_labels_and_group(
                                chat_id=chat_id,
                                labels=result_labels_and_group["labels"],
                                group=result_labels_and_group["group"],
                            )
                        except Exception as e:
                            logger.error(f"ERROR SETTING LABELS AND GROUP {str(e)}")

                        try:
                            set_true = await crud.set_labels_group( ## 5
                                session=session, chat_id=chat_id
                            )
                        except Exception as e:
                            logger.error(f"ERROR SET LABELS AND GROUP {str(e)}")
                logger.debug(
                    {
                        "response": response_invoke,
                        "prompt sended": system_message,
                        # "tokens_used":tokens_1+tokens_2,
                        "conversation": prompt,
                        "saved": saved.chat_id,
                        # "code":code,
                        # "labels_and_group":result_labels_and_group,
                        # "request_set_label_code":request_set_label,
                        # "set_true":set_true
                    }
                )

                return True

        except Exception as e:
            logger.error(f"Error concatenate and save: {str(e)}")
            return False

    async def add_message_to_buffer(self, chat_request: ChatRequest, content: str):
        try:
            buffer_key = self.BUFFER_KEY.format(chat_id=chat_request.chat_id)
            timer_key = self.TIMER_KEY.format(chat_id=chat_request.chat_id)

            message_data = {
                "chat_id": chat_request.chat_id,
                "user_id": chat_request.user_id,
                "message": content,
            }

            pipe = self.redis_client.pipeline()
            pipe.lpush(buffer_key, json.dumps(message_data))

            # set timer
            expire_at = datetime.now() + timedelta(seconds=self.buffer_timeout)
            pipe.set(
                timer_key, expire_at.isoformat()
            )  # now for example 10:47:00 + 00:01:30 = 10h:48m:30s   1:30m

            # Redis TTL - Time to live
            pipe.expire(
                buffer_key, self.buffer_timeout + 30
            )  # !! think about it // 00:01:30 + 00:01:00 = 00h:02m:30s  2:30m
            pipe.expire(
                timer_key, self.buffer_timeout + 30
            )  # !! // 00:01:30 + 00:00:30 = 00h:02m:00s 2:00m

            results = await pipe.execute()
            buffer_size = results[0]

            logger.info(
                f"Added message to Redis buffer for chat {chat_request.chat_id}. "
                f"Buffer size: {buffer_size}, expires at: {expire_at.strftime('%H:%M:%S')}"
            )

        except Exception as e:
            logger.error(
                f"Error adding message to Redis buffer: {str(e)}", exc_info=True
            )
            # Could fallback to immediate processing if Redis fails
            raise


redis_helper = RedisHelper(
    redis_url=settings.REDIS_URL, buffer_timeout=settings.BUFFER_TIMEOUT
)
