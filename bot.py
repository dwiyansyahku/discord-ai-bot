"""
╔══════════════════════════════════════════╗
║     DISCORD AI ASSISTANT BOT             ║
║     Dibuat dengan discord.py + Gemini    ║
╚══════════════════════════════════════════╝
"""

import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import logging

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('AIBot')

# Konfigurasi intents (izin bot)
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

# Buat bot dengan prefix 'w' dan '/'
bot = commands.Bot(
    command_prefix=['w', '/'],
    intents=intents,
    help_command=None,  # Matikan default help command agar bisa pakai custom whelp
    description="AI Assistant Bot - Siap membantu kamu! 🤖"
)

# ── Event: Bot siap ──────────────────────────────────────
@bot.event
async def on_ready():
    logger.info(f"✅ Bot online sebagai {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="whelp | Siap membantu!"
        )
    )
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        logger.error(f"❌ Error syncing commands: {e}")

# ── Load semua cogs (modul fitur) ────────────────────────
async def load_cogs():
    cogs = [
        'cogs.chat',        # Q&A + Curhat
        'cogs.autopost',    # Auto ramaikan server
        'cogs.voice',       # Voice channel
        'cogs.image',       # Generate gambar
        'cogs.info',        # Info bot
    ]
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            logger.info(f"✅ Loaded: {cog}")
        except Exception as e:
            logger.error(f"❌ Failed to load {cog}: {e}")

# ── Main ─────────────────────────────────────────────────
async def main():
    async with bot:
        await load_cogs()
        token = os.getenv('DISCORD_TOKEN')
        if not token:
            raise ValueError("❌ DISCORD_TOKEN tidak ditemukan di .env!")
        await bot.start(token)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
