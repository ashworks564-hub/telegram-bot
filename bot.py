from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os

TOKEN = os.environ.get("TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is responding ✅")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # 🚨 CRITICAL LINE — prevents loop
    if update.message.from_user.is_bot:
        return

    await update.message.reply_text("You said: " + update.message.text)

app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))

# ✅ SAFE FILTER
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

print("Bot Running 🚀")
app.run_polling()
