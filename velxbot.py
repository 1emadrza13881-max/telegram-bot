import os
import sqlite3
import telebot
from telebot import types
from datetime import datetime, timedelta
import threading

# ==================== CONFIG ====================
TOKEN = os.getenv("TOKEN")
OWNER_ID = 7725566652
DB_NAME = "velxbot.db"

bot = telebot.TeleBot(TOKEN)

# ==================== DATABASE ====================
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    vip INTEGER DEFAULT 0,
    last_use TIMESTAMP,
    daily_count INTEGER DEFAULT 0
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS channels (
    channel TEXT PRIMARY KEY
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    category TEXT,
    vip INTEGER DEFAULT 0,
    popular INTEGER DEFAULT 0,
    file_id TEXT
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS vip_codes (
    code TEXT PRIMARY KEY,
    days INTEGER DEFAULT 0
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)""")

conn.commit()

# ==================== UTIL ====================
def is_member(user_id):
    cursor.execute("SELECT channel FROM channels")
    channels = cursor.fetchall()
    for ch in channels:
        try:
            member = bot.get_chat_member(ch[0], user_id)
            if member.status in ["left", "kicked"]:
                return False
        except:
            return False
    return True

def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    return cursor.fetchone()

def register_user(message):
    if not get_user(message.from_user.id):
        cursor.execute("INSERT INTO users(user_id, username) VALUES(?,?)",
                       (message.from_user.id, message.from_user.username))
        conn.commit()

def check_limit(user_id):
    cursor.execute("SELECT vip, daily_count, last_use FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    if not user:
        return True
    vip, daily_count, last_use = user
    daily_limit = int(get_setting("free_limit") or 5)
    now = datetime.now()
    if last_use:
        last_use_dt = datetime.fromisoformat(last_use)
        if last_use_dt.date() != now.date():
            daily_count = 0
            cursor.execute("UPDATE users SET daily_count=0 WHERE user_id=?", (user_id,))
            conn.commit()
    if vip:
        return True
    return daily_count < daily_limit

def increment_use(user_id):
    cursor.execute("UPDATE users SET daily_count=daily_count+1, last_use=? WHERE user_id=?",
                   (datetime.now().isoformat(), user_id))
    conn.commit()

def get_setting(key):
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = cursor.fetchone()
    return res[0] if res else None

def set_setting(key, value):
    cursor.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key,value))
    conn.commit()

# ==================== HANDLERS ====================
@bot.message_handler(commands=["start"])
def start(message):
    register_user(message)
    if not is_member(message.from_user.id):
        bot.send_message(message.chat.id,
                         "لطفا ابتدا در کانال‌های عضویت عضو شوید و دوباره /start بزنید.")
        return
    show_main_panel(message)

def show_main_panel(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎬 دسته‌بندی‌ها", callback_data="categories"))
    markup.add(types.InlineKeyboardButton("🔥 محبوب‌ها", callback_data="popular"))
    markup.add(types.InlineKeyboardButton("💎 VIP", callback_data="vip"))
    markup.add(types.InlineKeyboardButton("🔎 جستجو", callback_data="search"))
    bot.send_message(message.chat.id, "پنل اصلی VELXBot:", reply_markup=markup)

# ==================== CALLBACK HANDLER ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "categories":
        bot.answer_callback_query(call.id, "دسته‌بندی‌ها را انتخاب کنید")
        # TODO: list categories
    elif call.data == "popular":
        bot.answer_callback_query(call.id, "محبوب‌ها را نمایش می‌دهیم")
        # TODO: list popular videos
    elif call.data == "vip":
        bot.answer_callback_query(call.id, "وارد بخش VIP شوید")
        # TODO: VIP panel
    elif call.data == "search":
        bot.answer_callback_query(call.id, "متن را ارسال کنید تا جستجو کنیم")
        # TODO: handle search

# ==================== ADMIN PANEL ====================
def is_owner(user_id):
    return user_id == OWNER_ID

@bot.message_handler(func=lambda m: m.from_user.id == OWNER_ID, commands=["admin"])
def admin_panel(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📊 آمار کاربران", "📢 ارسال همگانی")
    markup.row("🎬 مدیریت ویدیو", "🗂 دسته‌بندی‌ها")
    markup.row("💎 مدیریت VIP", "⚙️ محدودیت‌ها")
    markup.row("🔒 مدیریت کانال‌ها")
    bot.send_message(message.chat.id, "پنل ادمین VELXBot:", reply_markup=markup)

# ==================== BACKGROUND TASK ====================
def reset_daily_counts():
    while True:
        now = datetime.now()
        next_reset = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
        delta = (next_reset - now).total_seconds()
        threading.Event().wait(delta)
        cursor.execute("UPDATE users SET daily_count=0")
        conn.commit()

threading.Thread(target=reset_daily_counts, daemon=True).start()

# ==================== START BOT ====================
if __name__ == "__main__":
    print("VELXBot Service Running 🔥")
    bot.infinity_polling()
