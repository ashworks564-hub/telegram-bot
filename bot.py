import os
import psycopg2
from datetime import datetime, timedelta
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.environ.get("TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL, sslmode="require")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    gender TEXT,
    reports INT DEFAULT 0,
    banned_until TIMESTAMP
)
""")
conn.commit()

waiting_queue = []
active_chats = {}
last_partner = {}

# ---------------- KEYBOARDS ----------------

gender_keyboard = ReplyKeyboardMarkup(
    [["👦 Male", "👧 Female"]],
    resize_keyboard=True
)

main_menu = ReplyKeyboardMarkup(
    [["🔍 Find Partner"], ["👤 Profile", "⚙ Settings"]],
    resize_keyboard=True
)

chat_menu = ReplyKeyboardMarkup(
    [["⏭ Next", "❌ End"]],
    resize_keyboard=True
)

after_disconnect_menu = ReplyKeyboardMarkup(
    [["🚨 Report", "⏭ Next"]],
    resize_keyboard=True
)

settings_menu = ReplyKeyboardMarkup(
    [["🚨 Report"], ["💎 Match with Male", "💎 Match with Female"], ["⬅ Back"]],
    resize_keyboard=True
)

# ---------------- DATABASE HELPERS ----------------

def get_user(user_id):
    cur.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    return cur.fetchone()

def create_user(user_id):
    cur.execute("INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
    conn.commit()

def set_gender(user_id, gender):
    cur.execute("UPDATE users SET gender=%s WHERE user_id=%s", (gender, user_id))
    conn.commit()

def add_report(user_id):
    cur.execute("UPDATE users SET reports = reports + 1 WHERE user_id=%s", (user_id,))
    conn.commit()

def ban_user(user_id):
    banned_until = datetime.utcnow() + timedelta(hours=24)
    cur.execute("UPDATE users SET banned_until=%s WHERE user_id=%s", (banned_until, user_id))
    conn.commit()
    return banned_until

def is_banned(user):
    if user[3]:
        return user[3] > datetime.utcnow()
    return False

# ---------------- BOT LOGIC ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    create_user(user_id)

    user = get_user(user_id)

    if is_banned(user):
        await update.message.reply_text("🚫 You are temporarily banned.")
        return

    if not user[1]:
        await update.message.reply_text(
            "👋 Welcome!\n\nPlease select your gender:",
            reply_markup=gender_keyboard
        )
    else:
        await update.message.reply_text("Main Menu:", reply_markup=main_menu)

# ---------------- MATCHING ----------------

async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user[1]:
        await update.message.reply_text("⚠ Select gender first.")
        return

    if user_id in active_chats:
        await update.message.reply_text("⚠ Already in chat.")
        return

    await update.message.reply_text("🔎 Finding partner for you...")

    if waiting_queue:
        partner = waiting_queue.pop(0)

        active_chats[user_id] = partner
        active_chats[partner] = user_id

        last_partner[user_id] = partner
        last_partner[partner] = user_id

        await context.bot.send_message(user_id, "🤝 Partner Found!", reply_markup=chat_menu)
        await context.bot.send_message(partner, "🤝 Partner Found!", reply_markup=chat_menu)

    else:
        waiting_queue.append(user_id)

# ---------------- CHAT CONTROL ----------------

async def next_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in active_chats:
        partner = active_chats[user_id]

        del active_chats[user_id]
        del active_chats[partner]

        await context.bot.send_message(
            partner,
            "🚫 Your partner has disconnected.",
            reply_markup=after_disconnect_menu
        )

    await find_partner(update, context)

async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in active_chats:
        partner = active_chats[user_id]

        del active_chats[user_id]
        del active_chats[partner]

        await context.bot.send_message(
            partner,
            "🚫 Your partner has disconnected.",
            reply_markup=after_disconnect_menu
        )

    await update.message.reply_text("Main Menu:", reply_markup=main_menu)

# ---------------- REPORT ----------------

async def report_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in last_partner:
        await update.message.reply_text("⚠ No partner to report.")
        return

    reported = last_partner[user_id]

    add_report(reported)
    user = get_user(reported)

    if user[2] >= 10:
        banned_until = ban_user(reported)

        await context.bot.send_message(
            reported,
            f"🚫 You are banned until:\n{banned_until}"
        )

    await update.message.reply_text("✅ Report submitted.", reply_markup=main_menu)

# ---------------- PROFILE ----------------

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    await update.message.reply_text(
        f"👤 Your Profile\n\nGender: {user[1]}\nReports: {user[2]}",
        reply_markup=main_menu
    )

# ---------------- SETTINGS ----------------

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙ Settings\n\nSelect option:",
        reply_markup=settings_menu
    )

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "👦 Male":
        set_gender(user_id, "Male")
        await update.message.reply_text("✅ Gender set to Male", reply_markup=main_menu)
        return

    if text == "👧 Female":
        set_gender(user_id, "Female")
        await update.message.reply_text("✅ Gender set to Female", reply_markup=main_menu)
        return

    if text == "🔍 Find Partner":
        await find_partner(update, context)
        return

    if text == "⏭ Next":
        await next_partner(update, context)
        return

    if text == "❌ End":
        await end_chat(update, context)
        return

    if text == "🚨 Report":
        await report_user(update, context)
        return

    if text == "👤 Profile":
        await profile(update, context)
        return

    if text == "⚙ Settings":
        await settings(update, context)
        return

    if text.startswith("💎"):
        await update.message.reply_text("💎 Premium Required")
        return

    if user_id in active_chats:
        partner = active_chats[user_id]
        await context.bot.send_message(partner, text)

# ---------------- FLASK ----------------

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Running"

# ---------------- MAIN ----------------

if __name__ == "__main__":
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))

    print("Bot Running...")

    application.run_polling()
