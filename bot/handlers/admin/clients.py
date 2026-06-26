# bot/handlers/admin/clients.py
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import math

from bot.database.queries import (
    get_all_clients,
    get_client_profile,
    ban_client,
    unban_client,
    get_banned_clients,
    log_activity
)
from bot.keyboards.admin.clients_kb import (
    get_clients_list_kb,
    get_blacklist_kb,
    get_client_profile_kb
)
from bot.states.admin_states import AdminClientActions
from bot.handlers.admin.main_menu import is_admin

router = Router()

ITEMS_PER_PAGE = 10

@router.callback_query(F.data.startswith("admin_clients_"))
async def callback_clients_list(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    parts = callback_query.data.split("_")
    page = int(parts[-1]) if parts[-1].isdigit() else 1
    
    clients = await get_all_clients(session)
    total = len(clients)
    total_pages = math.ceil(total / ITEMS_PER_PAGE) or 1
    
    if page > total_pages:
        page = total_pages
        
    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    page_clients = clients[start:end]
    
    kb = get_clients_list_kb(page_clients, page, total_pages)
    
    text = (
        f"👥 <b>База клієнтів (всього: {total})</b>\n\n"
        f"Оберіть клієнта для перегляду профілю та історії бронювань:"
    )
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        reply_markup=kb
    )

# Blacklisted clients list view
@router.callback_query(F.data.startswith("ac_blacklist_"))
async def callback_blacklist_view(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    parts = callback_query.data.split("_")
    page = int(parts[-1]) if parts[-1].isdigit() else 1
    
    banned_users = await get_banned_clients(session)
    total = len(banned_users)
    total_pages = math.ceil(total / ITEMS_PER_PAGE) or 1
    
    if page > total_pages:
        page = total_pages
        
    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    page_banned = banned_users[start:end]
    
    kb = get_blacklist_kb(page_banned, page, total_pages)
    
    text = (
        f"🛑 <b>Чорний список (всього: {total})</b>\n\n"
        f"Список користувачів, які заблоковані в боті:"
    )
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        reply_markup=kb
    )

# View client profile
@router.callback_query(F.data.startswith("ac_v:"))
async def callback_client_profile(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    # Format: ac_v:<telegram_id>:<back_cb>
    parts = callback_query.data.split(":")
    telegram_id = int(parts[1])
    back_cb = ":".join(parts[2:])
    
    profile = await get_client_profile(session, telegram_id)
    if not profile:
        await callback_query.answer("Профіль не знайдено.", show_alert=True)
        return
        
    user = profile["user"]
    
    status_str = "🟢 Активний"
    if user.is_banned:
        status_str = f"🛑 Забанений\n📝 <b>Причина:</b> <i>{user.ban_reason}</i>\n📅 <b>Дата бану:</b> {user.banned_at.strftime('%d.%m.%Y %H:%M')}"
        
    first_b_str = profile["first_booking"].strftime("%d.%m.%Y") if profile["first_booking"] else "немає"
    last_b_str = profile["last_booking"].strftime("%d.%m.%Y") if profile["last_booking"] else "немає"
    
    text = (
        f"👤 <b>Профіль клієнта</b>\n\n"
        f"🆔 <b>Telegram ID:</b> <code>{user.telegram_id}</code>\n"
        f"👤 <b>Username:</b> @{user.username or 'немає'}\n"
        f"📝 <b>Повне ім'я:</b> {user.full_name or 'немає'}\n\n"
        f"🚦 <b>Статус:</b> {status_str}\n\n"
        f"📊 <b>Статистика замовлень:</b>\n"
        f"• Всього броней: <b>{profile['total_bookings']}</b>\n"
        f"• Схвалено: <b>{profile['confirmed_count']}</b>\n"
        f"• Скасовано: <b>{profile['cancelled_count']}</b>\n"
        f"• Витрачено коштів: <b>{profile['total_spent']:,} грн</b>\n\n"
        f"📅 Перше замовлення: {first_b_str}\n"
        f"📅 Останнє замовлення: {last_b_str}"
    )
    
    # Convert back_cb to format expected by keyboard
    # e.g. "1" from dashboard, or "bl_1"
    # Let's map back_cb back to real callback data:
    if back_cb.startswith("bl_"):
        page_num = back_cb.split("_")[-1]
        back_callback_data = f"ac_blacklist_{page_num}"
    elif back_cb.isdigit():
        back_callback_data = f"admin_clients_{back_cb}"
    else:
        # If it is a booking details page back target (e.g. ab_v:123:ab_l:...)
        back_callback_data = back_cb
        
    kb = get_client_profile_kb(user.telegram_id, user.is_banned, back_callback_data)
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        reply_markup=kb
    )

