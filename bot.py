import os
import psycopg2
import threading
from datetime import datetime, timedelta

from flask import Flask
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.environ.get("TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

if not TOKEN:
    raise ValueError("TOKEN not set")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set")

conn = psycopg2.connect(DATABASE_URL, sslmode="require")
cur = conn.cursor()

# ---------- DATABASE SETUP ----------

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    gender TEXT,
    premium BOOLEAN DEFAULT FALSE,
    banned_until TIMESTAMP
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS reports (
    reporter BIGINT,
    target BIGINT
)
""")

conn.commit()

# ---------- FLASK KEEPALIVE ----------

app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Bot Alive"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask).start()

# ---------- BOT STATE ----------

waiting_queue = []
active_chats = {}
last_partner = {}

# ---------- KEYBOARDS ----------

gender_keyboard = ReplyKeyboardMarkup(
    [["Male", "Female"]],
    resize_keyboard=True
)

menu_keyboard = ReplyKeyboardMarkup(
    [["Find Partner"], ["Profile", "Settings"]],
    resize_keyboard=True
)

chat_keyboard = ReplyKeyboardMarkup(
    [["Next", "End"]],
    resize_keyboard=True
)

disconnect_keyboard = ReplyKeyboardMarkup(
    [["Find Partner", "Report"]],
    resize_keyboard=True
)

settings_keyboard = ReplyKeyboardMarkup(
    [["Report"], ["Match with Male", "Match with Female"]],
    resize_keyboard=True
)

# ---------- HELPERS ----------

def is_banned(user_id):
    cur.execute("SELECT banned_until FROM users WHERE user_id=%s", (user_id,))
    result = cur.fetchone()

    if result and result[0]:
        if datetime.utcnow() < result[0]:
            return result[0]
    return None

def save_user(user_id):
    cur.execute(
        "INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING",
        (user_id,)
    )
    conn.commit()

def get_user(user_id):
    cur.execute("SELECT gender, premium FROM users WHERE user_id=%s", (user_id,))
    return cur.fetchone()

# ---------- COMMANDS ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)

    banned_until = is_banned(user_id)
    if banned_until:
        await update.message.reply_text(
            f"You are banned until {banned_until}",
        )
        return

    await update.message.reply_text(
        "👋 Welcome!\n\nPlease select your gender:",
        reply_markup=gender_keyboard
    )

# ---------- GENDER SELECTION ----------

async def select_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    gender = update.message.text

    if gender not in ["Male", "Female"]:
        return

    cur.execute("UPDATE users SET gender=%s WHERE user_id=%s", (gender, user_id))
    conn.commit()

    await update.message.reply_text(
        f"✅ Gender saved: {gender}",
        reply_markup=menu_keyboard
    )

# ---------- MATCHMAKING ----------

async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    banned_until = is_banned(user_id)
    if banned_until:
        await update.message.reply_text(f"You are banned until {banned_until}")
        return

    if user_id in active_chats:
        await update.message.reply_text("⚠️ You are already in a chat.")
        return

    if user_id not in waiting_queue:
        waiting_queue.append(user_id)

    await update.message.reply_text("🔎 Finding partner for you...")

    if len(waiting_queue) >= 2:
        user1 = waiting_queue.pop(0)
        user2 = waiting_queue.pop(0)

        active_chats[user1] = user2
        active_chats[user2] = user1

        await context.bot.send_message(
            user1,
            "🤝 Partner Found!\n\n🚫 Links are blocked\n📵 No media allowed",
            reply_markup=chat_keyboard
        )

        await context.bot.send_message(
            user2,
            "🤝 Partner Found!\n\n🚫 Links are blocked\n📵 No media allowed",
            reply_markup=chat_keyboard
        )

# ---------- CHAT RELAY ----------

async def relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in active_chats:
        return

    partner = active_chats[user_id]

    if text == "Next":
        await next_partner(update, context)
        return

    if text == "End":
        await end_chat(update, context)
        return

    await context.bot.send_message(partner, text)

# ---------- NEXT ----------

async def next_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in active_chats:
        return

    partner = active_chats[user_id]

    last_partner[user_id] = partner
    last_partner[partner] = user_id

    del active_chats[user_id]
    del active_chats[partner]

    await context.bot.send_message(
        partner,
        "🚫 Your partner has disconnected.",
        reply_markup=disconnect_keyboard
    )

    await update.message.reply_text("🔎 Finding new partner...")
    waiting_queue.append(user_id)

# ---------- END ----------

async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in active_chats:
        await update.message.reply_text("✅ Chat ended.", reply_markup=menu_keyboard)
        return

    partner = active_chats[user_id]

    last_partner[user_id] = partner
    last_partner[partner] = user_id

    del active_chats[user_id]
    del active_chats[partner]

    await context.bot.send_message(
        partner,
        "🚫 Your partner has disconnected.",
        reply_markup=disconnect_keyboard
    )

    await update.message.reply_text("✅ Chat ended.", reply_markup=menu_keyboard)

# ---------- REPORT ----------

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in last_partner:
        await update.message.reply_text("⚠️ No user to report.")
        return

    target = last_partner[user_id]

    cur.execute("INSERT INTO reports VALUES (%s, %s)", (user_id, target))
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM reports WHERE target=%s", (target,))
    count = cur.fetchone()[0]

    if count >= 10:
        banned_until = datetime.utcnow() + timedelta(hours=24)

        cur.execute(
            "UPDATE users SET banned_until=%s WHERE user_id=%s",
            (banned_until, target)
        )
        conn.commit()

        await context.bot.send_message(
            target,
            f"""You have been banned due to rules violation.

It is prohibited in the bot to sell anything, advertise, send invitations to external groups or channels, share links, or ask for money.

🔞 We also ban all users found sharing unwanted content (including stickers, photos or videos with pornography).

You will be able to use the chat again at {banned_until}.

Our policy on spam:
anonchatbot.com/rules

If you think that you have been banned by mistake – let us know:
@chatbotsupport"""
        )

    await update.message.reply_text("✅ Report submitted.")

# ---------- PROFILE ----------

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        return

    gender, premium = user

    await update.message.reply_text(
        f"👤 Profile\n\nGender: {gender}\nPremium: {premium}",
        reply_markup=menu_keyboard
    )

# ---------- SETTINGS ----------

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ Settings",
        reply_markup=settings_keyboard
    )

async def premium_lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💎 Premium required.")

# ---------- MAIN ----------

app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.Regex("^(Male|Female)$"), select_gender))
app.add_handler(MessageHandler(filters.Regex("^Find Partner$"), find_partner))
app.add_handler(MessageHandler(filters.Regex("^(Next|End)$"), relay))
app.add_handler(MessageHandler(filters.Regex("^Report$"), report))
app.add_handler(MessageHandler(filters.Regex("^Profile$"), profile))
app.add_handler(MessageHandler(filters.Regex("^Settings$"), settings))
app.add_handler(MessageHandler(filters.Regex("^(Match with Male|Match with Female)$"), premium_lock))

print("Bot Running 🚀")
app.run_polling()
