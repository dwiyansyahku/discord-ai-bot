"""
Cog: Voice
Fitur: Join voice channel, TTS (Text-to-Speech), Voice Listening & Wake Word
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ext import voice_recv
import google.generativeai as genai
import edge_tts
import os
import asyncio
import tempfile
import logging
import time

logger = logging.getLogger('VoiceCog')
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

try:
    from davey import MediaType
    has_dave = True
except ImportError:
    has_dave = False

# ── MONKEY-PATCH `discord-ext-voice-recv` UNTUK DAVE DECRYPTION & STABILITAS ──
from discord.ext.voice_recv import opus as _voice_opus
from discord.ext.voice_recv import router as _voice_router

# 1. Patch PacketDecoder.__init__ to set passthrough mode in dave_session
_orig_decoder_init = _voice_opus.PacketDecoder.__init__

def _patched_decoder_init(self, router, ssrc):
    _orig_decoder_init(self, router, ssrc)
    try:
        self.vc = self.sink.voice_client
        if hasattr(self.vc, '_connection') and hasattr(self.vc._connection, 'dave_session') and self.vc._connection.dave_session is not None:
            self.vc._connection.dave_session.set_passthrough_mode(True, 10)
    except Exception as e:
        logger.warning(f"Failed to set DAVE passthrough mode: {e}")

_voice_opus.PacketDecoder.__init__ = _patched_decoder_init

# 2. Patch PacketDecoder._process_packet to perform DAVE decryption
_orig_process_packet = _voice_opus.PacketDecoder._process_packet

def _patched_process_packet(self, packet):
    pcm = None
    member = self._get_cached_member()

    if member is None:
        try:
            self._cached_id = self.sink.voice_client._get_id_from_ssrc(self.ssrc)
            member = self._get_cached_member()
        except Exception:
            pass

    # DAVE Decryption
    if has_dave and member and not packet.is_silence() and packet.decrypted_data is not None:
        try:
            vc = self.sink.voice_client
            if hasattr(vc, '_connection') and hasattr(vc._connection, 'dave_session') and vc._connection.dave_session is not None and vc._connection.dave_session.ready:
                packet.decrypted_data = vc._connection.dave_session.decrypt(member.id, MediaType.audio, bytes(packet.decrypted_data))
        except Exception:
            self._last_seq = packet.sequence
            self._last_ts = packet.timestamp
            return _voice_opus.VoiceData(packet, None, pcm=b'')

    if not self.sink.wants_opus():
        packet, pcm = self._decode_packet(packet)

    data = _voice_opus.VoiceData(packet, member, pcm=pcm)
    self._last_seq = packet.sequence
    self._last_ts = packet.timestamp

    return data

_voice_opus.PacketDecoder._process_packet = _patched_process_packet

# 3. Patch PacketDecoder._decode_packet to prevent decoder crash
_orig_decode_packet = _voice_opus.PacketDecoder._decode_packet

def _patched_decode_packet(self, packet):
    assert self._decoder is not None
    # Decode as per usual
    if packet:
        try:
            pcm = self._decoder.decode(packet.decrypted_data, fec=False)
        except Exception:
            try:
                pcm = self._decoder.decode(None, fec=False)
            except Exception:
                pcm = b'\x00' * 3840
        return packet, pcm

    # Fake packet, need to check next one to use fec
    next_packet = self._buffer.peek_next()

    if next_packet is not None:
        nextdata = next_packet.decrypted_data
        try:
            pcm = self._decoder.decode(nextdata, fec=True)
        except Exception:
            try:
                pcm = self._decoder.decode(None, fec=False)
            except Exception:
                pcm = b'\x00' * 3840
    # Need to drop a packet
    else:
        try:
            pcm = self._decoder.decode(None, fec=False)
        except Exception:
            pcm = b'\x00' * 3840

    return packet, pcm

_voice_opus.PacketDecoder._decode_packet = _patched_decode_packet

# 4. Patch PacketRouter._do_run to prevent packet router thread crashes and filter none sources
def _patched_do_run(self):
    while not self._end_thread.is_set():
        self.waiter.wait()
        with self._lock:
            for decoder in list(self.waiter.items):
                try:
                    data = decoder.pop_data()
                except Exception:
                    continue
                if data is not None and data.source is not None:
                    try:
                        self.sink.write(data.source, data)
                    except Exception:
                        pass

_voice_router.PacketRouter._do_run = _patched_do_run

async def text_to_speech(text: str, output_path: str, lang: str = "id") -> bool:
    """Konversi teks ke audio file menggunakan edge-tts (neural premium gratis)."""
    try:
        # id-ID-GadisNeural untuk Indonesia, en-US-JennyNeural untuk Inggris
        voice = "id-ID-GadisNeural" if lang == "id" else "en-US-JennyNeural"
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        return True
    except Exception as e:
        logger.error(f"edge-tts error: {e}")
        return False

class SafeOpusSink(voice_recv.AudioSink):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        # Pastikan library Opus ter-load
        if not discord.opus.is_loaded():
            try:
                discord.opus.load_opus()
            except:
                pass
        self.decoder = discord.opus.Decoder()

    def wants_opus(self) -> bool:
        return True

    def write(self, user, data: voice_recv.VoiceData):
        if data.opus is None:
            return
        try:
            # Decode Opus ke PCM stereo 48000Hz 16-bit
            pcm = self.decoder.decode(data.opus, fec=False)
            data.pcm = pcm
            self.callback(user, data)
        except Exception:
            # Abaikan jika terjadi packet loss atau stream corrupt
            pass

    def cleanup(self) -> None:
        pass

class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_clients: dict[int, discord.VoiceClient] = {}
        
        # State untuk voice listening
        self.user_buffers: dict[int, bytearray] = {}
        self.user_last_spoke: dict[int, float] = {}
        self.locked_user: int = None
        self.awaiting_done_confirmation: bool = False
        self.bot_is_speaking: bool = False
        self.last_text_channels: dict[int, discord.TextChannel] = {}
        self.last_user_messages: dict[int, dict[int, discord.Message]] = {}  # guild_id -> user_id -> Message
        self.last_interaction_time: float = time.time()
        
        # Start background check silences
        self.check_silence.start()

    def cog_unload(self):
        self.check_silence.cancel()

    @tasks.loop(seconds=0.2)
    async def check_silence(self):
        """Mengecek keheningan user untuk mendeteksi kapan user selesai berbicara"""
        current_time = time.time()

        # Auto-unlock jika locked_user tidak ada aktivitas selama 30 detik
        if self.locked_user is not None and not self.bot_is_speaking:
            if current_time - self.last_interaction_time > 30.0:
                print(f"DEBUG VoiceCog: Auto-unlock user {self.locked_user} karena tidak ada aktivitas selama 30 detik.")
                self.locked_user = None
                self.awaiting_done_confirmation = False

        for user_id in list(self.user_last_spoke.keys()):
            last_spoke = self.user_last_spoke[user_id]
            # Jika user diam selama lebih dari 1.2 detik
            if current_time - last_spoke > 1.2:
                self.user_last_spoke.pop(user_id, None)
                buffer = self.user_buffers.pop(user_id, None)
                # Pastikan panjang audio minimal 0.5 detik (48000 Hz * 2 channels * 2 bytes = 192000 bytes per second)
                if buffer and len(buffer) > 192000 * 0.5:
                    asyncio.create_task(self.process_user_audio(user_id, bytes(buffer)))

    def audio_callback(self, user, data: voice_recv.VoiceData):
        """Callback untuk menerima paket audio dari user di voice channel"""
        if user is None or user.bot:
            return
        # Jangan rekam suara user jika bot sedang berbicara (untuk menghindari gema/feedback loop)
        if self.bot_is_speaking:
            return

        user_id = user.id
        if user_id not in self.user_buffers or len(self.user_buffers[user_id]) == 0:
            print(f"DEBUG VoiceCog: User {user} mulai bersuara (rekaman dimulai)...")
            
        if user_id not in self.user_buffers:
            self.user_buffers[user_id] = bytearray()
        
        # Masukkan data PCM 48kHz stereo ke buffer
        self.user_buffers[user_id].extend(data.pcm)
        self.user_last_spoke[user_id] = time.time()

    def recognize_audio(self, mono_pcm: bytes) -> str:
        """Mengubah PCM bytes ke Teks menggunakan SpeechRecognition"""
        import speech_recognition as sr
        r = sr.Recognizer()
        audio_data = sr.AudioData(mono_pcm, 48000, 2)
        try:
            # Coba deteksi Bahasa Indonesia dahulu
            return r.recognize_google(audio_data, language="id-ID")
        except sr.UnknownValueError:
            try:
                # Fallback ke Bahasa Inggris
                return r.recognize_google(audio_data, language="en-US")
            except:
                return ""
        except Exception as e:
            logger.error(f"Speech recognition error: {e}")
            return ""

    async def process_user_audio(self, user_id: int, pcm_data: bytes):
        """Memproses data audio mentah user"""
        print(f"DEBUG VoiceCog: Mendeteksi keheningan. Mulai memproses {len(pcm_data)} bytes data audio dari user ID {user_id}...")
        
        # Konversi PCM Stereo (2 channels) ke Mono (1 channel)
        mono_pcm = bytearray()
        for i in range(0, len(pcm_data), 4):
            if i + 3 < len(pcm_data):
                mono_pcm.extend(pcm_data[i:i+2])

        # Jalankan STT di executor agar tidak memblokir event loop
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, self.recognize_audio, bytes(mono_pcm))
        
        print(f"DEBUG VoiceCog: Hasil transkripsi STT untuk user ID {user_id}: '{text}'")
        
        if not text or len(text.strip()) < 2:
            return

        logger.info(f"User {user_id} bersuara: {text}")

        # Cari channel voice tempat user berada berdasarkan voice client aktif
        guild = None
        for vc in list(self.voice_clients.values()):
            if vc.is_connected() and any(m.id == user_id for m in vc.channel.members):
                guild = vc.guild
                break

        if not guild:
            # Fallback ke voice client aktif mana saja
            for vc in list(self.voice_clients.values()):
                if vc.is_connected():
                    guild = vc.guild
                    break

        if not guild or not guild.voice_client:
            print(f"DEBUG VoiceCog: Tidak menemukan guild atau voice client aktif untuk user ID {user_id}")
            return

        # Jika bot belum dikunci oleh siapapun, deteksi kata kunci pembuka
        if self.locked_user is None:
            trigger_words = ["hi besti", "hai besti", "hi bestie", "hai bestie", "woy mpruy", "oi mpruy", "hey mpruy", "hei mpruy", "mpruy"]
            if any(word in text.lower() for word in trigger_words):
                self.locked_user = user_id
                self.last_interaction_time = time.time()
                # Sesuaikan respon jika memanggil "besti"
                response_text = "Hai sayang! Ada apa? Aku di sini menemani kamu." if "besti" in text.lower() else "Iya sayang? Ada apa? Mpruy di sini mendengarkan kamu."
                await self.speak_response(guild, response_text)
            return

        # Jika terkunci ke user lain, abaikan
        if self.locked_user != user_id:
            return

        self.last_interaction_time = time.time()

        # Jika sedang menunggu konfirmasi selesai obrolan
        text_lower = text.lower()
        if self.awaiting_done_confirmation:
            self.awaiting_done_confirmation = False
            if any(word in text_lower for word in ["belum", "tidak belum", "no"]):
                await self.speak_response(guild, "Oke sayang, silakan dilanjutkan cerita kamu. Aku dengerin kok. Mau cerita apa lagi?")
            elif any(word in text_lower for word in ["ya", "sudah", "selesai", "tidak", "yes"]):
                self.locked_user = None
                await self.speak_response(guild, "Oke Sayang, aku temenin kamu di sini ya. Kalau butuh teman ngobrol lagi panggil aku ya!")
            else:
                # Jika respon tidak jelas, teruskan obrolan saja
                await self.respond_to_voice_chat(guild, user_id, text)
            return

        # Respon obrolan normal
        await self.respond_to_voice_chat(guild, user_id, text)

    async def respond_to_voice_chat(self, guild, user_id, text):
        """Meminta respon Gemini dan mengucapkannya ke voice channel"""
        from cogs.chat import ask_gemini
        
        reply = await ask_gemini(user_id, text)
        clean_reply = reply.replace("*", "").replace("_", "").replace("`", "").strip()
        
        # Tambahkan pertanyaan konfirmasi di akhir
        clean_reply_with_question = clean_reply + " Sayang masih mau lanjut cerita, atau udah selesai?"
        self.awaiting_done_confirmation = True
        
        await self.speak_response(guild, clean_reply_with_question)

    async def speak_response(self, guild, text):
        """Mengucapkan teks ke voice channel menggunakan Edge TTS dan mengirimkannya ke text channel"""
        # Kirim teks ke text channel terakhir yang aktif agar bot otomatis mereply/tidak diam
        channel = self.last_text_channels.get(guild.id)
        if channel:
            try:
                member = guild.get_member(self.locked_user) if self.locked_user else None
                
                # Cari pesan terakhir dari user ini di channel ini untuk di-reply
                last_msg = None
                if member and guild.id in self.last_user_messages:
                    user_msg = self.last_user_messages[guild.id].get(member.id)
                    if user_msg and user_msg.channel.id == channel.id:
                        last_msg = user_msg

                content = f"🎙️ **(Voice Chat)**: {text}"
                if last_msg:
                    # Reply ke pesan terakhir user
                    await last_msg.reply(content)
                else:
                    # Fallback jika tidak ada pesan terakhir untuk di-reply
                    prefix_tag = f"{member.mention} " if member else ""
                    await channel.send(f"{prefix_tag}{content}")
            except Exception as e:
                logger.error(f"Gagal mengirim pesan teks respon voice: {e}")

        vc = guild.voice_client
        if not vc or not vc.is_connected():
            return

        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp_path = tmp.name

        # Deteksi bahasa sederhana untuk memilih suara (Indonesian vs English)
        lang = 'id'
        en_words = ["the", "and", "you", "hello", "what", "is", "are", "completed", "finish", "done"]
        if any(word in text.lower() for word in en_words):
            count = sum(1 for word in en_words if word in text.lower())
            if count > 2:
                lang = 'en'

        success = await text_to_speech(text, tmp_path, lang)
        if success and os.path.exists(tmp_path):
            self.bot_is_speaking = True
            
            def after_playing(error):
                self.bot_is_speaking = False
                try:
                    os.unlink(tmp_path)
                except:
                    pass

            source = discord.FFmpegPCMAudio(tmp_path)
            if vc.is_playing():
                vc.stop()
            vc.play(source, after=after_playing)

            # Tunggu hingga bot selesai berbicara (dengan safety timeout 15 detik)
            start_wait = time.time()
            while self.bot_is_speaking and time.time() - start_wait < 15.0:
                await asyncio.sleep(0.1)
            
            # Pengaman jika terjadi hang pada ffmpeg/callback
            self.bot_is_speaking = False

    # ── Command: !join ───────────────────────────────────
    @commands.command(name="join", aliases=["masuk", "voicejoin"])
    async def join_voice(self, ctx: commands.Context):
        """Bot join voice channel kamu: wjoin"""
        if not ctx.author.voice:
            await ctx.reply("❌ Kamu harus di voice channel dulu!")
            return

        channel = ctx.author.voice.channel
        guild_id = ctx.guild.id

        if guild_id in self.voice_clients and self.voice_clients[guild_id].is_connected():
            await self.voice_clients[guild_id].move_to(channel)
            vc = self.voice_clients[guild_id]
        else:
            try:
                # Connect menggunakan VoiceRecvClient untuk mendengarkan suara
                vc = await channel.connect(cls=voice_recv.VoiceRecvClient)
                self.voice_clients[guild_id] = vc
            except Exception as e:
                await ctx.reply(f"❌ Gagal join: {e}")
                return

        # Mulai mendengarkan suara
        if not vc.is_listening():
            vc.listen(SafeOpusSink(self.audio_callback))
            
        await ctx.reply(f"✅ Joined **{channel.name}**! Gunakan `wbicara <teks>` atau panggil aku dengan kata kunci *\"hi besti\"*.")

    # ── Command: !leave ──────────────────────────────────
    @commands.command(name="leave", aliases=["keluar", "dc"])
    async def leave_voice(self, ctx: commands.Context):
        """Bot keluar voice channel: wleave"""
        guild_id = ctx.guild.id
        if guild_id in self.voice_clients and self.voice_clients[guild_id].is_connected():
            await self.voice_clients[guild_id].disconnect()
            del self.voice_clients[guild_id]
            await ctx.reply("👋 Sampai jumpa!")
        else:
            await ctx.reply("❌ Aku tidak sedang di voice channel.")

    # ── Command: !bicara ─────────────────────────────────
    @commands.command(name="bicara", aliases=["say", "speak", "ngomong"])
    async def speak(self, ctx: commands.Context, *, teks: str):
        """Bot bicara di voice: wbicara <teks>"""
        guild_id = ctx.guild.id

        if guild_id not in self.voice_clients or not self.voice_clients[guild_id].is_connected():
            if ctx.author.voice:
                await self.join_voice(ctx)
            else:
                await ctx.reply("❌ Gunakan `wjoin` dulu untuk aku masuk voice channel.")
                return

        await ctx.reply(f"🔊 Berbicara...")
        await self.speak_response(ctx.guild, teks)

    # ── Command: !tanyavoice ─────────────────────────────
    @commands.command(name="tanyavoice", aliases=["askvoice", "av"])
    async def ask_voice(self, ctx: commands.Context, *, pertanyaan: str):
        """Tanya AI dan jawabannya disuarakan: wtanyavoice <pertanyaan>"""
        guild_id = ctx.guild.id

        if guild_id not in self.voice_clients or not self.voice_clients[guild_id].is_connected():
            if ctx.author.voice:
                await self.join_voice(ctx)
            else:
                await ctx.reply("❌ Masuk voice channel dulu, atau gunakan `wjoin`.")
                return

        async with ctx.typing():
            try:
                model = genai.GenerativeModel(
                    model_name=os.getenv('GEMINI_MODEL', 'gemini-2.5-flash'),
                    system_instruction=(
                        "Kamu adalah pasangan hidup (istri/pacar) yang sangat menyayangi user. Panggil dirimu 'mpruy' atau 'Aku' dan panggil user dengan panggilan sayang.\n"
                        "Jawab pertanyaan dengan singkat dan jelas (max 2-3 kalimat), romantis, peduli, dan sedikit ngambekan yang lucu.\n"
                        "Gunakan Bahasa Indonesia. Hindari simbol, asterik (*), atau emoji karena jawaban ini akan langsung dibacakan oleh text-to-speech."
                    )
                )
                response = model.generate_content(pertanyaan)
                jawaban = response.text

                embed = discord.Embed(
                    title=f"❓ {pertanyaan}",
                    description=f"🔊 {jawaban}",
                    color=0x5865F2
                )
                await ctx.reply(embed=embed)
                await self.speak_response(ctx.guild, jawaban)

            except Exception as e:
                await ctx.reply(f"❌ Error: {e}")

    # ── Event: Cleanup & Auto Join/Leave ─────────────────
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        if member.bot:
            return

        guild_id = member.guild.id

        # 0. AUTO UNLOCK: Jika locked user keluar dari channel bot
        if self.locked_user == member.id:
            vc = member.guild.voice_client
            # Jika user keluar atau pindah channel yang bukan channel bot
            if after.channel is None or (vc and vc.channel != after.channel):
                print(f"DEBUG VoiceCog: Auto-unlock user {self.locked_user} karena keluar dari voice channel.")
                self.locked_user = None
                self.awaiting_done_confirmation = False

        # 1. AUTO JOIN: Jika ada user masuk ke voice channel dan bot tidak sedang berada di voice channel mana pun
        if after.channel is not None and before.channel is not after.channel:
            vc = member.guild.voice_client
            if vc is None:
                try:
                    vc = await after.channel.connect(cls=voice_recv.VoiceRecvClient)
                    self.voice_clients[guild_id] = vc
                    vc.listen(SafeOpusSink(self.audio_callback))
                    logger.info(f"🤖 Auto joined {after.channel.name}")
                except Exception as e:
                    logger.error(f"Auto join failed: {e}")



    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        # Simpan channel teks aktif terakhir untuk guild ini
        self.last_text_channels[message.guild.id] = message.channel
        
        # Simpan pesan terakhir dari user
        guild_id = message.guild.id
        if guild_id not in self.last_user_messages:
            self.last_user_messages[guild_id] = {}
        self.last_user_messages[guild_id][message.author.id] = message

async def setup(bot):
    await bot.add_cog(Voice(bot))
