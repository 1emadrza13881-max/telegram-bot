import os
import telebot
from telebot import types
import sqlite3
import time
import logging

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN not set in Environment Variables")

OWNER_ID = 7725566652
BOT_NAME = "VELXBot"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

logging.basicConfig(level=logging.INFO)

db = sqlite3.connect("velxbot.db", check_same_thread=False)
cursor = db.cursor()

# ================= DATABASE =================

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
id INTEGER PRIMARY KEY,
vip_until INTEGER DEFAULT 0,
daily_views INTEGER DEFAULT 0,
last_reset INTEGER DEFAULT 0,
banned INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS categories (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS videos (
id INTEGER PRIMARY KEY AUTOINCREMENT,
category_id INTEGER,
file_id TEXT,
title TEXT,
is_vip INTEGER DEFAULT 0,
views INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS vip_codes (
code TEXT PRIMARY KEY,
days INTEGER
)
""")

db.commit()

# ================= HELPERS =================

def add_user(uid):
    cursor.execute("INSERT OR IGNORE INTO users(id,last_reset) VALUES (?,?)",
                   (uid,int(time.time())))
    db.commit()

def is_admin(uid):
    return uid == OWNER_ID

def is_banned(uid):
    cursor.execute("SELECT banned FROM users WHERE id=?",(uid,))
    row = cursor.fetchone()
    return row and row[0] == 1

def is_vip(uid):
    cursor.execute("SELECT vip_until FROM users WHERE id=?",(uid,))
    row = cursor.fetchone()
    return row and row[0] > int(time.time())

def reset_daily(uid):
    cursor.execute("SELECT last_reset FROM users WHERE id=?",(uid,))
    row = cursor.fetchone()
    if row and int(time.time()) - row[0] > 86400:
        cursor.execute("UPDATE users SET daily_views=0,last_reset=? WHERE id=?",
                       (int(time.time()),uid))
        db.commit()

def can_watch(uid):
    reset_daily(uid)
    if is_vip(uid):
        return True
    cursor.execute("SELECT daily_views FROM users WHERE id=?",(uid,))
    views = cursor.fetchone()[0]
    return views < 5

def increase_view(uid):
    cursor.execute("UPDATE users SET daily_views=daily_views+1 WHERE id=?",(uid,))
    db.commit()

# ================= START =================

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    add_user(uid)

    if is_banned(uid):
        bot.reply_to(message,"🚫 شما مسدود شده‌اید")
        return

    main_menu(message.chat.id,uid)

# ================= MAIN MENU =================

def main_menu(cid,uid):
    markup = types.InlineKeyboardMarkup()

    cursor.execute("SELECT * FROM categories")
    for c in cursor.fetchall():
        markup.add(
            types.InlineKeyboardButton(
                "📂 " + c[1],
                callback_data="cat_" + str(c[0])
            )
        )

    markup.add(types.InlineKeyboardButton("👑 فعالسازی VIP",callback_data="vip_info"))

    if is_admin(uid):
        markup.add(types.InlineKeyboardButton("⚙ پنل مدیریت",callback_data="admin_panel"))

    bot.send_message(cid,"به " + BOT_NAME + " خوش اومدی 👑",reply_markup=markup)

# ================= RUN =================

print("Bot Running...")
bot.infinity_polling()
# ================= CATEGORY OPEN =================

@bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
def open_category(call):
    cid = call.message.chat.id
    uid = call.from_user.id
    cat_id = int(call.data.split("_")[1])

    cursor.execute("SELECT * FROM videos WHERE category_id=?", (cat_id,))
    videos = cursor.fetchall()

    if not videos:
        bot.answer_callback_query(call.id,"ویدیویی وجود ندارد")
        return

    for v in videos:
        video_id = v[0]
        file_id = v[2]
        title = v[3]
        is_vip_video = v[4]

        if is_vip_video == 1 and not is_vip(uid):
            bot.send_message(cid,"🔒 این ویدیو مخصوص VIP است")
            continue

        if not can_watch(uid):
            bot.send_message(cid,"❌ محدودیت روزانه شما تمام شده")
            return

        bot.send_video(cid,file_id,caption=title)
        increase_view(uid)

# ================= VIP INFO =================

@bot.callback_query_handler(func=lambda call: call.data=="vip_info")
def vip_info(call):
    bot.send_message(call.message.chat.id,
                     "برای فعالسازی VIP دستور زیر را بزن:\n/vip CODE")

@bot.message_handler(commands=['vip'])
def activate_vip(message):
    uid = message.from_user.id
    parts = message.text.split()

    if len(parts) < 2:
        bot.reply_to(message,"فرمت صحیح:\n/vip CODE")
        return

    code = parts[1]

    cursor.execute("SELECT days FROM vip_codes WHERE code=?", (code,))
    row = cursor.fetchone()

    if not row:
        bot.reply_to(message,"❌ کد نامعتبر است")
        return

    days = row[0]
    vip_until = int(time.time()) + days*86400

    cursor.execute("UPDATE users SET vip_until=? WHERE id=?", (vip_until, uid))
    cursor.execute("DELETE FROM vip_codes WHERE code=?", (code,))
    db.commit()

    bot.reply_to(message,"👑 VIP فعال شد")

# ================= ADMIN PANEL =================

@bot.callback_query_handler(func=lambda call: call.data=="admin_panel")
def admin_panel(call):
    if not is_admin(call.from_user.id):
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ افزودن دسته",callback_data="add_cat"))
    markup.add(types.InlineKeyboardButton("➕ افزودن ویدیو",callback_data="add_video"))
    markup.add(types.InlineKeyboardButton("👑 ساخت کد VIP",callback_data="make_vip"))
    markup.add(types.InlineKeyboardButton("📊 آمار",callback_data="stats"))
    markup.add(types.InlineKeyboardButton("📢 پیام همگانی",callback_data="broadcast"))
    markup.add(types.InlineKeyboardButton("🚫 بن کاربر",callback_data="ban_user"))
    markup.add(types.InlineKeyboardButton("💾 بکاپ دیتابیس",callback_data="backup"))

    bot.send_message(call.message.chat.id,"پنل مدیریت 👑",reply_markup=markup)

# ================= ADD CATEGORY =================

@bot.callback_query_handler(func=lambda call: call.data=="add_cat")
def add_cat(call):
    msg = bot.send_message(call.message.chat.id,"نام دسته را بفرست:")
    bot.register_next_step_handler(msg,save_cat)

def save_cat(message):
    cursor.execute("INSERT INTO categories(name) VALUES (?)",(message.text,))
    db.commit()
    bot.reply_to(message,"✅ دسته اضافه شد")

# ================= ADD VIDEO =================

temp_video = {}

@bot.callback_query_handler(func=lambda call: call.data=="add_video")
def add_video(call):
    msg = bot.send_message(call.message.chat.id,"ویدیو را ارسال کن:")
    bot.register_next_step_handler(msg,get_video_file)

def get_video_file(message):
    if not message.video:
        bot.reply_to(message,"فقط ویدیو بفرست")
        return
    temp_video["file_id"] = message.video.file_id
    msg = bot.send_message(message.chat.id,"عنوان ویدیو:")
    bot.register_next_step_handler(msg,get_video_title)

def get_video_title(message):
    temp_video["title"] = message.text
    cursor.execute("SELECT * FROM categories")
    cats = cursor.fetchall()

    markup = types.InlineKeyboardMarkup()
    for c in cats:
        markup.add(types.InlineKeyboardButton(c[1],callback_data="setcat_"+str(c[0])))

    bot.send_message(message.chat.id,"دسته را انتخاب کن:",reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("setcat_"))
def save_video(call):
    cat_id = int(call.data.split("_")[1])

    cursor.execute("""
    INSERT INTO videos(category_id,file_id,title)
    VALUES (?,?,?)
    """,(cat_id,temp_video["file_id"],temp_video["title"]))
    db.commit()

    bot.send_message(call.message.chat.id,"✅ ویدیو ذخیره شد")

# ================= MAKE VIP CODE =================

@bot.callback_query_handler(func=lambda call: call.data=="make_vip")
def make_vip(call):
    msg = bot.send_message(call.message.chat.id,"کد و تعداد روز را بفرست:\nمثال:\nVELX7 7")
    bot.register_next_step_handler(msg,save_vip_code)

def save_vip_code(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message,"فرمت اشتباه")
        return
    code = parts[0]
    days = int(parts[1])
    cursor.execute("INSERT OR REPLACE INTO vip_codes VALUES (?,?)",(code,days))
    db.commit()
    bot.reply_to(message,"✅ کد ساخته شد")

# ================= STATS =================

@bot.callback_query_handler(func=lambda call: call.data=="stats")
def stats(call):
    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM videos")
    videos = cursor.fetchone()[0]
    bot.send_message(call.message.chat.id,
                     "👥 کاربران: " + str(users) +
                     "\n🎬 ویدیوها: " + str(videos))

# ================= BROADCAST =================

@bot.callback_query_handler(func=lambda call: call.data=="broadcast")
def broadcast(call):
    msg = bot.send_message(call.message.chat.id,"پیام همگانی را بفرست:")
    bot.register_next_step_handler(msg,send_broadcast)

def send_broadcast(message):
    cursor.execute("SELECT id FROM users")
    users = cursor.fetchall()
    for u in users:
        try:
            bot.send_message(u[0],message.text
bot.send_message(u[0],message.text)
        except:
            pass
    bot.reply_to(message,"✅ ارسال شد")

# ================= BAN USER =================

@bot.callback_query_handler(func=lambda call: call.data=="ban_user")
def ban_user(call):
    msg = bot.send_message(call.message.chat.id,"آیدی عددی کاربر:")
    bot.register_next_step_handler(msg,do_ban)

def do_ban(message):
    uid = int(message.text)
    cursor.execute("UPDATE users SET banned=1 WHERE id=?",(uid,))
    db.commit()
    bot.reply_to(message,"🚫 کاربر بن شد")

# ================= BACKUP =================

@bot.callback_query_handler(func=lambda call: call.data=="backup")
def backup(call):
    bot.send_document(call.message.chat.id,open("velxbot.db","rb"))
