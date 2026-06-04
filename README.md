# 🤖 Discord AI Assistant Bot

Bot Discord bertenaga AI (Gemini) dengan fitur lengkap: chat, voice, image generation, dan teman curhat.

---

## ✨ Fitur

| Fitur | Perintah | Keterangan |
|-------|----------|------------|
| 💬 Chat AI | `wtanya`, `@mention` | Jawab pertanyaan dengan Gemini |
| 💙 Curhat | `wcurhat` | Teman curhat empatik + saran |
| 🎙️ Voice | `wjoin`, `wbicara` | Ngobrol lewat voice channel |
| 🎨 Image | `wgambar` | Generate gambar dari teks |
| 📢 Auto Post | `wsetautopost` | Ramaikan server otomatis |
| ℹ️ Info | `winfo` | Info pembuat & kegunaan bot |

---

## 🚀 Setup (Step by Step)

### Step 1: Persiapan Akun

#### 1a. Buat Discord Bot
1. Buka [discord.com/developers/applications](https://discord.com/developers/applications)
2. Klik **"New Application"** → beri nama bot
3. Pergi ke tab **"Bot"** → klik **"Add Bot"**
4. Di bagian **"TOKEN"** → klik **"Reset Token"** → copy tokennya
5. Di **"Privileged Gateway Intents"**, aktifkan:
   - ✅ **Server Members Intent**
   - ✅ **Message Content Intent**
6. Pergi ke tab **"OAuth2" → "URL Generator"**:
   - Centang: `bot` dan `applications.commands`
   - Bot Permissions: `Send Messages`, `Read Messages`, `Connect`, `Speak`, `Use Voice Activity`, `Embed Links`, `Attach Files`
   - Copy URL dan buka di browser untuk invite bot ke servermu

#### 1b. Dapatkan Gemini API Key
1. Buka [aistudio.google.com](https://aistudio.google.com)
2. Daftar/login dengan akun Google Anda
3. Klik **"Get API Key"** -> **"Create API Key"** -> copy keynya

---

### Step 2: Install Bot

```bash
# Clone / download project ini
cd discord-ai-bot

# Buat virtual environment (direkomendasikan)
python -m venv venv

# Aktifkan venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### Install FFmpeg (WAJIB untuk voice)
- **Windows**: Download dari [ffmpeg.org](https://ffmpeg.org/download.html), tambahkan ke PATH
- **Ubuntu/Debian**: `sudo apt install ffmpeg`
- **Mac**: `brew install ffmpeg`

---

### Step 3: Konfigurasi

```bash
# Copy file template
cp .env.example .env

# Edit .env dengan text editor favoritmu
notepad .env     # Windows
nano .env        # Linux/Mac
```

Isi minimal yang **WAJIB**:
```env
DISCORD_TOKEN=token_discord_kamu
GEMINI_API_KEY=api_key_gemini_kamu
BOT_AUTHOR=Nama Kamu
```

---

### Step 4: Jalankan Bot

```bash
python bot.py
```

Kalau berhasil, akan muncul:
```
✅ Bot online sebagai NamaBotmu#1234 (ID: 123456789)
✅ Loaded: cogs.chat
✅ Loaded: cogs.autopost
✅ Loaded: cogs.voice
✅ Loaded: cogs.image
✅ Loaded: cogs.info
✅ Synced 5 slash commands
```

---

## 🎙️ Setup Voice (Lebih Detail)

Bot mendukung 3 engine TTS, gunakan yang sesuai kebutuhan:

### Opsi A: gTTS (Gratis, butuh internet)
```bash
pip install gTTS
```
Otomatis aktif, tidak perlu konfigurasi tambahan.

### Opsi B: pyttsx3 (Gratis, offline)
```bash
pip install pyttsx3
```
Kualitas suara tergantung TTS engine sistem operasimu.

### Opsi C: ElevenLabs (Berbayar, kualitas terbaik)
1. Daftar di [elevenlabs.io](https://elevenlabs.io) (ada free tier)
2. Copy API Key dari Settings
3. Tambahkan ke `.env`:
   ```env
   ELEVENLABS_API_KEY=your_key_here
   ```
4. Install library:
   ```bash
   pip install elevenlabs
   ```

---

## 🎨 Setup Image Generation

### Opsi A: Stable Diffusion (Lokal, Gratis, Kualitas Terbaik)
1. Download [AUTOMATIC1111 WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui)
2. Download model (contoh: [Realistic Vision](https://civitai.com/models/4201))
3. Jalankan dengan flag `--api`:
   ```bash
   # Windows
   webui.bat --api
   # Linux/Mac
   ./webui.sh --api
   ```
4. Tambahkan ke `.env`:
   ```env
   SD_API_URL=http://127.0.0.1:7860
   ```

### Opsi B: Hugging Face (Online, Gratis limited)
1. Daftar di [huggingface.co](https://huggingface.co)
2. Pergi ke Settings → Access Tokens → New token
3. Tambahkan ke `.env`:
   ```env
   HF_API_KEY=hf_xxxxxxxxxxxxx
   ```

---

## 📢 Setup Auto Post

1. Jalankan bot dan invite ke server
2. Di channel yang diinginkan, ketik:
   ```
   wsetautopost
   ```
   atau di channel tertentu:
   ```
   wsetautopost #general
   ```
3. Bot akan auto posting setiap 60 menit (bisa diubah di `.env`)

---

## 📁 Struktur File

```
discord-ai-bot/
├── bot.py              # File utama, jalankan ini
├── .env                # Konfigurasi (jangan di-share!)
├── .env.example        # Template konfigurasi
├── requirements.txt    # Daftar library
├── cogs/
│   ├── chat.py         # Fitur Q&A + Curhat
│   ├── autopost.py     # Auto posting
│   ├── voice.py        # Voice channel
│   ├── image.py        # Image generation
│   └── info.py         # Info bot + help
└── utils/
    └── helpers.py      # Fungsi pembantu
```

---

## 🔧 Troubleshooting

**Bot tidak muncul online?**
→ Cek `DISCORD_TOKEN` di `.env`, pastikan benar

**Error "Privileged Intent"?**
→ Aktifkan "Message Content Intent" di Discord Developer Portal

**Voice tidak bisa join?**
→ Pastikan ffmpeg terinstall dan ada di PATH

**Image generation gagal?**
→ Cek `SD_API_URL` or `HF_API_KEY` di `.env`

**Slash commands tidak muncul?**
→ Tunggu hingga 1 jam untuk Discord sync, atau kick + reinvite bot

---

## 📜 Lisensi

Free to use dan modifikasi untuk keperluan pribadi/komunitas.

---

*Dibuat dengan ❤️ menggunakan Gemini API + discord.py*
