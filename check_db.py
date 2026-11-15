import sqlite3

conn = sqlite3.connect("bot.db")
cursor = conn.cursor()

cursor.execute("SELECT * FROM subscribers")
users = cursor.fetchall()
print("Кто в базе:", users)

conn.close()