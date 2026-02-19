import logging
import os
import random
from flask import Flask
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TOKEN")

logging.basicConfig(level=logging.INFO)

# ---------------- FLASK SERVER ---------------- #

app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Bot Alive 🚀"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask).start()

# ---------------- BOT DATA ---------------- #

waiting_users = []
active_chats = {}
user_gender = {}
user_reports = {}

BAN_LIMIT = 10

# ---------------- HELPERS ---------------- #

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("🔎 Find Partner", callback_data="find")],
        [InlineKeyboardButton("👤 Profile", callback_data="profile")],
        [InlineKeyboardButton("⚙ Settings", callback_data="settings")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_chat_controls():
    keyboard = [
        [
            InlineKeyboardButton("⏭ Next", callback_data="next"),
            InlineKeyboardButton("❌ End", callback_data="end"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def is_banned(user_id):
    return user_reports.get(user_id, 0) >= BAN_LIMIT

# ---------------- COMMANDS ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned.")
        return

    keyboard = [
        [
            InlineKeyboardButton("👦 Male", callback_data="gender_male"),
            InlineKeyboardButton("👧 Female", callback_data="gender_female"),
        ]
    ]

    await update.message.reply_text(
        "Welcome 😎\n\nPlease select your gender:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# ---------------- CALLBACKS ---------------- #

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    await query.answer()

    if is_banned(user_id):
        await query.message.reply_text("🚫 You are banned.")
        return

    # -------- GENDER -------- #

    if query.data.startswith("gender_"):
        gender = query.data.split("_")[1]
        user_gender[user_id] = gender

        await query.message.reply_text(
            f"✅ Gender set to {gender.capitalize()}",
            reply_markup=get_main_menu(),
        )
        return

    # -------- FIND PARTNER -------- #

    if query.data == "find":
        if user_id in active_chats:
            await query.message.reply_text("⚠ You are already in chat.")
            return

        if user_id not in waiting_users:
            waiting_users.append(user_id)

        await query.message.reply_text("🔎 Searching for partner...")

        if len(waiting_users) >= 2:
            user1 = waiting_users.pop(0)
            user2 = waiting_users.pop(0)

            active_chats[user1] = user2
            active_chats[user2] = user1

            await context.bot.send_message(
                user1,
                "🤝 Partner Found!",
                reply_markup=get_chat_controls(),
            )

            await context.bot.send_message(
                user2,
                "🤝 Partner Found!",
                reply_markup=get_chat_controls(),
            )
        return

    # -------- NEXT -------- #

    if query.data == "next":
        partner = active_chats.get(user_id)

        if not partner:
            await query.message.reply_text("⚠ No active chat.")
            return

        del active_chats[user_id]
        del active_chats[partner]

        waiting_users.append(user_id)

        await context.bot.send_message(partner, "❌ Partner left.")

        await query.message.reply_text("🔎 Finding new partner...")

        if len(waiting_users) >= 2:
            user1 = waiting_users.pop(0)
            user2 = waiting_users.pop(0)

            active_chats[user1] = user2
            active_chats[user2] = user1

            await context.bot.send_message(
                user1,
                "🤝 Partner Found!",
                reply_markup=get_chat_controls(),
            )

            await context.bot.send_message(
                user2,
                "🤝 Partner Found!",
                reply_markup=get_chat_controls(),
            )
        return

    # -------- END -------- #

    if query.data == "end":
        partner = active_chats.get(user_id)

        if not partner:
            await query.message.reply_text("⚠ No active chat.")
            return

        del active_chats[user_id]
        del active_chats[partner]

        await context.bot.send_message(partner, "❌ Chat ended.")

        await query.message.reply_text(
            "❌ Chat ended.",
            reply_markup=get_main_menu(),
        )
        return

    # -------- PROFILE -------- #

    if query.data == "profile":
        gender = user_gender.get(user_id, "Not Set")
        reports = user_reports.get(user_id, 0)

        await query.message.reply_text(
            f"👤 Your Profile\n\nGender: {gender}\nReports: {reports}",
            reply_markup=get_main_menu(),
        )
        return

    # -------- SETTINGS -------- #

    if query.data == "settings":
        keyboard = [
            [InlineKeyboardButton("🚩 Report", callback_data="report")],
            [InlineKeyboardButton("⬅ Back", callback_data="back")],
        ]

        await query.message.reply_text(
            "⚙ Settings",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if query.data == "back":
        await query.message.reply_text("⬅ Back", reply_markup=get_main_menu())
        return

    # -------- REPORT -------- #

    if query.data == "report":
        partner = active_chats.get(user_id)

        if not partner:
            await query.message.reply_text("⚠ No active chat.")
            return

        user_reports[partner] = user_reports.get(partner, 0) + 1

        await query.message.reply_text("🚩 User Reported.")

        if is_banned(partner):
            await context.bot.send_message(partner, "🚫 You are banned.")
        return

# ---------------- MESSAGE RELAY ---------------- #

async def relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if is_banned(user_id):
        return

    partner = active_chats.get(user_id)

    if partner:
        await context.bot.send_message(partner, update.message.text)

# ---------------- MAIN ---------------- #

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, relay))

    print("Bot Running 🚀")

    app.run_polling()

if __name__ == "__main__":
    main()
