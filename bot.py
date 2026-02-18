import os
import psycopg2
import threading
from datetime import datetime, timedelta

from flask import Flask
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================= DATABASE =================

DATABASE_URL = os.environ.get("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL, sslmode="require")
cursor = conn.cursor()

def create_user(user_id):
    cursor.execute(
        "INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING",
        (user_id,),
    )
    conn.commit()

def set_gender(user_id, gender):
    cursor.execute(
        "UPDATE users SET gender=%s WHERE user_id=%s",
        (gender, user_id),
    )
    conn.commit()

def get_user(user_id):
    cursor.execute("SELECT gender, premium, reports, banned_until FROM users WHERE user_id=%s", (user_id,))
    return cursor.fetchone()

def add_report(user_id):
    cursor.execute("UPDATE users SET reports = reports + 1 WHERE user_id=%s", (user_id,))
    conn.commit()

def ban_user(user_id):
    banned_until = datetime.utcnow() + timedelta(hours=24)
    cursor.execute("UPDATE users SET banned_until=%s WHERE user_id=%s", (banned_until, user_id))
    conn.commit()
    return banned_until

# ================= FLASK (KEEPALIVE) =================

app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Bot Alive"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask).start()

# ================= BOT LOGIC =================

waiting_users = []
active_chats = {}
can_report = {}

# ================= MENUS =================

main_menu = ReplyKeyboardMarkup(
    [["🔎 Find Partner"], ["👤 Profile", "⚙️ Settings"]],
    resize_keyboard=True,
)

gender_menu = ReplyKeyboardMarkup(
    [["👨 Male", "👩 Female"]],
    resize_keyboard=True,
)

chat_menu = ReplyKeyboardMarkup(
    [["⏭ NEXT", "❌ END"]],
    resize_keyboard=True,
)

settings_menu = ReplyKeyboardMarkup(
    [["🚨 Report"], ["💎 Match Male", "💎 Match Female"], ["⬅️ Back"]],
    resize_keyboard=True,
)

# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    create_user(user_id)

    user = get_user(user_id)

    # Check ban
    if user and user[3]:
        if user[3] > datetime.utcnow():
            await update.message.reply_text(
                f"⛔ You are banned until {user[3]}"
            )
            return

    await update.message.reply_text(
        "👋 Welcome!\n\nPlease select your gender:",
        reply_markup=gender_menu,
    )

# ================= GENDER =================

async def handle_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if update.message.text == "👨 Male":
        set_gender(user_id, "Male")
    elif update.message.text == "👩 Female":
        set_gender(user_id, "Female")
    else:
        return

    await update.message.reply_text(
        "✅ Gender Saved!",
        reply_markup=main_menu,
    )

# ================= FIND PARTNER =================

async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in active_chats:
        await update.message.reply_text("⚠️ Already in chat.")
        return

    if user_id in waiting_users:
        await update.message.reply_text("⏳ Searching...")
        return

    waiting_users.append(user_id)

    await update.message.reply_text("🔎 Finding partner...")

    if len(waiting_users) >= 2:
        user1 = waiting_users.pop(0)
        user2 = waiting_users.pop(0)

        if user1 == user2:
            waiting_users.append(user1)
            return

        active_chats[user1] = user2
        active_chats[user2] = user1

        await context.bot.send_message(user1, "🤝 Partner Found!", reply_markup=chat_menu)
        await context.bot.send_message(user2, "🤝 Partner Found!", reply_markup=chat_menu)

# ================= NEXT =================

async def next_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in active_chats:
        return

    partner = active_chats[user_id]

    del active_chats[user_id]
    del active_chats[partner]

    can_report[user_id] = partner

    await context.bot.send_message(partner, "🚫 Your partner left.")
    await update.message.reply_text("🔎 Finding new partner...")

    waiting_users.append(user_id)

# ================= END =================

async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in active_chats:
        return

    partner = active_chats[user_id]

    del active_chats[user_id]
    del active_chats[partner]

    can_report[user_id] = partner

    await context.bot.send_message(partner, "❌ Chat Ended.")
    await update.message.reply_text("❌ Chat Ended.", reply_markup=main_menu)

# ================= REPORT =================

async def report_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in can_report:
        await update.message.reply_text("⚠️ No user to report.")
        return

    reported_user = can_report[user_id]
    add_report(reported_user)

    user_data = get_user(reported_user)

    if user_data[2] >= 10:
        banned_until = ban_user(reported_user)

        await context.bot.send_message(
            reported_user,
            f"""🚨 You have been banned.

You violated bot rules.

You will be unbanned at:
{banned_until} UTC"""
        )

    await update.message.reply_text("✅ Report Submitted.")

    del can_report[user_id]

# ================= PROFILE =================

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        return

    premium_status = "Yes 💎" if user[1] else "No"

    await update.message.reply_text(
        f"""👤 Your Profile

Gender: {user[0]}
Premium: {premium_status}""",
        reply_markup=main_menu,
    )

# ================= SETTINGS =================

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ Settings",
        reply_markup=settings_menu,
    )

async def premium_required(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💎 Premium Required")

# ================= MESSAGE RELAY =================

async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in active_chats:
        return

    partner = active_chats[user_id]

    await context.bot.send_message(partner, update.message.text)

# ================= MAIN =================

TOKEN = os.environ.get("TOKEN")

app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.Regex("👨 Male|👩 Female"), handle_gender))
app.add_handler(MessageHandler(filters.Regex("🔎 Find Partner"), find_partner))
app.add_handler(MessageHandler(filters.Regex("⏭ NEXT"), next_chat))
app.add_handler(MessageHandler(filters.Regex("❌ END"), end_chat))
app.add_handler(MessageHandler(filters.Regex("🚨 Report"), report_user))
app.add_handler(MessageHandler(filters.Regex("👤 Profile"), profile))
app.add_handler(MessageHandler(filters.Regex("⚙️ Settings"), settings))
app.add_handler(MessageHandler(filters.Regex("💎 Match Male|💎 Match Female"), premium_required))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, relay_message))

print("Bot Running...")

app.run_polling()
