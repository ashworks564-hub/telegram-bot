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
import uuid

TOKEN = "7568782062:AAF-abA22OoC2icewtwKROXS8kIWulCGO6k"

# ===================== DATA =====================
users = {}              # uid -> profile
male_queue = []
female_queue = []
active = {}             # uid -> partner uid

COUNTRIES = [
    "🇮🇳 India", "🇺🇸 USA", "🇬🇧 UK", "🇨🇦 Canada", "🇦🇺 Australia",
    "🇩🇪 Germany", "🇫🇷 France", "🇯🇵 Japan", "🇰🇷 Korea",
    "🇧🇷 Brazil", "🇷🇺 Russia", "🇮🇹 Italy", "🇪🇸 Spain",
    "🇳🇬 Nigeria", "🇲🇾 Malaysia", "🇸🇦 Saudi Arabia",
]

# ===================== UI =====================
MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["⚡ Find a partner", "👤 My Profile"],
        ["⚙️ Settings"]
    ],
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
    uid = update.effective_user.id
    users[uid] = {
        "gender": None,
        "age": None,
        "country": None,
    }

    kb = [
        [
            InlineKeyboardButton("👦 Male", callback_data="gender_male"),
            InlineKeyboardButton("👧 Female", callback_data="gender_female"),
        ]
    ]

    await update.message.reply_text(
        "👋 **Welcome to DateMate ❤️**\n\n"
        "Please select your gender:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )

# ===================== GENDER =====================
async def set_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    gender = q.data.split("_")[1]
    uid = q.from_user.id

    users.setdefault(uid, {})
    users[uid]["gender"] = gender

    await q.edit_message_text(
        f"✅ **Gender saved:** {gender.capitalize()}\n\n👇 Use the menu below",
        parse_mode="Markdown",
    )
    await context.bot.send_message(uid, "Ready to go 🚀", reply_markup=MAIN_MENU)

# ===================== PROFILE =====================
async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = users.get(uid)

    if not u:
        await update.message.reply_text("Use /start first.")
        return

    text = (
        "👤 **Your Profile**\n\n"
        f"👥 Gender: {u['gender'] or 'Not set'}\n"
        f"🎂 Age: {u['age'] or 'Not set'}\n"
        f"🌍 Country: {u['country'] or 'Not set'}"
    )

    kb = [
        [InlineKeyboardButton("🎂 Set Age", callback_data="set_age")],
        [InlineKeyboardButton("🌍 Set Country", callback_data="set_country")],
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )

# ===================== AGE =====================
async def ask_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["awaiting_age"] = True
    await q.edit_message_text("🎂 Send your age (e.g. 18, 21, 25)")

# ===================== COUNTRY =====================
async def ask_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    buttons = [
        [InlineKeyboardButton(c, callback_data=f"country_{c}")]
        for c in COUNTRIES
    ]

    await q.edit_message_text(
        "🌍 **Select your country:**",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )

async def save_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    country = q.data.replace("country_", "")
    users[uid]["country"] = country

    await q.edit_message_text(f"🌍 Country saved: **{country}**", parse_mode="Markdown")

# ===================== FIND PARTNER =====================
async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = users.get(uid)

    if not u or not u.get("gender"):
        await update.message.reply_text("❗ Set gender first using /start")
        return

    if uid in active:
        await update.message.reply_text("⚠️ You are already chatting.")
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
        my_queue.append(uid)
        await update.message.reply_text("⏳ Waiting for a partner...")

# ===================== MATCH UI =====================
async def show_match(uid, partner, context):
    p = users.get(partner, {})
    card = (
        "✅ **Partner Matched!**\n\n"
        f"👥 Gender: {p.get('gender','Unknown')}\n"
        f"🎂 Age: {p.get('age','Unknown')}\n"
        f"🌍 Country: {p.get('country','Unknown')}\n\n"
        "🔒 Links blocked\n"
        "⏳ Media allowed after 2 minutes"
    )

    await context.bot.send_message(
        uid,
        card,
        reply_markup=chat_buttons(),
        parse_mode="Markdown",
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
            await update.message.reply_text("❌ Send a valid number.")
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

    if action == "exit":
        if partner:
            active.pop(partner, None)
            await context.bot.send_message(partner, "❌ Partner left the chat")
        active.pop(uid, None)
        await q.edit_message_text("You exited the chat ❌")

    elif action == "next":
        if partner:
            active.pop(partner, None)
            await context.bot.send_message(partner, "⏭ Partner skipped")
            active.pop(uid, None)

        await q.edit_message_text("⏳ Finding new partner...")
        fake = Update(update.update_id, message=q.message)
        fake.message.from_user = q.from_user
        await find_partner(fake, context)

# ===================== ROUTER =====================
async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "⚡ Find a partner":
        await find_partner(update, context)
    elif text == "👤 My Profile":
        await my_profile(update, context)
    elif text == "⚙️ Settings":
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
app.add_handler(CallbackQueryHandler(buttons, pattern="^(next|exit)$"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

print("🔥 DateMate bot running...")
app.run_polling()
