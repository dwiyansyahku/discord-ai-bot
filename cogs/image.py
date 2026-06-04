"""
Cog: Image Generation
Fitur: Generate gambar dari teks
Support: Stable Diffusion (lokal) atau Hugging Face (online gratis)
"""

import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
import base64
import io
import google.generativeai as genai
import logging

logger = logging.getLogger('ImageCog')
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

SD_API_URL = os.getenv('SD_API_URL', 'http://127.0.0.1:7860')
HF_API_KEY = os.getenv('HF_API_KEY', '')

# Model HF gratis untuk image generation
HF_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"


async def translate_to_english(prompt: str) -> str:
    """Terjemahkan prompt ke Bahasa Inggris untuk hasil gambar lebih baik."""
    try:
        model = genai.GenerativeModel(
            model_name=os.getenv('GEMINI_MODEL', 'gemini-1.5-flash'),
            system_instruction="Translate the following image generation prompt to English. Make it descriptive and artistic. Return ONLY the translated prompt, nothing else."
        )
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return prompt


async def generate_via_stable_diffusion(prompt: str) -> bytes | None:
    """Generate gambar via Automatic1111 WebUI (lokal)."""
    payload = {
        "prompt": prompt,
        "negative_prompt": "ugly, blurry, bad quality, watermark, nsfw",
        "steps": 20,
        "width": 512,
        "height": 512,
        "cfg_scale": 7,
        "sampler_name": "DPM++ 2M Karras"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{SD_API_URL}/sdapi/v1/txt2img",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    img_data = base64.b64decode(data['images'][0])
                    return img_data
    except Exception as e:
        logger.error(f"SD error: {e}")
    return None


async def generate_via_huggingface(prompt: str) -> bytes | None:
    """Generate gambar via Hugging Face Inference API (online)."""
    if not HF_API_KEY:
        return None

    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {"inputs": prompt}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://api-inference.huggingface.co/models/{HF_MODEL}",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status == 200:
                    return await resp.read()
                else:
                    text = await resp.text()
                    logger.error(f"HF error {resp.status}: {text}")
    except Exception as e:
        logger.error(f"HF error: {e}")
    return None


class ImageGen(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Slash Command: /gambar ───────────────────────────
    @app_commands.command(name="gambar", description="Generate gambar dari deskripsi teks 🎨")
    @app_commands.describe(
        deskripsi="Deskripsi gambar yang mau dibuat",
        terjemahkan="Terjemahkan otomatis ke Inggris untuk hasil lebih baik (default: Ya)"
    )
    async def gambar(
        self,
        interaction: discord.Interaction,
        deskripsi: str,
        terjemahkan: bool = True
    ):
        await interaction.response.defer(thinking=True)
        await self._generate_image(interaction, deskripsi, terjemahkan, slash=True)

    # ── Prefix Command: wgambar ──────────────────────────
    @commands.command(name="gambar", aliases=["generate", "gen", "buatgambar", "img"])
    async def gambar_prefix(self, ctx: commands.Context, *, deskripsi: str):
        """Generate gambar: wgambar <deskripsi>
        Contoh: wgambar pemandangan gunung saat senja, anime style"""
        async with ctx.typing():
            await self._generate_image(ctx, deskripsi, terjemahkan=True, slash=False)

    async def _generate_image(self, ctx_or_interaction, deskripsi: str, terjemahkan: bool, slash: bool):
        """Logic generate gambar (shared untuk slash & prefix)"""
        prompt = deskripsi
        translated_prompt = None

        # Terjemahkan jika perlu
        if terjemahkan:
            translated_prompt = await translate_to_english(deskripsi)
            prompt = translated_prompt

        # Coba generate: SD lokal dulu, fallback ke HF
        img_data = await generate_via_stable_diffusion(prompt)
        source = "Stable Diffusion"

        if not img_data:
            img_data = await generate_via_huggingface(prompt)
            source = "Hugging Face"

        if img_data:
            file = discord.File(io.BytesIO(img_data), filename="generated.png")
            embed = discord.Embed(
                title="🎨 Gambar Generated!",
                color=0xEB459E
            )
            embed.add_field(name="📝 Prompt asli", value=deskripsi, inline=False)
            if translated_prompt:
                embed.add_field(name="🌐 Prompt (EN)", value=translated_prompt, inline=False)
            embed.add_field(name="🔧 Engine", value=source, inline=True)
            embed.set_image(url="attachment://generated.png")

            if slash:
                await ctx_or_interaction.followup.send(embed=embed, file=file)
            else:
                await ctx_or_interaction.reply(embed=embed, file=file)
        else:
            msg = (
                "❌ **Gagal generate gambar!**\n\n"
                "Pastikan salah satu ini aktif:\n"
                "• **Stable Diffusion WebUI** (`--api` flag) berjalan di localhost\n"
                "• **HF_API_KEY** diisi di `.env`\n\n"
                "Setup guide: `whelpimage`"
            )
            if slash:
                await ctx_or_interaction.followup.send(msg)
            else:
                await ctx_or_interaction.reply(msg)

    # ── Command: !helpimage ──────────────────────────────
    @commands.command(name="helpimage", aliases=["imagehelp"])
    async def help_image(self, ctx: commands.Context):
        """Panduan setup image generation"""
        embed = discord.Embed(
            title="🎨 Panduan Image Generation",
            color=0xEB459E
        )
        embed.add_field(
            name="Opsi 1: Stable Diffusion (Lokal, Gratis)",
            value=(
                "1. Download [AUTOMATIC1111 WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui)\n"
                "2. Jalankan dengan flag `--api`\n"
                "3. Set `SD_API_URL=http://127.0.0.1:7860` di `.env`"
            ),
            inline=False
        )
        embed.add_field(
            name="Opsi 2: Hugging Face (Online, Gratis limited)",
            value=(
                "1. Daftar di [huggingface.co](https://huggingface.co)\n"
                "2. Buat API token di Settings > Access Tokens\n"
                "3. Set `HF_API_KEY=your_token` di `.env`"
            ),
            inline=False
        )
        embed.add_field(
            name="Penggunaan",
            value=(
                "`wgambar <deskripsi>` - Generate gambar\n"
                "Contoh: `wgambar kota futuristik malam hari, cyberpunk`\n"
                "Contoh: `wgambar kucing lucu memakai topi, watercolor style`"
            ),
            inline=False
        )
        await ctx.reply(embed=embed)


async def setup(bot):
    await bot.add_cog(ImageGen(bot))
