import json
import time
from aio_pika import IncomingMessage
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.core.logging import get_logger
from app.core.rabbitmq import rabbitmq_client, USER_CREATED_QUEUE
from app.crud import update_user_id, check_message_processed, save_processed_message
from app.session import get_async_session
from app.schemas.message import UserCreatedResponse, UserCreationStatus

logger = get_logger(__name__)

async def handle_user_created_message(message: IncomingMessage) -> None:
    """
    user-serviceからのユーザー作成完了メッセージを処理する
    """
    async with message.process():
        start_time = time.time()
        
        try:
            # メッセージ本文をデコード
            body = message.body.decode()
            data = json.loads(body)
            
            # UserCreatedResponseオブジェクトに変換
            response = UserCreatedResponse(**data)
            
            # 成功ステータスの場合のみuser_idを更新
            if response.status == UserCreationStatus.SUCCESS and response.user_id:
                logger.info(f"ユーザー作成完了メッセージを受信: user_id={response.user_id}, username={response.username}")
                
                # データベースセッションを取得
                async for session in get_async_session():
                    try:
                        # 冪等性チェック - 同じメッセージが既に処理済みかどうかを確認
                        processed_message = await check_message_processed(
                            session, 
                            response.message_id, 
                            USER_CREATED_QUEUE
                        )
                        
                        if processed_message:
                            # 既に処理済みの場合はスキップ
                            logger.info(f"メッセージは既に処理済みです: message_id={response.message_id}")
                        else:
                            # user_idを更新
                            updated_user = await update_user_id(session, response.username, response.user_id)
                            
                            # 処理結果を記録
                            result_data = {
                                "username": response.username,
                                "user_id": str(response.user_id),
                                "updated": updated_user is not None
                            }
                            
                            status = "success" if updated_user else "error"
                            await save_processed_message(
                                session, 
                                response.message_id, 
                                USER_CREATED_QUEUE, 
                                status,
                                result_data
                            )
                            
                            if updated_user:
                                logger.info(f"AuthUserのuser_idを更新しました: username={response.username}, user_id={response.user_id}")
                            else:
                                logger.error(f"AuthUserの更新に失敗: ユーザーが見つかりません: username={response.username}")
                        
                        # トランザクションをコミット
                        await session.commit()
                            
                    except Exception as e:
                        await session.rollback()
                        logger.error(f"AuthUserの更新中にエラーが発生: {str(e)}")
                        
                        # エラー情報を処理済みメッセージとして記録
                        try:
                            result_data = {
                                "username": response.username,
                                "error": str(e)
                            }
                            await save_processed_message(
                                session, 
                                response.message_id, 
                                USER_CREATED_QUEUE, 
                                "error",
                                result_data
                            )
                            await session.commit()
                        except Exception as inner_e:
                            await session.rollback()
                            logger.error(f"エラー情報の保存に失敗: {str(inner_e)}")
            else:
                if response.status != UserCreationStatus.SUCCESS:
                    logger.warning(f"ユーザー作成が成功していません: status={response.status}, username={response.username}")
                elif not response.user_id:
                    logger.warning(f"user_idが提供されていません: username={response.username}")
                
                # 処理結果を記録（エラーケース）
                async for session in get_async_session():
                    try:
                        result_data = {
                            "username": response.username,
                            "status": response.status,
                            "error_message": response.error_message
                        }
                        await save_processed_message(
                            session, 
                            response.message_id, 
                            USER_CREATED_QUEUE, 
                            "error",
                            result_data
                        )
                        await session.commit()
                    except Exception as e:
                        await session.rollback()
                        logger.error(f"エラー情報の保存に失敗: {str(e)}")
                
        except json.JSONDecodeError as e:
            logger.error(f"メッセージのJSONデコードに失敗: {str(e)}")
        except Exception as e:
            logger.error(f"ユーザー作成完了メッセージの処理中にエラーが発生: {str(e)}")
        finally:
            processing_time = (time.time() - start_time) * 1000
            logger.debug(f"メッセージ処理時間: {processing_time:.2f}ms")

async def register_message_handlers() -> None:
    """
    メッセージハンドラーを登録する
    """
    await rabbitmq_client.register_consumer(USER_CREATED_QUEUE, handle_user_created_message)
    logger.info(f"メッセージハンドラーを登録しました: queue={USER_CREATED_QUEUE}")
