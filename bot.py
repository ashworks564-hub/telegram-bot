import os
import threading
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

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
    [["🚩 Report"], ["⬅ Back"]],
    resize_keyboard=True
)

# ---------------- START ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    users[user_id] = {
        "gender": None,
        "reports": 0,
        "premium": False
    }

await update.message.reply_text(
    "⚡ Welcome to Chatx99\n\n"
    "Thousands of conversations happen here every day.\n"
    "Your next one could be interesting 😌\n\n"
    "👇 Pick your gender and jump in:",
    reply_markup=gender_keyboard
)

# ---------------- GENDER ---------------- #

async def set_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if text not in ["👦 Male", "👧 Female"]:
        return

    users[user_id]["gender"] = "Male" if "Male" in text else "Female"

    await update.message.reply_text(
        f"✅ Gender set to {users[user_id]['gender']}",
        reply_markup=main_menu_keyboard
    )

# ---------------- FIND PARTNER ---------------- #

async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in active_chats:
        await update.message.reply_text("⚠ Already in chat.")
        return

    if user_id not in waiting_users:
        waiting_users.append(user_id)

    await update.message.reply_text("⏳ Finding better match...")

    await match_users(context)

# ---------------- MATCHING ---------------- #

async def match_users(context):

    if len(waiting_users) < 2:
        return

    user1 = waiting_users.pop(0)
    user2 = waiting_users.pop(0)

    active_chats[user1] = user2
    active_chats[user2] = user1

    inline_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭ Next", callback_data="next"),
            InlineKeyboardButton("❌ End", callback_data="end")
        ]
    ])

    msg = (
        "🤝 Partner Found!\n\n"
        "✅ You joined a chat\n"
        "🚫 Links are blocked\n"
        "📵 No media allowed"
    )

    # Send with BOTH keyboards
    await context.bot.send_message(
        user1,
        msg,
        reply_markup=inline_keyboard
    )

    await context.bot.send_message(
        user1,
        "Chat Controls 👇",
        reply_markup=chat_keyboard
    )

    await context.bot.send_message(
        user2,
        msg,
        reply_markup=inline_keyboard
    )

    await context.bot.send_message(
        user2,
        "Chat Controls 👇",
        reply_markup=chat_keyboard
    )

# ---------------- PROFILE ---------------- #

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = users.get(user_id)

    if not data:
        return

    premium_status = "Yes ✅" if data["premium"] else "No ❌"

    await update.message.reply_text(
        f"👤 Your Profile\n\n"
        f"Gender: {data['gender']}\n"
        f"Reports: {data['reports']}\n"
        f"Premium: {premium_status}"
    )

# ---------------- SETTINGS ---------------- #

from telegram import InlineKeyboardMarkup, InlineKeyboardButton

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = users.get(user_id)

    if not user:
        return

    text = (
        "👤 User\n"
        "Free Member\n\n"
        f"🆔 ID: {user_id}\n\n"
        "⚙ Your Preferences:\n"
        f"🚻 Gender: {user.get('gender', 'Not Set')}\n"
        f"🎯 Looking for: {user.get('match_pref', 'Everyone')}\n"
        f"🎂 Age: {user.get('age', 'Not Set')}\n"
        f"🌍 Country: {user.get('country', 'India')}\n"
        f"🗣 Language: {user.get('language', 'English')}"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚻 Change Gender", callback_data="change_gender"),
            InlineKeyboardButton("🎯 Partner Pref", callback_data="partner_pref")
        ],
        [
            InlineKeyboardButton("🎂 Set Age", callback_data="set_age"),
            InlineKeyboardButton("🌍 Set Country", callback_data="set_country")
        ],
        [
            InlineKeyboardButton("🗣 Language", callback_data="set_language"),
            InlineKeyboardButton("❌ Close", callback_data="close_settings")
        ]
    ])

    await update.message.reply_text(text, reply_markup=keyboard)

# ---------------- BACK ---------------- #

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏠 Main Menu",
        reply_markup=main_menu_keyboard
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

# ---------------- RELAY ---------------- #

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

    # -------- COMMAND -------- #
    app.add_handler(CommandHandler("start", start))

    # -------- ONBOARDING -------- #
    app.add_handler(MessageHandler(filters.Regex("👦 Male|👧 Female"), set_gender))

    # -------- MAIN MENU -------- #
    app.add_handler(MessageHandler(filters.Regex("🔎 Find Partner"), find_partner))
    app.add_handler(MessageHandler(filters.Regex("👤 Profile"), profile))
    app.add_handler(MessageHandler(filters.Regex("⚙ Settings"), settings))

    # -------- SETTINGS -------- #
    app.add_handler(MessageHandler(filters.Regex("🚩 Report"), report))
    app.add_handler(MessageHandler(filters.Regex("⬅ Back"), back_to_menu))

    # -------- CHAT CONTROLS -------- #
    app.add_handler(MessageHandler(filters.Regex("⏭ Next"), next_chat))
    app.add_handler(MessageHandler(filters.Regex("❌ End"), end_chat))

    # -------- MESSAGE RELAY -------- #
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, relay))

    # -------- START BOT -------- #
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()








