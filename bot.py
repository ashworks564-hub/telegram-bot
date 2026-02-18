import os
import logging
import psycopg2
from datetime import datetime, timedelta
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.INFO)

# ---------- DATABASE CONNECTION ----------

conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    gender TEXT,
    partner BIGINT,
    reports INT DEFAULT 0,
    banned_until TIMESTAMP,
    premium BOOLEAN DEFAULT FALSE
)
""")
conn.commit()

# ---------- KEYBOARDS ----------

main_keyboard = ReplyKeyboardMarkup(
    [["🔎 Find Partner"], ["👤 Profile", "⚙️ Settings"]],
    resize_keyboard=True
)

gender_keyboard = ReplyKeyboardMarkup(
    [["👨 Male", "👩 Female"]],
    resize_keyboard=True
)

settings_keyboard = ReplyKeyboardMarkup(
    [["🚫 Report"], ["💎 Match with Male", "💎 Match with Female"], ["⬅️ Back"]],
    resize_keyboard=True
)

after_chat_keyboard = ReplyKeyboardMarkup(
    [["🔎 Find Partner"]],
    resize_keyboard=True
)

# ---------- HELPERS ----------

def get_user(user_id):
    cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    return cur.fetchone()

def create_user(user_id):
    cur.execute(
        "INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING",
        (user_id,)
    )
    conn.commit()

def is_banned(user):
    if user[4]:
        return user[4] > datetime.utcnow()
    return False()

# ---------- COMMANDS ----------

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
        await update.message.reply_text(
            "👋 Welcome back!",
            reply_markup=main_keyboard
        )

# ---------- GENDER ----------

async def set_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if text not in ["👨 Male", "👩 Female"]:
        return

    gender = "Male" if "Male" in text else "Female"

    cur.execute(
        "UPDATE users SET gender = %s WHERE user_id = %s",
        (gender, user_id)
    )
    conn.commit()

    await update.message.reply_text(
        f"✅ Gender set to {gender}",
        reply_markup=main_keyboard
    )

# ---------- FIND PARTNER ----------

async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if is_banned(user):
        await update.message.reply_text("🚫 You are banned.")
        return

    if user[2]:
        await update.message.reply_text("⚠️ You are already in chat.")
        return

    await update.message.reply_text("🔎 Finding partner for you...")

    cur.execute("""
    SELECT user_id FROM users
    WHERE partner IS NULL
    AND gender IS NOT NULL
    AND user_id != %s
    LIMIT 1
    """, (user_id,))

    partner = cur.fetchone()

    if not partner:
        return

    partner_id = partner[0]

    cur.execute("UPDATE users SET partner = %s WHERE user_id = %s", (partner_id, user_id))
    cur.execute("UPDATE users SET partner = %s WHERE user_id = %s", (user_id, partner_id))
    conn.commit()

    await context.bot.send_message(
        user_id,
        "🤝 Partner Found!\n\n🚫 Links are blocked\n📵 No media allowed",
    )

    await context.bot.send_message(
        partner_id,
        "🤝 Partner Found!\n\n🚫 Links are blocked\n📵 No media allowed",
    )

# ---------- CHAT RELAY ----------

async def relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user[2]:
        return

    if "http" in update.message.text.lower():
        await update.message.reply_text("🚫 Links are blocked.")
        return

    await context.bot.send_message(user[2], update.message.text)

# ---------- PROFILE ----------

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    premium = "💎 Premium User" if user[5] else "👤 Free User"

    await update.message.reply_text(
        f"👤 Your Profile\n\n"
        f"Gender: {user[1]}\n"
        f"Status: {premium}"
    )

# ---------- SETTINGS ----------

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ Settings",
        reply_markup=settings_keyboard
    )

# ---------- PREMIUM ----------

async def premium_required(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💎 Premium Required")

# ---------- REPORT ----------

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user[2]:
        await update.message.reply_text("⚠️ No partner to report.")
        return

    partner_id = user[2]

    cur.execute("UPDATE users SET reports = reports + 1 WHERE user_id = %s", (partner_id,))
    conn.commit()

    cur.execute("SELECT reports FROM users WHERE user_id = %s", (partner_id,))
    reports = cur.fetchone()[0]

    if reports >= 10:
        banned_until = datetime.utcnow() + timedelta(hours=24)

        cur.execute(
            "UPDATE users SET banned_until = %s WHERE user_id = %s",
            (banned_until, partner_id)
        )
        conn.commit()

        await context.bot.send_message(
            partner_id,
            f"🚫 You have been banned for 24 hours."
        )

    await update.message.reply_text("🚫 User reported.")

# ---------- BACK ----------

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⬅️ Back",
        reply_markup=main_keyboard
    )

# ---------- MAIN ----------

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.Regex("👨 Male|👩 Female"), set_gender))
app.add_handler(MessageHandler(filters.Regex("🔎 Find Partner"), find_partner))
app.add_handler(MessageHandler(filters.Regex("👤 Profile"), profile))
app.add_handler(MessageHandler(filters.Regex("⚙️ Settings"), settings))
app.add_handler(MessageHandler(filters.Regex("💎"), premium_required))
app.add_handler(MessageHandler(filters.Regex("🚫 Report"), report))
app.add_handler(MessageHandler(filters.Regex("⬅️ Back"), back))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, relay))

print("Bot Running...")
app.run_polling()
