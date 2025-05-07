import json
import time
from aio_pika import IncomingMessage
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.core.logging import get_logger
from app.core.rabbitmq import rabbitmq_client, USER_CREATED_QUEUE
from app.crud.auth_user import auth_user_crud
from app.db.session import AsyncSessionLocal
from app.schemas.message import UserCreatedResponse, UserCreationStatus

logger = get_logger(__name__)

async def handle_user_created_message(message: IncomingMessage) -> None:
    """
    user-serviceからのユーザー作成結果メッセージを処理する
    """
    async with message.process():
        start_time = time.time()
        
        try:
            # メッセージ本文をデコード
            body = message.body.decode()
            data = json.loads(body)
            
            # UserCreatedResponseオブジェクトに変換
            response = UserCreatedResponse(**data)
            
            logger.info(f"ユーザー作成結果メッセージを受信: message_id={response.message_id}, status={response.status}")
            
            # 成功した場合のみ、auth_userのuser_idを更新
            if response.status == UserCreationStatus.SUCCESS and response.user_id:
                # AsyncSessionLocalを使用して明示的にセッションを作成
                async with AsyncSessionLocal() as session:
                    try:
                        # ユーザー名でauth_userを検索
                        db_user = await auth_user_crud.get_by_username(session, response.username)
                        
                        # user_idを更新
                        db_user.user_id = response.user_id
                        await session.commit()
                        
                        logger.info(f"auth_userのuser_idを更新しました: username={response.username}, user_id={response.user_id}")
                    except Exception as e:
                        await session.rollback()
                        logger.error(f"auth_userのuser_id更新中にエラーが発生: {str(e)}")
            else:
                # エラーの場合はログに記録
                logger.warning(f"ユーザー作成に失敗: status={response.status}, error={response.error_message}")
                
        except json.JSONDecodeError as e:
            logger.error(f"メッセージのJSONデコードに失敗: {str(e)}")
        except Exception as e:
            logger.error(f"ユーザー作成結果メッセージの処理中にエラーが発生: {str(e)}")
        finally:
            processing_time = (time.time() - start_time) * 1000
            logger.debug(f"メッセージ処理時間: {processing_time:.2f}ms")

async def register_message_handlers() -> None:
    """
    メッセージハンドラーを登録する
    """
    await rabbitmq_client.register_consumer(USER_CREATED_QUEUE, handle_user_created_message)
    logger.info(f"メッセージハンドラーを登録しました: queue={USER_CREATED_QUEUE}")