import os
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

TOKEN = os.environ.get("TOKEN")

waiting_users = []
active_chats = {}
profiles = {}
reports = {}
banned_users = {}

# ================= MENUS =================

MAIN_MENU = ReplyKeyboardMarkup(
    [["⚡ Find Partner", "👤 My Profile"],
     ["⚙ Settings"]],
    resize_keyboard=True
)

GENDER_MENU = ReplyKeyboardMarkup(
    [["👦 Male", "👧 Female"]],
    resize_keyboard=True
)

PROFILE_MENU = ReplyKeyboardMarkup(
    [["🎂 Set Age", "🌍 Set Country"],
     ["🚻 Set Gender"],
     ["🔙 Back"]],
    resize_keyboard=True
)

SETTINGS_MENU = ReplyKeyboardMarkup(
    [["💎 Match with Male", "💎 Match with Female"],
     ["🚫 Report User"],
     ["🔙 Back"]],
    resize_keyboard=True
)

CHAT_MENU = ReplyKeyboardMarkup(
    [["⏭ Next", "❌ End"]],
    resize_keyboard=True
)

COUNTRIES = ["India", "USA", "UK", "Canada", "Australia"]

COUNTRY_MENU = ReplyKeyboardMarkup(
    [[c] for c in COUNTRIES] + [["🔙 Back"]],
    resize_keyboard=True
)

# ================= HELPERS =================

def is_banned(user_id):
    if user_id not in banned_users:
        return False

    if datetime.now() > banned_users[user_id]:
        del banned_users[user_id]
        return False

    return True


def profile_complete(user_id):
    p = profiles.get(user_id)
    return p and p.get("gender") and p.get("age") and p.get("country")


async def disconnect(bot, user_id):
    await bot.send_message(
        user_id,
        "🚫 Your partner has disconnected.\n\n⚡ Find Partner to continue",
        reply_markup=MAIN_MENU
    )

# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if is_banned(user_id):
        expiry = banned_users[user_id]
        await update.message.reply_text(
            f"🚫 You are banned until:\n{expiry.strftime('%d %B %Y %H:%M')}"
        )
        return

    profiles[user_id] = {}

    await update.message.reply_text(
        "🔥 Welcome to DateMate!\n\nSelect your gender:",
        reply_markup=GENDER_MENU
    )

# ================= PROFILE =================

async def show_profile(update, context):
    user_id = update.effective_user.id
    p = profiles.get(user_id, {})

    await update.message.reply_text(
        "👤 Your Profile\n\n"
        f"🎂 Age: {p.get('age', 'Not set')}\n"
        f"🚻 Gender: {p.get('gender', 'Not set')}\n"
        f"🌍 Country: {p.get('country', 'Not set')}",
        reply_markup=PROFILE_MENU
    )

# ================= MATCHING =================

async def find_partner(update, context):
    user_id = update.effective_user.id

    if not profile_complete(user_id):
        await update.message.reply_text("🚫 Complete profile first")
        return

    if user_id in waiting_users:
        return

    waiting_users.append(user_id)

    await update.message.reply_text("⏳ Searching for partner...")

    if len(waiting_users) >= 2:
        u1 = waiting_users.pop(0)
        u2 = waiting_users.pop(0)

        active_chats[u1] = u2
        active_chats[u2] = u1

        for u, partner in [(u1, u2), (u2, u1)]:
            p = profiles.get(partner)

            await context.bot.send_message(
                u,
                "🤝 Partner Found!\n\n"
                f"🎂 Age: {p.get('age')}\n"
                f"🌍 Country: {p.get('country')}\n\n"
                "🚫 Links & Media Blocked",
                reply_markup=CHAT_MENU
            )

# ================= CHAT CONTROL =================

async def next_chat(update, context):
    user_id = update.effective_user.id
    partner = active_chats.get(user_id)

    if not partner:
        return

    del active_chats[user_id]
    del active_chats[partner]

    await disconnect(context.bot, partner)
    await find_partner(update, context)


async def end_chat(update, context):
    user_id = update.effective_user.id
    partner = active_chats.get(user_id)

    if not partner:
        return

    del active_chats[user_id]
    del active_chats[partner]

    await disconnect(context.bot, partner)

    await update.message.reply_text("❌ Chat Ended", reply_markup=MAIN_MENU)

# ================= REPORT =================

async def report_user(update, context):
    user_id = update.effective_user.id
    partner = active_chats.get(user_id)

    if not partner:
        await update.message.reply_text("🚫 Not in chat")
        return

    reports[partner] = reports.get(partner, 0) + 1

    await update.message.reply_text("✅ User Reported")

    if reports[partner] >= 10:
        banned_users[partner] = datetime.now() + timedelta(hours=24)
        del reports[partner]

        await context.bot.send_message(
            partner,
            "🚫 You are banned for 24 hours.\n\nRules violation detected."
        )

# ================= MESSAGE HANDLER =================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if is_banned(user_id):
        return

    if update.message.photo or update.message.video or update.message.sticker:
        await update.message.reply_text("🚫 Only text allowed")
        return

    text = update.message.text

    # ===== Gender Selection =====
    if text in ["👦 Male", "👧 Female"]:
        profiles[user_id]["gender"] = text.replace("👦 ", "").replace("👧 ", "")
        await update.message.reply_text("🎂 Send your age:")
        context.user_data["awaiting_age"] = True
        return

    # ===== Age Input =====
    if context.user_data.get("awaiting_age"):
        profiles[user_id]["age"] = text
        context.user_data["awaiting_age"] = False

        await update.message.reply_text(
            "🌍 Select your country:",
            reply_markup=COUNTRY_MENU
        )
        return

    # ===== Country Selection =====
    if text in COUNTRIES:
        profiles[user_id]["country"] = text
        await update.message.reply_text(
            "✅ Profile Saved!",
            reply_markup=MAIN_MENU
        )
        return

    # ===== Main Menu =====
    if text == "⚡ Find Partner":
        await find_partner(update, context)
        return

    if text == "👤 My Profile":
        await show_profile(update, context)
        return

    if text == "⚙ Settings":
        await update.message.reply_text(
            "⚙ Settings",
            reply_markup=SETTINGS_MENU
        )
        return

    # ===== Settings =====
    if text.startswith("💎"):
        await update.message.reply_text("💎 Premium Required")
        return

    if text == "🚫 Report User":
        await report_user(update, context)
        return

    if text == "🔙 Back":
        await update.message.reply_text("⬅ Back", reply_markup=MAIN_MENU)
        return

    # ===== Chat Controls =====
    if text == "⏭ Next":
        await next_chat(update, context)
        return

    if text == "❌ End":
        await end_chat(update, context)
        return

    # ===== Chat Relay =====
    partner = active_chats.get(user_id)
    if partner:
        await context.bot.send_message(partner, text)

# ================= MAIN =================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, handle_message))

print("Bot Running...")
app.run_polling()
