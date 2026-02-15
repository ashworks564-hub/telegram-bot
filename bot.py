import os
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

TOKEN = os.environ.get("TOKEN")  # Render variable

# ===================== DATA =====================
users = {}
male_queue = []
female_queue = []
active = {}

# ===================== UI =====================
MAIN_MENU = ReplyKeyboardMarkup(
    [["⚡ Find Partner", "👤 My Profile"]],
    resize_keyboard=True
)

def find_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Find Partner", callback_data="find")]
    ])

def chat_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭ NEXT", callback_data="next"),
            InlineKeyboardButton("❌ END", callback_data="end"),
        ]
    ])

# ===================== START =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    users[uid] = {
        "gender": None,
        "age": None,
        "country": None,
    }

    kb = [[
        InlineKeyboardButton("👦 Male", callback_data="gender_male"),
        InlineKeyboardButton("👧 Female", callback_data="gender_female"),
    ]]

    await update.message.reply_text(
        "👋 Welcome to DateMate ❤️\n\nSelect your gender:",
        reply_markup=InlineKeyboardMarkup(kb),
    )

# ===================== GENDER =====================
async def set_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    gender = q.data.split("_")[1]
    uid = q.from_user.id

    users.setdefault(uid, {})
    users[uid]["gender"] = gender

    await q.edit_message_text(f"✅ Registered as {gender.capitalize()}")

    await context.bot.send_message(uid, "Ready 😎", reply_markup=MAIN_MENU)

# ===================== PROFILE =====================
async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = users.get(uid)

    if not u:
        await update.message.reply_text("Use /start first.")
        return

    text = (
        "👤 Your Profile\n\n"
        f"👥 Gender: {u['gender'] or 'Not set'}\n"
        f"🎂 Age: {u['age'] or 'Not set'}\n"
        f"🌍 Country: {u['country'] or 'Not set'}"
    )

    kb = [
        [InlineKeyboardButton("🎂 Set Age", callback_data="set_age")],
        [InlineKeyboardButton("🌍 Set Country", callback_data="set_country")],
    ]

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

# ===================== AGE =====================
async def ask_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    context.user_data["awaiting_age"] = True
    await q.edit_message_text("🎂 Send your age")

# ===================== COUNTRY =====================
COUNTRIES = ["🇮🇳 India", "🇺🇸 USA", "🇬🇧 UK"]

async def ask_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    buttons = [
        [InlineKeyboardButton(c, callback_data=f"country_{c}")]
        for c in COUNTRIES
    ]

    await q.edit_message_text(
        "🌍 Select country:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def save_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    country = q.data.replace("country_", "")
    users[uid]["country"] = country

    await q.edit_message_text(f"🌍 Country saved: {country}")

# ===================== FIND PARTNER =====================
async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await find_logic(uid, context)

async def find_logic(uid, context):
    u = users.get(uid)

    if not u or not u.get("gender"):
        await context.bot.send_message(uid, "❗ Use /start first")
        return

    if uid in active:
        await context.bot.send_message(uid, "⚠️ Already chatting")
        return

    queue = female_queue if u["gender"] == "male" else male_queue
    my_queue = male_queue if u["gender"] == "male" else female_queue

    if queue:
        partner = queue.pop(0)

        active[uid] = partner
        active[partner] = uid

        await show_match(uid, partner, context)
        await show_match(partner, uid, context)
    else:
        if uid not in my_queue:
            my_queue.append(uid)

        await context.bot.send_message(uid, "⏳ Searching for partner...")

# ===================== MATCH MESSAGE =====================
async def show_match(uid, partner, context):
    p = users.get(partner, {})

    card = (
        "🤝 *Partner Found!*\n"
        "━━━━━━━━━━━━━━━\n\n"
        f"🎂 Age: {p.get('age','Unknown')}\n"
        f"🌍 Country: {p.get('country','Unknown')}\n\n"
        "━━━━━━━━━━━━━━━\n"
        "/next — find new partner\n"
        "/end — end chat"
    )

    await context.bot.send_message(uid, card, parse_mode="Markdown")

# ===================== DISCONNECT MESSAGE =====================
async def disconnect_message(uid, context):
    text = (
        "🚫 *Your partner has disconnected.*\n\n"
        "Want to meet someone new? 😌"
    )

    await context.bot.send_message(
        uid,
        text,
        reply_markup=find_button(),
        parse_mode="Markdown"
    )

# ===================== RELAY =====================
async def relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if context.user_data.get("awaiting_age"):
        try:
            age = int(update.message.text)
            users[uid]["age"] = age
            context.user_data["awaiting_age"] = False
            await update.message.reply_text("🎂 Age saved ✅")
        except:
            await update.message.reply_text("❌ Send number")
        return

    partner = active.get(uid)

    if partner:
        await context.bot.send_message(partner, update.message.text)

# ===================== BUTTONS =====================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    action = q.data
    partner = active.get(uid)

    if action == "find":
        await find_logic(uid, context)

    if not partner:
        await q.edit_message_text("❌ Chat already ended")
        return

    if action == "end":
        active.pop(partner, None)
        active.pop(uid, None)

        await disconnect_message(partner, context)
        await q.edit_message_text("❌ Chat ended")

    elif action == "next":
        active.pop(partner, None)
        active.pop(uid, None)

        await disconnect_message(partner, context)
        await q.edit_message_text("⏭ Finding new partner...")
        await find_logic(uid, context)

# ===================== ROUTER =====================
async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "⚡ Find Partner":
        await find_partner(update, context)
    elif text == "👤 My Profile":
        await my_profile(update, context)
    else:
        await relay(update, context)

# ===================== APP =====================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(set_gender, pattern="^gender_"))
app.add_handler(CallbackQueryHandler(ask_age, pattern="^set_age$"))
app.add_handler(CallbackQueryHandler(ask_country, pattern="^set_country$"))
app.add_handler(CallbackQueryHandler(save_country, pattern="^country_"))
app.add_handler(CallbackQueryHandler(buttons))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

print("🔥 DateMate Running...")
app.run_polling()
