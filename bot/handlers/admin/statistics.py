# bot/handlers/admin/statistics.py
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.queries import get_statistics
from bot.handlers.admin.main_menu import is_admin

router = Router()

def get_stats_menu_kb() -> InlineKeyboardMarkup:
    """Returns period selector buttons."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Сьогодні", callback_data="ab_st:today"),
            InlineKeyboardButton(text="📅 7 Днів", callback_data="ab_st:week")
        ],
        [
            InlineKeyboardButton(text="📅 30 Днів", callback_data="ab_st:month"),
            InlineKeyboardButton(text="🌐 Весь час", callback_data="ab_st:all")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад до меню", callback_data="admin_menu")
        ]
    ])

@router.callback_query(F.data == "admin_stats_menu")
async def callback_stats_menu(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="📊 <b>Аналітика та Статистика</b>\n\nОберіть період для генерації звіту:",
        reply_markup=get_stats_menu_kb()
    )

@router.callback_query(F.data.startswith("ab_st:"))
async def callback_stats_report(callback_query: CallbackQuery, session: AsyncSession, bot: Bot):
    if not await is_admin(callback_query.from_user.id, session):
        await callback_query.answer()
        return
    await callback_query.answer()
    
    period = callback_query.data.split(":")[1]
    
    stats = await get_statistics(session, period)
    
    lbl_period = "сьогодні"
    if period == "week": lbl_period = "останні 7 днів"
    elif period == "month": lbl_period = "останні 30 днів"
    elif period == "all": lbl_period = "весь час"
    
    top_dates_lines = []
    for dt, count in stats["top_dates"]:
        top_dates_lines.append(f"  • {dt}: заброньовано {count} шатер")
    top_dates_str = "\n".join(top_dates_lines) if top_dates_lines else "  • немає даних"
    
    tent_ranking_lines = []
    for shelter_num, count in stats["tent_ranking"]:
        tent_ranking_lines.append(f"  • Шатро №{shelter_num}: {count} разів")
    tent_ranking_str = "\n".join(tent_ranking_lines) if tent_ranking_lines else "  • немає даних"
    
    text = (
        f"📊 <b>Звіт за період: {lbl_period.upper()}</b>\n\n"
        f"📈 <b>Заявки та бронювання:</b>\n"
        f"• Опрацьовано всього: <b>{stats['total']}</b>\n"
        f"• Схвалено (Confirmed): <b>{stats['confirmed']}</b>\n"
        f"• Скасовано (Cancelled): <b>{stats['cancelled']}</b>\n"
        f"• Очікують перевірки (Pending): <b>{stats['pending']}</b>\n\n"
        f"💰 <b>Фінанси:</b>\n"
        f"• Отриманий дохід: <b>{stats['revenue']:,.0f} грн</b>\n"
        f"• Відхилено оплат (помилкові чеки): <b>{stats['payments_rejected']}</b>\n\n"
        f"👥 <b>Клієнти:</b>\n"
        f"• Унікальних гостей: <b>{stats['unique_clients']}</b>\n"
        f"• Постійних гостей (>=2 броней): <b>{stats['repeat_clients']}</b>\n\n"
        f"🛖 <b>Завантаженість:</b>\n"
        f"• Середня завантаженість: <b>{stats['occupancy_rate']}%</b>\n\n"
        f"🔥 <b>Найпопулярніші дати:</b>\n{top_dates_str}\n\n"
        f"🛖 <b>Рейтинг шатер:</b>\n{tent_ranking_str}\n\n"
        f"<i>Оберіть інший період для порівняння:</i>"
    )
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        reply_markup=get_stats_menu_kb()
    )
