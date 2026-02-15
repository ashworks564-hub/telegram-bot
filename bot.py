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

# ===================== CONFIG =====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ✅ FIXED TOKEN LINE
TOKEN = os.environ.get("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN environment variable is not set!")

# ===================== DATA STORAGE =====================
DATA_FILE = Path("datemate_data.json")
_save_lock = asyncio.Lock()
_match_lock = asyncio.Lock()


def load_data():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Data load failed: {e}")

    return {
        "users": {},
        "active_chats": {},
        "male_queue": [],
        "female_queue": [],
    }


async def save_data(data):
    async with _save_lock:
        tmp = DATA_FILE.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(data, f)
        tmp.replace(DATA_FILE)


bot_data = load_data()

# ===================== UI =====================
MAIN_MENU = ReplyKeyboardMarkup(
    [["⚡ Find a partner", "👤 My Profile"]],
    resize_keyboard=True
)


def chat_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭ NEXT", callback_data="chat_next"),
            InlineKeyboardButton("❌ EXIT", callback_data="chat_exit"),
        ]
    ])

# ===================== HELPERS =====================

async def leave_queue(uid):
    uid_str = str(uid)
    removed = False

    for queue in ("male_queue", "female_queue"):
        if uid_str in bot_data[queue]:
            bot_data[queue].remove(uid_str)
            removed = True

    if removed:
        await save_data(bot_data)

    return removed


async def end_chat(uid, partner_id, context, reason="ended"):
    uid_str = str(uid)
    pid_str = str(partner_id)

    bot_data["active_chats"].pop(uid_str, None)
    bot_data["active_chats"].pop(pid_str, None)

    await save_data(bot_data)

    try:
        await context.bot.send_message(uid, "❌ Chat ended.", reply_markup=MAIN_MENU)
    except:
        pass

    try:
        await context.bot.send_message(partner_id, "❌ Partner left.", reply_markup=MAIN_MENU)
    except:
        pass


async def find_partner_logic(uid, context):
    uid_str = str(uid)
    user = bot_data["users"].get(uid_str)

    if not user or not user.get("gender"):
        await context.bot.send_message(uid, "❗ Use /start first.")
        return

    gender = user["gender"]

    async with _match_lock:
        if uid_str in bot_data["active_chats"]:
            await context.bot.send_message(uid, "⚠️ Already chatting.")
            return

        target_queue = bot_data["female_queue"] if gender == "male" else bot_data["male_queue"]
        my_queue = bot_data["male_queue"] if gender == "male" else bot_data["female_queue"]

        target_queue[:] = [u for u in target_queue if u != uid_str]

        if target_queue:
            partner_id_str = target_queue.pop(0)
            partner_id = int(partner_id_str)

            bot_data["active_chats"][uid_str] = partner_id_str
            bot_data["active_chats"][partner_id_str] = uid_str

            await save_data(bot_data)

        else:
            if uid_str not in my_queue:
                my_queue.append(uid_str)
                await save_data(bot_data)

            await context.bot.send_message(uid, "⏳ Waiting for partner...")
            return

    partner_id = int(bot_data["active_chats"][uid_str])

    for person, other in [(uid, partner_id), (partner_id, uid)]:
        await context.bot.send_message(
            person,
            "💖 Match Found!\n💬 Text only",
            reply_markup=chat_buttons()
        )

# ===================== COMMANDS =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    uid_str = str(uid)

    if uid_str in bot_data["active_chats"]:
        partner_id = int(bot_data["active_chats"][uid_str])
        await end_chat(uid, partner_id, context)

    await leave_queue(uid)

    bot_data["users"][uid_str] = {"gender": None}
    await save_data(bot_data)

    kb = [[
        InlineKeyboardButton("👦 Male", callback_data="reg_male"),
        InlineKeyboardButton("👧 Female", callback_data="reg_female"),
    ]]

    await update.message.reply_text(
        "👋 Welcome to DateMate ❤️\nSelect gender:",
        reply_markup=InlineKeyboardMarkup(kb)
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    uid_str = str(uid)

    if uid_str in bot_data["active_chats"]:
        partner_id = int(bot_data["active_chats"][uid_str])
        await end_chat(uid, partner_id, context)
        return

    removed = await leave_queue(uid)

    if removed:
        await update.message.reply_text("✅ Removed from queue", reply_markup=MAIN_MENU)
    else:
        await update.message.reply_text("ℹ️ Not in queue/chat", reply_markup=MAIN_MENU)


async def leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await stop(update, context)

# ===================== CALLBACKS =====================

async def handle_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    gender = q.data.split("_")[1]
    uid = q.from_user.id
    uid_str = str(uid)

    bot_data["users"].setdefault(uid_str, {})
    bot_data["users"][uid_str]["gender"] = gender

    await save_data(bot_data)

    await q.edit_message_text(f"✅ Registered as {gender.capitalize()}")
    await context.bot.send_message(uid, "Ready!", reply_markup=MAIN_MENU)


async def chat_buttons_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    uid_str = str(uid)

    if uid_str not in bot_data["active_chats"]:
        await q.message.reply_text("❌ Chat expired", reply_markup=MAIN_MENU)
        return

    partner_id = int(bot_data["active_chats"][uid_str])

    if q.data == "chat_exit":
        await end_chat(uid, partner_id, context)

    elif q.data == "chat_next":
        await end_chat(uid, partner_id, context)
        await find_partner_logic(uid, context)

# ===================== MESSAGES =====================

async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    uid_str = str(uid)
    text = update.message.text

    if text == "⚡ Find a partner":
        await find_partner_logic(uid, context)
        return

    if text == "👤 My Profile":
        gender = bot_data["users"].get(uid_str, {}).get("gender", "Not set")
        await update.message.reply_text(f"👤 Gender: {gender}")
        return

    if uid_str in bot_data["active_chats"]:
        partner_id = int(bot_data["active_chats"][uid_str])
        await context.bot.send_message(partner_id, text)
    else:
        await update.message.reply_text("Click Find Partner")

# ===================== MAIN =====================

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("leave", leave))

    app.add_handler(CallbackQueryHandler(handle_registration, pattern="^reg_"))
    app.add_handler(CallbackQueryHandler(chat_buttons_handler, pattern="^chat_"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))

    logger.info("🔥 DateMate Running...")
    app.run_polling()

