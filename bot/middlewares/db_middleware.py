# bot/middlewares/db_middleware.py
from aiogram import BaseMiddleware
from bot.database.engine import async_session
from bot.database.queries import get_or_create_user

class DatabaseMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        async with async_session() as session:
            if user:
                db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
                if db_user and db_user.is_banned:
                    from aiogram.types import Message, CallbackQuery
                    if isinstance(event, Message):
                        await event.answer("🛑 <b>Ви заблоковані в цій системі.</b>\n\nВи більше не можете користуватися цим ботом.")
                    elif isinstance(event, CallbackQuery):
                        await event.answer("🛑 Ви заблоковані в системі.", show_alert=True)
                    return
            data["session"] = session
            return await handler(event, data)
