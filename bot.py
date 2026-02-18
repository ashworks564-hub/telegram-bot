import os
import threading
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ---------------- FLASK (Render Keep Alive) ----------------

app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Bot Alive 🚀"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask).start()

# ---------------- BOT LOGIC ----------------

TOKEN = os.environ.get("TOKEN")

waiting_users = []
active_chats = {}
user_gender = {}

# ---------------- KEYBOARDS ----------------

def main_keyboard():
    return ReplyKeyboardMarkup(
        [["🔎 Find Partner", "👤 Profile"]],
        resize_keyboard=True
    )

def gender_keyboard():
    return ReplyKeyboardMarkup(
        [["👨 Male", "👩 Female"]],
        resize_keyboard=True
    )

def chat_keyboard():
    return ReplyKeyboardMarkup(
        [["⏭ Next", "❌ End"]],
        resize_keyboard=True
    )

# ---------------- MATCHING ENGINE ----------------

def find_partner(user_id):

    if user_id in waiting_users:
        return None

    for partner_id in waiting_users:
        if partner_id != user_id:

            waiting_users.remove(partner_id)

            active_chats[user_id] = partner_id
            active_chats[partner_id] = user_id

            return partner_id

    waiting_users.append(user_id)
    return None

def end_chat(user_id):

    if user_id not in active_chats:
        return None

    partner_id = active_chats.pop(user_id)
    active_chats.pop(partner_id, None)

    return partner_id

# ---------------- HANDLERS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    await update.message.reply_text(
        "👋 Welcome!\n\nPlease select your gender:",
        reply_markup=gender_keyboard()
    )

async def handle_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    text = update.message.text

    if "Male" in text:
        user_gender[user_id] = "Male"
    elif "Female" in text:
        user_gender[user_id] = "Female"
    else:
        return

    await update.message.reply_text(
        f"✅ Gender set to {user_gender[user_id]}",
        reply_markup=main_keyboard()
    )

async def handle_find(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if user_id not in user_gender:
        await update.message.reply_text("⚠ Please select gender first.")
        return

    partner = find_partner(user_id)

    if partner:

        await update.message.reply_text(
            "🤝 Partner Found!",
            reply_markup=chat_keyboard()
        )

        await context.bot.send_message(
            partner,
            "🤝 Partner Found!",
            reply_markup=chat_keyboard()
        )

    else:
        await update.message.reply_text("🔎 Searching for partner...")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in active_chats:
        return

    partner_id = active_chats[user_id]

    if partner_id == user_id:
        return

    await context.bot.send_message(partner_id, text)

async def handle_next(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    partner_id = end_chat(user_id)

    if partner_id:
        await context.bot.send_message(partner_id, "❌ Your partner left the chat.")
        waiting_users.append(partner_id)

    partner = find_partner(user_id)

    if partner:

        await update.message.reply_text(
            "🤝 New Partner Found!",
            reply_markup=chat_keyboard()
        )

        await context.bot.send_message(
            partner,
            "🤝 New Partner Found!",
            reply_markup=chat_keyboard()
        )

    else:
        await update.message.reply_text("🔎 Searching for new partner...")

async def handle_end(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    partner_id = end_chat(user_id)

    if partner_id:
        await context.bot.send_message(partner_id, "❌ Chat ended.")

    await update.message.reply_text(
        "✅ Chat ended.",
        reply_markup=main_keyboard()
    )

async def handle_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    gender = user_gender.get(user_id, "Not Set")

    await update.message.reply_text(
        f"👤 Your Profile\n\nGender: {gender}"
    )

# ---------------- MAIN ----------------

def main():

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(MessageHandler(filters.Regex("Male|Female"), handle_gender))
    app.add_handler(MessageHandler(filters.Regex("Find Partner"), handle_find))
    app.add_handler(MessageHandler(filters.Regex("Next"), handle_next))
    app.add_handler(MessageHandler(filters.Regex("End"), handle_end))
    app.add_handler(MessageHandler(filters.Regex("Profile"), handle_profile))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot Running 🚀")

    app.run_polling()

if __name__ == "__main__":
    main()
