import logging
import psycopg2
from flask import Flask
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import os
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Flask fake endpoint (keeps Render alive)
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Bot Running"

# Database connection
conn = psycopg2.connect(DATABASE_URL, sslmode="require")
cursor = conn.cursor()

# Runtime memory (ONLY matchmaking state)
waiting_users = []
active_chats = {}


# ✅ DATABASE HELPERS

def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    return cursor.fetchone()

def create_user(user_id):
    cursor.execute(
        "INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING",
        (user_id,)
    )
    conn.commit()

def set_gender(user_id, gender):
    cursor.execute(
        "UPDATE users SET gender = %s WHERE user_id = %s",
        (gender, user_id)
    )
    conn.commit()

def add_report(user_id):
    cursor.execute(
        "UPDATE users SET reports = reports + 1 WHERE user_id = %s",
        (user_id,)
    )
    conn.commit()

def get_reports(user_id):
    cursor.execute("SELECT reports FROM users WHERE user_id = %s", (user_id,))
    return cursor.fetchone()[0]

def ban_user(user_id):
    ban_until = datetime.utcnow() + timedelta(hours=24)
    cursor.execute(
        "UPDATE users SET ban_until = %s WHERE user_id = %s",
        (ban_until, user_id)
    )
    conn.commit()
    return ban_until

def is_banned(user_id):
    cursor.execute(
        "SELECT ban_until FROM users WHERE user_id = %s",
        (user_id,)
    )
    result = cursor.fetchone()
    if result and result[0]:
        return datetime.utcnow() < result[0]
    return False


# ✅ KEYBOARDS

gender_keyboard = ReplyKeyboardMarkup(
    [["Male", "Female"]],
    resize_keyboard=True
)

main_keyboard = ReplyKeyboardMarkup(
    [["Find Partner"], ["Profile", "Settings"]],
    resize_keyboard=True
)

chat_keyboard = ReplyKeyboardMarkup(
    [["Next", "End"]],
    resize_keyboard=True
)

report_keyboard = ReplyKeyboardMarkup(
    [["Report 🚫", "Next"]],
    resize_keyboard=True
)

settings_keyboard = ReplyKeyboardMarkup(
    [["Report 🚫"], ["Match Male 💎", "Match Female 💎"], ["Back"]],
    resize_keyboard=True
)


# ✅ COMMANDS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    create_user(user_id)

    if is_banned(user_id):
        await send_ban_message(update, user_id)
        return

    await update.message.reply_text(
        "👋 Welcome!\n\nPlease select your gender:",
        reply_markup=gender_keyboard
    )


async def send_ban_message(update, user_id):
    cursor.execute(
        "SELECT ban_until FROM users WHERE user_id = %s",
        (user_id,)
    )
    ban_until = cursor.fetchone()[0]

    await update.message.reply_text(
        f"You have been banned due to rules violation.\n\n"
        f"It is prohibited in the bot to sell anything, advertise, send invitations, share links, or ask for money.\n\n"
        f"🔞 Users sharing unwanted content will also be banned.\n\n"
        f"You will be able to use the chat again at:\n{ban_until}",
        reply_markup=ReplyKeyboardRemove()
    )


# ✅ MESSAGE HANDLER

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    create_user(user_id)

    if is_banned(user_id):
        await send_ban_message(update, user_id)
        return

    # Gender selection
    if text in ["Male", "Female"]:
        set_gender(user_id, text)

        await update.message.reply_text(
            "✅ Gender saved!",
            reply_markup=main_keyboard
        )
        return

    # Find partner
    if text == "Find Partner":
        await find_partner(update, context)
        return

    # Next
    if text == "Next":
        await next_partner(update, context)
        return

    # End
    if text == "End":
        await end_chat(update, context)
        return

    # Profile
    if text == "Profile":
        await show_profile(update)
        return

    # Settings
    if text == "Settings":
        await update.message.reply_text(
            "⚙ Settings:",
            reply_markup=settings_keyboard
        )
        return

    # Back
    if text == "Back":
        await update.message.reply_text(
            "⬅ Back to menu",
            reply_markup=main_keyboard
        )
        return

    # Premium buttons
    if "💎" in text:
        await update.message.reply_text("💎 Premium required")
        return

    # Report logic
    if text.startswith("Report"):
        await process_report(update, context)
        return

    # Chat relay
    if user_id in active_chats:
        partner_id = active_chats[user_id]
        await context.bot.send_message(partner_id, text)


# ✅ MATCHING SYSTEM

async def find_partner(update, context):
    user_id = update.effective_user.id

    if user_id in active_chats:
        await update.message.reply_text("Already in chat")
        return

    if user_id not in waiting_users:
        waiting_users.append(user_id)

    await update.message.reply_text("🔎 Finding partner...")


async def next_partner(update, context):
    await end_chat(update, context)
    await find_partner(update, context)


async def end_chat(update, context):
    user_id = update.effective_user.id

    if user_id in active_chats:
        partner_id = active_chats[user_id]

        del active_chats[user_id]
        del active_chats[partner_id]

        await context.bot.send_message(
            partner_id,
            "🚫 Your partner has disconnected.",
            reply_markup=report_keyboard
        )

        await update.message.reply_text(
            "Chat ended.",
            reply_markup=main_keyboard
        )


async def process_report(update, context):
    user_id = update.effective_user.id

    # Report previous partner ONLY
    if user_id in active_chats:
        return

    context.user_data.setdefault("last_partner", None)
    partner_id = context.user_data["last_partner"]

    if not partner_id:
        await update.message.reply_text("Nothing to report")
        return

    add_report(partner_id)
    reports = get_reports(partner_id)

    if reports >= 10:
        ban_until = ban_user(partner_id)

        await context.bot.send_message(
            partner_id,
            f"You have been banned until {ban_until}"
        )

    await update.message.reply_text("✅ Report submitted")


# ✅ PROFILE

async def show_profile(update):
    user_id = update.effective_user.id

    cursor.execute(
        "SELECT gender, premium FROM users WHERE user_id = %s",
        (user_id,)
    )
    gender, premium = cursor.fetchone()

    await update.message.reply_text(
        f"👤 Profile\n\nGender: {gender}\nPremium: {premium}",
        reply_markup=main_keyboard
    )


# ✅ MAIN

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT, handle_message))

    print("Bot Running with PostgreSQL...")
    application.run_polling()


if __name__ == "__main__":
    main()
