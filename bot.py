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

# ===================== CONFIG & LOGGING =====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("7568782062:AAHiNQvaGbnqDfu78iZinGaSBIbgtx_UUxQ")
if not TOKEN:
    raise ValueError("TOKEN environment variable is not set!")

# ===================== JSON PERSISTENCE (Render-safe) =====================
# FIX 1: Replace PicklePersistence with atomic JSON writes.
# Render's filesystem is ephemeral across DEPLOYS, but data survives
# normal restarts within the same deploy. Atomic writes prevent corruption.

DATA_FILE = Path("datemate_data.json")
_save_lock = asyncio.Lock()  # FIX 3 (partial): thread-safe file writes


def load_data() -> dict:
    """Load bot data from JSON file, return empty structure if missing."""
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load data file, starting fresh: {e}")
    return {
        "users": {},
        "active_chats": {},
        "male_queue": [],
        "female_queue": [],
    }


async def save_data(data: dict):
    """Atomically write data to JSON. Uses a temp file + rename to avoid corruption."""
    async with _save_lock:
        tmp = DATA_FILE.with_suffix(".tmp")
        try:
            with open(tmp, "w") as f:
                json.dump(data, f)
            tmp.replace(DATA_FILE)  # atomic on most OSes
        except IOError as e:
            logger.error(f"Failed to save data: {e}")


# Load once at startup into memory; persist after every mutation.
bot_data = load_data()

# ===================== UI COMPONENTS =====================
MAIN_MENU = ReplyKeyboardMarkup(
    [["⚡ Find a partner", "👤 My Profile"]],
    resize_keyboard=True
)


def chat_control_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭ NEXT", callback_data="chat_next"),
            InlineKeyboardButton("❌ EXIT", callback_data="chat_exit"),
        ]
    ])


# ===================== CORE LOGIC HELPERS =====================

# FIX 3: Per-operation asyncio lock to prevent race conditions in queue matching.
_match_lock = asyncio.Lock()


async def end_chat(uid: int, partner_id: int, context: ContextTypes.DEFAULT_TYPE, reason: str = "ended"):
    """Properly disconnects two users and cleans state."""
    # FIX 4: Remove both users atomically so no ghost sessions remain.
    uid_str = str(uid)
    pid_str = str(partner_id)

    bot_data["active_chats"].pop(uid_str, None)
    bot_data["active_chats"].pop(pid_str, None)
    await save_data(bot_data)

    msg_to_uid = "❌ Chat ended." if reason == "ended" else "⏭ Finding someone new..."
    msg_to_partner = (
        "❌ Your partner left the chat."
        if reason == "ended"
        else "⏭ Your partner skipped. Finding you a new match..."
    )

    # FIX 2: Replaced bare except with specific error logging.
    try:
        await context.bot.send_message(uid, msg_to_uid, reply_markup=MAIN_MENU)
    except Exception as e:
        logger.warning(f"Could not notify user {uid} of chat end: {e}")

    try:
        await context.bot.send_message(partner_id, msg_to_partner, reply_markup=MAIN_MENU)
        if reason == "skipped":
            await find_partner_logic(partner_id, context)
    except Exception as e:
        logger.warning(f"Could not notify partner {partner_id} of chat end: {e}")