# Unban client action
@router.callback_query(F.data.startswith("ac_unb:"))
async def callback_client_unban(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
        
    parts = callback_query.data.split(":")
    telegram_id = int(parts[1])
    back_cb = ":".join(parts[2:])
    
    await unban_client(session, telegram_id)
    await callback_query.answer("Клієнта успішно розбанено!", show_alert=True)
    
    # Log
    await log_activity(
        session, "unban",
        f"Адмін розбанив користувача ID:{telegram_id}",
        user_id=callback_query.from_user.id
    )
    
    # Notify user
    try:
        await bot.send_message(
            chat_id=telegram_id,
            text="🟢 <b>Ваш доступ до бота відновлено!</b>\n\nВи знову можете бронювати шатра."
        )
    except Exception:
        pass
        
    # Re-render profile
    # Update callback data to view profile again
    callback_query.data = f"ac_v:{telegram_id}:{back_cb}"
    await callback_client_profile(callback_query, session, bot)

# Ban client request (starts FSM)
@router.callback_query(F.data.startswith("ac_ban:"))
async def callback_client_ban_request(callback_query: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    parts = callback_query.data.split(":")
    telegram_id = int(parts[1])
    back_cb = ":".join(parts[2:])
    
    await state.set_state(AdminClientActions.waiting_ban_reason)
    await state.update_data(
        ban_telegram_id=telegram_id,
        back_cb=back_cb,
        orig_msg_id=callback_query.message.message_id
    )
    
    await bot.send_message(
        chat_id=callback_query.message.chat.id,
        text=f"✍_ <b>Введіть причину блокування для користувача ID:{telegram_id}:</b>"
    )

# Receive ban reason
@router.message(AdminClientActions.waiting_ban_reason)
async def process_client_ban_reason(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    if not await is_admin(message.from_user.id, session):
        return
        
    data = await state.get_data()
    telegram_id = data["ban_telegram_id"]
    back_cb = data["back_cb"]
    orig_msg_id = data["orig_msg_id"]
    
    reason = message.text.strip() if message.text else "Порушення правил бронювання"
    await state.clear()
    
    await ban_client(session, telegram_id, reason)
    
    # Log
    await log_activity(
        session, "ban",
        f"Адмін забанив користувача ID:{telegram_id} з причиною: {reason}",
        user_id=message.from_user.id
    )
    
    # Notify user
    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=f"🛑 <b>Ви були заблоковані адміністратором!</b>\n\n<b>Причина:</b> <i>{reason}</i>\n\nВи більше не можете користуватися цим ботом."
        )
    except Exception:
        pass
        
    await message.answer(f"✅ Користувача ID:{telegram_id} успішно додано до чорного списку.")
    
    # Try deleting original request prompt message
    try:
        await message.delete()
    except Exception:
        pass
        
    # Send updated profile as new message
    profile = await get_client_profile(session, telegram_id)
    if profile:
        user = profile["user"]
        status_str = f"🛑 Забанений\n📝 <b>Причина:</b> <i>{user.ban_reason}</i>\n📅 <b>Дата бану:</b> {user.banned_at.strftime('%d.%m.%Y %H:%M')}"
        first_b_str = profile["first_booking"].strftime("%d.%m.%Y") if profile["first_booking"] else "немає"
        last_b_str = profile["last_booking"].strftime("%d.%m.%Y") if profile["last_booking"] else "немає"
        
        text = (
            f"👤 <b>Профіль клієнта</b>\n\n"
            f"🆔 <b>Telegram ID:</b> <code>{user.telegram_id}</code>\n"
            f"👤 <b>Username:</b> @{user.username or 'немає'}\n"
            f"📝 <b>Повне ім'я:</b> {user.full_name or 'немає'}\n\n"
            f"🚦 <b>Статус:</b> {status_str}\n\n"
            f"📊 <b>Статистика замовлень:</b>\n"
            f"• Всього броней: <b>{profile['total_bookings']}</b>\n"
            f"• Схвалено: <b>{profile['confirmed_count']}</b>\n"
            f"• Скасовано: <b>{profile['cancelled_count']}</b>\n"
            f"• Витрачено коштів: <b>{profile['total_spent']:,} грн</b>\n\n"
            f"📅 Перше замовлення: {first_b_str}\n"
            f"📅 Останнє замовлення: {last_b_str}"
        )
        
        if back_cb.startswith("bl_"):
            page_num = back_cb.split("_")[-1]
            back_callback_data = f"ac_blacklist_{page_num}"
        elif back_cb.isdigit():
            back_callback_data = f"admin_clients_{back_cb}"
        else:
            back_callback_data = back_cb
            
        kb = get_client_profile_kb(user.telegram_id, user.is_banned, back_callback_data)
        await message.answer(text=text, reply_markup=kb)
