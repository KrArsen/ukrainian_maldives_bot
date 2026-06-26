# bot/handlers/admin/__init__.py
from aiogram import Router
from .main_menu import router as main_menu_router
from .bookings import router as bookings_router
from .payments import router as payments_router
from .schedule import router as schedule_router
from .statistics import router as statistics_router
from .clients import router as clients_router
from .search import router as search_router
from .settings import router as settings_router

admin_router = Router()
admin_router.include_routers(
    main_menu_router,
    bookings_router,
    payments_router,
    schedule_router,
    statistics_router,
    clients_router,
    search_router,
    settings_router
)
