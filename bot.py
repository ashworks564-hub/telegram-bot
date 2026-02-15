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

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.environ.get("7568782062:AAHiNQvaGbnqDfu78iZinGaSBIbgtx_UUxQ")

# ===================== CONSTANTS =====================
COUNTRIES = ["🇮🇳 India", "🇺🇸 USA", "🇬🇧 UK", "🇨🇦 Canada", "🇦🇺 Australia", "🇩🇪 Germany"]

# Queues (Now handled via context.bot_data for persistence)
# bot_data['male_queue'] = []
# bot_data['female_queue'] = []
# bot_data['active_chats'] = {user_id: partner_id}

# ===================== UI COMPONENTS =====================
MAIN_MENU = ReplyKeyboardMarkup(
    [["⚡ Find a partner", "👤 My Profile"], ["⚙️ Settings"]],
    resize_keyboard=True
)

def chat_control_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭ NEXT", callback_data="chat_next"),
            InlineKeyboardButton("❌ EXIT", callback_data="chat_exit"),
        ]
    ])

# ===================== HELPERS =====================
async def end_chat(uid, partner_id, context, reason="ended"):
    """Cleanly disconnects two users."""
    if uid in context.bot_data.get('active_chats', {}):
        del context.bot_data['active_chats'][uid]
    if partner_id in context.bot_data.get('active_chats', {}):
        del context.bot_data['active_chats'][partner_id]
    
    msg = "❌ Chat ended." if reason == "ended" else "⏭ Partner skipped. Finding someone else..."
    
    try:
        await context.bot.send_message(partner_id, msg, reply_markup=MAIN_MENU)
    except: pass
    
    try:
        await context.bot.send_message(uid, "Chat closed.", reply_markup=MAIN_MENU)
    except: pass

# ===================== HANDLERS =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    # Initialize user in bot_data if not exists
    if 'users' not in context.bot_data: context.bot_data['users'] = {}
    
    context.bot_data['users'][uid] = {
        "gender": None,
        "age": "Not set",
        "country": "Not set",
    }

    kb = [[
        InlineKeyboardButton("👦 Male", callback_data="reg_male"),
        InlineKeyboardButton("👧 Female", callback_data="reg_female"),
    ]]

    await update.message.reply_text(
        "👋 Welcome to DateMate ❤️\nSelect your gender to begin:",
        reply_markup=InlineKeyboardMarkup(kb),
    )

async def handle_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    data = q.data.split("_")
    uid = q.from_user.id
    
    if data[0] == "reg":
        gender = data[1]
        context.bot_data['users'][uid]["gender"] = gender
        await q.edit_message_text(f"✅ Gender set to {gender.capitalize()}!")
        await context.bot.send_message(uid, "You're all set! Use the menu below to find a partner.", reply_markup=MAIN_MENU)

async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_info = context.bot_data.get('users', {}).get(uid)

    if not user_info or not user_info['gender']:
        await update.message.reply_text("Please /start first.")
        return

    # Check if already in chat
    if uid in context.bot_data.get('active_chats', {}):
        await update.message.reply_text("You are already in a chat!")
        return

    # Initialize queues
    if 'male_queue' not in context.bot_data: context.bot_data['male_queue'] = []
    if 'female_queue' not in context.bot_data: context.bot_data['female_queue'] = []
    if 'active_chats' not in context.bot_data: context.bot_data['active_chats'] = {}

    my_gender = user_info['gender']
    target_queue = context.bot_data['female_queue'] if my_gender == "male" else context.bot_data['male_queue']
    my_queue = context.bot_data['male_queue'] if my_gender == "male" else context.bot_data['female_queue']

    if target_queue:
        partner_id = target_queue.pop(0)
        context.bot_data['active_chats'][uid] = partner_id
        context.bot_data['active_chats'][partner_id] = uid
        
        # Notify both
        for person, other in [(uid, partner_id), (partner_id, uid)]:
            p_info = context.bot_data['users'].get(other, {})
            card = (
                "💖 **Match Found!**\n"
                f"👤 Gender: {p_info.get('gender')}\n"
                f"🎂 Age: {p_info.get('age')}\n"
                f"🌍 Country: {p_info.get('country')}\n\n"
                "Type a message to start chatting!"
            )
            await context.bot.send_message(person, card, reply_markup=chat_control_buttons(), parse_mode="Markdown")
    else:
        if uid not in my_queue:
            my_queue.append(uid)
            await update.message.reply_text("⏳ Searching for a partner... please wait.")
        else:
            await update.message.reply_text("⏳ Still searching...")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    active_chats = context.bot_data.get('active_chats', {})

    # 1. Handle Menu Buttons
    if text == "⚡ Find a partner":
        await find_partner(update, context)
        return
    elif text == "👤 My Profile":
        u = context.bot_data['users'].get(uid, {})
        await update.message.reply_text(f"Your Profile:\nGender: {u.get('gender')}\nAge: {u.get('age')}\nCountry: {u.get('country')}")
        return

    # 2. Handle Chat Relay
    if uid in active_chats:
        partner_id = active_chats[uid]
        await context.bot.send_message(partner_id, text)
    else:
        await update.message.reply_text("You are not in a chat. Click 'Find a partner'!")

async def chat_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    active_chats = context.bot_data.get('active_chats', {})
    
    if uid not in active_chats:
        await q.edit_message_text("This chat session has already ended.")
        return

    partner_id = active_chats[uid]

    if q.data == "chat_exit":
        await end_chat(uid, partner_id, context, reason="ended")
    
    elif q.data == "chat_next":
        await end_chat(uid, partner_id, context, reason="skipped")
        # Reuse logic to find new partner
        await find_partner(update, context)

# ===================== MAIN =====================
if __name__ == "__main__":
    # Use Persistence so data survives a server restart
    persistence = PicklePersistence(filepath="datemate_data.pickle")
    
    app = ApplicationBuilder().token(TOKEN).persistence(persistence).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_registration, pattern="^reg_"))
    app.add_handler(CallbackQueryHandler(chat_callback_handler, pattern="^chat_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("🚀 DateMate is Online with Persistence...")
    app.run_polling()
