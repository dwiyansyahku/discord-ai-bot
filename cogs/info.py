"""
Cog: Info
Fitur: Info bot, help command, statistik
"""

import discord
from discord.ext import commands
from discord import app_commands
import os
import platform
from datetime import datetime

BOT_AUTHOR = os.getenv('BOT_AUTHOR', 'Developer')
BOT_VERSION = os.getenv('BOT_VERSION', '1.0.0')
BOT_PURPOSE = os.getenv('BOT_PURPOSE', 'Bot AI serba bisa untuk server Discord')


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.now()

    # ── Command: !info / !about ──────────────────────────
    @commands.command(name="info", aliases=["about", "siapa", "botinfo"])
    async def show_bot_info(self, ctx: commands.Context):
        """Info tentang bot ini"""
        uptime = datetime.now() - self.start_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)

        embed = discord.Embed(
            title=f"🤖 {self.bot.user.name}",
            description=BOT_PURPOSE,
            color=0x5865F2
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        embed.add_field(name="👨‍💻 Dibuat oleh", value=BOT_AUTHOR, inline=True)
        embed.add_field(name="📦 Versi", value=BOT_VERSION, inline=True)
        embed.add_field(name="⏱️ Uptime", value=f"{hours}j {minutes}m {seconds}d", inline=True)

        embed.add_field(
            name="⚡ Teknologi",
            value=(
                "• **AI:** Gemini (Google)\n"
                "• **Framework:** discord.py\n"
                "• **Voice TTS:** ElevenLabs / gTTS\n"
                "• **Image:** Stable Diffusion / HuggingFace"
            ),
            inline=False
        )

        embed.add_field(
            name="🌟 Fitur Utama",
            value=(
                "• Jawab pertanyaan dengan AI\n"
                "• Auto post untuk ramaikan server\n"
                "• Ngobrol via voice channel\n"
                "• Generate gambar dari teks\n"
                "• Teman curhat yang empatik\n"
                "• Ingat konteks percakapan"
            ),
            inline=False
        )

        embed.add_field(
            name="📊 Stats",
            value=(
                f"• Server: {len(self.bot.guilds)}\n"
                f"• Users: {sum(g.member_count for g in self.bot.guilds):,}"
            ),
            inline=True
        )

        embed.set_footer(text="Gunakan whelp untuk melihat semua perintah")
        await ctx.reply(embed=embed)

    # ── Command: whelp ───────────────────────────────────
    @commands.command(name="help", aliases=["bantuan", "commands", "cmd"])
    async def help_custom(self, ctx: commands.Context):
        """Tampilkan semua perintah"""
        embed = discord.Embed(
            title="📚 Daftar Perintah",
            description="Gunakan prefix `w` atau `/` untuk slash commands",
            color=0x5865F2
        )

        embed.add_field(
            name="💬 Chat & AI",
            value=(
                "`wtanya <pertanyaan>` - Tanya AI\n"
                "`wcurhat <cerita>` - Mode curhat\n"
                "`wlanjut <pesan>` - Lanjut percakapan\n"
                "`wreset` - Reset memori AI\n"
                "**@mention bot** - Chat langsung"
            ),
            inline=False
        )

        embed.add_field(
            name="🎙️ Voice",
            value=(
                "`wjoin` - Bot masuk voice\n"
                "`wleave` - Bot keluar voice\n"
                "`wbicara <teks>` - Bot bicara\n"
                "`wtanyavoice <pertanyaan>` - Tanya + suara"
            ),
            inline=False
        )

        embed.add_field(
            name="🎨 Gambar",
            value=(
                "`wgambar <deskripsi>` - Generate gambar\n"
                "`whelpimage` - Panduan setup image gen"
            ),
            inline=False
        )

        embed.add_field(
            name="📢 Auto Post (Admin)",
            value=(
                "`wsetautopost [#channel]` - Aktifkan auto post\n"
                "`wstopautopost [#channel]` - Hentikan auto post\n"
                "`wpostnow [topik]` - Post sekarang\n"
                "`wautopoststatus` - Cek status"
            ),
            inline=False
        )

        embed.add_field(
            name="ℹ️ Info",
            value=(
                "`winfo` - Info bot\n"
                "`whelp` - Perintah ini\n"
                "`wping` - Cek latency"
            ),
            inline=False
        )

        embed.set_footer(text="💡 Slash commands: /tanya /gambar /curhat")
        await ctx.reply(embed=embed)

    # ── Command: !ping ───────────────────────────────────
    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        """Cek latency bot"""
        latency = round(self.bot.latency * 1000)
        emoji = "🟢" if latency < 100 else "🟡" if latency < 200 else "🔴"
        await ctx.reply(f"{emoji} **Pong!** Latency: `{latency}ms`")

    # ── Slash: /info ─────────────────────────────────────
    @app_commands.command(name="info", description="Info tentang bot ini")
    async def info_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        # Reuse logic dengan context palsu
        ctx = await self.bot.get_context(interaction.message if hasattr(interaction, 'message') else None)
        embed = discord.Embed(
            title=f"🤖 {self.bot.user.name}",
            description=BOT_PURPOSE,
            color=0x5865F2
        )
        embed.add_field(name="👨‍💻 Dibuat oleh", value=BOT_AUTHOR, inline=True)
        embed.add_field(name="📦 Versi", value=BOT_VERSION, inline=True)
        embed.add_field(
            name="🌟 Fitur",
            value="Chat AI · Voice · Image Gen · Auto Post · Curhat",
            inline=False
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Info(bot))
