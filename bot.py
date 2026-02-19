import os
import threading
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

TOKEN = os.environ.get("TOKEN")

# ------------------ FLASK (Keep Render Awake) ------------------

app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Bot Alive 🚀"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask).start()

# ------------------ DATA STORAGE ------------------

users = {}  
waiting_queue = []  
active_chats = {}  
last_partner = {}  

# ------------------ KEYBOARDS ------------------

def gender_menu():
    keyboard = [["👦 Male", "👧 Female"]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def main_menu():
    keyboard = [
        ["🔎 Find Partner"],
        ["👤 Profile", "⚙️ Settings"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def settings_menu():
    keyboard = [
        ["🚩 Report"],
        ["💎 Premium"],
        ["⬅️ Back"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def chat_menu():
    keyboard = [
        ["⏭ Next"],
        ["❌ End"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ------------------ HELPERS ------------------

def is_chatting(user_id):
    return user_id in active_chats

def disconnect(user_id):
    if user_id not in active_chats:
        return

    partner = active_chats[user_id]

    del active_chats[user_id]
    del active_chats[partner]

    last_partner[user_id] = partner
    last_partner[partner] = user_id

    return partner

# ------------------ HANDLERS ------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in users:
        users[user_id] = {
            "gender": None,
            "premium": False,
            "reports": 0
        }

    await update.message.reply_text(
        "Welcome 😎\n\nPlease select your gender:",
        reply_markup=gender_menu()
    )

# ------------------ GENDER ------------------

async def set_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if text not in ["👦 Male", "👧 Female"]:
        return

    gender = "Male" if "Male" in text else "Female"
    users[user_id]["gender"] = gender

    await update.message.reply_text(
        f"✅ Gender set to {gender}",
        reply_markup=main_menu()
    )

# ------------------ FIND PARTNER ------------------

async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if users[user_id]["gender"] is None:
        await update.message.reply_text("Please select gender first.")
        return

    if is_chatting(user_id):
        return

    if user_id in waiting_queue:
        return

    await update.message.reply_text("🔎 Finding partner for you...")

    if waiting_queue:
        partner = waiting_queue.pop(0)

        active_chats[user_id] = partner
        active_chats[partner] = user_id

        await context.bot.send_message(partner, "🤝 Partner Found!", reply_markup=chat_menu())
        await update.message.reply_text("🤝 Partner Found!", reply_markup=chat_menu())

    else:
        waiting_queue.append(user_id)

# ------------------ CHAT RELAY ------------------

async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if not is_chatting(user_id):
        return

    partner = active_chats[user_id]

    await context.bot.send_message(partner, text)

# ------------------ NEXT ------------------

async def next_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    partner = disconnect(user_id)

    if partner:
        await context.bot.send_message(
            partner,
            "❌ Your partner has disconnected.\n\nYou can report them.",
            reply_markup=settings_menu()
        )

    await find_partner(update, context)

# ------------------ END ------------------

async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    partner = disconnect(user_id)

    if partner:
        await context.bot.send_message(
            partner,
            "❌ Your partner has left.\n\nYou can report them.",
            reply_markup=settings_menu()
        )

    await update.message.reply_text(
        "❌ Chat ended",
        reply_markup=main_menu()
    )

# ------------------ PROFILE ------------------

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = users[user_id]

    premium_status = "Yes 💎" if user["premium"] else "No"

    await update.message.reply_text(
        f"👤 Your Profile\n\n"
        f"Gender: {user['gender']}\n"
        f"Premium: {premium_status}\n"
        f"Reports: {user['reports']}",
        reply_markup=main_menu()
    )

# ------------------ SETTINGS ------------------

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ Settings",
        reply_markup=settings_menu()
    )

# ------------------ REPORT ------------------

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in last_partner:
        await update.message.reply_text("Nothing to report.")
        return

    partner = last_partner[user_id]
    users[partner]["reports"] += 1

    await update.message.reply_text("🚩 Report submitted")

# ------------------ PREMIUM ------------------

async def premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💎 Premium system coming soon")

# ------------------ BACK ------------------

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⬅️ Back", reply_markup=main_menu())

# ------------------ MAIN ------------------

def main():
    print("Bot Running 🚀")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(MessageHandler(filters.Regex("^(👦 Male|👧 Female)$"), set_gender))

    app.add_handler(MessageHandler(filters.Regex("^🔎 Find Partner$"), find_partner))
    app.add_handler(MessageHandler(filters.Regex("^⏭ Next$"), next_partner))
    app.add_handler(MessageHandler(filters.Regex("^❌ End$"), end_chat))

    app.add_handler(MessageHandler(filters.Regex("^👤 Profile$"), profile))
    app.add_handler(MessageHandler(filters.Regex("^⚙️ Settings$"), settings))
    app.add_handler(MessageHandler(filters.Regex("^🚩 Report$"), report))
    app.add_handler(MessageHandler(filters.Regex("^💎 Premium$"), premium))
    app.add_handler(MessageHandler(filters.Regex("^⬅️ Back$"), back))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, relay_message))

    app.run_polling()

if __name__ == "__main__":
    main()
