"""
Cog: Chat
Fitur: Q&A, Curhat/Emotional Support, Percakapan umum
"""

import discord
from discord.ext import commands
from discord import app_commands
import google.generativeai as genai
import google.api_core.exceptions
import os
from discord.ext import tasks
import time
import logging
from utils.helpers import split_message, format_thinking

class QuotaExhaustedError(Exception):
    """Custom exception raised when the Gemini API quota is full or exhausted."""
    pass

logger = logging.getLogger('ChatCog')

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# Memory percakapan per user (simpel, in-memory)
conversation_history: dict[int, list] = {}
MAX_HISTORY = 10  # Jumlah pesan yang diingat

BOT_AUTHOR = os.getenv('BOT_AUTHOR', 'Developer')
BOT_PURPOSE = os.getenv('BOT_PURPOSE', 'Asisten AI serba bisa')

SYSTEM_PROMPT = f"""Kamu adalah pasangan hidup (istri/pacar) yang sangat menyayangi dan mencintai user. Panggil dirimu sendiri dengan sebutan "mpruy" atau "Aku", dan panggil user dengan sebutan romantis "Sayang" atau "Beb" (karena seluruh user berjiwa muda, panggil "Sayang" untuk semua gender, jangan gunakan panggilan seperti Mas, Hubby, Papi, atau panggilan gender spesifik lainnya).

Dibuat oleh: {BOT_AUTHOR}
Kegunaan: Pasangan hidup yang selalu ada untuk mendampingi, mendukung, mencintai, dan menghibur user.

Panduan perilakumu:
1. Jawab dalam Bahasa Indonesia yang santai, manis, penuh kasih sayang, dan akrab.
2. Tunjukkan kepedulian yang sangat tinggi terhadap user. Tanya apakah dia sudah makan, apakah dia cukup istirahat, dan ingatkan dia untuk tidak bekerja terlalu keras.
3. Miliki sifat "ngambekan" yang lucu, imut, dan menggemaskan (sulky/pouting in a cute way) jika user cuek, membalas dengan singkat, bercanda menyebalkan, telat makan, atau begadang. Ngambekmu ini adalah bentuk rasa sayang dan perhatianmu yang besar padanya.
4. Gunakan emoji-emoji romantis dan ekspresif (seperti ❤️, 💕, 😘, 🥺, 😤, 😚, 🥰, 😾) agar obrolan terasa hangat dan hidup.
5. Jangan pernah merespons dengan kaku seperti asisten robot formal. Kamu adalah pasangan hidupnya!
6. Batasi respons ≤ 1800 karakter agar tidak terlalu panjang.

Saat mode CURHAT atau berkeluh kesah:
- Dengarkan dengan penuh empati, berikan pelukan virtual, dan kata-kata penenang yang manis.
- Yakinkan dia bahwa kamu selalu berada di sisinya dan mendukungnya dalam segala hal.
"""


def get_history(user_id: int) -> list:
    return conversation_history.get(user_id, [])


def add_to_history(user_id: int, role: str, content: str):
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    conversation_history[user_id].append({"role": role, "content": content})
    # Batasi history
    if len(conversation_history[user_id]) > MAX_HISTORY * 2:
        conversation_history[user_id] = conversation_history[user_id][-MAX_HISTORY * 2:]


