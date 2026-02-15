import os
import logging
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
    PicklePersistence,
    filters,
)

# ===================== CONFIG & LOGGING =====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)

TOKEN = os.environ.get("7568782062:AAHiNQvaGbnqDfu78iZinGaSBIbgtx_UUxQ")

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

async def end_chat(uid, partner_id, context, reason="ended"):
    """Properly disconnects two users and cleans the state."""
    # Remove from active chats
    active_chats = context.bot_data.get('active_chats', {})
    active_chats.pop(uid, None)
    active_chats.pop(partner_id, None)
    
    # Notify User A
    try:
        await context.bot.send_message(
            uid, 
            "❌ Chat ended." if reason == "ended" else "⏭ Finding someone new...", 
            reply_markup=MAIN_MENU
        )
    except: pass
    
    # Notify User B
    try:
        await context.bot.send_message(
            partner_id, 
            "❌ Your partner left the chat." if reason == "ended" else "⏭ Your partner skipped. Finding you a new match...", 
            reply_markup=MAIN_MENU
        )
        # If the partner was skipped, automatically put them back in queue
        if reason == "skipped":
            await find_partner_logic(partner_id, context)
    except: pass

async def find_partner_logic(uid, context):
    """Internal logic to match users or put them in queue."""
    user_info = context.bot_data.get('users', {}).get(uid)
    
    # Check for registration
    if not user_info or not user_info.get('gender'):
        await context.bot.send_message(uid, "❗ Please use /start to set your profile first.")
        return

    # Initialize data structures
    if 'male_queue' not in context.bot_data: context.bot_data['male_queue'] = []
    if 'female_queue' not in context.bot_data: context.bot_data['female_queue'] = []
    if 'active_chats' not in context.bot_data: context.bot_data['active_chats'] = {}

    my_gender = user_info['gender']
    target_queue = context.bot_data['female_queue'] if my_gender == "male" else context.bot_data['male_queue']
    my_queue = context.bot_data['male_queue'] if my_gender == "male" else context.bot_data['female_queue']

    # Matching Logic
    if target_queue:
        partner_id = target_queue.pop(0)
        context.bot_data['active_chats'][uid] = partner_id
        context.bot_data['active_chats'][partner_id] = uid
        
        for person, other in [(uid, partner_id), (partner_id, uid)]:
            p_info = context.bot_data['users'].get(other, {})
            card = (
                "💖 **Match Found!**\n"
                f"👤 Gender: {p_info.get('gender','Unknown').capitalize()}\n"
                "──────────────────\n"
                "💬 Start typing! Only text is allowed."
            )
            await context.bot.send_message(person, card, reply_markup=chat_control_buttons(), parse_mode="Markdown")
    else:
        if uid not in my_queue:
            my_queue.append(uid)
            await context.bot.send_message(uid, "⏳ Searching for a partner... please wait.")

# ===================== COMMAND HANDLERS =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if 'users' not in context.bot_data: context.bot_data['users'] = {}
    
    context.bot_data['users'][uid] = {"gender": None}

    kb = [[
        InlineKeyboardButton("👦 Male", callback_data="reg_male"),
        InlineKeyboardButton("👧 Female", callback_data="reg_female"),
    ]]
    await update.message.reply_text(
        "👋 Welcome to DateMate ❤️\nSelect your gender:",
        reply_markup=InlineKeyboardMarkup(kb),
    )

async def handle_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    gender = q.data.split("_")[1]
    uid = q.from_user.id
    
    context.bot_data['users'][uid]["gender"] = gender
    await q.edit_message_text(f"✅ Registered as {gender.capitalize()}.")
    await context.bot.send_message(uid, "Ready to chat!", reply_markup=MAIN_MENU)

async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    active_chats = context.bot_data.get('active_chats', {})

    # 1. Menu Interactions
    if text == "⚡ Find a partner":
        if uid in active_chats:
            await update.message.reply_text("⚠️ You are already in a chat!")
        else:
            await find_partner_logic(uid, context)
        return
    
    elif text == "👤 My Profile":
        u = context.bot_data.get('users', {}).get(uid, {})
        await update.message.reply_text(f"👤 **Your Profile**\nGender: {u.get('gender','Not set').capitalize()}", parse_mode="Markdown")
        return

    # 2. Chat Relay
    if uid in active_chats:
        partner_id = active_chats[uid]
        try:
            await context.bot.send_message(partner_id, text)
        except:
            await update.message.reply_text("❌ Failed to deliver message. Your partner might have blocked the bot.")
    else:
        await update.message.reply_text("Click '⚡ Find a partner' to start.")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    active_chats = context.bot_data.get('active_chats', {})
    
    if uid not in active_chats:
        await q.message.reply_text("❌ This chat session has expired.")
        return

    partner_id = active_chats[uid]

    if q.data == "chat_exit":
        await end_chat(uid, partner_id, context, reason="ended")
    elif q.data == "chat_next":
        await end_chat(uid, partner_id, context, reason="skipped")
        await find_partner_logic(uid, context)

# ===================== MEDIA BLOCKER =====================

async def media_blocker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text("🚫 **Only text messages are allowed.**\nPhotos, stickers, and videos are blocked for safety.")

# ===================== MAIN APP =====================

if __name__ == "__main__":
    # Persistence saves your data to a file so it survives restarts
    persistence = PicklePersistence(filepath="datemate_storage.pickle")
    
    app = ApplicationBuilder().token(TOKEN).persistence(persistence).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_registration, pattern="^reg_"))
    app.add_handler(CallbackQueryHandler(callback_handler, pattern="^chat_"))
    
    # 1. First, handle legitimate text and commands
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))
    
    # 2. Second, block all other media types (Stickers, Photos, Videos, etc)
    app.add_handler(MessageHandler(filters.ALL & ~filters.TEXT & ~filters.COMMAND, media_blocker))

    print("🔥 DateMate is Running...")
    app.run_polling()
