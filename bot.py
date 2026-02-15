import os
import logging
import threading
from flask import Flask
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
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN not set")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= FLASK SERVER =================
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Bot Running 😎"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

# ================= DATA =================
users = {}
male_queue = []
female_queue = []
active_chats = {}

COUNTRIES = [
    "🇮🇳 India", "🇺🇸 USA", "🇬🇧 UK", "🇨🇦 Canada",
    "🇦🇺 Australia", "🇩🇪 Germany", "🇫🇷 France"
]

# ================= UI =================
MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["⚡ Find Partner"],
        ["👤 My Profile"]
    ],
    resize_keyboard=True
)

def gender_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👦 Male", callback_data="gender_male"),
            InlineKeyboardButton("👧 Female", callback_data="gender_female"),
        ]
    ])

def chat_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭ NEXT", callback_data="next"),
            InlineKeyboardButton("❌ END", callback_data="end"),
        ]
    ])

def country_buttons():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(c, callback_data=f"country_{c}")]
         for c in COUNTRIES]
    )

def reconnect_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Find Partner", callback_data="reconnect")]
    ])

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    users[uid] = {"gender": None, "age": None, "country": None}

    await update.message.reply_text(
        "👋 Welcome to DateMate ❤️\n\nSelect your gender:",
        reply_markup=gender_buttons()
    )

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

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎂 Set Age", callback_data="set_age")],
        [InlineKeyboardButton("🌍 Set Country", callback_data="set_country")],
    ])

    await update.message.reply_text(text, reply_markup=buttons)

async def next_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_next(update.effective_user.id, context)

async def end_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_end(update.effective_user.id, context)

# ================= CALLBACKS =================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    data = q.data

    if data.startswith("gender_"):
        gender = data.split("_")[1]
        users[uid]["gender"] = gender

        await q.edit_message_text(f"✅ Gender set: {gender.capitalize()}")

        context.user_data["awaiting_age"] = True
        await context.bot.send_message(uid, "🎂 Send your age:")

    elif data == "set_age":
        context.user_data["awaiting_age"] = True
        await q.edit_message_text("🎂 Send your age:")

    elif data == "set_country":
        await q.edit_message_text(
            "🌍 Select Country:",
            reply_markup=country_buttons()
        )

    elif data.startswith("country_"):
        country = data.replace("country_", "")
        users[uid]["country"] = country

        await q.edit_message_text(f"✅ Country set: {country}")

    elif data == "next":
        await handle_next(uid, context)

    elif data == "end":
        await handle_end(uid, context)

    elif data == "reconnect":
        await find_partner(uid, context)

# ================= MATCHING =================
async def find_partner(uid, context):
    u = users.get(uid)

    if not u or not u.get("gender"):
        await context.bot.send_message(uid, "❗ Complete profile first.")
        return

    if uid in active_chats:
        await context.bot.send_message(uid, "⚠️ Already in chat.")
        return

    target_queue = female_queue if u["gender"] == "male" else male_queue
    my_queue = male_queue if u["gender"] == "male" else female_queue

    if target_queue:
        partner = target_queue.pop(0)

        active_chats[uid] = partner
        active_chats[partner] = uid

        await show_match(uid, partner, context)
        await show_match(partner, uid, context)

    else:
        if uid not in my_queue:
            my_queue.append(uid)

        await context.bot.send_message(uid, "⏳ Searching for partner...")

async def show_match(uid, partner, context):
    p = users.get(partner, {})

    card = (
        "🤝 Partner Found!\n\n"
        f"🎂 Age: {p.get('age','Unknown')} \n"
        f"🌍 Country: {p.get('country','Unknown')}\n\n"
        "/next — find new partner\n"
        "/end — end chat"
    )

    await context.bot.send_message(
        uid,
        card,
        reply_markup=chat_buttons()
    )

# ================= CHAT CONTROL =================
async def handle_next(uid, context):
    partner = active_chats.get(uid)
    if not partner:
        return

    active_chats.pop(uid, None)
    active_chats.pop(partner, None)

    await context.bot.send_message(
        partner,
        "🚫 Your partner has disconnected.",
        reply_markup=reconnect_buttons()
    )

    await find_partner(uid, context)

async def handle_end(uid, context):
    partner = active_chats.get(uid)
    if not partner:
        return

    active_chats.pop(uid, None)
    active_chats.pop(partner, None)

    await context.bot.send_message(
        partner,
        "🚫 Your partner has disconnected.",
        reply_markup=reconnect_buttons()
    )

    await context.bot.send_message(uid, "❌ Chat Ended.", reply_markup=MAIN_MENU)

# ================= MESSAGE ROUTER =================
async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    if context.user_data.get("awaiting_age"):
        try:
            age = int(text)
            users[uid]["age"] = age
            context.user_data["awaiting_age"] = False

            await update.message.reply_text("✅ Age Saved", reply_markup=MAIN_MENU)
        except:
            await update.message.reply_text("❌ Send valid age.")
        return

    if text == "⚡ Find Partner":
        await find_partner(uid, context)
        return

    if text == "👤 My Profile":
        await my_profile(update, context)
        return

    partner = active_chats.get(uid)
    if partner:
        await context.bot.send_message(partner, text)
    else:
        await update.message.reply_text("Click ⚡ Find Partner")

# ================= MEDIA BLOCK =================
async def media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Only text allowed")

# ================= MAIN =================
def run_bot():
    bot = ApplicationBuilder().token(TOKEN).build()

    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("next", next_cmd))
    bot.add_handler(CommandHandler("end", end_cmd))

    bot.add_handler(CallbackQueryHandler(callbacks))

    bot.add_handler(MessageHandler(filters.TEXT, messages))
    bot.add_handler(MessageHandler(~filters.TEXT, media))

    bot.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    run_bot()
