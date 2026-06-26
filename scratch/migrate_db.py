import sqlite3

def run_migration():
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()

    # 1. Add payment_deadline to bookings if it doesn't exist
    try:
        cursor.execute("ALTER TABLE bookings ADD COLUMN payment_deadline DATETIME")
        print("Column 'payment_deadline' added successfully to 'bookings' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("Column 'payment_deadline' already exists in 'bookings' table.")
        else:
            print(f"Error adding column 'payment_deadline': {e}")

    # 2. Create payments table if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
        amount DECIMAL(10, 2) NOT NULL,
        monobank_card VARCHAR(20) NOT NULL,
        payment_comment VARCHAR(100) NOT NULL,
        screenshot_file_id VARCHAR(255),
        status VARCHAR(30) NOT NULL DEFAULT 'pending',
        rejection_reason VARCHAR(255),
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        confirmed_at DATETIME,
        confirmed_by BIGINT
    )
    """)
    print("Table 'payments' created or verified successfully.")

    # 3. Update existing 'pending' status bookings to 'awaiting_payment'
    cursor.execute("UPDATE bookings SET status = 'awaiting_payment' WHERE status = 'pending'")
    print("Existing bookings with 'pending' status updated to 'awaiting_payment'.")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    run_migration()
