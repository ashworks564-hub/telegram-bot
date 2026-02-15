import os
import json
import logging
import asyncio
from pathlib import Path
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN missing")

DATA_FILE = Path("datemate_data.json")
_save_lock = asyncio.Lock()
_match_lock = asyncio.Lock()


def load_data():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {
        "users": {},
        "active_chats": {},
        "queue": []
    }


async def save_data():
    async with _save_lock:
        with open(DATA_FILE, "w") as f:
            json.dump(bot_data, f)


bot_data = load_data()

MENU = ReplyKeyboardMarkup(
    [["⚡ Find Partner", "👤 My Profile"]],
    resize_keyboard=True
)


def chat_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭ NEXT", callback_data="next"),
            InlineKeyboardButton("❌ EXIT", callback_data="exit"),
        ]
    ])


# ===================== START =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    uid = str(update.effective_user.id)

    bot_data["users"][uid] = {
        "age": None,
        "country": None
    }

    await save_data()

    await update.message.reply_text(
        "👋 Welcome to DateMate ❤️",
        reply_markup=MENU
    )


# ===================== FIND PARTNER =====================

async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    uid = str(update.effective_user.id)

    if uid in bot_data["active_chats"]:
        await update.message.reply_text("⚠️ Already chatting")
        return

    async with _match_lock:

        queue = bot_data["queue"]

        if queue and queue[0] != uid:
            partner = queue.pop(0)

            bot_data["active_chats"][uid] = partner
            bot_data["active_chats"][partner] = uid

            await save_data()

        else:
            if uid not in queue:
                queue.append(uid)
                await save_data()

            await update.message.reply_text("⏳ Searching...")
            return

    # MATCH MESSAGE

    partner = bot_data["active_chats"][uid]
    p = bot_data["users"].get(partner, {})

    msg = (
        "🤝 Partner Found!\n\n"
        f"🎂 Age: {p.get('age','Unknown')}\n"
        f"🌍 Country: {p.get('country','Unknown')}\n\n"
        "/next — new partner\n"
        "/end — end chat"
    )

    await context.bot.send_message(uid, msg, reply_markup=chat_buttons())
    await context.bot.send_message(int(partner), msg, reply_markup=chat_buttons())


# ===================== RELAY =====================

async def relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    uid = str(update.effective_user.id)

    if uid in bot_data["active_chats"]:
        partner = bot_data["active_chats"][uid]

        try:
            await context.bot.send_message(int(partner), update.message.text)
        except Exception as e:
            logger.warning(e)


# ===================== BUTTONS =====================

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    uid = str(query.from_user.id)

    if uid not in bot_data["active_chats"]:
        await query.edit_message_text("Session expired ❌")
        return

    partner = bot_data["active_chats"][uid]

    if query.data == "exit":

        bot_data["active_chats"].pop(uid, None)
        bot_data["active_chats"].pop(partner, None)

        await save_data()

        await context.bot.send_message(int(partner),
            "🚫 Your partner has disconnected.\n\n⚡ Find Partner",
            reply_markup=MENU
        )

        await query.edit_message_text("Chat ended ❌")

    elif query.data == "next":

        bot_data["active_chats"].pop(uid, None)
        bot_data["active_chats"].pop(partner, None)

        await save_data()

        await context.bot.send_message(int(partner),
            "⏭ Partner skipped.\n\n⚡ Find Partner",
            reply_markup=MENU
        )

        await query.edit_message_text("⏳ Finding new partner...")
        await find_partner_logic(uid, context)


async def find_partner_logic(uid, context):
    fake_update = Update(update_id=0, message=None)
    await context.bot.send_message(int(uid), "Click ⚡ Find Partner")


# ===================== ROUTER =====================

async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.message:

        text = update.message.text

        if text == "⚡ Find Partner":
            await find_partner(update, context)
        elif text == "👤 My Profile":
            await update.message.reply_text("Profile coming soon 😎")
        else:
            await relay(update, context)


# ===================== APP =====================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))

app.add_handler(CallbackQueryHandler(buttons))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))

app.add_handler(MessageHandler(filters.ALL & ~filters.TEXT, lambda u,c: None))

print("🔥 RUNNING")
app.run_polling()
