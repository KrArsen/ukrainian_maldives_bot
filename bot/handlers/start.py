# bot/handlers/start.py
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from bot.keyboards.main_menu import get_main_menu
from bot.config import settings

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handles the /start command, displaying resort greetings and main menu."""
    welcome_text = (
        "🌊 Вітаємо в «Українських Мальдівах»!\n\n"
        "Громадський басейн — перший комплекс із піском та хвилями у Чернівцях! 🌴\n"
        "⏰ Щодня з 10:00-19:30\n"
        "🧸 Знижка для дітей –50% до 1,20 м\n\n"
        "🌞 Для дітей до 3-х років БЕЗКОШТОВНО\n\n"
        "Оберіть дію в меню нижче 👇"
    )
    await message.answer(
        text=welcome_text,
        reply_markup=get_main_menu()
    )

@router.message(F.text == "📞 Контакти")
@router.message(Command("contacts"))
async def cmd_contacts(message: Message):
    """Displays contact information for the resort."""
    inst_handle = settings.RESORT_INSTAGRAM
    if inst_handle.startswith("@"):
        inst_url = f"https://instagram.com/{inst_handle[1:]}"
        inst_link = f"<a href=\"{inst_url}\">{inst_handle}</a>"
    else:
        inst_link = inst_handle

    contacts_text = (
        "🌊 <b>«Українські Мальдіви» Чернівці</b>\n"
        "Перший комплекс із піском та хвилями у Чернівцях! 🏖️\n\n"
        f"⏰ <b>Час роботи:</b> Щодня з 10:00 до 19:30\n"
        f"📍 <b>Адреса:</b> {settings.RESORT_ADDRESS}\n"
        f"📱 <b>Телефон:</b> {settings.RESORT_PHONE}\n"
        f"📸 <b>Instagram:</b> {inst_link}\n\n"
    )
    await message.answer(text=contacts_text)
