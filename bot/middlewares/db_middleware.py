# bot/middlewares/db_middleware.py
from aiogram import BaseMiddleware
from bot.database.engine import async_session
from bot.database.queries import get_or_create_user

class DatabaseMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        async with async_session() as session:
            if user:
                await get_or_create_user(session, user.id, user.username, user.full_name)
            data["session"] = session
            return await handler(event, data)
