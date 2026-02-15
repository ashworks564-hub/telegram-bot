import os
import json
import logging
import asyncio
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================= CONFIG =================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN environment variable is not set!")

DATA_FILE = "datemate_data.json"
lock = asyncio.Lock()

# ================= DATA =================

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {
            "users": {},
            "queue": [],
            "active": {},
            "reports": {},
            "bans": {},
        }

async def save_data(data):
    async with lock:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f)

bot_data = load_data()

# ================= MENUS =================

MAIN_MENU = ReplyKeyboardMarkup(
    [["⚡ Find Partner"], ["👤 Profile", "⚙ Settings"]],
    resize_keyboard=True
)

def chat_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭ NEXT", callback_data="next"),
            InlineKeyboardButton("❌ STOP", callback_data="stop"),
        ]
    ])

def profile_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎂 Set Age", callback_data="set_age")],
        [InlineKeyboardButton("🚻 Set Gender", callback_data="set_gender")],
        [InlineKeyboardButton("🌍 Set Country", callback_data="set_country")],
    ])

def settings_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Match Male Only (Premium)", callback_data="premium")],
        [InlineKeyboardButton("💎 Match Female Only (Premium)", callback_data="premium")],
        [InlineKeyboardButton("🚨 Report User", callback_data="report")],
    ])

# ================= HELPERS =================

def is_banned(uid):
    ban = bot_data["bans"].get(str(uid))
    if not ban:
        return False
    if datetime.utcnow() > datetime.fromisoformat(ban):
        bot_data["bans"].pop(str(uid))
        return False
    return True

async def ban_user(uid):
    unban_time = datetime.utcnow() + timedelta(hours=24)
    bot_data["bans"][str(uid)] = unban_time.isoformat()
    await save_data(bot_data)

async def end_chat(uid, context, notify=True):
    uid_str = str(uid)

    if uid_str not in bot_data["active"]:
        return

    partner = int(bot_data["active"][uid_str])

    bot_data["active"].pop(uid_str, None)
    bot_data["active"].pop(str(partner), None)

    await save_data(bot_data)

    if notify:
        try:
            await context.bot.send_message(
                partner,
                "🚫 Your partner has disconnected.\n\nClick ⚡ Find Partner to continue.",
                reply_markup=MAIN_MENU
            )
        except:
            pass

async def find_partner(uid, context):
    uid_str = str(uid)

    if is_banned(uid):
        ban_time = bot_data["bans"][uid_str]
        await context.bot.send_message(
            uid,
            f"🚫 You are banned until:\n{ban_time}"
        )
        return

    if bot_data["queue"]:
        partner_str = bot_data["queue"].pop(0)
        partner = int(partner_str)

        bot_data["active"][uid_str] = partner_str
        bot_data["active"][partner_str] = uid_str

        await save_data(bot_data)

        for user, other in [(uid, partner), (partner, uid)]:
            other_data = bot_data["users"].get(str(other), {})
            await context.bot.send_message(
                user,
                "🤝 *Partner Found!*\n\n"
                f"🎂 Age: {other_data.get('age', 'Not set')}\n"
                f"🚻 Gender: {other_data.get('gender', 'Not set')}\n"
                f"🌍 Country: {other_data.get('country', 'Not set')}\n\n"
                "🚫 Links & Media Blocked",
                reply_markup=chat_buttons(),
                parse_mode="Markdown"
            )
    else:
        bot_data["queue"].append(uid_str)
        await save_data(bot_data)

        await context.bot.send_message(
            uid,
            "🔍 Finding partner for you..."
        )

# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    uid_str = str(uid)

    bot_data["users"][uid_str] = {
        "age": None,
        "gender": None,
        "country": None,
        "state": None
    }

    await save_data(bot_data)

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👦 Male", callback_data="gender_male"),
            InlineKeyboardButton("👧 Female", callback_data="gender_female"),
        ]
    ])

    await update.message.reply_text(
        "👋 Welcome to DateMate ❤️\nSelect your gender:",
        reply_markup=buttons
    )

async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    uid_str = str(uid)
    text = update.message.text

    if is_banned(uid):
        await update.message.reply_text("🚫 You are banned.")
        return

    user = bot_data["users"].get(uid_str)

    if user.get("state") == "age":
        user["age"] = text
        user["state"] = None
        await save_data(bot_data)
        await update.message.reply_text("✅ Age saved.", reply_markup=MAIN_MENU)
        return

    if user.get("state") == "country":
        user["country"] = text
        user["state"] = None
        await save_data(bot_data)
        await update.message.reply_text("✅ Country saved.", reply_markup=MAIN_MENU)
        return

    if text == "⚡ Find Partner":
        await find_partner(uid, context)
        return

    if text == "👤 Profile":
        await update.message.reply_text(
            f"👤 *Your Profile*\n\n"
            f"🎂 Age: {user.get('age')}\n"
            f"🚻 Gender: {user.get('gender')}\n"
            f"🌍 Country: {user.get('country')}",
            reply_markup=profile_buttons(),
            parse_mode="Markdown"
        )
        return

    if text == "⚙ Settings":
        await update.message.reply_text(
            "⚙ Settings",
            reply_markup=settings_buttons()
        )
        return

    if uid_str in bot_data["active"]:
        if "http" in text:
            await update.message.reply_text("🚫 Links are blocked.")
            return

        partner = int(bot_data["active"][uid_str])
        try:
            await context.bot.send_message(partner, text)
        except:
            await update.message.reply_text("❌ Failed to send.")

# ================= CALLBACKS =================

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    uid_str = str(uid)
    user = bot_data["users"][uid_str]

    await q.answer()

    if q.data.startswith("gender_"):
        gender = q.data.split("_")[1]
        user["gender"] = gender
        await save_data(bot_data)

        await q.edit_message_text(f"✅ Registered as {gender}")
        await context.bot.send_message(uid, "Ready!", reply_markup=MAIN_MENU)

    elif q.data == "set_age":
        user["state"] = "age"
        await save_data(bot_data)
        await context.bot.send_message(uid, "Enter your age:")

    elif q.data == "set_country":
        user["state"] = "country"
        await save_data(bot_data)
        await context.bot.send_message(uid, "Enter your country:")

    elif q.data == "premium":
        await context.bot.send_message(uid, "💎 Premium required.")

    elif q.data == "next":
        await end_chat(uid, context)
        await find_partner(uid, context)

    elif q.data == "stop":
        await end_chat(uid, context)

    elif q.data == "report":
        if uid_str not in bot_data["active"]:
            return

        partner = bot_data["active"][uid_str]
        bot_data["reports"][partner] = bot_data["reports"].get(partner, 0) + 1

        if bot_data["reports"][partner] >= 10:
            await ban_user(int(partner))

        await save_data(bot_data)
        await context.bot.send_message(uid, "🚨 User reported.")

# ================= MAIN =================

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("🔥 Bot Running...")
    app.run_polling()
