import os
import threading
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

TOKEN = os.getenv("TOKEN")

# ---------------- FLASK SERVER ---------------- #

app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Bot Alive"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask).start()

# ---------------- BOT DATA ---------------- #

users = {}
waiting_users = []
active_chats = {}

# ---------------- KEYBOARDS ---------------- #

gender_keyboard = ReplyKeyboardMarkup(
    [["👦 Male", "👧 Female"]],
    resize_keyboard=True
)

main_menu_keyboard = ReplyKeyboardMarkup(
    [["🔎 Find Partner"], ["👤 Profile", "⚙ Settings"]],
    resize_keyboard=True
)

chat_keyboard = ReplyKeyboardMarkup(
    [["⏭ Next", "❌ End"]],
    resize_keyboard=True
)

settings_keyboard = ReplyKeyboardMarkup(
    [["🚩 Report"]],
    resize_keyboard=True
)

# ---------------- COMMANDS ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    users[user_id] = {
        "gender": None,
        "reports": 0,
        "premium": False,
        "match_pref": None
    }

    await update.message.reply_text(
        "Welcome 😎\n\nPlease select your gender:",
        reply_markup=gender_keyboard
    )

# ---------------- GENDER ---------------- #

async def set_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in users:
        return

    if text == "👦 Male":
        users[user_id]["gender"] = "Male"
    elif text == "👧 Female":
        users[user_id]["gender"] = "Female"
    else:
        return

    await update.message.reply_text(
        f"✅ Gender set to {users[user_id]['gender']}",
        reply_markup=main_menu_keyboard
    )

# ---------------- FIND PARTNER ---------------- #

async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in active_chats:
        await update.message.reply_text("Already in chat.")
        return

    if user_id not in waiting_users:
        waiting_users.append(user_id)

    await update.message.reply_text("🔎 Searching for partner...")

    await match_users(context)

# ---------------- MATCHING ---------------- #

async def match_users(context):

    if len(waiting_users) < 2:
        return

    user1 = waiting_users.pop(0)
    user2 = waiting_users.pop(0)

    active_chats[user1] = user2
    active_chats[user2] = user1

    keyboard_chat = ReplyKeyboardMarkup(
        [["⏭ Next", "❌ End"]],
        resize_keyboard=True
    )

    msg = (
        "🤝 Partner Found!\n\n"
        "🚫 Links are blocked\n"
        "📵 No media allowed"
    )

    try:
        await context.bot.send_message(user1, msg, reply_markup=keyboard_chat)
        await context.bot.send_message(user2, msg, reply_markup=keyboard_chat)

    except:
        # If one user fails → clean chat
        active_chats.pop(user1, None)
        active_chats.pop(user2, None)
# ---------------- PROFILE ---------------- #

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in users:
        return

    data = users[user_id]

    premium_status = "Yes ✅" if data["premium"] else "No ❌"

    await update.message.reply_text(
        f"👤 Your Profile\n\n"
        f"Gender: {data['gender']}\n"
        f"Reports: {data['reports']}\n"
        f"Premium: {premium_status}"
    )

# ---------------- SETTINGS ---------------- #

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = ReplyKeyboardMarkup(
        [
            ["🚩 Report"],
            ["👦 Match with Male", "👧 Match with Female"],
            ["⬅ Back"]
        ],
        resize_keyboard=True
    )

    await update.message.reply_text(
        "⚙ Settings\n\nSelect an option:",
        reply_markup=keyboard
    )

# ---------------- REPORT ---------------- #

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in active_chats:
        await update.message.reply_text("No active partner.")
        return

    partner_id = active_chats[user_id]

    users[partner_id]["reports"] += 1

    await update.message.reply_text("🚩 User reported.")

    if users[partner_id]["reports"] >= 10:
        await context.bot.send_message(partner_id, "🚫 You have been banned.")

# ---------------- NEXT ---------------- #

async def next_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in active_chats:
        return

    partner_id = active_chats[user_id]

    del active_chats[user_id]
    del active_chats[partner_id]

    waiting_users.append(user_id)
    waiting_users.append(partner_id)

    await context.bot.send_message(user_id, "⏭ Finding new partner...")
    await context.bot.send_message(partner_id, "⏭ Finding new partner...")

    await match_users(context)

# ---------------- END ---------------- #

async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in active_chats:
        return

    partner_id = active_chats[user_id]

    del active_chats[user_id]
    del active_chats[partner_id]

    await context.bot.send_message(user_id, "❌ Chat ended.", reply_markup=main_menu_keyboard)
    await context.bot.send_message(partner_id, "❌ Partner disconnected.", reply_markup=main_menu_keyboard)

# ---------------- MESSAGE RELAY ---------------- #

async def relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in active_chats:
        return

    partner_id = active_chats[user_id]

    await context.bot.send_message(partner_id, update.message.text)

# ---------------- MAIN ---------------- #

def main():
    print("Bot Running 🚀")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(MessageHandler(filters.Regex("👦 Male|👧 Female"), set_gender))
    app.add_handler(MessageHandler(filters.Regex("🔎 Find Partner"), find_partner))
    app.add_handler(MessageHandler(filters.Regex("👤 Profile"), profile))
    app.add_handler(MessageHandler(filters.Regex("⚙ Settings"), settings))
    app.add_handler(MessageHandler(filters.Regex("🚩 Report"), report))
    app.add_handler(MessageHandler(filters.Regex("⏭ Next"), next_chat))
    app.add_handler(MessageHandler(filters.Regex("❌ End"), end_chat))

    
    app.add_handler(MessageHandler(filters.Regex("^⬅ Back$"), back_to_menu))

    
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            relay
        )
    )

    app.run_polling(drop_pending_updates=True)