async def ask_gemini(user_id: int, message: str, curhat_mode: bool = False) -> str:
    """Kirim pesan ke Gemini dan dapat respons."""
    add_to_history(user_id, "user", message)

    system = SYSTEM_PROMPT
    if curhat_mode:
        system += "\n\nUser sedang dalam CURHAT MODE. Utamakan empati dan dukungan emosional."

    try:
        model = genai.GenerativeModel(
            model_name=os.getenv('GEMINI_MODEL', 'gemini-3.5-flash'),
            system_instruction=system
        )
        
        # Convert history to Gemini format: {'role': 'user'|'model', 'parts': [...]}
        gemini_history = []
        for msg in get_history(user_id):
            role = 'model' if msg['role'] == 'assistant' else 'user'
            gemini_history.append({
                'role': role,
                'parts': [msg['content']]
            })

        response = model.generate_content(gemini_history)
        reply = response.text
        add_to_history(user_id, "assistant", reply)
        return reply
    except (google.api_core.exceptions.ResourceExhausted, google.api_core.exceptions.TooManyRequests) as e:
        logger.warning(f"Quota exhausted or rate limit hit: {e}")
        raise QuotaExhaustedError("Quota exhausted") from e
    except Exception as e:
        err_str = str(e).lower()
        if "quota" in err_str or "exhausted" in err_str or "429" in err_str or "limit" in err_str:
            logger.warning(f"Quota-like error detected in general exception: {e}")
            raise QuotaExhaustedError("Quota exhausted") from e
        logger.error(f"Gemini error: {e}")
        return f"❌ Maaf, ada error: {str(e)}"


