import os
import asyncio
import logging
import aiohttp
import io
from datetime import datetime
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ============ CONFIGURATION ============
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ============ BOT CLASS ============
class AIPaintBot:
    """AI Image Generation Telegram Bot"""

    def __init__(self, token: str):
        self.token = token
        self.pollinations_url = "https://image.pollinations.ai/prompt/"
        self.pollinations_params = "?width=1024&height=1024&nologo=true&seed="
        
        # User session tracking (simple in-memory, consider Redis for production)
        self.user_sessions = {}

    # ============ COMMAND HANDLERS ============

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        user_name = user.first_name or "User"

        keyboard = [
            [InlineKeyboardButton("🎨 Generate Image", callback_data="generate")],
            [InlineKeyboardButton("ℹ️ Help", callback_data="help")],
            [InlineKeyboardButton("📊 Stats", callback_data="stats")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        welcome_msg = (
            f"🎨 *Welcome {user_name}!*\n\n"
            "I'm your AI Paint Bot - transform your ideas into stunning images!\n\n"
            "📝 *How to use:*\n"
            "• Send any text description\n"
            "• Use /generate <your prompt>\n"
            "• Use inline buttons below\n\n"
            "✨ *Example:*\n"
            "`/generate a beautiful sunset over mountains, oil painting style`\n\n"
            "⚡ *Free & Unlimited!*"
        )

        await update.message.reply_text(
            welcome_msg,
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_msg = (
            "🖼️ *AI Paint Bot Help*\n\n"
            "🔹 *Text to Image:* Send any description\n"
            "🔹 *Commands:*\n"
            "  • /start - Main menu\n"
            "  • /help - This help message\n"
            "  • /generate <prompt> - Generate image\n"
            "  • /stats - Your usage stats\n\n"
            "🎯 *Tips for better results:*\n"
            "• Be descriptive: style, colors, mood\n"
            "• Use artistic keywords: oil painting, cyberpunk, watercolor\n"
            "• Specify quality: 4K, HD, detailed\n"
            "• Include subject, environment, lighting\n\n"
            "📌 *Examples:*\n"
            "• `cyberpunk city at night, neon lights`\n"
            "• `watercolor painting of a forest, soft colors`\n"
            "• `3D render of a futuristic car, photorealistic`\n\n"
            "⚡ *Free & Unlimited!*"
        )
        await update.message.reply_text(help_msg, parse_mode="Markdown")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        user_id = update.effective_user.id
        
        # Track user stats
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {"count": 0, "last_used": None}
        
        stats = self.user_sessions[user_id]
        
        stats_msg = (
            f"📊 *Your Statistics*\n\n"
            f"• Images generated: `{stats['count']}`\n"
            f"• Last used: `{stats['last_used'] or 'Never'}`\n\n"
            f"💡 Keep generating! The more you create, the better your prompts become!"
        )
        await update.message.reply_text(stats_msg, parse_mode="Markdown")

    # ============ CORE GENERATION LOGIC ============

    async def generate_image(self, prompt: str) -> bytes:
        """Generate image using Pollinations.ai API (async)"""
        if not prompt or len(prompt.strip()) < 3:
            raise ValueError("❌ Prompt must be at least 3 characters")

        # Clean and encode prompt
        prompt = prompt.strip()
        encoded_prompt = aiohttp.helpers.quote(prompt)
        
        # Add random seed for variety
        import random
        seed = random.randint(1, 1000000)
        
        url = f"{self.pollinations_url}{encoded_prompt}{self.pollinations_params}{seed}"
        
        logger.info(f"Generating image for prompt: {prompt[:50]}...")
        
        try:
            timeout = aiohttp.ClientTimeout(total=45)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    image_data = await response.read()
                    
                    if len(image_data) < 1000:  # Too small, likely error
                        raise Exception("Generated image too small, please try a different prompt")
                    
                    return image_data
                    
        except aiohttp.ClientError as e:
            logger.error(f"Network error: {e}")
            raise Exception(f"🌐 Network error: {str(e)}")
        except asyncio.TimeoutError:
            raise Exception("⏰ Generation timed out, please try again")
        except Exception as e:
            logger.error(f"Generation error: {e}")
            raise Exception(f"❌ Generation failed: {str(e)}")

    async def _process_generation(self, update: Update, prompt: str):
        """Core processing logic for image generation"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "User"

        # Track user stats
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {"count": 0, "last_used": None}
        self.user_sessions[user_id]["count"] += 1
        self.user_sessions[user_id]["last_used"] = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Send processing message
        status_msg = await update.message.reply_text(
            f"🎨 *Generating image for {user_name}...*\n\n"
            f"📝 *Prompt:* `{prompt[:100]}{'...' if len(prompt) > 100 else ''}`\n"
            f"⏳ Please wait 5-15 seconds\n"
            f"🔄 This is generation #{self.user_sessions[user_id]['count']}",
            parse_mode="Markdown",
        )

        try:
            # Generate image
            image_data = await self.generate_image(prompt)
            
            # Send result
            await update.message.reply_photo(
                photo=io.BytesIO(image_data),
                caption=(
                    f"✅ *Image Generated!*\n\n"
                    f"📝 `{prompt[:150]}{'...' if len(prompt) > 150 else ''}`\n"
                    f"👤 Generated by: {user_name}\n"
                    f"📊 Generation #{self.user_sessions[user_id]['count']}\n\n"
                    f"✨ *Try another prompt!* Just send a new description."
                ),
                parse_mode="Markdown",
            )
            
            # Delete status message
            await status_msg.delete()

        except ValueError as e:
            await status_msg.edit_text(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"Generation error for user {user_id}: {e}")
            await status_msg.edit_text(
                f"❌ *Generation Failed*\n\n"
                f"Error: `{str(e)}`\n\n"
                f"💡 *Tips:*\n"
                f"• Try a different prompt\n"
                f"• Make it more descriptive\n"
                f"• Use /help for examples\n"
                f"• Try again in a moment",
                parse_mode="Markdown",
            )

    # ============ MESSAGE HANDLERS ============

    async def generate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /generate <prompt> command"""
        if not context.args:
            await update.message.reply_text(
                "❌ *Please provide a description*\n\n"
                "Example: `/generate a cute cat wearing a hat, watercolor style`\n\n"
                "Send /help for more examples",
                parse_mode="Markdown",
            )
            return

        prompt = " ".join(context.args)
        await self._process_generation(update, prompt)

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle plain text messages as image prompts"""
        prompt = update.message.text
        
        # Ignore commands
        if prompt.startswith('/'):
            return
            
        # Validate prompt
        if len(prompt.strip()) < 3:
            await update.message.reply_text(
                "❌ Please send a longer description (at least 3 characters)\n\n"
                "Example: `a beautiful landscape with mountains`"
            )
            return
            
        if len(prompt) > 1000:
            await update.message.reply_text(
                "❌ Prompt too long! Please keep it under 1000 characters."
            )
            return
            
        await self._process_generation(update, prompt)

    # ============ INLINE BUTTON HANDLERS ============

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "generate":
            await query.edit_message_text(
                "📝 *Send your image description*\n\n"
                "Example: `a futuristic city with neon lights, cyberpunk style`\n\n"
                "Be creative and descriptive for best results!",
                parse_mode="Markdown",
            )
        elif query.data == "help":
            await self.help_command(update, context)
        elif query.data == "stats":
            # Create a fake update for stats
            class FakeUpdate:
                effective_user = update.effective_user
                async def reply_text(self, *args, **kwargs):
                    await query.edit_message_text(*args, **kwargs)
            
            fake_update = FakeUpdate()
            await self.stats_command(fake_update, context)

    # ============ ERROR HANDLING ============

    async def error_handler(self, update: Optional[Update], context: ContextTypes.DEFAULT_TYPE):
        """Handle errors gracefully"""
        logger.error(f"Update {update} caused error {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ *Something went wrong*\n\n"
                "Please try again or use /help for assistance.\n"
                "If this persists, try again later.",
                parse_mode="Markdown",
            )

    # ============ MAIN ENTRY POINT ============

    def run(self):
        """Start the bot"""
        app = Application.builder().token(self.token).build()

        # Add command handlers
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(CommandHandler("generate", self.generate_command))
        app.add_handler(CommandHandler("stats", self.stats_command))

        # Add message handler for text (non-command)
        app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.handle_text_message,
            )
        )

        # Add callback handler for inline buttons
        app.add_handler(CallbackQueryHandler(self.button_callback))

        # Add error handler
        app.add_error_handler(self.error_handler)

        # Start the bot
        logger.info("🤖 AI Paint Bot is starting up...")
        logger.info(f"📊 Using Pollinations.ai API")
        
        # Get port for Railway (health check compatibility)
        port = int(os.environ.get("PORT", 8080))
        logger.info(f"🌐 Running on port {port}")
        
        # Start polling (not webhook for simplicity)
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )


# ============ MAIN EXECUTION ============
if __name__ == "__main__":
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN environment variable not set!")
        logger.error("💡 Set it in Railway Dashboard > Variables")
        exit(1)
    
    if not TOKEN.startswith("7") and not TOKEN.startswith("8"):
        logger.warning("⚠️ Token doesn't start with 7 or 8, but continuing...")
    
    try:
        bot = AIPaintBot(TOKEN)
        bot.run()
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        exit(1)
