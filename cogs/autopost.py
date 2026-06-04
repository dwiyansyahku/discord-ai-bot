"""
Cog: AutoPost
Fitur: Auto kirim pesan untuk ramaikan server Discord
"""

import discord
from discord.ext import commands, tasks
import google.generativeai as genai
import os
import random
import asyncio
from datetime import datetime

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# Topik-topik untuk auto post
AUTO_POST_TOPICS = [
    "Fakta unik dan menarik tentang alam semesta atau sains",
    "Quote motivasi dalam Bahasa Indonesia yang inspiratif",
    "Tips produktivitas atau self-improvement yang praktis",
    "Fakta mengejutkan tentang teknologi modern",
    "Pertanyaan seru untuk diskusi komunitas",
    "Fun fact tentang sejarah dunia",
    "Tips kesehatan mental yang simple",
    "Trivia seru yang bikin penasaran",
    "Pertanyaan 'Would You Rather' yang menarik",
    "Tips belajar yang efektif",
]

SYSTEM_AUTOPOST = """Kamu adalah bot yang bertugas membuat konten menarik untuk server Discord.
Buat pesan yang:
- Menarik dan mengundang diskusi
- Menggunakan bahasa santai ala anak muda Indonesia
- Panjang 2-4 kalimat saja
- Boleh pakai emoji secukupnya
- Kadang ajak member untuk reply/diskusi
- Jangan terlalu formal"""


async def generate_auto_message(topic: str) -> str:
    try:
        model = genai.GenerativeModel(
            model_name=os.getenv('GEMINI_MODEL', 'gemini-1.5-flash'),
            system_instruction=SYSTEM_AUTOPOST
        )
        response = model.generate_content(f"Buat pesan Discord tentang: {topic}")
        return response.text
    except Exception as e:
        return f"Hei semua! Ada yang mau diskusi hari ini? 😊"


class AutoPost(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_channels: list[int] = []
        self.interval_minutes = int(os.getenv('AUTO_POST_INTERVAL', 60))

        # Load channel IDs dari env
        channel_ids = os.getenv('AUTO_POST_CHANNELS', '')
        if channel_ids:
            for cid in channel_ids.split(','):
                try:
                    self.target_channels.append(int(cid.strip()))
                except:
                    pass

        # Start auto post task
        self.auto_post_task.change_interval(minutes=self.interval_minutes)
        if self.target_channels:
            self.auto_post_task.start()

    def cog_unload(self):
        self.auto_post_task.cancel()

    @tasks.loop(minutes=60)
    async def auto_post_task(self):
        """Task yang jalan otomatis setiap X menit"""
        if not self.target_channels:
            return

        topic = random.choice(AUTO_POST_TOPICS)
        message = await generate_auto_message(topic)

        for channel_id in self.target_channels:
            channel = self.bot.get_channel(channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                try:
                    embed = discord.Embed(
                        description=message,
                        color=random.choice([0x5865F2, 0x57F287, 0xFEE75C, 0xEB459E, 0xED4245])
                    )
                    embed.set_footer(text=f"🤖 AI Post • {datetime.now().strftime('%H:%M')}")
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    pass  # Bot tidak punya izin kirim di channel tersebut

    @auto_post_task.before_loop
    async def before_auto_post(self):
        await self.bot.wait_until_ready()

    # ── Command: !setautopost ────────────────────────────
    @commands.command(name="setautopost")
    @commands.has_permissions(administrator=True)
    async def set_auto_post(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """[Admin] Set channel untuk auto post: !setautopost #channel"""
        if channel is None:
            channel = ctx.channel

        if channel.id not in self.target_channels:
            self.target_channels.append(channel.id)
            if not self.auto_post_task.is_running():
                self.auto_post_task.start()
            await ctx.reply(f"✅ Auto post diaktifkan di {channel.mention}! "
                          f"Bot akan posting setiap {self.interval_minutes} menit.")
        else:
            await ctx.reply(f"ℹ️ {channel.mention} sudah terdaftar untuk auto post.")

    @commands.command(name="stopautopost")
    @commands.has_permissions(administrator=True)
    async def stop_auto_post(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """[Admin] Hentikan auto post di channel: !stopautopost #channel"""
        if channel is None:
            channel = ctx.channel

        if channel.id in self.target_channels:
            self.target_channels.remove(channel.id)
            if not self.target_channels:
                self.auto_post_task.cancel()
            await ctx.reply(f"✅ Auto post dihentikan di {channel.mention}.")
        else:
            await ctx.reply(f"ℹ️ {channel.mention} tidak terdaftar untuk auto post.")

    @commands.command(name="postnow", aliases=["postsekaran"])
    @commands.has_permissions(manage_messages=True)
    async def post_now(self, ctx: commands.Context, *, topik: str = None):
        """[Mod] Kirim auto post sekarang: !postnow [topik]"""
        async with ctx.typing():
            topic = topik or random.choice(AUTO_POST_TOPICS)
            message = await generate_auto_message(topic)

            embed = discord.Embed(
                description=message,
                color=0x5865F2
            )
            embed.set_footer(text=f"🤖 AI Post • Manual")
            await ctx.reply(embed=embed)

    @commands.command(name="autopoststatus")
    async def auto_post_status(self, ctx: commands.Context):
        """Cek status auto post"""
        if self.target_channels:
            channels_mention = [f"<#{cid}>" for cid in self.target_channels]
            status = "✅ Aktif" if self.auto_post_task.is_running() else "⏸️ Paused"
            await ctx.reply(
                f"**Auto Post Status:** {status}\n"
                f"**Channels:** {', '.join(channels_mention)}\n"
                f"**Interval:** setiap {self.interval_minutes} menit"
            )
        else:
            await ctx.reply("ℹ️ Auto post belum diaktifkan. Gunakan `!setautopost #channel`")


async def setup(bot):
    await bot.add_cog(AutoPost(bot))
