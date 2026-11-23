from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton #pip install python telegram bot (терминал)
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler #pip install python telegram bot 
from dotenv import load_dotenv #pip install python-dotenv
import os #pip не нужен
import random #pip не нужен
import sqlite3  #pip не нужен
import datetime #для исключения ночного времени в рассылке мемов
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler #pip install APScheduler
from flask import Flask #pip install Flask
import threading  #pip не нужен
import asyncio
from telegram import Bot
from telegram.error import Forbidden


#Flask - веб-сервис, чтобы бот мог отвечать на HTTP запросы (создает мини сайт)
app_flask = Flask(__name__)
@app_flask.route('/')
def health():
    return "Bot is running!"

def run_web():
    # Render сам подставит нужный порт
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

# Загрузка токена
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# База данных
def init_db():
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    
    # Таблица подписчиков
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            user_id INTEGER PRIMARY KEY,
            last_meme_id INTEGER 
        )
    """)
    conn.commit()
    conn.close()


# Отправка мема дня
async def send_daily_meme(bot):
    # --- ПРОВЕРКА НОЧНОГО ВРЕМЕНИ ПО МОСКВЕ ---
    moscow_tz = ZoneInfo("Europe/Moscow")
    current_hour = datetime.datetime.now(moscow_tz).hour
    
    if 0 <= current_hour < 10:
        print(f"Ночное время по Москве ({current_hour}:00). Бот спит.")
        return
    # --- КОНЕЦ ПРОВЕРКИ ---
    
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM subscribers")
    users = cursor.fetchall()
    conn.close()

    # 1. Проверяем и собираем список мемов
    meme_folder = "memes"
    if not os.path.exists(meme_folder) or not os.listdir(meme_folder):
        print("Папка с мемами пуста или не найдена!")
        return

    meme_list = os.listdir(meme_folder)

    # 2. Идем по пользователям
    for (user_id,) in users:
        try:
            # 3. Для КАЖДОГО пользователя (или один на всех) выбираем случайный мем
            random_meme = random.choice(meme_list)
            meme_path = os.path.join(meme_folder, random_meme)
            
            with open(meme_path, "rb") as photo:
                # 1. Сохраняем результат отправки в переменную sent_message
                sent_message = await bot.send_photo(
                    chat_id=user_id,
                    photo=photo,
                    caption="Вот твой мем дня!"
                )
                
                # 2. Запускаем таймер на удаление
                scheduler.add_job(
                    bot.delete_message,
                    'date',
                    run_date=datetime.datetime.now() + datetime.timedelta(hours=1),
                    kwargs={'chat_id': user_id, 'message_id': sent_message.message_id}
                )
        except Forbidden:
            # Если пользователь заблокировал бота — удаляем его из БД
            print(f"Пользователь {user_id} заблокировал бота. Удаляем.")
            conn = sqlite3.connect("bot.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM subscribers WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Ошибка при отправке {user_id}: {e}")


#Кнопка – случайный мем
keyboard = [
    [InlineKeyboardButton("Случайный Мем", callback_data="random_meme")]
]
menu = InlineKeyboardMarkup(keyboard)

#Команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # СОХРАНЕНИЕ ПОЛЬЗОВАТЕЛЯ В БАЗУ 
    user_id = update.message.from_user.id
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    # INSERT OR IGNORE не даст добавить дубликат, если он нажмет /start дважды
    cursor.execute("INSERT OR IGNORE INTO subscribers (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()
    print(f"Пользователь {user_id} добавлен в базу!")
    # Создаем клавиатуру, которая будет внизу
    reply_keyboard = [
        [KeyboardButton("Случайный мем 🎲")] # Кнопка в первом ряду
    ]
    # resize_keyboard=True делает кнопку аккуратной (не на весь экран)
    reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    
    # Отправляем сообщение с этой клавиатурой
    await update.message.reply_text(
        "Привет! Я бот-мемотерапевт. \n\n"
        "Я буду присылать тебе мемы каждый час, чтобы поднимать настроение! 🎁\n"
        "А если захочешь мем прямо сейчас — просто нажми на кнопку ниже. 👇",
        reply_markup=reply_markup
    )


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/start - подписаться на мемы")   

# Меню
async def menu_hundler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выберидействие:", reply_markup=menu)

# Обработка кнопок
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "random_meme":
        meme_folder = "memes"
        if not os.path.exists(meme_folder) or not os.listdir(meme_folder):
            await query.edit_message_text("Ой папка с мемами пуста! Добавь туда картинки.")
            return
        
        meme_list = os.listdir(meme_folder)
        random_meme = random.choice(meme_list)
        meme_path = os.path.join(meme_folder, random_meme)

        await query.message.reply_photo(
            photo=open(meme_path, "rb"),
            caption="Вот твой мем!"
        )
        await query.delete_message()

# Словарь для хранения ID последних сообщений (чтобы удалять их)
user_last_meme = {}
user_last_request = {} # Будем хранить ID сообщения с текстом "Случайный мем"

async def send_meme_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # 1. Удаляем сообщение пользователя (текст "Случайный мем")
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    except Exception:
        pass

    # 2. Удаляем предыдущий мем, если он был
    if user_id in user_last_meme:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=user_last_meme[user_id])
        except Exception:
            pass

    # 3. Выбираем и отправляем новый мем
    meme_folder = "memes"
    if not os.path.exists(meme_folder) or not os.listdir(meme_folder):
        return

    meme_list = os.listdir(meme_folder)
    random_meme = random.choice(meme_list)
    meme_path = os.path.join(meme_folder, random_meme)

    sent_message = await update.message.reply_photo(
        photo=open(meme_path, "rb"),
        caption="Вот твой мем!"
    )
    
    # 4. Сохраняем ID нового мема
    user_last_meme[user_id] = sent_message.message_id


    
# Запуск приложения

init_db()
app = ApplicationBuilder().token(BOT_TOKEN) \
    .read_timeout(10) \
    .write_timeout(10) \
    .connect_timeout(10) \
    .build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help))
app.add_handler(CommandHandler("menu", menu_hundler))
app.add_handler(CallbackQueryHandler(handle_buttons))
app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^Случайный мем 🎲$"), send_meme_reply))

# БЛОК ДЛЯ БУДИЛЬНИКА 
from apscheduler.schedulers.asyncio import AsyncIOScheduler
scheduler = AsyncIOScheduler() 
 


# Функция, которая запустит будильник ПОСЛЕ старта бота
async def post_init(application):
    scheduler.start()
    # Запускаем задачу с интервалом, передавая bot
    scheduler.add_job(
        send_daily_meme,
        'interval',
        hours=1,  
        args=[application.bot]  # Передаем бота в аргументы
    )
    print("Планировщик запущен!")

# ...
app.post_init = post_init
app.run_polling() 


