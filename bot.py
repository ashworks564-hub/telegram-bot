import logging
import time
import random
from datetime import datetime, timedelta

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ===== CONFIG =====

import os
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN environment variable not set!")

logging.basicConfig(level=logging.INFO)

# ===== STORAGE =====

waiting_users = []
active_chats = {}
user_profiles = {}
reports = {}
banned_users = {}

# ===== KEYBOARDS =====

start_keyboard = ReplyKeyboardMarkup(
    [["♂️ Male", "♀️ Female"]],
    resize_keyboard=True
)

main_keyboard = ReplyKeyboardMarkup(
    [["🔎 Find Partner"], ["👤 Profile", "⚙️ Settings"]],
    resize_keyboard=True
)

chat_keyboard = ReplyKeyboardMarkup(
    [["➡️ Next", "⛔ Stop"]],
    resize_keyboard=True
)

settings_keyboard = ReplyKeyboardMarkup(
    [["🚨 Report"], ["⬅️ Back"]],
    resize_keyboard=True
)

profile_keyboard = ReplyKeyboardMarkup(
    [["🔁 Change Gender"], ["💎 Buy Premium"], ["⬅️ Back"]],
    resize_keyboard=True
)

# ===== BAN CHECK =====

def is_banned(user_id):
    if user_id not in banned_users:
        return False

    if time.time() > banned_users[user_id]:
        del banned_users[user_id]
        return False

    return True

# ===== MATCHING =====

async def match_user(update, context, user_id):
    if user_id in active_chats:
        await update.message.reply_text("⚠️ You are already in chat.")
        return

    if user_id not in waiting_users:
        waiting_users.append(user_id)

    await update.message.reply_text("🔎 Finding partner for you...")

    if len(waiting_users) >= 2:
        u1 = waiting_users.pop(0)
        u2 = waiting_users.pop(0)

        active_chats[u1] = u2
        active_chats[u2] = u1

        await context.bot.send_message(
            u1,
            "🤝 Partner Found!\n\n"
            "🚫 Links are blocked\n"
            "🚫 Media is not allowed",
            reply_markup=chat_keyboard
        )

        await context.bot.send_message(
            u2,
            "🤝 Partner Found!\n\n"
            "🚫 Links are blocked\n"
            "🚫 Media is not allowed",
            reply_markup=chat_keyboard
        )

# ===== START =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if is_banned(user_id):
        return

    await update.message.reply_text(
        "👋 Welcome!\n\nPlease select your gender:",
        reply_markup=start_keyboard
    )

# ===== MESSAGE HANDLER =====

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if is_banned(user_id):
        ban_time = datetime.fromtimestamp(banned_users[user_id])
        formatted = ban_time.strftime("%d %B %Y at %H:%M")

        await update.message.reply_text(
            f"🚫 You are banned until {formatted}"
        )
        return

    # ===== GENDER SELECTION =====

    if text in ["♂️ Male", "♀️ Female"]:
        gender = "Male" if "Male" in text else "Female"

        user_profiles[user_id] = {
            "gender": gender,
            "premium": False
        }

        await update.message.reply_text(
            f"✅ Gender set to {gender}",
            reply_markup=main_keyboard
        )
        return

    # ===== FIND PARTNER =====

    if text == "🔎 Find Partner":
        await match_user(update, context, user_id)
        return

    # ===== CHAT CONTROLS =====

    if text == "➡️ Next":
        if user_id in active_chats:
            partner = active_chats[user_id]

            del active_chats[partner]
            del active_chats[user_id]

            await context.bot.send_message(
                partner,
                "🚫 Your partner disconnected.",
                reply_markup=main_keyboard
            )

        await match_user(update, context, user_id)
        return

    if text == "⛔ Stop":
        if user_id in active_chats:
            partner = active_chats[user_id]

            del active_chats[partner]
            del active_chats[user_id]

            await context.bot.send_message(
                partner,
                "🚫 Your partner disconnected.",
                reply_markup=main_keyboard
            )

        await update.message.reply_text(
            "✅ Chat ended.",
            reply_markup=main_keyboard
        )
        return

    # ===== PROFILE =====

    if text == "👤 Profile":
        profile = user_profiles.get(user_id)

        if not profile:
            await update.message.reply_text(
                "⚠️ Please select gender first.",
                reply_markup=start_keyboard
            )
            return

        premium_status = "💎 Premium User" if profile["premium"] else "🆓 Free User"

        await update.message.reply_text(
            f"👤 Your Profile\n\n"
            f"Gender: {profile['gender']}\n"
            f"Status: {premium_status}",
            reply_markup=profile_keyboard
        )
        return

    if text == "🔁 Change Gender":
        await update.message.reply_text(
            "Select new gender:",
            reply_markup=start_keyboard
        )
        return

    if text == "💎 Buy Premium":
        await update.message.reply_text(
            "💎 Premium feature coming soon 😉"
        )
        return

    # ===== SETTINGS =====

    if text == "⚙️ Settings":
        await update.message.reply_text(
            "⚙️ Settings",
            reply_markup=settings_keyboard
        )
        return

    if text == "🚨 Report":
        reports[user_id] = reports.get(user_id, 0) + 1
        count = reports[user_id]

        if count >= 10:
            ban_until = datetime.now() + timedelta(hours=24)
            banned_users[user_id] = time.time() + 86400

            formatted_time = ban_until.strftime("%d %B %Y at %H:%M")

            await update.message.reply_text(
                "🚫 You have been banned due to rules violation.\n\n"
                "It is prohibited in the bot to sell anything, advertise, "
                "send invitations to external groups or channels, share links, "
                "or ask for money.\n\n"
                "🔞 We also ban users sharing unwanted content.\n\n"
                f"You will be able to use the chat again at {formatted_time}.\n\n"
                "Our policy on spam:\n"
                "anonchatbot.com/rules\n\n"
                "If banned by mistake – contact: @chatbotsupport",
                reply_markup=main_keyboard
            )
            return

        await update.message.reply_text(
            f"🚨 Report submitted ({count}/10)",
            reply_markup=settings_keyboard
        )
        return

    if text == "⬅️ Back":
        await update.message.reply_text(
            "⬅️ Back to menu",
            reply_markup=main_keyboard
        )
        return

    # ===== MESSAGE FORWARDING =====

    if user_id in active_chats:
        partner = active_chats[user_id]

        if "http" in text or "www" in text:
            return

        await context.bot.send_message(partner, text)
        return

# ===== MAIN =====

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
