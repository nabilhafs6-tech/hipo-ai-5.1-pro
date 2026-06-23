# Hipo Ai 5.1 Pro

**Hipo Ai 5.1 Pro** adalah terminal AI assistant/agent untuk Termux, mirip workflow terminal AI coding tools.

Owner: **BrawnCheezl - Nabil**

## Fitur

- Premium ASCII banner.
- Security gate username/password lokal.
- Password disimpan sebagai salted PBKDF2 hash.
- AI Chatbot via OpenRouter-compatible API.
- Agent mode untuk coding, debugging, shell planning, file workflow.
- Status CPU, RAM, Disk, GPU/SoC, battery Termux, network probe.
- Status Hipo Cloud / OpenRouter probe.
- Command center interaktif.
- `hipo --help`.
- Audit log lokal tanpa menyimpan password.

> Demi keamanan, Hipo tidak mengirim username/password ke email atau layanan luar. Password tidak boleh dikirim karena itu berisiko kebocoran credential. Yang tersedia adalah audit log lokal di `~/.hipo_ai_5_1_pro/audit.log`.

## Install di Termux

```bash
pkg update && pkg upgrade
pkg install python
cd hipo-ai-5.1-pro
bash install_termux.sh
```

## Set API Key

Jangan hardcode API key di source code. Set via environment variable:

```bash
export OPENROUTER_API_KEY="ISI_API_KEY_KAMU"
```

Agar permanen di Termux:

```bash
echo 'export OPENROUTER_API_KEY="ISI_API_KEY_KAMU"' >> ~/.bashrc
source ~/.bashrc
```

Atau buat file `.env` di folder project:

```bash
cp .env.example .env
nano .env
```

## Setup Login Lokal

```bash
./hipo setup --reset
```

Lalu jalankan:

```bash
./hipo
```

Kalau installer membuat command global:

```bash
hipo
hipo --help
Hipo --help
```

## Command CLI

```bash
./hipo --help
./Hipo --help
./hipo about
./hipo status
./hipo apikey
./hipo models --limit 20
./hipo chat
./hipo ask "buatkan script python hello world"
./hipo agent "buat project REST API sederhana"
./hipo scan .
./hipo read README.md
./hipo run "ls -la"
```

## Command Center Interaktif

Saat menjalankan `./hipo`, kamu masuk ke command center:

```text
hipo> help
hipo> chat
hipo> ask jelaskan docker
hipo> agent buat website portfolio
hipo> status
hipo> models 10
hipo> scan .
hipo> read file.py
hipo> run python --version
hipo> exit
```

## Chat Commands

Di mode chat:

```text
/help
/model openai/gpt-4o-mini
/status
/agent buat script backup folder
/clear
/save chat.md
/exit
```

## Catatan Keamanan

- Jika API key pernah kamu kirim ke tempat publik/chat, sebaiknya **rotate/revoke** dan buat key baru.
- Hipo tidak menyimpan API key kecuali kamu sendiri menaruhnya di `.env`.
- Hipo tidak menyimpan password plaintext.
- Hipo tidak mengirim password ke email.
- Command `run` selalu meminta konfirmasi sebelum menjalankan shell command.

## Struktur Project

```text
hipo-ai-5.1-pro/
├── hipo.py              # main app
├── hipo                 # launcher Termux/Linux
├── install_termux.sh    # installer Termux
├── .env.example         # contoh konfigurasi API key
├── .gitignore
├── requirements.txt
└── README.md
```
