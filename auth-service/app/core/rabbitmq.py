import asyncio
import json
import time
from aio_pika import connect_robust, Message, ExchangeType, DeliveryMode
from typing import Any, Callable, Dict, Optional
import uuid

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# キューの定義
USER_CREATE_QUEUE = "user.create"
USER_CREATED_QUEUE = "user.created"

class RabbitMQClient:
    """RabbitMQ接続クライアント"""
    
    def __init__(self):
        self.connection = None
        self.channel = None
        self.exchange = None
        self._consumers = {}
        self._consume_task = None
        self._connected = False
    
    async def connect(self) -> None:
        """RabbitMQに接続する"""
        if self._connected:
            return
        
        rabbitmq_url = f"amqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASSWORD}@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}/"
        
        try:
            # 接続の確立（リトライ機能付き）
            for attempt in range(5):
                try:
                    logger.info(f"RabbitMQへの接続を試行: 試行回数 {attempt + 1}/5")
                    self.connection = await connect_robust(rabbitmq_url)
                    break
                except Exception as e:
                    logger.error(f"RabbitMQ接続エラー（試行 {attempt + 1}/5）: {str(e)}")
                    if attempt < 4:  # 最後の試行でなければ
                        await asyncio.sleep(2 ** attempt)  # 指数バックオフ
                    else:
                        raise
            
            # チャネルとエクスチェンジの設定
            self.channel = await self.connection.channel()
            self.exchange = await self.channel.declare_exchange(
                "user_exchange", ExchangeType.DIRECT, durable=True
            )
            
            # キューの宣言と設定
            user_create_queue = await self.channel.declare_queue(
                USER_CREATE_QUEUE, durable=True
            )
            await user_create_queue.bind(self.exchange, USER_CREATE_QUEUE)
            
            user_created_queue = await self.channel.declare_queue(
                USER_CREATED_QUEUE, durable=True
            )
            await user_created_queue.bind(self.exchange, USER_CREATED_QUEUE)
            
            # デッドレターキュー（処理に失敗したメッセージを格納するキュー）の設定
            dead_letter_exchange = await self.channel.declare_exchange(
                "dead_letter_exchange", ExchangeType.DIRECT, durable=True
            )
            
            dead_letter_queue = await self.channel.declare_queue(
                "dead_letter_queue", durable=True
            )
            await dead_letter_queue.bind(dead_letter_exchange, "dead_letter")
            
            self._connected = True
            logger.info("RabbitMQに正常に接続しました")
        except Exception as e:
            logger.error(f"RabbitMQへの接続に失敗しました: {str(e)}")
            if self.connection:
                await self.connection.close()
            self.connection = None
            self.channel = None
            self.exchange = None
            self._connected = False
            raise
    
    async def publish_message(self, routing_key: str, message_data: Dict[str, Any]) -> bool:
        """メッセージをパブリッシュする"""
        if not self._connected:
            await self.connect()
        
        try:
            # メッセージをJSON形式にシリアライズ
            message_body = json.dumps(message_data, default=str).encode()
            
            # メッセージを作成（永続化設定）
            message = Message(
                body=message_body,
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json",
                message_id=str(uuid.uuid4())
            )
            
            # メッセージをパブリッシュ
            await self.exchange.publish(message, routing_key=routing_key)
            logger.info(f"メッセージをパブリッシュしました: routing_key={routing_key}")
            return True
        except Exception as e:
            logger.error(f"メッセージのパブリッシュに失敗しました: {str(e)}")
            return False
    
    async def register_consumer(self, queue_name: str, callback: Callable) -> None:
        """メッセージコンシューマーを登録する"""
        if not self._connected:
            await self.connect()
        
        self._consumers[queue_name] = callback
        logger.info(f"コンシューマーを登録しました: queue={queue_name}")
    
    async def start_consuming(self) -> None:
        """全てのコンシューマーを起動する"""
        if not self._connected:
            await self.connect()
        
        if self._consume_task is not None and not self._consume_task.done():
            return  # すでに実行中の場合は何もしない
        
        async def _consume():
            try:
                for queue_name, callback in self._consumers.items():
                    queue = await self.channel.declare_queue(queue_name, durable=True)
                    await queue.consume(callback)
                    logger.info(f"キュー {queue_name} の消費を開始しました")
                # 無期限に実行し続ける
                while True:
                    await asyncio.sleep(3600)  # 1時間ごとにログ出力
                    logger.debug("RabbitMQコンシューマー実行中")
            except asyncio.CancelledError:
                logger.info("RabbitMQコンシューマーがキャンセルされました")
                raise
            except Exception as e:
                logger.error(f"RabbitMQコンシューマーでエラーが発生しました: {str(e)}")
                raise
        
        self._consume_task = asyncio.create_task(_consume())
        logger.info("RabbitMQコンシューマーを起動しました")
    
    async def stop_consuming(self) -> None:
        """コンシューマーを停止する"""
        if self._consume_task is not None and not self._consume_task.done():
            self._consume_task.cancel()
            try:
                await self._consume_task
            except asyncio.CancelledError:
                pass
            self._consume_task = None
            logger.info("RabbitMQコンシューマーを停止しました")
    
    async def close(self) -> None:
        """RabbitMQ接続を閉じる"""
        await self.stop_consuming()
        
        if self.connection:
            await self.connection.close()
            self.connection = None
            self.channel = None
            self.exchange = None
            self._connected = False
            logger.info("RabbitMQ接続を閉じました")

# グローバルインスタンス
rabbitmq_client = RabbitMQClient()