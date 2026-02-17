import os
import logging
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ.get("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN not set in Render!")

# ====== MEMORY ======
users = {}
waiting_users = []
active_chats = {}

# ====== KEYBOARDS ======

gender_keyboard = ReplyKeyboardMarkup(
    [["👨 Male", "👩 Female"]],
    resize_keyboard=True
)

main_keyboard = ReplyKeyboardMarkup(
    [["🔍 Find Partner"],
     ["👤 Profile", "⚙ Settings"]],
    resize_keyboard=True
)

chat_keyboard = ReplyKeyboardMarkup(
    [["➡ Next", "⛔ Stop"]],
    resize_keyboard=True
)

settings_keyboard = ReplyKeyboardMarkup(
    [["💎 Premium"],
     ["🚫 Report"],
     ["👤 Profile"]],
    resize_keyboard=True
)

premium_keyboard = ReplyKeyboardMarkup(
    [["👨 Match Male (Premium)"],
     ["👩 Match Female (Premium)"]],
    resize_keyboard=True
)

profile_keyboard = ReplyKeyboardMarkup(
    [["🎂 Set Age"],
     ["🌍 Set Country"],
     ["🔙 Back"]],
    resize_keyboard=True
)

# ====== HELPERS ======

def get_partner(user_id):
    return active_chats.get(user_id)

async def disconnect(user_id, context):
    partner = get_partner(user_id)

    if partner:
        del active_chats[partner]
        del active_chats[user_id]

        await context.bot.send_message(
            partner,
            "🚫 Your partner has disconnected.\n\n🔍 Click Find Partner to continue.",
            reply_markup=main_keyboard
        )

# ====== COMMANDS ======

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id

    users[user_id] = {
        "gender": None,
        "age": None,
        "country": None,
        "premium": False
    }

    await update.message.reply_text(
        "🔥 Welcome!\n\nSelect your gender:",
        reply_markup=gender_keyboard
    )

async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id

    await disconnect(user_id, context)

    if user_id not in waiting_users:
        waiting_users.append(user_id)

    await update.message.reply_text(
        "🔍 Finding partner for you...",
        reply_markup=ReplyKeyboardRemove()
    )

    if len(waiting_users) >= 2:
        user1 = waiting_users.pop(0)
        user2 = waiting_users.pop(0)

        active_chats[user1] = user2
        active_chats[user2] = user1

        msg = (
            "🤝 Partner Found!\n\n"
            "🚫 Links are blocked\n"
            "🚫 No media allowed"
        )

        await context.bot.send_message(user1, msg, reply_markup=chat_keyboard)
        await context.bot.send_message(user2, msg, reply_markup=chat_keyboard)

async def next_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    await find_partner(update, context)

async def stop_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    await disconnect(user_id, context)

    await update.message.reply_text(
        "⛔ Chat ended.",
        reply_markup=main_keyboard
    )

# ====== PROFILE ======

async def open_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    user = users[user_id]

    profile_text = (
        "👤 Your Profile\n\n"
        f"Gender: {user['gender'] or 'Not set'}\n"
        f"Age: {user['age'] or 'Not set'}\n"
        f"Country: {user['country'] or 'Not set'}"
    )

    await update.message.reply_text(
        profile_text,
        reply_markup=profile_keyboard
    )

# ====== SETTINGS ======

async def open_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙ Settings\n\nSelect option:",
        reply_markup=settings_keyboard
    )

# ====== MESSAGES ======

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    text = update.message.text

    if user_id not in users:
        return

    user = users[user_id]
    partner = get_partner(user_id)

    # ===== GENDER SELECTION =====
    if text in ["👨 Male", "👩 Female"]:
        user["gender"] = text.replace("👨 ", "").replace("👩 ", "")

        await update.message.reply_text(
            "✅ Gender saved!",
            reply_markup=main_keyboard
        )
        return

    # ===== MAIN MENU =====
    if text == "🔍 Find Partner":
        await find_partner(update, context)
        return

    if text == "👤 Profile":
        await open_profile(update, context)
        return

    if text == "⚙ Settings":
        await open_settings(update, context)
        return

    # ===== PROFILE SETTINGS =====
    if text == "🎂 Set Age":
        context.user_data["setting_age"] = True
        await update.message.reply_text("Enter your age:")
        return

    if context.user_data.get("setting_age"):
        user["age"] = text
        context.user_data["setting_age"] = False

        await update.message.reply_text(
            "🎂 Age saved!",
            reply_markup=profile_keyboard
        )
        return

    if text == "🌍 Set Country":
        context.user_data["setting_country"] = True
        await update.message.reply_text("Enter your country:")
        return

    if context.user_data.get("setting_country"):
        user["country"] = text
        context.user_data["setting_country"] = False

        await update.message.reply_text(
            "🌍 Country saved!",
            reply_markup=profile_keyboard
        )
        return

    if text == "🔙 Back":
        await update.message.reply_text(
            "⬅ Back to menu",
            reply_markup=main_keyboard
        )
        return

    # ===== SETTINGS =====
    if text == "💎 Premium":
        await update.message.reply_text(
            "💎 Premium Features",
            reply_markup=premium_keyboard
        )
        return

    if "Premium" in text:
        await update.message.reply_text(
            "💎 Premium required for this feature."
        )
        return

    if text == "🚫 Report":
        if partner:
            await update.message.reply_text("🚫 Partner reported.")
        else:
            await update.message.reply_text("No partner to report.")
        return

    # ===== CHAT FORWARDING =====
    if partner:
        await context.bot.send_message(partner, text)

# ====== RUN ======

app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("Bot Running...")

app.run_polling(drop_pending_updates=True)
