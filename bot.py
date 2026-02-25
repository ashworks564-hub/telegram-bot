def main():
    print("Bot Running 🚀")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(MessageHandler(filters.Regex("👦 Male|👧 Female"), set_gender))
    app.add_handler(MessageHandler(filters.Regex("🔎 Find Partner"), find_partner))
    app.add_handler(MessageHandler(filters.Regex("👤 Profile"), profile))
    app.add_handler(MessageHandler(filters.Regex("⚙ Settings"), settings))
    app.add_handler(MessageHandler(filters.Regex("🚩 Report"), report))
    app.add_handler(MessageHandler(filters.Regex("⏭ Next"), next_chat))
    app.add_handler(MessageHandler(filters.Regex("❌ End"), end_chat))
    app.add_handler(MessageHandler(filters.Regex("⬅ Back"), back_to_menu))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, relay))

    app.run_polling()

if __name__ == "__main__":
    main()
