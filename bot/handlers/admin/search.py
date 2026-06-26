# bot/handlers/admin/search.py
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.queries import search_bookings
from bot.database.models import BookingStatus
from bot.states.admin_states import AdminSearch
from bot.handlers.admin.main_menu import is_admin

router = Router()

@router.callback_query(F.data == "admin_search")
async def callback_admin_search_request(callback_query: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    await state.set_state(AdminSearch.waiting_search_query)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад до меню", callback_data="admin_menu")]
    ])
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="🔍 <b>Пошук бронювань</b>\n\nВведіть пошуковий запит (Ім'я клієнта, Номер телефону, Номер шатра або ID бронювання):",
        reply_markup=kb
    )

# Receive query and perform search
@router.message(AdminSearch.waiting_search_query)
async def process_search_query(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    if not await is_admin(message.from_user.id, session):
        await state.clear()
        return
        
    query = message.text.strip()
    if not query:
        await message.answer("Пошуковий запит не може бути порожнім. Спробуйте ще раз:")
        return
        
    bookings = await search_bookings(session, query)
    await state.clear() # Clear search state
    
    if not bookings:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Шукати знову", callback_data="admin_search")],
            [InlineKeyboardButton(text="⬅️ Головне меню", callback_data="admin_menu")]
        ])
        await message.answer(
            text=f"🔍 <b>Результати пошуку для:</b> «{query}»\n\n❌ Нічого не знайдено за вашим запитом.",
            reply_markup=kb
        )
        return
        
    buttons = []
    for b in bookings:
        status_icon = "⏳"
        if b.status == BookingStatus.payment_pending_review:
            status_icon = "🔍"
        elif b.status == BookingStatus.confirmed:
            status_icon = "✅"
        elif b.status == BookingStatus.cancelled:
            status_icon = "❌"
            
        date_str = b.booking_date.strftime("%d.%m")
        btn_text = f"🛖 №{b.shelter_num} | 📅 {date_str} | {b.client_name} ({status_icon})"
        
        # When clicking back from detail card, let's return to the search prompt
        back_cb = "admin_search"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"ab_v:{b.id}:{back_cb}")])
        
    buttons.append([InlineKeyboardButton(text="🔍 Шукати знову", callback_data="admin_search")])
    buttons.append([InlineKeyboardButton(text="⬅️ Головне меню", callback_data="admin_menu")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await message.answer(
        text=f"🔍 <b>Результати пошуку для:</b> «{query}»\n\nЗнайдено збігів: <b>{len(bookings)}</b>\nОберіть бронювання для керування:",
        reply_markup=kb
    )
