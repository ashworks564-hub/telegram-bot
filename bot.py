import os
import random
from datetime import datetime, timedelta

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

TOKEN = os.environ.get("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN environment variable not set")

# ------------------ STORAGE ------------------

waiting_users = []
active_chats = {}          # user_id -> partner_id
user_profiles = {}         # user_id -> {gender, premium}
reports = {}               # user_id -> report_count
banned_users = {}          # user_id -> unban_time
last_partner = {}          # user_id -> last partner for reporting

# ------------------ KEYBOARDS ------------------

gender_keyboard = ReplyKeyboardMarkup(
    [["👨 Male", "👩 Female"]],
    resize_keyboard=True
)

main_keyboard = ReplyKeyboardMarkup(
    [["🔎 Find Partner"]],
    resize_keyboard=True
)

chat_keyboard = ReplyKeyboardMarkup(
    [["➡️ Next", "⛔ Stop"]],
    resize_keyboard=True
)

menu_keyboard = ReplyKeyboardMarkup(
    [["👤 Profile", "⚙️ Settings"]],
    resize_keyboard=True
)

settings_keyboard = ReplyKeyboardMarkup(
    [["🚫 Report"],
     ["💎 Match Male (Premium)", "💎 Match Female (Premium)"],
     ["⬅️ Back"]],
    resize_keyboard=True
)

# ------------------ HELPERS ------------------

def is_banned(user_id):
    if user_id in banned_users:
        if datetime.now() < banned_users[user_id]:
            return True
        else:
            del banned_users[user_id]
    return False


async def disconnect(user_id, context):
    if user_id in active_chats:
        partner_id = active_chats[user_id]

        del active_chats[user_id]
        if partner_id in active_chats:
            del active_chats[partner_id]

        last_partner[user_id] = partner_id
        last_partner[partner_id] = user_id

        try:
            await context.bot.send_message(
                partner_id,
                "🚫 Your partner has disconnected.",
                reply_markup=main_keyboard
            )
        except:
            pass

# ------------------ COMMANDS ------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if is_banned(user_id):
        unban_time = banned_users[user_id]
        await update.message.reply_text(
            f"You are banned until:\n{unban_time.strftime('%d %B %Y %H:%M')}",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    user_profiles.setdefault(user_id, {
        "gender": None,
        "premium": False
    })

    await update.message.reply_text(
        "👋 Welcome!\n\nSelect your gender:",
        reply_markup=gender_keyboard
    )


# ------------------ MATCHING ------------------

async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if is_banned(user_id):
        return

    if user_profiles[user_id]["gender"] is None:
        await update.message.reply_text("Select gender first.")
        return

    if user_id in active_chats:
        return

    if user_id not in waiting_users:
        waiting_users.append(user_id)

    await update.message.reply_text("🔎 Finding partner...")

    if len(waiting_users) >= 2:
        user1 = waiting_users.pop(0)
        user2 = waiting_users.pop(0)

        active_chats[user1] = user2
        active_chats[user2] = user1

        await context.bot.send_message(
            user1,
            "🤝 Partner Found!\n\n🚫 Links blocked\n📵 No media allowed",
            reply_markup=chat_keyboard
        )

        await context.bot.send_message(
            user2,
            "🤝 Partner Found!\n\n🚫 Links blocked\n📵 No media allowed",
            reply_markup=chat_keyboard
        )


# ------------------ REPORT SYSTEM ------------------

async def report_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in last_partner:
        await update.message.reply_text("Nothing to report.")
        return

    target = last_partner[user_id]

    reports[target] = reports.get(target, 0) + 1

    await update.message.reply_text("🚫 User reported.")

    if reports[target] >= 10:
        banned_users[target] = datetime.now() + timedelta(hours=24)

        try:
            await context.bot.send_message(
                target,
                "*You have been banned due to rules violation.*\n\n"
                "It is prohibited to sell, advertise, send links, or share unwanted content.\n\n"
                f"You will be able to use the bot again at "
                f"{banned_users[target].strftime('%d %B %Y %H:%M')}",
                parse_mode="Markdown"
            )
        except:
            pass


# ------------------ PROFILE ------------------

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    profile = user_profiles[user_id]

    gender = profile["gender"] or "Not selected"
    premium = "💎 Premium User" if profile["premium"] else "Free User"

    await update.message.reply_text(
        f"👤 Your Profile\n\n"
        f"Gender: {gender}\n"
        f"Status: {premium}",
        reply_markup=menu_keyboard
    )


# ------------------ SETTINGS ------------------

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ Settings\n\nSelect option:",
        reply_markup=settings_keyboard
    )


# ------------------ MESSAGE ROUTER ------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if is_banned(user_id):
        return

    # Gender selection
    if text in ["👨 Male", "👩 Female"]:
        user_profiles[user_id]["gender"] = text
        await update.message.reply_text(
            "✅ Gender saved.",
            reply_markup=main_keyboard
        )
        return

    # Find partner
    if text == "🔎 Find Partner":
        await find_partner(update, context)
        return

    # Next
    if text == "➡️ Next":
        await disconnect(user_id, context)
        await find_partner(update, context)
        return

    # Stop
    if text == "⛔ Stop":
        await disconnect(user_id, context)
        await update.message.reply_text(
            "⛔ Chat ended.",
            reply_markup=main_keyboard
        )
        return

    # Profile
    if text == "👤 Profile":
        await show_profile(update, context)
        return

    # Settings
    if text == "⚙️ Settings":
        await show_settings(update, context)
        return

    # Back
    if text == "⬅️ Back":
        await update.message.reply_text(
            "⬅️ Back to menu",
            reply_markup=menu_keyboard
        )
        return

    # Report
    if text == "🚫 Report":
        await report_user(update, context)
        return

    # Premium locked features
    if "Premium" in text:
        await update.message.reply_text("💎 Premium required.")
        return

    # Chat forwarding
    if user_id in active_chats:
        partner = active_chats[user_id]

        if "http" in text.lower():
            await update.message.reply_text("🚫 Links blocked.")
            return

        await context.bot.send_message(partner, text)


# ------------------ MAIN ------------------

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot Running...")
    app.run_polling()


if __name__ == "__main__":
    main()
