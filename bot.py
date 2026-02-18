import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import threading
from flask import Flask

TOKEN = os.getenv("7712667824:AAGGrpHNTC8F-EN6D-86dx4TGx60nC8M7po")  # ← مهم: از env بگیره
ADMIN_ID = 7725566652

bot = telebot.TeleBot(TOKEN)

# ---------------- DATABASE ----------------
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS banned (user_id INTEGER PRIMARY KEY)")
cursor.execute("""CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    link TEXT
)""")
cursor.execute("""CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)""")
conn.commit()

def get_setting(key, default):
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    data = cursor.fetchone()
    return data[0] if data else default

def set_setting(key, value):
    cursor.execute("REPLACE INTO settings (key,value) VALUES (?,?)", (key,str(value)))
    conn.commit()

if not get_setting("force_join", None):
    set_setting("force_join", "on")
if not get_setting("delete_time", None):
    set_setting("delete_time", "30")

# ---------------- CHECK JOIN ----------------
def check_join(user_id):
    if get_setting("force_join","on") == "off":
        return True

    cursor.execute("SELECT chat_id FROM channels")
    channels = cursor.fetchall()

    for ch in channels:
        try:
            member = bot.get_chat_member(ch[0], user_id)
            if member.status not in ["member","administrator","creator"]:
                return False
        except:
            return False

    return True

# ---------------- START ----------------
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id

    cursor.execute("SELECT user_id FROM banned WHERE user_id=?", (user_id,))
    if cursor.fetchone():
        bot.send_message(user_id,"🚫 شما مسدود هستید")
        return

    if not check_join(user_id):
        markup = InlineKeyboardMarkup()
        cursor.execute("SELECT link FROM channels")
        for ch in cursor.fetchall():
            markup.add(InlineKeyboardButton("📢 عضویت در کانال", url=ch[0]))
        markup.add(InlineKeyboardButton("✅ بررسی عضویت", callback_data="check_join"))

        bot.send_message(user_id,
                         "🔒 برای استفاده باید عضو کانال‌ها شوید",
                         reply_markup=markup)
        return

    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)",(user_id,))
    conn.commit()

    bot.send_message(user_id,"🎬 خوش آمدی به ربات حرفه‌ای!")

# ---------------- CALLBACK ----------------
@bot.callback_query_handler(func=lambda call: call.data=="check_join")
def recheck(call):
    if check_join(call.from_user.id):
        bot.answer_callback_query(call.id,"✅ تایید شد")
        bot.send_message(call.from_user.id,"🎉 حالا میتونی استفاده کنی")
    else:
        bot.answer_callback_query(call.id,"❌ هنوز عضو نشدی",show_alert=True)

# ---------------- ADMIN PANEL ----------------
@bot.message_handler(commands=['panel'])
def panel(message):
    if message.from_user.id != ADMIN_ID:
        return

    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("➕ افزودن کانال",callback_data="add_channel"))
    markup.row(InlineKeyboardButton("📋 لیست کانال‌ها",callback_data="list_channels"))
    markup.row(InlineKeyboardButton("🔄 فعال/غیرفعال اد اجباری",callback_data="toggle_force"))
    markup.row(InlineKeyboardButton("⏱ تغییر تایمر حذف",callback_data="change_timer"))
    markup.row(InlineKeyboardButton("📊 آمار",callback_data="stats"))
    markup.row(InlineKeyboardButton("📢 پیام همگانی",callback_data="broadcast"))
    markup.row(InlineKeyboardButton("⛔ بن کاربر",callback_data="ban_user"))

    bot.send_message(message.chat.id,"👑 پنل مدیریت VIP",reply_markup=markup)

# ---------------- ADMIN CALLBACKS ----------------
@bot.callback_query_handler(func=lambda call: call.from_user.id==ADMIN_ID)
def admin_callbacks(call):

    if call.data=="add_channel":
        msg=bot.send_message(call.message.chat.id,"لینک کانال رو بفرست")
        bot.register_next_step_handler(msg,get_link)

    elif call.data=="list_channels":
        cursor.execute("SELECT id,link FROM channels")
        data=cursor.fetchall()
        if not data:
            bot.send_message(call.message.chat.id,"لیست خالیه")
            return
        text="📋 لیست کانال‌ها:\n\n"
        for ch in data:
            text+=f"{ch[0]}. {ch[1]}\n"
        bot.send_message(call.message.chat.id,text)

    elif call.data=="toggle_force":
        current=get_setting("force_join","on")
        new="off" if current=="on" else "on"
        set_setting("force_join",new)
        bot.send_message(call.message.chat.id,f"اد اجباری {new}")

    elif call.data=="change_timer":
        msg=bot.send_message(call.message.chat.id,"چند ثانیه؟")
        bot.register_next_step_handler(msg,set_timer)

    elif call.data=="stats":
        cursor.execute("SELECT COUNT(*) FROM users")
        users_count=cursor.fetchone()[0]
        bot.send_message(call.message.chat.id,f"👥 کاربران: {users_count}")

    elif call.data=="broadcast":
        msg=bot.send_message(call.message.chat.id,"پیام رو بفرست")
        bot.register_next_step_handler(msg,send_broadcast)

    elif call.data=="ban_user":
        msg=bot.send_message(call.message.chat.id,"آیدی کاربر رو بفرست")
        bot.register_next_step_handler(msg,ban_user)

# ---------------- FUNCTIONS ----------------
def get_link(message):
    link=message.text.strip()
    msg=bot.send_message(message.chat.id,"آیدی عددی کانال رو بفرست")
    bot.register_next_step_handler(msg,save_channel,link)

def save_channel(message,link):
    try:
        chat_id=int(message.text.strip())
        cursor.execute("INSERT INTO channels (chat_id,link) VALUES (?,?)",(chat_id,link))
        conn.commit()
        bot.send_message(message.chat.id,"✅ ذخیره شد")
    except:
        bot.send_message(message.chat.id,"❌ خطا")

def set_timer(message):
    try:
        set_setting("delete_time",message.text.strip())
        bot.send_message(message.chat.id,"✅ تنظیم شد")
    except:
        bot.send_message(message.chat.id,"عدد وارد کن")

def send_broadcast(message):
    cursor.execute("SELECT user_id FROM users")
    users=cursor.fetchall()
    for u in users:
        try:
            bot.send_message(u[0],message.text)
        except:
            pass
    bot.send_message(message.chat.id,"✅ ارسال شد")

def ban_user(message):
    try:
        user_id=int(message.text.strip())
        cursor.execute("INSERT OR IGNORE INTO banned (user_id) VALUES (?)",(user_id,))
        conn.commit()
        bot.send_message(message.chat.id,"🚫 بن شد")
    except:
        bot.send_message(message.chat.id,"❌ خطا")

# ---------------- FLASK FOR RENDER FREE ----------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_bot():
    bot.infinity_polling()

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
