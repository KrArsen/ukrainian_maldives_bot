import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import settings
from bot.database.engine import init_db
from bot.handlers import start, booking, my_bookings, payment
from bot.handlers.admin import admin_router
from bot.middlewares.db_middleware import DatabaseMiddleware
from bot.services.scheduler import setup_scheduler

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    bot = Bot(token=settings.BOT_TOKEN,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.update.middleware(DatabaseMiddleware())

    dp.include_router(start.router)
    dp.include_router(booking.router)
    dp.include_router(my_bookings.router)
    dp.include_router(admin_router)
    dp.include_router(payment.router)

    await init_db()

    scheduler = AsyncIOScheduler()
    setup_scheduler(scheduler, bot)
    scheduler.start()

    logging.info("✅ Бот запущено!")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
