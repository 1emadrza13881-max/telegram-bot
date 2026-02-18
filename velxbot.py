import telebot
from telebot import types
import sqlite3
import time

TOKEN = os.getenv("TOKEN")
OWNER_ID = 7725566652
BOT_NAME = "VELXBot"

bot = telebot.TeleBot(TOKEN)
db = sqlite3.connect("velxbot.db", check_same_thread=False)
cursor = db.cursor()

# ================= DATABASE =================

cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, invites INTEGER DEFAULT 0, vip_until INTEGER DEFAULT 0, daily_views INTEGER DEFAULT 0, last_reset INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS videos (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, file_id TEXT, title TEXT, is_vip INTEGER DEFAULT 0, views INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS force_channels (username TEXT PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
db.commit()

# ================= DEFAULT SETTINGS =================

defaults = {
"force_join":"0",
"daily_limit_enabled":"0",
"daily_limit_user":"3",
"daily_limit_vip":"999",
"invite_enabled":"1",
"invite_required":"10",
"invite_reward_days":"3",
"protect_mode":"1"
}

for k,v in defaults.items():
    cursor.execute("INSERT OR IGNORE INTO settings VALUES (?,?)",(k,v))
db.commit()

def get_setting(k):
    cursor.execute("SELECT value FROM settings WHERE key=?",(k,))
    return cursor.fetchone()[0]

def set_setting(k,v):
    cursor.execute("UPDATE settings SET value=? WHERE key=?",(v,k))
    db.commit()

# ================= UTIL =================

def add_user(uid):
    cursor.execute("INSERT OR IGNORE INTO users(id,last_reset) VALUES (?,?)",(uid,int(time.time())))
    db.commit()

def is_admin(uid):
    if uid == OWNER_ID:
        return True
    cursor.execute("SELECT id FROM admins WHERE id=?",(uid,))
    return cursor.fetchone() is not None

def is_vip(uid):
    cursor.execute("SELECT vip_until FROM users WHERE id=?",(uid,))
    row = cursor.fetchone()
    return row and row[0] > int(time.time())

def check_force_join(uid):
    if get_setting("force_join")=="0":
        return True
    cursor.execute("SELECT username FROM force_channels")
    channels = cursor.fetchall()
    for ch in channels:
        try:
            member = bot.get_chat_member(ch[0], uid)
            if member.status not in ["member","administrator","creator"]:
                return False
        except:
            return False
    return True

def force_join_message(chat_id):
    markup = types.InlineKeyboardMarkup()
    cursor.execute("SELECT username FROM force_channels")
    for ch in cursor.fetchall():
        markup.add(types.InlineKeyboardButton("📢 عضویت",url=f"https://t.me/{ch[0].replace('@','')}"))
    markup.add(types.InlineKeyboardButton("✅ بررسی عضویت",callback_data="check_join"))
    bot.send_message(chat_id,"ابتدا در کانال‌ها عضو شوید 👇",reply_markup=markup)

# ================= START =================

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    add_user(uid)

    args = message.text.split()
    if len(args)>1:
        inviter = int(args[1])
        if inviter != uid and get_setting("invite_enabled")=="1":
            cursor.execute("UPDATE users SET invites=invites+1 WHERE id=?",(inviter,))
            req = int(get_setting("invite_required"))
            cursor.execute("SELECT invites FROM users WHERE id=?",(inviter,))
            invites = cursor.fetchone()[0]
            if invites % req == 0:
                days = int(get_setting("invite_reward_days"))
                cursor.execute("UPDATE users SET vip_until=? WHERE id=?",
                               (int(time.time())+days*86400,inviter))
            db.commit()

    if not check_force_join(uid):
        force_join_message(message.chat.id)
        return

    main_menu(message.chat.id,uid)

# ================= MAIN MENU =================

def main_menu(cid,uid):
    markup = types.InlineKeyboardMarkup()

    cursor.execute("SELECT * FROM categories")
    for c in cursor.fetchall():
        markup.add(types.InlineKeyboardButton(f"📂 {c[1]}",callback_data=f"cat_{c[0]}"))

    markup.add(types.InlineKeyboardButton("🎁 دعوت دوستان",callback_data="invite"))
    markup.add(types.InlineKeyboardButton("👑 VIP",callback_data="vip"))

    if uid==OWNER_ID:
        markup.add(types.InlineKeyboardButton("⚙ پنل مالک",callback_data="owner_panel"))
    elif is_admin(uid):
        markup.add(types.InlineKeyboardButton("⚙ پنل ادمین",callback_data="admin_panel"))

    bot.send_message(cid,f"به {BOT_NAME} خوش اومدی 👑",reply_markup=markup)

# ================= CALLBACK =================

@bot.callback_query_handler(func=lambda call:True)
def callback(call):
    uid = call.from_user.id

    if call.data=="check_join":
        if check_force_join(uid):
            bot.answer_callback_query(call.id,"تایید شد ✅")
            main_menu(call.message.chat.id,uid)
        else:
            bot.answer_callback_query(call.id,"هنوز عضو نشدی ❌")

    elif call.data=="owner_panel" and uid==OWNER_ID:
        owner_panel(call.message)

# ================= OWNER PANEL =================

def owner_panel(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📊 آمار",callback_data="stats"))
    markup.add(types.InlineKeyboardButton("📢 عضویت اجباری",callback_data="force_manage"))
    markup.add(types.InlineKeyboardButton("⚙ تنظیمات کلی",callback_data="settings_manage"))
    markup.add(types.InlineKeyboardButton("📂 مدیریت دسته‌ها",callback_data="cat_manage"))
    bot.send_message(message.chat.id,"👑 پنل مالک پیشرفته",reply_markup=markup)

# ================= FORCE JOIN MANAGE =================

@bot.callback_query_handler(func=lambda call: call.data=="force_manage")
def force_manage(call):
    markup = types.InlineKeyboardMarkup()
    status = "فعال ✅" if get_setting("force_join")=="1" else "غیرفعال ❌"
    markup.add(types.InlineKeyboardButton(f"وضعیت: {status}",callback_data="toggle_force"))
    markup.add(types.InlineKeyboardButton("➕ افزودن کانال",callback_data="add_channel"))
    markup.add(types.InlineKeyboardButton("🗑 حذف کانال",callback_data="del_channel"))
    bot.edit_message_text("مدیریت عضویت اجباری",
                          call.message.chat.id,
                          call.message.message_id,
                          reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data=="toggle_force")
def toggle_force(call):
    new = "0" if get_setting("force_join")=="1" else "1"
    set_setting("force_join",new)
    bot.answer_callback_query(call.id,"وضعیت تغییر کرد")

# ================= RUN =================

print("VELXBot Empire Running 👑🔥")
bot.infinity_polling()