async def find_partner_logic(uid: int, context: ContextTypes.DEFAULT_TYPE):
    """Match users or put them in queue. Protected by lock to prevent race conditions."""
    uid_str = str(uid)
    user_info = bot_data.get("users", {}).get(uid_str)

    if not user_info or not user_info.get("gender"):
        try:
            await context.bot.send_message(uid, "❗ Please use /start to set your profile first.")
        except Exception as e:
            logger.warning(f"Could not send profile reminder to {uid}: {e}")
        return

    my_gender = user_info["gender"]

    # FIX 3: Lock the entire match operation so two users can't race into the same slot.
    async with _match_lock:
        # FIX 4: Check if user is already in an active chat before queuing.
        if uid_str in bot_data["active_chats"]:
            try:
                await context.bot.send_message(uid, "⚠️ You are already in a chat!")
            except Exception as e:
                logger.warning(f"Could not warn {uid} about existing chat: {e}")
            return

        target_queue_key = "female_queue" if my_gender == "male" else "male_queue"
        my_queue_key = "male_queue" if my_gender == "male" else "female_queue"

        target_queue = bot_data[target_queue_key]
        my_queue = bot_data[my_queue_key]

        # FIX 3: Filter out self-matches (user somehow in the opposite queue).
        target_queue[:] = [u for u in target_queue if u != uid_str]

        if target_queue:
            partner_id_str = target_queue.pop(0)
            partner_id = int(partner_id_str)

            bot_data["active_chats"][uid_str] = partner_id_str
            bot_data["active_chats"][partner_id_str] = uid_str
            await save_data(bot_data)

        else:
            # Put in queue only if not already waiting.
            if uid_str not in my_queue:
                my_queue.append(uid_str)
                await save_data(bot_data)

            try:
                await context.bot.send_message(uid, "⏳ Searching for a partner... please wait.\n\nSend /stop to cancel.")
            except Exception as e:
                logger.warning(f"Could not send queue message to {uid}: {e}")
            return

        # Notify both users of the match (outside the lock since I/O can be slow).
        partner_id_str = bot_data["active_chats"][uid_str]
        partner_id = int(partner_id_str)

        for person, other_str in [(uid, partner_id_str), (partner_id, uid_str)]:
            p_info = bot_data["users"].get(other_str, {})
            card = (
                "💖 *Match Found!*\n"
                f"👤 Gender: {p_info.get('gender', 'Unknown').capitalize()}\n"
                "──────────────────\n"
                "💬 Start typing! Only text is allowed.\n"
                "Use /stop to leave anytime."
            )
            try:
                await context.bot.send_message(
                    person, card,
                    reply_markup=chat_control_buttons(),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Could not send match card to {person}: {e}")


async def leave_queue(uid: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Remove a user from whichever queue they're in. Returns True if they were in a queue."""
    uid_str = str(uid)
    removed = False
    for queue_key in ("male_queue", "female_queue"):
        if uid_str in bot_data[queue_key]:
            bot_data[queue_key].remove(uid_str)
            removed = True
    if removed:
        await save_data(bot_data)
    return removed


# ===================== COMMAND HANDLERS =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    uid_str = str(uid)

    # If they're in a chat, end it first.
    if uid_str in bot_data["active_chats"]:
        partner_id = int(bot_data["active_chats"][uid_str])
        await end_chat(uid, partner_id, context, reason="ended")

    await leave_queue(uid, context)

    if "users" not in bot_data:
        bot_data["users"] = {}

    bot_data["users"][uid_str] = {"gender": None}
    await save_data(bot_data)

    kb = [[
        InlineKeyboardButton("👦 Male", callback_data="reg_male"),
        InlineKeyboardButton("👧 Female", callback_data="reg_female"),
    ]]
    await update.message.reply_text(
        "👋 Welcome to DateMate ❤️\nSelect your gender:",
        reply_markup=InlineKeyboardMarkup(kb),
    )


# FIX: New /stop command — leaves queue OR active chat cleanly.
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    uid_str = str(uid)

    # Case 1: User is in an active chat.
    if uid_str in bot_data["active_chats"]:
        partner_id = int(bot_data["active_chats"][uid_str])
        await end_chat(uid, partner_id, context, reason="ended")
        return

    # Case 2: User is waiting in a queue.
    was_in_queue = await leave_queue(uid, context)
    if was_in_queue:
        await update.message.reply_text("✅ Removed from the queue.", reply_markup=MAIN_MENU)
        return

    # Case 3: Not in a chat or queue.
    await update.message.reply_text("ℹ️ You're not in a chat or queue right now.", reply_markup=MAIN_MENU)


# FIX: /leave is an alias for /stop (user-friendly).
async def leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await stop(update, context)


async def handle_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    gender = q.data.split("_")[1]
    uid = q.from_user.id
    uid_str = str(uid)

    if uid_str not in bot_data.get("users", {}):
        bot_data.setdefault("users", {})[uid_str] = {}

    bot_data["users"][uid_str]["gender"] = gender
    await save_data(bot_data)

    try:
        await q.edit_message_text(f"✅ Registered as {gender.capitalize()}.")
    except Exception as e:
        logger.warning(f"Could not edit registration message for {uid}: {e}")

    await context.bot.send_message(uid, "Ready to chat!", reply_markup=MAIN_MENU)


async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    uid_str = str(uid)
    text = update.message.text

    # 1. Menu interactions.
    if text == "⚡ Find a partner":
        if uid_str in bot_data.get("active_chats", {}):
            await update.message.reply_text("⚠️ You are already in a chat! Use /stop to leave first.")
        else:
            await find_partner_logic(uid, context)
        return

    elif text == "👤 My Profile":
        u = bot_data.get("users", {}).get(uid_str, {})
        gender = u.get("gender", "Not set").capitalize()
        status = "In a chat 💬" if uid_str in bot_data.get("active_chats", {}) else "Not in a chat"
        await update.message.reply_text(
            f"👤 *Your Profile*\nGender: {gender}\nStatus: {status}",
            parse_mode="Markdown"
        )
        return

    # 2. Chat relay.
    if uid_str in bot_data.get("active_chats", {}):
        partner_id = int(bot_data["active_chats"][uid_str])
        try:
            await context.bot.send_message(partner_id, text)
        except Exception as e:
            logger.warning(f"Failed to relay message from {uid} to {partner_id}: {e}")
            await update.message.reply_text(
                "❌ Failed to deliver message. Your partner may have blocked the bot."
            )
    else:
        await update.message.reply_text("Click '⚡ Find a partner' to start chatting.")


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    uid_str = str(uid)

    # FIX 4: Check for ghost sessions — button pressed after chat already ended.
    if uid_str not in bot_data.get("active_chats", {}):
        try:
            await q.edit_message_reply_markup(reply_markup=None)  # Remove stale buttons.
        except Exception:
            pass
        await q.message.reply_text("❌ This chat session has already ended.", reply_markup=MAIN_MENU)
        return

    partner_id = int(bot_data["active_chats"][uid_str])

    if q.data == "chat_exit":
        await end_chat(uid, partner_id, context, reason="ended")
    elif q.data == "chat_next":
        await end_chat(uid, partner_id, context, reason="skipped")
        await find_partner_logic(uid, context)


# ===================== MEDIA BLOCKER =====================

async def media_blocker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚫 *Only text messages are allowed.*\nPhotos, stickers, and videos are blocked for safety.",
        parse_mode="Markdown"
    )


# ===================== MAIN APP =====================

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    # Handlers — order matters.
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))    # FIX: leave queue or chat
    app.add_handler(CommandHandler("leave", leave))  # FIX: alias for /stop

    app.add_handler(CallbackQueryHandler(handle_registration, pattern="^reg_"))
    app.add_handler(CallbackQueryHandler(callback_handler, pattern="^chat_"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))
    app.add_handler(MessageHandler(filters.ALL & ~filters.TEXT & ~filters.COMMAND, media_blocker))

    logger.info("🔥 DateMate is Running...")
    app.run_polling()
