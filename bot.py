import os
import random
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

TOKEN = os.environ.get("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN not set")

waiting_users = []
active_chats = {}
profiles = {}
user_state = {}

MAIN_MENU = ReplyKeyboardMarkup(
    [["⚡ Find Partner", "👤 My Profile"],
     ["⚙ Settings"]],
    resize_keyboard=True
)

GENDER_MENU = ReplyKeyboardMarkup(
    [["👨 Male", "👩 Female"]],
    resize_keyboard=True
)

SETTINGS_MENU = ReplyKeyboardMarkup(
    [["💎 Match with Male", "💎 Match with Female"],
     ["🔙 Back"]],
    resize_keyboard=True
)

CHAT_MENU = ReplyKeyboardMarkup(
    [["⏭ NEXT", "❌ END"]],
    resize_keyboard=True
)

# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state[user_id] = "gender"

    await update.message.reply_text(
        "🔥 Welcome to DateMate!\n\nSelect your gender:",
        reply_markup=GENDER_MENU
    )

# ================= PROFILE =================

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    profile = profiles.get(user_id, {})

    gender = profile.get("gender", "Not set")
    age = profile.get("age", "Not set")
    country = profile.get("country", "Not set")

    await update.message.reply_text(
        f"👤 Your Profile\n\n"
        f"👫 Gender: {gender}\n"
        f"🎂 Age: {age}\n"
        f"🌍 Country: {country}",
        reply_markup=MAIN_MENU
    )

# ================= SETTINGS =================

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙ Settings\n\nPremium options:",
        reply_markup=SETTINGS_MENU
    )

# ================= MATCHMAKING =================

async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    profile = profiles.get(user_id, {})
    if not all(k in profile for k in ["gender", "age", "country"]):
        await update.message.reply_text(
            "❗ Complete profile first",
            reply_markup=MAIN_MENU
        )
        return

    if user_id in waiting_users:
        return

    waiting_users.append(user_id)

    await update.message.reply_text("⏳ Searching for partner...")

    if len(waiting_users) >= 2:
        user1 = waiting_users.pop(0)
        user2 = waiting_users.pop(0)

        if user1 == user2:
            waiting_users.append(user2)
            return

        active_chats[user1] = user2
        active_chats[user2] = user1

        await context.bot.send_message(
            user1,
            "🤝 Partner Found!\n\n🚫 No media allowed\n🔗 Links blocked",
            reply_markup=CHAT_MENU
        )

        await context.bot.send_message(
            user2,
            "🤝 Partner Found!\n\n🚫 No media allowed\n🔗 Links blocked",
            reply_markup=CHAT_MENU
        )

# ================= NEXT =================

async def next_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    partner_id = active_chats.get(user_id)

    if partner_id:
        del active_chats[user_id]
        del active_chats[partner_id]

        await context.bot.send_message(
            partner_id,
            "🚫 Your partner left.\n\n⚡ Click Find Partner",
            reply_markup=MAIN_MENU
        )

    await find_partner(update, context)

# ================= END =================

async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    partner_id = active_chats.get(user_id)

    if partner_id:
        del active_chats[user_id]
        del active_chats[partner_id]

        await context.bot.send_message(
            partner_id,
            "🚫 Your partner left.",
            reply_markup=MAIN_MENU
        )

    await update.message.reply_text(
        "❌ Chat ended",
        reply_markup=MAIN_MENU
    )

# ================= MESSAGE ROUTER =================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    state = user_state.get(user_id)

    if text == "👨 Male":
        profiles.setdefault(user_id, {})["gender"] = "Male"
        user_state[user_id] = "age"

        await update.message.reply_text("🎂 Send your age:")
        return

    if text == "👩 Female":
        profiles.setdefault(user_id, {})["gender"] = "Female"
        user_state[user_id] = "age"

        await update.message.reply_text("🎂 Send your age:")
        return

    if state == "age":
        profiles.setdefault(user_id, {})["age"] = text
        user_state[user_id] = "country"

        await update.message.reply_text("🌍 Send your country:")
        return

    if state == "country":
        profiles.setdefault(user_id, {})["country"] = text
        user_state[user_id] = None

        await update.message.reply_text(
            "✅ Profile Complete!",
            reply_markup=MAIN_MENU
        )
        return

    if text == "⚡ Find Partner":
        await find_partner(update, context)
        return

    if text == "👤 My Profile":
        await profile(update, context)
        return

    if text == "⚙ Settings":
        await settings(update, context)
        return

    if text.startswith("💎"):
        await update.message.reply_text("💎 Premium Required")
        return

    if text == "⏭ NEXT":
        await next_chat(update, context)
        return

    if text == "❌ END":
        await end_chat(update, context)
        return

    partner_id = active_chats.get(user_id)

    if partner_id:
        await context.bot.send_message(partner_id, text)

# ================= MEDIA BLOCK =================

async def block_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Only text allowed")

# ================= MAIN =================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(MessageHandler(filters.ALL & ~filters.TEXT, block_media))

print("Bot running...")
app.run_polling()
