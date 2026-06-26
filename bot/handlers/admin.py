# bot/handlers/admin.py
import math
from datetime import date, timedelta
from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import BookingStatus, Booking
from bot.database.queries import (
    get_pending_bookings,
    get_all_bookings,
    get_bookings_on_date,
    confirm_booking,
    cancel_booking,
    log_activity,
    get_recent_activity
)
from bot.keyboards.admin_kb import (
    get_admin_main_kb,
    get_booking_details_kb,
    get_all_bookings_pagination_kb
)
from bot.states.booking_states import AdminFSM

router = Router()

ITEMS_PER_PAGE = 5

def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Admin control panel welcome screen."""
    if not is_admin(message.from_user.id):
        return
        
    await message.answer(
        text="🛠️ <b>Панель адміністратора «Українські Мальдіви»</b>",
        reply_markup=get_admin_main_kb()
    )

# Callback to view main panel menu again
@router.callback_query(F.data == "admin_menu")
async def callback_admin_menu(callback_query: CallbackQuery, bot: Bot):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer()
        return
    await callback_query.answer()
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="🛠️ <b>Панель адміністратора «Українські Мальдіви»</b>",
        reply_markup=get_admin_main_kb()
    )

@router.callback_query(F.data == "admin_close_panel")
async def callback_admin_close(callback_query: CallbackQuery, bot: Bot):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer()
        return
    await callback_query.answer()
    try:
        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
    except Exception:
        pass

# 🔔 Нові заявки (Pending bookings list)
@router.callback_query(F.data == "admin_pending")
async def callback_admin_pending(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer()
        return
        
    await callback_query.answer()
    bookings = await get_pending_bookings(session)
    
    if not bookings:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
        ])
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text="🔔 Немає нових заявок в очікуванні підтвердження.",
            reply_markup=kb
        )
        return
        
    lines = ["🔔 <b>Нові заявки в очікуванні підтвердження:</b>\n\nОберіть заявку для керування:"]
    buttons = []
    
    for b in bookings:
        date_str = b.booking_date.strftime("%d.%m.%Y")
        btn_text = f"🛖 №{b.shelter_num} | 📅 {date_str} | {b.client_name}"
        # Callback encodes booking_id and back target 'pending'
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"adm_view_{b.id}_pending")])
        
    buttons.append([InlineKeyboardButton(text="⬅️ Назад до меню", callback_data="admin_menu")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="\n".join(lines),
        reply_markup=kb
    )

# Today's list
@router.callback_query(F.data == "admin_today")
async def callback_admin_today(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    await show_bookings_on_target_date(callback_query, date.today(), "today", session, bot)

# Tomorrow's list
@router.callback_query(F.data == "admin_tomorrow")
async def callback_admin_tomorrow(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    await show_bookings_on_target_date(callback_query, date.today() + timedelta(days=1), "tomorrow", session, bot)

async def show_bookings_on_date_internal(chat_id: int, target_date: date, back_callback: str, session: AsyncSession, bot: Bot, edit_message_id: int | None = None):
    bookings = await get_bookings_on_date(session, target_date)
    date_str = target_date.strftime("%d.%m.%Y")
    
    booked_nums = [str(b.shelter_num) for b in bookings]
    free_nums = [str(i) for i in range(1, 11) if str(i) not in booked_nums]
    
    lines = [f"📅 <b>Бронювання на {date_str}:</b>\n"]
    buttons = []
    
    if bookings:
        for b in bookings:
            status_icon = "✅" if b.status == BookingStatus.confirmed else "⏳"
            lines.append(f"{status_icon} Шатро №{b.shelter_num} — {b.client_name} — {b.client_phone}")
            # Add inline button to manage this booking
            btn_text = f"⚙️ Керувати Шатро №{b.shelter_num} ({b.client_name})"
            buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"adm_view_{b.id}_{back_callback}")])
    else:
        lines.append("<i>Бронювань немає</i>")
        
    if free_nums:
        lines.append(f"\nВільні: №{', №'.join(free_nums)}")
        
    buttons.append([InlineKeyboardButton(text="⬅️ Назад до меню", callback_data="admin_menu")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    text = "\n".join(lines)
    
    if edit_message_id:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=edit_message_id, text=text, reply_markup=kb)
        except Exception:
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)
    else:
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)

async def show_bookings_on_target_date(callback_query: CallbackQuery, target_date: date, back_callback: str, session: AsyncSession, bot: Bot):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer()
        return
    await callback_query.answer()
    await show_bookings_on_date_internal(
        chat_id=callback_query.message.chat.id,
        target_date=target_date,
        back_callback=back_callback,
        session=session,
        bot=bot,
        edit_message_id=callback_query.message.message_id
    )

# All bookings list (Paginated with interactive details)
async def show_all_bookings_internal(chat_id: int, page: int, session: AsyncSession, bot: Bot, edit_message_id: int | None = None):
    bookings = await get_all_bookings(session) # Fetch last 50
    total_count = len(bookings)
    
    if not bookings:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
        ])
        text = "📋 Всього в базі немає бронювань."
        if edit_message_id:
            await bot.edit_message_text(chat_id=chat_id, message_id=edit_message_id, text=text, reply_markup=kb)
        else:
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)
        return
        
    total_pages = math.ceil(total_count / ITEMS_PER_PAGE)
    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_bookings = bookings[start_idx:end_idx]
    
    text = f"📋 <b>Останні {total_count} бронювань (сторінка {page}/{total_pages}):</b>\n\nОберіть бронювання для перегляду та дій:"
    
    buttons = []
    for b in page_bookings:
        status_icon = "⏳"
        if b.status == BookingStatus.confirmed:
            status_icon = "✅"
        elif b.status == BookingStatus.cancelled:
            status_icon = "❌"
            
        date_str = b.booking_date.strftime("%d.%m")
        btn_text = f"#{b.id} | 🛖 №{b.shelter_num} | 📅 {date_str} | {b.client_name} ({status_icon})"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"adm_view_{b.id}_all_{page}")])
        
    pagination_kb = get_all_bookings_pagination_kb(page, total_pages)
    # Merge pagination buttons
    merged_buttons = buttons + pagination_kb.inline_keyboard
    # Insert back to menu button at the top of menu navigation controls
    merged_buttons.insert(-1, [InlineKeyboardButton(text="⬅️ Назад до меню", callback_data="admin_menu")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=merged_buttons)
    
    if edit_message_id:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=edit_message_id, text=text, reply_markup=kb)
        except Exception:
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)
    else:
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)

@router.callback_query(F.data.startswith("admin_all_"))
async def callback_admin_all(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer()
        return
        
    page = int(callback_query.data.split("_")[-1])
    await callback_query.answer()
    await show_all_bookings_internal(
        chat_id=callback_query.message.chat.id,
        page=page,
        session=session,
        bot=bot,
        edit_message_id=callback_query.message.message_id
    )

# Booking Details view handler
@router.callback_query(F.data.startswith("adm_view_"))
async def callback_admin_view_booking(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer()
        return
        
    await callback_query.answer()
    parts = callback_query.data.split("_")
    booking_id = int(parts[2])
    back_callback = "_".join(parts[3:]) # e.g., 'all_1', 'today', 'tomorrow', 'pending'
    
    b = await session.get(Booking, booking_id)
    if not b:
        await callback_query.answer("Бронювання не знайдено.", show_alert=True)
        return
        
    status_label = "⏳ Очікує підтвердження"
    if b.status == BookingStatus.confirmed:
        status_label = "✅ Підтверджено"
    elif b.status == BookingStatus.cancelled:
        status_label = "❌ Скасовано"
        
    comment_text = f"\n📝 <b>Причина скасування:</b> <i>{b.admin_comment}</i>" if b.admin_comment else ""
    created_at_str = b.created_at.strftime("%H:%M %d.%m.%Y")
    
    text = (
        f"📌 <b>Деталі заявки #{b.id}</b>\n\n"
        f"🛖 <b>Шатро:</b> Шатро №{b.shelter_num}\n"
        f"📅 <b>Дата:</b> {b.booking_date.strftime('%d.%m.%Y')}\n"
        f"👥 <b>Місткість:</b> 2 дорослих (фіксовано)\n\n"
        f"👤 <b>Клієнт:</b> {b.client_name}\n"
        f"📞 <b>Телефон:</b> {b.client_phone}\n\n"
        f"🚦 <b>Статус:</b> {status_label}"
        f"{comment_text}\n"
        f"🕐 <b>Подано:</b> {created_at_str}"
    )
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        reply_markup=get_booking_details_kb(b.id, b.status.value, back_callback)
    )

# Confirm booking action
@router.callback_query(F.data.startswith("adm_confirm_"))
async def callback_confirm_booking(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer()
        return
        
    parts = callback_query.data.split("_")
    booking_id = int(parts[2])
    back_callback = "_".join(parts[3:])
    
    b = await confirm_booking(session, booking_id)
    if b:
        await session.commit()
        await callback_query.answer("Бронювання підтверджено!")
        
        # Log activity
        date_str = b.booking_date.strftime("%d.%m.%Y")
        await log_activity(
            session=session,
            action_type="confirmed",
            details=f"Адмін підтвердив бронь #{b.id} (Шатро №{b.shelter_num}, {date_str}, {b.client_name})",
            booking_id=b.id,
            user_id=callback_query.from_user.id
        )
        
        # Notify user
        try:
            user_text = (
                "✅ <b>Бронювання підтверджено!</b>\n\n"
                f"🛖 Шатро №{b.shelter_num}\n"
                f"📅 {date_str}\n"
                f"👤 {b.client_name}\n\n"
                f"Чекаємо вас! З питань: {settings.RESORT_PHONE}"
            )
            await bot.send_message(chat_id=b.user_id, text=user_text)
        except Exception:
            pass
            
        # Re-render details view
        await callback_admin_view_booking(callback_query, session, bot)
    else:
        await callback_query.answer("Помилка підтвердження.", show_alert=True)

# Cancel booking action (Starts FSM for cancel reason)
@router.callback_query(F.data.startswith("adm_cancel_"))
async def callback_cancel_booking_request(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer()
        return
        
    await callback_query.answer()
    parts = callback_query.data.split("_")
    booking_id = int(parts[2])
    back_callback = "_".join(parts[3:])
    
    await state.set_state(AdminFSM.waiting_cancel_reason)
    await state.update_data(
        cancel_booking_id=booking_id, 
        cancel_message_id=callback_query.message.message_id,
        cancel_back_callback=back_callback
    )
    
    # Send a prompt and hide keyboard
    await bot.send_message(
        chat_id=callback_query.message.chat.id,
        text=f"✍️ <b>Скасування заявки #{booking_id}</b>\n\nВведіть причину скасування для клієнта:",
        reply_markup=ReplyKeyboardRemove()
    )

# Receive cancellation reason text
@router.message(StateFilter(AdminFSM.waiting_cancel_reason))
async def process_cancel_reason(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
        
    reason = message.text.strip() if message.text else "Не вказано"
    state_data = await state.get_data()
    booking_id = state_data["cancel_booking_id"]
    old_msg_id = state_data["cancel_message_id"]
    back_callback = state_data["cancel_back_callback"]
    
    b = await cancel_booking(session, booking_id, reason)
    if b:
        await session.commit()
        await message.answer(f"✅ Бронювання #{booking_id} успішно скасовано з причиною: <i>{reason}</i>")
        
        # Log activity
        await log_activity(
            session=session,
            action_type="cancelled",
            details=f"Адмін скасував бронь #{b.id} (Шатро №{b.shelter_num}, {b.booking_date.strftime('%d.%m.%Y')}, {b.client_name}). Причина: {reason}",
            booking_id=b.id,
            user_id=message.from_user.id
        )
        
        # Delete old detail view card
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=old_msg_id)
        except Exception:
            pass
            
        # Notify user
        date_str = b.booking_date.strftime("%d.%m.%Y")
        try:
            user_text = (
                "❌ <b>Бронювання скасовано</b>\n\n"
                f"🛖 Шатро №{b.shelter_num}  |  📅 {date_str}\n"
                f"Причина: <i>{reason}</i>\n\n"
                "Для нового бронювання натисніть /start"
            )
            await bot.send_message(chat_id=b.user_id, text=user_text)
        except Exception:
            pass
            
        # Clear FSM and redirect back to the parent list
        await state.clear()
        
        # Redirect back to list
        if back_callback == "pending":
            # Simulate callback query trigger by calling logic
            await show_pending_list_redirect(message.chat.id, session, bot)
        elif back_callback == "today":
            await show_bookings_on_date_internal(message.chat.id, date.today(), "today", session, bot)
        elif back_callback == "tomorrow":
            await show_bookings_on_date_internal(message.chat.id, date.today() + timedelta(days=1), "tomorrow", session, bot)
        elif back_callback.startswith("all_"):
            page = int(back_callback.split("_")[-1])
            await show_all_bookings_internal(message.chat.id, page, session, bot)
    else:
        await message.answer("❌ Сталася помилка при скасуванні.")
        await state.clear()

async def show_pending_list_redirect(chat_id: int, session: AsyncSession, bot: Bot):
    bookings = await get_pending_bookings(session)
    if not bookings:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]])
        await bot.send_message(chat_id=chat_id, text="🔔 Немає нових заявок в очікуванні підтвердження.", reply_markup=kb)
        return
        
    lines = ["🔔 <b>Нові заявки в очікуванні підтвердження:</b>\n\nОберіть заявку для керування:"]
    buttons = []
    for b in bookings:
        date_str = b.booking_date.strftime("%d.%m.%Y")
        btn_text = f"🛖 №{b.shelter_num} | 📅 {date_str} | {b.client_name}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"adm_view_{b.id}_pending")])
        
    buttons.append([InlineKeyboardButton(text="⬅️ Назад до меню", callback_data="admin_menu")])
    await bot.send_message(chat_id=chat_id, text="\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# 📝 Журнал подій
async def show_activity_log_internal(chat_id: int, session: AsyncSession, bot: Bot, edit_message_id: int | None = None):
    logs = await get_recent_activity(session, limit=20)
    
    lines = ["📝 <b>Журнал подій (останні 20)</b>\n"]
    
    if not logs:
        lines.append("<i>Подій ще немає в базі даних.</i>")
    else:
        for log in logs:
            kyiv_time = log.created_at + timedelta(hours=3)
            time_str = kyiv_time.strftime("%H:%M %d.%m")
            
            icon = "⚪️"
            if log.action_type == "created":
                icon = "🟢 Створення"
            elif log.action_type == "confirmed":
                icon = "🔵 Підтверджено"
            elif log.action_type == "cancelled":
                icon = "🔴 Скасовано"
            elif log.action_type == "reminder_sent":
                icon = "🟡 Нагадування"
                
            lines.append(f"🕒 <b>[{time_str}]</b> {icon}:\n{log.details}\n")
            
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Оновити", callback_data="admin_activity_refresh"),
            InlineKeyboardButton(text="⬅️ Назад до меню", callback_data="admin_menu")
        ]
    ])
    
    text = "\n".join(lines)
    if edit_message_id:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=edit_message_id, text=text, reply_markup=kb)
        except Exception:
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)
    else:
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)

@router.callback_query(F.data == "admin_activity_log")
async def callback_admin_activity_log(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer()
        return
    await callback_query.answer()
    await show_activity_log_internal(
        chat_id=callback_query.message.chat.id,
        session=session,
        bot=bot,
        edit_message_id=callback_query.message.message_id
    )

@router.callback_query(F.data == "admin_activity_refresh")
async def callback_admin_activity_refresh(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer()
        return
    await callback_query.answer("Дані оновлено!")
    await show_activity_log_internal(
        chat_id=callback_query.message.chat.id,
        session=session,
        bot=bot,
        edit_message_id=callback_query.message.message_id
    )
