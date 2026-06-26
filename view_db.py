import sqlite3
import sys
from datetime import datetime

# Configure console output to support Ukrainian text and emojis on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass  # Not all Python versions/environments support sys.stdout.reconfigure

def format_date(date_str):
    if not date_str:
        return ""
    try:
        if " " in date_str or "T" in date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", ""))
            return dt.strftime("%d.%m.%Y %H:%M")
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    except Exception:
        return date_str

def view_database():
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()

    print("=" * 80)
    print("🌴 БАЗА ДАНИХ БОТА «УКРАЇНСЬКІ МАЛЬДІВИ» 🌊")
    print("=" * 80)

    # 1. Users
    print("\n👤 КОРИСТУВАЧІ (users):")
    try:
        cursor.execute("SELECT telegram_id, username, full_name, is_admin, created_at FROM users")
        users = cursor.fetchall()
        if not users:
            print("  Немає зареєстрованих користувачів.")
        else:
            print(f"  {'ID Telegram':<15} | {'Username':<15} | {'Повне ім`я':<25} | {'Адмін':<5} | {'Створено'}")
            print("  " + "-" * 75)
            for u in users:
                is_admin_str = "Так" if u[3] else "Ні"
                created = format_date(u[4])
                # Ensure values are stringified to prevent formatting errors
                username = str(u[1]) if u[1] is not None else ""
                fullname = str(u[2]) if u[2] is not None else ""
                print(f"  {u[0]:<15} | {username:<15} | {fullname:<25} | {is_admin_str:<5} | {created}")
    except sqlite3.OperationalError as e:
        print(f"  Помилка доступу до таблиці users: {e}")

    # 2. Bookings
    print("\n📅 БРОНЮВАННЯ (bookings):")
    try:
        cursor.execute("SELECT id, shelter_num, booking_date, client_name, client_phone, status, created_at FROM bookings ORDER BY booking_date DESC")
        bookings = cursor.fetchall()
        if not bookings:
            print("  Немає замовлень.")
        else:
            print(f"  {'ID':<4} | {'Шатро':<5} | {'Дата':<10} | {'Клієнт':<20} | {'Телефон':<15} | {'Статус':<10} | {'Створено'}")
            print("  " + "-" * 85)
            for b in bookings:
                b_date = format_date(b[2])
                created = format_date(b[6])
                client_name = str(b[3]) if b[3] is not None else ""
                client_phone = str(b[4]) if b[4] is not None else ""
                status = str(b[5]) if b[5] is not None else ""
                print(f"  {b[0]:<4} | №{b[1]:<4} | {b_date:<10} | {client_name:<20} | {client_phone:<15} | {status:<10} | {created}")
    except sqlite3.OperationalError as e:
        print(f"  Помилка доступу до таблиці bookings: {e}")

    # 3. Logs
    print("\n\n📝 ОСТАННІ 5 ПОДІЙ (activity_logs):")
    try:
        cursor.execute("SELECT id, action_type, details, created_at FROM activity_logs ORDER BY created_at DESC LIMIT 5")
        logs = cursor.fetchall()
        if not logs:
            print("  Журнал подій порожній.")
        else:
            for log in logs:
                created = format_date(log[3])
                print(f"  [{created}] {log[1].upper()}: {log[2]}")
    except sqlite3.OperationalError as e:
        print(f"  Помилка доступу до таблиці activity_logs: {e}")

    print("\n" + "=" * 80)
    conn.close()

if __name__ == "__main__":
    view_database()