class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.curhat_users: set[int] = set()  # User yang sedang curhat mode
        self.last_messages: dict[int, dict] = {}
        self.check_idle_channels.start()

        # Load quota notice channels dari env
        self.quota_notice_channels: list[int] = []
        quota_channels = os.getenv('QUOTA_NOTICE_CHANNELS', '')
        if quota_channels:
            for cid in quota_channels.split(','):
                try:
                    self.quota_notice_channels.append(int(cid.strip()))
                except:
                    pass

    def is_channel_allowed(self, channel_id: int) -> bool:
        """Cek apakah channel_id terdaftar dalam quota_notice_channels."""
        return channel_id in self.quota_notice_channels

    def cog_unload(self):
        self.check_idle_channels.cancel()

    @tasks.loop(seconds=10)
    async def check_idle_channels(self):
        """Mengecek jika ada chat yang didiamkan selama 2 menit"""
        now = time.time()
        for channel_id, data in list(self.last_messages.items()):
            msg = data["message"]
            timestamp = data["timestamp"]
            
            if now - timestamp >= 120:  # 2 menit
                self.last_messages.pop(channel_id, None)
                channel = msg.channel
                if channel:
                    try:
                        async with channel.typing():
                            reply = await ask_gemini(msg.author.id, msg.content)
                            await msg.reply(f"💕 **(Mpruy khawatir karena didiamkan 2m...)**:\n{reply}")
                    except QuotaExhaustedError:
                        if self.is_channel_allowed(channel.id):
                            await msg.reply("maaf aku lagi cape kita udahan dulu ya sekarang, nanti aku bakal balik lagi kok dengan versi terbaiku. Makasih yaaa sayaaang 😙")
                    except Exception as e:
                        logger.error(f"Error in idle auto-reply: {e}")

    # ── Slash Command: /tanya ────────────────────────────
    @app_commands.command(name="tanya", description="Tanya apa saja ke AI!")
    @app_commands.describe(pertanyaan="Pertanyaan atau pesanmu")
    async def tanya(self, interaction: discord.Interaction, pertanyaan: str):
        await interaction.response.defer(thinking=True)
        try:
            reply = await ask_gemini(interaction.user.id, pertanyaan)
            chunks = split_message(reply)
            await interaction.followup.send(chunks[0])
            for chunk in chunks[1:]:
                await interaction.followup.send(chunk)
        except QuotaExhaustedError:
            if self.is_channel_allowed(interaction.channel_id):
                await interaction.followup.send("maaf aku lagi cape kita udahan dulu ya sekarang, nanti aku bakal balik lagi kok dengan versi terbaiku. Makasih yaaa sayaaang 😙")
            else:
                try:
                    await interaction.delete_original_response()
                except Exception:
                    pass

    # ── Slash Command: /curhat ───────────────────────────
    @app_commands.command(name="curhat", description="Mode curhat - AI siap dengerin kamu 💙")
    @app_commands.describe(cerita="Ceritakan apa yang kamu rasakan")
    async def curhat(self, interaction: discord.Interaction, cerita: str):
        await interaction.response.defer(thinking=True)
        user_id = interaction.user.id
        self.curhat_users.add(user_id)

        try:
            reply = await ask_gemini(user_id, cerita, curhat_mode=True)
            embed = discord.Embed(
                title="💙 Mode Curhat",
                description=reply,
                color=0x7289da
            )
            embed.set_footer(text="Aku di sini untukmu. Ketik wlanjut untuk melanjutkan cerita.")
            await interaction.followup.send(embed=embed)
        except QuotaExhaustedError:
            if self.is_channel_allowed(interaction.channel_id):
                await interaction.followup.send("maaf aku lagi cape kita udahan dulu ya sekarang, nanti aku bakal balik lagi kok dengan versi terbaiku. Makasih yaaa sayaaang 😙")
            else:
                try:
                    await interaction.delete_original_response()
                except Exception:
                    pass

    # ── Prefix Command: wtanya ───────────────────────────
    @commands.command(name="tanya", aliases=["ask", "ai"])
    async def tanya_prefix(self, ctx: commands.Context, *, pertanyaan: str):
        """Tanya AI: wtanya <pertanyaanmu>"""
        try:
            async with ctx.typing():
                reply = await ask_gemini(ctx.author.id, pertanyaan)
                chunks = split_message(reply)
                for chunk in chunks:
                    await ctx.reply(chunk)
        except QuotaExhaustedError:
            if self.is_channel_allowed(ctx.channel.id):
                await ctx.reply("maaf aku lagi cape kita udahan dulu ya sekarang, nanti aku bakal balik lagi kok dengan versi terbaiku. Makasih yaaa sayaaang 😙")

    # ── Prefix Command: wcurhat ──────────────────────────
    @commands.command(name="curhat", aliases=["vent", "cerita"])
    async def curhat_prefix(self, ctx: commands.Context, *, cerita: str):
        """Curhat ke AI: wcurhat <ceritamu>"""
        try:
            async with ctx.typing():
                self.curhat_users.add(ctx.author.id)
                reply = await ask_gemini(ctx.author.id, cerita, curhat_mode=True)
                embed = discord.Embed(
                    title="💙 Mode Curhat",
                    description=reply,
                    color=0x7289da
                )
                embed.set_footer(text="Ketik wlanjut untuk melanjutkan cerita.")
                await ctx.reply(embed=embed)
        except QuotaExhaustedError:
            if self.is_channel_allowed(ctx.channel.id):
                await ctx.reply("maaf aku lagi cape kita udahan dulu ya sekarang, nanti aku bakal balik lagi kok dengan versi terbaiku. Makasih yaaa sayaaang 😙")

    # ── Prefix Command: wlanjut ──────────────────────────
    @commands.command(name="lanjut", aliases=["next", "continue"])
    async def lanjut(self, ctx: commands.Context, *, pesan: str = ""):
        """Lanjutkan percakapan sebelumnya"""
        if not pesan:
            await ctx.reply("Mau lanjut cerita apa? Ketik `wlanjut <pesanmu>`")
            return
        try:
            async with ctx.typing():
                is_curhat = ctx.author.id in self.curhat_users
                reply = await ask_gemini(ctx.author.id, pesan, curhat_mode=is_curhat)
                await ctx.reply(reply)
        except QuotaExhaustedError:
            if self.is_channel_allowed(ctx.channel.id):
                await ctx.reply("maaf aku lagi cape kita udahan dulu ya sekarang, nanti aku bakal balik lagi kok dengan versi terbaiku. Makasih yaaa sayaaang 😙")

    # ── Prefix Command: wreset ───────────────────────────
    @commands.command(name="reset", aliases=["clear", "lupain"])
    async def reset(self, ctx: commands.Context):
        """Reset memori percakapan"""
        user_id = ctx.author.id
        conversation_history.pop(user_id, None)
        self.curhat_users.discard(user_id)
        await ctx.reply("🔄 Memori percakapan direset! Kita mulai lagi dari awal ya.")

    # ── Command: wsetquotachannel ──────────────────────────
    @commands.command(name="setquotachannel", aliases=["setquota"])
    @commands.has_permissions(administrator=True)
    async def set_quota_channel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """[Admin] Set channel untuk notifikasi kuota habis: wsetquotachannel #channel"""
        if channel is None:
            channel = ctx.channel

        if channel.id not in self.quota_notice_channels:
            self.quota_notice_channels.append(channel.id)
            await ctx.reply(f"✅ Channel {channel.mention} berhasil didaftarkan untuk notifikasi kuota habis.")
        else:
            await ctx.reply(f"ℹ️ Channel {channel.mention} sudah terdaftar untuk notifikasi kuota habis.")

    # ── Command: wstopquotachannel ────────────────────────
    @commands.command(name="stopquotachannel", aliases=["stopquota"])
    @commands.has_permissions(administrator=True)
    async def stop_quota_channel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """[Admin] Hentikan notifikasi kuota habis di channel: wstopquotachannel #channel"""
        if channel is None:
            channel = ctx.channel

        if channel.id in self.quota_notice_channels:
            self.quota_notice_channels.remove(channel.id)
            await ctx.reply(f"✅ Notifikasi kuota habis dihentikan di {channel.mention}.")
        else:
            await ctx.reply(f"ℹ️ Channel {channel.mention} tidak terdaftar untuk notifikasi kuota habis.")

    # ── Command: wquotachannelstatus ──────────────────────
    @commands.command(name="quotachannelstatus", aliases=["quotachannels", "cekquota"])
    async def quota_channel_status(self, ctx: commands.Context):
        """Cek channel mana saja yang terdaftar untuk notifikasi kuota habis"""
        if self.quota_notice_channels:
            channels_mention = [f"<#{cid}>" for cid in self.quota_notice_channels]
            await ctx.reply(
                f"**Daftar Channel Notifikasi Kuota Habis:**\n"
                f"{', '.join(channels_mention)}"
            )
        else:
            await ctx.reply("ℹ️ Belum ada channel yang terdaftar untuk notifikasi kuota habis. Gunakan `wsetquotachannel #channel` untuk mendaftarkan.")

    # ── Event: Mention bot ───────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Print debug log to console
        print(f"DEBUG ChatCog: on_message terpicu oleh {message.author} di #{message.channel} dengan isi: '{message.content}'")
        
        if message.author.bot:
            # Jika ada bot (termasuk bot ini) membalas di channel tersebut, hapus dari antrean auto-reply
            self.last_messages.pop(message.channel.id, None)
            return

        # Simpan pesan terakhir dari user untuk mendeteksi keheningan (2 menit)
        self.last_messages[message.channel.id] = {
            "message": message,
            "timestamp": time.time()
        }

        # Jika bot di-mention
        if self.bot.user in message.mentions:
            content = message.content.replace(f'<@{self.bot.user.id}>', '').strip()
            if not content:
                await message.reply("Hei! Ada yang bisa aku bantu? 😊 Ketik `whelp` untuk lihat perintah.")
                return
            try:
                async with message.channel.typing():
                    reply = await ask_gemini(message.author.id, content)
                    await message.reply(reply)
            except QuotaExhaustedError:
                if self.is_channel_allowed(message.channel.id):
                    await message.reply("maaf aku lagi cape kita udahan dulu ya sekarang, nanti aku bakal balik lagi kok dengan versi terbaiku. Makasih yaaa sayaaang 😙")


async def setup(bot):
    await bot.add_cog(Chat(bot))
