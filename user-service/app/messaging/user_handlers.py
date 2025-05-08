import json
import time
from aio_pika import IncomingMessage
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.core.logging import get_logger
from app.core.rabbitmq import rabbitmq_client, USER_CREATE_QUEUE, USER_CREATED_QUEUE
from app.crud import create as user_create, UserCreate
from app.session import get_async_session
from app.schemas.message import UserCreateRequest, UserCreatedResponse, UserCreationStatus

logger = get_logger(__name__)

async def handle_user_create_message(message: IncomingMessage) -> None:
    """
    auth-serviceからのユーザー作成リクエストメッセージを処理する
    """
    async with message.process():
        start_time = time.time()
        
        try:
            # メッセージ本文をデコード
            body = message.body.decode()
            data = json.loads(body)
            
            # UserCreateRequestオブジェクトに変換
            request = UserCreateRequest(**data)
            
            logger.info(f"ユーザー作成リクエストメッセージを受信: message_id={request.message_id}, username={request.username}")
            
            # レスポンスの初期化
            response = UserCreatedResponse(
                request_id=request.message_id,
                status=UserCreationStatus.UNKNOWN_ERROR,
                username=request.username
            )
            
            # データベースセッションを取得
            async for session in get_async_session():
                try:
                    # UserCreateオブジェクトを作成
                    user_create_obj = UserCreate(
                        username=request.username
                    )
                    
                    # ユーザーを作成
                    created_user = await user_create(session, user_create_obj)
                    await session.commit()
                    
                    # 作成されたユーザーのIDを取得
                    user_id = created_user.id if hasattr(created_user, 'id') else None
                    
                    # 成功レスポンスを設定
                    response.status = UserCreationStatus.SUCCESS
                    response.user_id = user_id
                    response.processing_time_ms = (time.time() - start_time) * 1000
                    
                    logger.info(f"ユーザーを作成しました: username={request.username}, user_id={user_id}")
                    
                except Exception as e:
                    await session.rollback()
                    
                    # エラー種別に応じてステータスを設定
                    if "duplicate username" in str(e).lower():
                        response.status = UserCreationStatus.DUPLICATE_USERNAME
                    elif "duplicate email" in str(e).lower():
                        response.status = UserCreationStatus.DUPLICATE_EMAIL
                    elif "database" in str(e).lower():
                        response.status = UserCreationStatus.DATABASE_ERROR
                    elif "validation" in str(e).lower():
                        response.status = UserCreationStatus.VALIDATION_ERROR
                    else:
                        response.status = UserCreationStatus.UNKNOWN_ERROR
                    
                    response.error_message = str(e)
                    logger.error(f"ユーザー作成中にエラーが発生: {str(e)}")
            
            # 結果をauth-serviceに送信
            await rabbitmq_client.publish_message(
                USER_CREATED_QUEUE,
                response.model_dump()
            )
            
            logger.info(f"ユーザー作成結果を送信: message_id={response.message_id}, status={response.status}")
            
        except json.JSONDecodeError as e:
            logger.error(f"メッセージのJSONデコードに失敗: {str(e)}")
        except Exception as e:
            logger.error(f"ユーザー作成リクエストメッセージの処理中にエラーが発生: {str(e)}")
        finally:
            processing_time = (time.time() - start_time) * 1000
            logger.debug(f"メッセージ処理時間: {processing_time:.2f}ms")

async def register_message_handlers() -> None:
    """
    メッセージハンドラーを登録する
    """
    await rabbitmq_client.register_consumer(USER_CREATE_QUEUE, handle_user_create_message)
    logger.info(f"メッセージハンドラーを登録しました: queue={USER_CREATE_QUEUE}")
