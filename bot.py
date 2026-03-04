import os
import threading
import psycopg2
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")


# ---------------- DATABASE ---------------- #

def db():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        gender TEXT,
        reports INTEGER DEFAULT 0,
        premium BOOLEAN DEFAULT FALSE,
        banned BOOLEAN DEFAULT FALSE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS waiting_users (
        user_id BIGINT PRIMARY KEY
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS active_chats (
        user1 BIGINT,
        user2 BIGINT
    )
    """)

    conn.commit()
    conn.close()


init_db()


# ---------------- FLASK SERVER ---------------- #

app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Bot Alive"


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)


threading.Thread(target=run_flask).start()


# ---------------- KEYBOARDS ---------------- #

gender_keyboard = ReplyKeyboardMarkup(
    [["👦 Male", "👧 Female"]],
    resize_keyboard=True
)

main_menu_keyboard = ReplyKeyboardMarkup(
    [["🔎 Find Partner"],
     ["👤 Profile", "⚙ Settings"],
     ["💎 Premium"]],
    resize_keyboard=True
)


# ---------------- START ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    conn = db()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING",
        (user_id,)
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(
        "⚡ Welcome to Chatx99\n\nChoose your gender:",
        reply_markup=gender_keyboard
    )


# ---------------- GENDER ---------------- #

async def set_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    text = update.message.text

    gender = "Male" if "Male" in text else "Female"

    conn = db()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET gender=%s WHERE user_id=%s",
        (gender, user_id)
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Gender set to {gender}",
        reply_markup=main_menu_keyboard
    )


# ---------------- FIND PARTNER ---------------- #

async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    conn = db()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO waiting_users (user_id) VALUES (%s) ON CONFLICT DO NOTHING",
        (user_id,)
    )

    conn.commit()

    await update.message.reply_text("🔎 Searching for partner...")

    cursor.execute("SELECT user_id FROM waiting_users LIMIT 2")
    users = cursor.fetchall()

    if len(users) < 2:
        conn.close()
        return

    user1 = users[0][0]
    user2 = users[1][0]

    cursor.execute(
        "DELETE FROM waiting_users WHERE user_id IN (%s,%s)",
        (user1, user2)
    )

    cursor.execute(
        "INSERT INTO active_chats (user1,user2) VALUES (%s,%s)",
        (user1, user2)
    )

    conn.commit()
    conn.close()

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭ Next", callback_data="next"),
            InlineKeyboardButton("❌ End", callback_data="end")
        ]
    ])

    msg = "🤝 Partner Found!"

    await context.bot.send_message(user1, msg, reply_markup=keyboard)
    await context.bot.send_message(user2, msg, reply_markup=keyboard)


# ---------------- PROFILE ---------------- #

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    conn = db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT gender,reports,premium FROM users WHERE user_id=%s",
        (user_id,)
    )

    data = cursor.fetchone()
    conn.close()

    if not data:
        return

    gender, reports, premium = data

    premium_status = "Yes ✅" if premium else "No ❌"

    await update.message.reply_text(
        f"👤 Profile\n\nGender: {gender}\nReports: {reports}\nPremium: {premium_status}"
    )


# ---------------- SETTINGS ---------------- #

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    conn = db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT gender FROM users WHERE user_id=%s",
        (user_id,)
    )

    gender = cursor.fetchone()[0]
    conn.close()

    await update.message.reply_text(
        f"⚙ Settings\n\nGender: {gender}"
    )


# ---------------- TEXT ROUTER ---------------- #

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text

    if text == "🔎 Find Partner":
        await find_partner(update, context)
        return

    if text == "👤 Profile":
        await profile(update, context)
        return

    if text == "⚙ Settings":
        await settings(update, context)
        return


# ---------------- MAIN ---------------- #

def main():

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(MessageHandler(filters.Regex("^(👦 Male|👧 Female)$"), set_gender))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    app.run_polling()


if __name__ == "__main__":
    main()
