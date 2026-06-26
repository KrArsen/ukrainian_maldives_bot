# bot/keyboards/catalog_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData

class CatalogCallback(CallbackData, prefix="cat"):
    action: str  # "prev", "next", "book", "close"
    property_id: int
    index: int

def get_catalog_kb(property_id: int, index: int, total_count: int) -> InlineKeyboardMarkup:
    """
    Returns navigation and action keyboard for catalog items.
    """
    buttons = []
    
    # Row 1: Action (Book)
    buttons.append([
        InlineKeyboardButton(
            text="📅 Забронювати це шатро",
            callback_data=CatalogCallback(action="book", property_id=property_id, index=index).pack()
        )
    ])
    
    # Row 2: Navigation
    nav_row = []
    if total_count > 1:
        # Calculate prev and next indices
        prev_idx = (index - 1) % total_count
        next_idx = (index + 1) % total_count
        
        nav_row.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=CatalogCallback(action="prev", property_id=property_id, index=prev_idx).pack()
        ))
        nav_row.append(InlineKeyboardButton(
            text=f"{index + 1} / {total_count}",
            callback_data=CatalogCallback(action="ignore", property_id=property_id, index=index).pack()
        ))
        nav_row.append(InlineKeyboardButton(
            text="Вперед ▶️",
            callback_data=CatalogCallback(action="next", property_id=property_id, index=next_idx).pack()
        ))
        buttons.append(nav_row)
        
    # Row 3: Close
    buttons.append([
        InlineKeyboardButton(
            text="❌ Закрити каталог",
            callback_data=CatalogCallback(action="close", property_id=0, index=0).pack()
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
