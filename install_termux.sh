#!/data/data/com.termux/files/usr/bin/bash
set -e
printf "\n╔════════════════════════════════════════════╗\n"
printf "║        Hipo Ai 5.1 Pro Installer          ║\n"
printf "╚════════════════════════════════════════════╝\n\n"
pkg update -y
pkg install -y python
chmod +x hipo Hipo hipo.py
mkdir -p "$HOME/.hipo_ai_5_1_pro"

if [ -n "$PREFIX" ]; then
  ln -sf "$(pwd)/hipo" "$PREFIX/bin/hipo"
  ln -sf "$(pwd)/Hipo" "$PREFIX/bin/Hipo"
  printf "Command global dibuat: hipo dan Hipo\n"
fi

printf "\nInstall selesai.\n"
printf "1) Set API key dengan environment variable:\n"
printf "   export OPENROUTER_API_KEY=\"ISI_KEY_KAMU\"\n\n"
printf "2) Setup akun lokal:\n"
printf "   ./hipo setup --reset\n\n"
printf "3) Jalankan:\n"
printf "   ./hipo\n"
printf "   hipo --help\n   Hipo --help\n\n"
