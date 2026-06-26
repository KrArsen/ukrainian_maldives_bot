# bot/database/seed.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import Property
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

async def seed_initial_data(session: AsyncSession):
    """Seeds initial mock bungalows/properties if the database catalog is empty."""
    result = await session.execute(select(Property).limit(1))
    if result.scalar_one_or_none() is not None:
        return  # Already seeded
        
    logger.info("Database catalog is empty. Seeding mock bungalow properties...")
    
    prop1 = Property(
        name="Бунгало №1 — Лагуна",
        description="Затишне бунгало на самісінькому березі з видом на блакитну лагуну. Ідеально підходить для романтичного відпочинку удвох.",
        capacity=2,
        price_per_night=Decimal("1500.00"),
        price_weekend=Decimal("1800.00"),
        amenities=["WiFi", "Кондиціонер", "Холодильник", "Тераса", "Вид на озеро"],
        photos=["https://images.unsplash.com/photo-1544735716-392fe2489ffa?q=80&w=800"],
        is_active=True,
        sort_order=1
    )
    
    prop2 = Property(
        name="Бунгало №2 — Сансет",
        description="Просторе сімейне бунгало з великою терасою, де можна насолоджуватися неймовірними заходами сонця та вечірнім затишком.",
        capacity=4,
        price_per_night=Decimal("2200.00"),
        price_weekend=Decimal("2600.00"),
        amenities=["WiFi", "Кондиціонер", "Холодильник", "Тераса", "Душ", "Кухня"],
        photos=["https://images.unsplash.com/photo-1507525428034-b723cf961d3e?q=80&w=800"],
        is_active=True,
        sort_order=2
    )
    
    session.add_all([prop1, prop2])
    await session.commit()
    logger.info("Successfully seeded database with 2 mock properties.")
