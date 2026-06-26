# bot/handlers/admin/main_menu.py
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import User
from bot.database.queries import count_bookings_by_status
from bot.keyboards.admin.main_kb import get_admin_main_kb

router = Router()

async def is_admin(user_id: int, session: AsyncSession) -> bool:
    """Helper to verify if a telegram user is an admin."""
    if user_id in settings.ADMIN_IDS:
        return True
    user = await session.get(User, user_id)
    return user is not None and user.is_admin

@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession, state: FSMContext):
    """Admin control panel welcome screen."""
    if not await is_admin(message.from_user.id, session):
        return
        
    await state.clear() # Clear state when opening admin panel
    
    # Fetch counts for badges
    pending_bookings = await count_bookings_by_status(session, "awaiting_payment")
    pending_payments = await count_bookings_by_status(session, "payment_pending_review")
    
    await message.answer(
        text="🛠️ <b>Панель адміністратора «Українські Мальдіви»</b>",
        reply_markup=get_admin_main_kb(pending_bookings, pending_payments)
    )

@router.callback_query(F.data == "admin_menu")
async def callback_admin_menu(callback_query: CallbackQuery, bot: Bot, session: AsyncSession, state: FSMContext):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
        
    await state.clear()
    await callback_query.answer()
    
    pending_bookings = await count_bookings_by_status(session, "awaiting_payment")
    pending_payments = await count_bookings_by_status(session, "payment_pending_review")
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="🛠️ <b>Панель адміністратора «Українські Мальдіви»</b>",
        reply_markup=get_admin_main_kb(pending_bookings, pending_payments)
    )

@router.callback_query(F.data == "admin_close_panel")
async def callback_admin_close(callback_query: CallbackQuery, bot: Bot, session: AsyncSession, state: FSMContext):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
        
    await state.clear()
    await callback_query.answer()
    try:
        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
    except Exception:
        pass
