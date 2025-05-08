import json
import time
from aio_pika import IncomingMessage
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.core.logging import get_logger
from app.core.rabbitmq import rabbitmq_client, USER_CREATE_QUEUE, USER_CREATED_QUEUE
from app.crud import create as user_create, UserCreate, check_message_processed, save_processed_message
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
                    # 冪等性チェック - 同じメッセージが既に処理済みかどうかを確認
                    processed_message = await check_message_processed(
                        session, 
                        request.message_id, 
                        USER_CREATE_QUEUE
                    )
                    
                    if processed_message:
                        # 既に処理済みの場合は、保存されている結果を返す
                        logger.info(f"メッセージは既に処理済みです: message_id={request.message_id}")
                        
                        # 保存されている結果データがあれば復元
                        if processed_message.result_data:
                            try:
                                result_data = json.loads(processed_message.result_data)
                                if result_data.get("user_id"):
                                    response.user_id = uuid.UUID(result_data["user_id"])
                                if result_data.get("status"):
                                    response.status = result_data["status"]
                            except Exception as e:
                                logger.error(f"保存された結果データの解析に失敗: {str(e)}")
                        
                        # 既に成功していた場合は成功ステータスを設定
                        if processed_message.status == "success":
                            response.status = UserCreationStatus.SUCCESS
                    else:
                        # 新規メッセージの場合は処理を実行
                        # UserCreateオブジェクトを作成
                        user_create_obj = UserCreate(
                            username=request.username
                        )
                        
                        # ユーザーを作成
                        created_user = await user_create(session, user_create_obj)
                        
                        # 作成されたユーザーのIDを取得
                        user_id = created_user.id if hasattr(created_user, 'id') else None
                        
                        # 成功レスポンスを設定
                        response.status = UserCreationStatus.SUCCESS
                        response.user_id = user_id
                        response.processing_time_ms = (time.time() - start_time) * 1000
                        
                        # 処理済みメッセージとして記録
                        result_data = {
                            "user_id": str(user_id) if user_id else None,
                            "status": response.status
                        }
                        await save_processed_message(
                            session, 
                            request.message_id, 
                            USER_CREATE_QUEUE, 
                            "success",
                            result_data
                        )
                        
                        logger.info(f"ユーザーを作成しました: username={request.username}, user_id={user_id}")
                    
                    # トランザクションをコミット
                    await session.commit()
                        
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
                    
                    # エラー情報を処理済みメッセージとして記録
                    try:
                        result_data = {
                            "error": str(e),
                            "status": response.status
                        }
                        await save_processed_message(
                            session, 
                            request.message_id, 
                            USER_CREATE_QUEUE, 
                            "error",
                            result_data
                        )
                        await session.commit()
                    except Exception as inner_e:
                        await session.rollback()
                        logger.error(f"エラー情報の保存に失敗: {str(inner_e)}")
            
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
