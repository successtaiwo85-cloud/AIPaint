import os
import asyncio
import logging
import aiohttp
import io
from datetime import datetime
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ============ LOGGING ============
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ============ FLASK APP FOR RAILWAY ============
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ AI Paint Bot is running!", 200

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    """Run Flask on Railway's PORT"""
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ============ BOT CLASS ============
class AIPaintBot:
    def __init__(self, token: str):
        self.token = token
        self.pollinations_url = "https://image.pollinations.ai/prompt/"
        self.pollinations_params = "?width=1024&height=1024&nologo=true"
        self.user_stats = {}

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        keyboard = [
            [InlineKeyboardButton("🎨 Generate", callback_data="generate")],
            [InlineKeyboardButton("ℹ️ Help", callback_data="help")],
            [InlineKeyboardButton("📊 Stats", callback_data="stats")],
        ]
        await update.message.reply_text(
            f"🎨 *Welcome {user.first_name}!*\n\nSend me any text description and I'll generate an AI image!\n\n"
            f"📝 Example: `/generate a beautiful sunset over mountains`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🖼️ *AI Paint Bot Help*\n\n"
            "• Send any text description\n"
            "• /generate <prompt> - Generate image\n"
            "• /stats - Your usage stats\n\n"
            "🎯 *Tips:* Be descriptive! Use style keywords like 'oil painting', 'cyberpunk', 'watercolor'",
            parse_mode="Markdown",
        )

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        stats = self.user_stats.get(user_id, {"count": 0})
        await update.message.reply_text(
            f"📊 *Your Stats*\n\nImages generated: `{stats['count']}`",
            parse_mode="Markdown",
        )

    async def generate_image(self, prompt: str) -> bytes:
        """Generate image using Pollinations.ai"""
        if len(prompt.strip()) < 3:
            raise ValueError("Prompt must be at least 3 characters")
        
        import random
        encoded = aiohttp.helpers.quote(prompt.strip())
        url = f"{self.pollinations_url}{encoded}{self.pollinations_params}&seed={random.randint(1, 999999)}"
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.read()
                if len(data) < 1000:
                    raise Exception("Image generation failed, try a different prompt")
                return data

    async def generate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("❌ Please provide a description.\nExample: `/generate a cute cat`", parse_mode="Markdown")
            return
        prompt = " ".join(context.args)
        await self._process_generation(update, prompt)

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        prompt = update.message.text
        if prompt.startswith('/'):
            return
        await self._process_generation(update, prompt)

    async def _process_generation(self, update: Update, prompt: str):
        user_id = update.effective_user.id
        
        # Update stats
        if user_id not in self.user_stats:
            self.user_stats[user_id] = {"count": 0}
        self.user_stats[user_id]["count"] += 1

        status = await update.message.reply_text(
            f"🎨 *Generating...*\n📝 `{prompt[:60]}{'...' if len(prompt) > 60 else ''}`",
            parse_mode="Markdown",
        )

        try:
            image = await self.generate_image(prompt)
            await update.message.reply_photo(
                photo=io.BytesIO(image),
                caption=f"✅ *Generated!*\n\n📝 {prompt}\n\n🔄 Generation #{self.user_stats[user_id]['count']}",
                parse_mode="Markdown",
            )
            await status.delete()
        except Exception as e:
            await status.edit_text(f"❌ Error: {str(e)}")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "generate":
            await query.edit_message_text("📝 Send me your image description!")
        elif query.data == "help":
            await self.help_command(update, context)
        elif query.data == "stats":
            await self.stats_command(update, context)

    def run(self):
        # Start Flask server for Railway
        Thread(target=run_flask, daemon=True).start()
        logger.info("🌐 Web server running for Railway")

        # Run bot
        app = Application.builder().token(self.token).build()
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(CommandHandler("generate", self.generate_command))
        app.add_handler(CommandHandler("stats", self.stats_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        app.add_handler(CallbackQueryHandler(self.button_callback))
        
        logger.info("🤖 Bot started successfully!")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

# ============ MAIN ============
if __name__ == "__main__":
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("❌ TELEGRAM_BOT_TOKEN not set!")
        exit(1)
    AIPaintBot(token).run()
