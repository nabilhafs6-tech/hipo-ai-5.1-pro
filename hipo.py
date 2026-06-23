#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hipo Ai 5.1 Pro — Termux / Terminal AI Agent
Owner: BrawnCheezl - Nabil

Safe design notes:
- Login credentials are stored locally as salted PBKDF2 hashes.
- Passwords are never written to logs and never sent to email/API.
- API key is read from environment variable or local .env file, not hardcoded.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import json
import os
import pathlib
import platform
import re
import secrets
import shlex
import shutil
import socket
import ssl
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

APP_NAME = "Hipo Ai 5.1 Pro"
APP_VERSION = "5.1.0-pro"
OWNER = "BrawnCheezl - Nabil"
SESSION_ID = uuid.uuid4().hex[:10]
ROOT = pathlib.Path(__file__).resolve().parent
CONFIG_DIR = pathlib.Path.home() / ".hipo_ai_5_1_pro"
AUTH_FILE = CONFIG_DIR / "auth.json"
AUDIT_FILE = CONFIG_DIR / "audit.log"
HISTORY_FILE = CONFIG_DIR / "history.jsonl"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
DEFAULT_MODEL = "openai/gpt-4o-mini"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS_URL = "https://openrouter.ai/api/v1/models"


class C:
    reset = "\033[0m"
    bold = "\033[1m"
    dim = "\033[2m"
    red = "\033[31m"
    green = "\033[32m"
    yellow = "\033[33m"
    blue = "\033[34m"
    magenta = "\033[35m"
    cyan = "\033[36m"
    white = "\033[37m"


NO_COLOR = False


def supports_color() -> bool:
    return sys.stdout.isatty() and not NO_COLOR and os.environ.get("NO_COLOR") is None


def color(text: str, col: str) -> str:
    return f"{col}{text}{C.reset}" if supports_color() else text


def clear_screen() -> None:
    os.system("clear" if os.name != "nt" else "cls")


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_dotenv() -> None:
    """Tiny .env loader without external dependency."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    try:
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass


def load_settings() -> Dict[str, Any]:
    try:
        if SETTINGS_FILE.exists():
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"model": os.environ.get("HIPO_MODEL", DEFAULT_MODEL), "temperature": 0.7, "max_tokens": 1800}


def save_settings(settings: Dict[str, Any]) -> None:
    ensure_dirs()
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")


def audit(event: str, username: str = "-", detail: str = "") -> None:
    ensure_dirs()
    payload = {
        "time": now(),
        "session": SESSION_ID,
        "event": event,
        "username": username,
        "detail": detail[:500],
    }
    try:
        with AUDIT_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def banner() -> str:
    return r"""
╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║   ██╗  ██╗██╗██████╗  ██████╗      █████╗ ██╗                    ║
║   ██║  ██║██║██╔══██╗██╔═══██╗    ██╔══██╗██║                    ║
║   ███████║██║██████╔╝██║   ██║    ███████║██║                    ║
║   ██╔══██║██║██╔═══╝ ██║   ██║    ██╔══██║██║                    ║
║   ██║  ██║██║██║     ╚██████╔╝    ██║  ██║██║                    ║
║   ╚═╝  ╚═╝╚═╝╚═╝      ╚═════╝     ╚═╝  ╚═╝╚═╝                    ║
║                                                                    ║
║             5.1 PRO  •  TERMINAL AGENT  •  TERMUX READY           ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
""".strip("\n")


def print_banner() -> None:
    print(color(banner(), C.cyan + C.bold))
    print(color(f"  Owner   : {OWNER}", C.magenta))
    print(color(f"  Version : {APP_VERSION} | Session: {SESSION_ID}", C.dim))
    print()


def hash_password(password: str, salt_hex: Optional[str] = None, iterations: int = 240_000) -> Dict[str, Any]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(24)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return {"salt": salt.hex(), "hash": digest.hex(), "iterations": iterations, "algo": "pbkdf2_hmac_sha256"}


def verify_password(password: str, record: Dict[str, Any]) -> bool:
    try:
        calc = hash_password(password, record["salt"], int(record.get("iterations", 240_000)))
        return hmac.compare_digest(calc["hash"], record["hash"])
    except Exception:
        return False


def setup_auth(force: bool = False) -> int:
    ensure_dirs()
    if AUTH_FILE.exists() and not force:
        print(color("Auth sudah dibuat. Pakai `./hipo setup --reset` untuk reset lokal.", C.yellow))
        return 0
    print_banner()
    print(color("Setup keamanan lokal Hipo Ai", C.bold))
    print(color("Credential akan disimpan sebagai hash lokal. Password tidak dikirim ke mana pun.\n", C.dim))
    username = input("Buat username: ").strip()
    if not username:
        print(color("Username tidak boleh kosong.", C.red))
        return 1
    while True:
        p1 = getpass.getpass("Buat password: ")
        p2 = getpass.getpass("Ulangi password: ")
        if len(p1) < 6:
            print(color("Password minimal 6 karakter.", C.yellow))
            continue
        if p1 != p2:
            print(color("Password tidak sama, ulangi.", C.yellow))
            continue
        break
    record = {"username": username, "password": hash_password(p1), "created_at": now(), "owner": OWNER}
    AUTH_FILE.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(AUTH_FILE, 0o600)
    except Exception:
        pass
    audit("auth_setup", username, "local auth created/reset")
    print(color("\nSetup selesai. Jalankan `./hipo` untuk masuk.", C.green))
    return 0


def authenticate() -> str:
    ensure_dirs()
    if not AUTH_FILE.exists():
        print(color("Belum ada akun lokal. Setup dulu.\n", C.yellow))
        code = setup_auth(force=True)
        if code != 0:
            raise SystemExit(code)
    try:
        record = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    except Exception:
        print(color("File auth rusak. Jalankan `./hipo setup --reset`.", C.red))
        raise SystemExit(1)

    expected_user = str(record.get("username", ""))
    print_banner()
    print(color("Login Hipo Ai Security Gate", C.bold))
    for attempt in range(1, 4):
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ")
        ok_user = hmac.compare_digest(username, expected_user)
        ok_pass = verify_password(password, record.get("password", {}))
        if ok_user and ok_pass:
            audit("login_success", username, f"attempt={attempt}")
            print(color("\nAccess granted. Welcome to Hipo Ai 5.1 Pro.\n", C.green))
            return username
        audit("login_failed", username or "-", f"attempt={attempt}")
        print(color(f"Login gagal ({attempt}/3).", C.red))
    print(color("Terlalu banyak percobaan gagal. Keluar.", C.red))
    raise SystemExit(1)


def get_api_key() -> str:
    load_dotenv()
    return os.environ.get("OPENROUTER_API_KEY") or os.environ.get("HIPO_API_KEY") or ""


def mask_key(key: str) -> str:
    if not key:
        return "NOT SET"
    if len(key) <= 12:
        return "***"
    return key[:7] + "..." + key[-6:]


def http_json(url: str, payload: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: int = 45) -> Tuple[int, Dict[str, Any], float]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req_headers = {
        "User-Agent": f"HipoAi/{APP_VERSION} TermuxTerminal",
        "Accept": "application/json",
    }
    if payload is not None:
        req_headers["Content-Type"] = "application/json"
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST" if payload is not None else "GET")
    start = time.perf_counter()
    context = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        elapsed = (time.perf_counter() - start) * 1000
        return resp.getcode(), json.loads(raw or "{}"), elapsed


def ai_complete(messages: List[Dict[str, str]], model: Optional[str] = None, temperature: float = 0.7, max_tokens: int = 1800) -> str:
    key = get_api_key()
    if not key:
        raise RuntimeError("API key belum diset. Set `OPENROUTER_API_KEY` atau `HIPO_API_KEY` dulu.")
    model = model or load_settings().get("model", DEFAULT_MODEL)
    headers = {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": "https://termux.local/hipo-ai-5.1-pro",
        "X-Title": APP_NAME,
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        status, data, elapsed = http_json(OPENROUTER_URL, payload=payload, headers=headers, timeout=75)
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
        raise RuntimeError(f"OpenRouter HTTP {exc.code}: {err_body[:700]}") from exc
    if status < 200 or status >= 300:
        raise RuntimeError(f"OpenRouter HTTP {status}: {data}")
    if "error" in data:
        raise RuntimeError(f"OpenRouter error: {data['error']}")
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("Response AI kosong.")
    content = (choices[0].get("message") or {}).get("content") or choices[0].get("text") or ""
    audit("ai_request", "-", f"model={model} latency_ms={elapsed:.1f}")
    return content.strip()


def system_prompt(username: str) -> str:
    return f"""Kamu adalah {APP_NAME}, AI terminal agent premium yang berjalan di Termux/terminal.
Owner: {OWNER}. User login lokal: {username}.
Tugas: bantu coding, debugging, shell, riset teknis, penjelasan singkat-jelas dalam bahasa Indonesia jika user memakai Indonesia.
Aturan keamanan: jangan meminta password/API key user, jangan mencetak credential, jangan menyarankan pencurian data, dan jangan mengirim credential ke email/layanan luar.
Jika diminta menjalankan command berbahaya, beri warning dan alternatif aman.
"""


def type_print(text: str, delay: float = 0.001) -> None:
    if not sys.stdout.isatty() or len(text) > 3000:
        print(text)
        return
    for ch in text:
        print(ch, end="", flush=True)
        if ch not in "\n \t":
            time.sleep(delay)
    print()


def save_history(role: str, content: str) -> None:
    ensure_dirs()
    try:
        with HISTORY_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"time": now(), "role": role, "content": content}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def offline_reply(prompt: str) -> str:
    return textwrap.dedent(f"""
    Mode offline aktif karena API key belum diset / request gagal.

    Prompt kamu:
    {prompt}

    Agar Hipo Ai menjawab dengan model online, set API key di Termux:
      export OPENROUTER_API_KEY="ISI_KEY_KAMU"

    Atau buat file .env di folder project:
      OPENROUTER_API_KEY=ISI_KEY_KAMU
    """).strip()


def chat_loop(username: str, first_message: str = "") -> int:
    settings = load_settings()
    model = settings.get("model", DEFAULT_MODEL)
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt(username)}]
    print(color(f"Chatbot aktif. Model: {model}", C.green))
    print(color("Ketik /help untuk command chat, /exit untuk keluar.\n", C.dim))

    def handle_user(text: str) -> None:
        nonlocal messages, model, settings
        if text.startswith("/model"):
            parts = text.split(maxsplit=1)
            if len(parts) == 1:
                print(f"Model sekarang: {model}")
            else:
                model = parts[1].strip()
                settings["model"] = model
                save_settings(settings)
                print(color(f"Model diganti ke: {model}", C.green))
            return
        if text == "/clear":
            messages = [{"role": "system", "content": system_prompt(username)}]
            print(color("Memory chat dibersihkan.", C.green))
            return
        if text == "/status":
            print_status(full=False)
            return
        if text.startswith("/agent"):
            task = text[len("/agent"):].strip()
            if not task:
                print("Usage: /agent buat script python scanner file")
                return
            run_agent(username, task)
            return
        if text.startswith("/save"):
            parts = text.split(maxsplit=1)
            out = pathlib.Path(parts[1]) if len(parts) > 1 else pathlib.Path(f"hipo_chat_{int(time.time())}.md")
            md = []
            for m in messages:
                if m["role"] != "system":
                    md.append(f"## {m['role']}\n\n{m['content']}\n")
            out.write_text("\n".join(md), encoding="utf-8")
            print(color(f"Chat tersimpan: {out}", C.green))
            return
        if text == "/help":
            print(textwrap.dedent("""
            Chat commands:
              /help              Tampilkan bantuan
              /model [id]         Lihat/ganti model OpenRouter
              /status             Lihat status device/server Hipo
              /agent <task>       Minta Hipo membuat rencana agent/coding
              /clear              Bersihkan memory chat
              /save [file.md]     Simpan percakapan
              /exit               Keluar chat
            """).strip())
            return
        messages.append({"role": "user", "content": text})
        save_history("user", text)
        try:
            print(color("\nHipo thinking...", C.dim))
            answer = ai_complete(messages, model=model, temperature=float(settings.get("temperature", 0.7)), max_tokens=int(settings.get("max_tokens", 1800)))
        except Exception as exc:
            answer = offline_reply(text) + f"\n\nDetail error: {exc}"
        messages.append({"role": "assistant", "content": answer})
        save_history("assistant", answer)
        print(color("\nHipo Ai:", C.cyan + C.bold))
        type_print(answer)
        print()

    if first_message:
        handle_user(first_message)
        return 0

    while True:
        try:
            user_text = input(color("hipo.chat> ", C.green)).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar chat.")
            return 0
        if not user_text:
            continue
        if user_text in {"/exit", "exit", "quit"}:
            return 0
        handle_user(user_text)


def read_cpu_times() -> Optional[Tuple[int, int]]:
    try:
        first = pathlib.Path("/proc/stat").read_text().splitlines()[0].split()
        vals = [int(x) for x in first[1:]]
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
        total = sum(vals)
        return idle, total
    except Exception:
        return None


def cpu_percent() -> Optional[float]:
    a = read_cpu_times()
    if not a:
        return None
    time.sleep(0.18)
    b = read_cpu_times()
    if not b:
        return None
    idle_delta = b[0] - a[0]
    total_delta = b[1] - a[1]
    if total_delta <= 0:
        return None
    return max(0.0, min(100.0, 100.0 * (1.0 - idle_delta / total_delta)))


def mem_info() -> Dict[str, float]:
    data: Dict[str, int] = {}
    try:
        for line in pathlib.Path("/proc/meminfo").read_text().splitlines():
            key, rest = line.split(":", 1)
            val = int(rest.strip().split()[0])
            data[key] = val
        total = data.get("MemTotal", 0) / 1024
        available = data.get("MemAvailable", data.get("MemFree", 0)) / 1024
        used = max(0.0, total - available)
        pct = (used / total * 100) if total else 0.0
        return {"total_mb": total, "used_mb": used, "available_mb": available, "percent": pct}
    except Exception:
        return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}


def run_cmd(command: List[str], timeout: int = 4) -> str:
    try:
        p = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=timeout)
        return p.stdout.strip()
    except Exception:
        return ""


def get_android_gpu_info() -> Dict[str, str]:
    hardware = run_cmd(["getprop", "ro.hardware"])
    platform_name = run_cmd(["getprop", "ro.board.platform"])
    renderer = run_cmd(["getprop", "ro.hardware.egl"])
    opengles = run_cmd(["getprop", "ro.opengles.version"])
    return {
        "hardware": hardware or "unknown",
        "platform": platform_name or "unknown",
        "renderer": renderer or "not exposed",
        "opengles": opengles or "not exposed",
    }


def termux_battery() -> Dict[str, Any]:
    if not shutil.which("termux-battery-status"):
        return {}
    out = run_cmd(["termux-battery-status"], timeout=5)
    try:
        return json.loads(out) if out else {}
    except Exception:
        return {}


def probe(url: str, timeout: int = 8) -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"HipoAi/{APP_VERSION}"})
        context = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            resp.read(128)
            ms = (time.perf_counter() - start) * 1000
            return {"ok": True, "status": resp.getcode(), "latency_ms": ms, "error": ""}
    except urllib.error.HTTPError as exc:
        ms = (time.perf_counter() - start) * 1000
        return {"ok": 200 <= exc.code < 500, "status": exc.code, "latency_ms": ms, "error": str(exc)}
    except Exception as exc:
        ms = (time.perf_counter() - start) * 1000
        return {"ok": False, "status": None, "latency_ms": ms, "error": f"{type(exc).__name__}: {exc}"}


def bar(percent: float, width: int = 24) -> str:
    percent = max(0.0, min(100.0, percent))
    filled = int(round(width * percent / 100))
    return "█" * filled + "░" * (width - filled)


def fmt_mb(mb: float) -> str:
    if mb >= 1024:
        return f"{mb/1024:.1f} GB"
    return f"{mb:.0f} MB"


def collect_status() -> Dict[str, Any]:
    cpu = cpu_percent()
    mem = mem_info()
    disk = shutil.disk_usage(pathlib.Path.home())
    disk_pct = disk.used / disk.total * 100 if disk.total else 0
    gpu = get_android_gpu_info()
    battery = termux_battery()
    api_key = get_api_key()
    openrouter_probe = probe(MODELS_URL)
    google_probe = probe("https://www.google.com/generate_204")
    return {
        "time": now(),
        "app": APP_NAME,
        "version": APP_VERSION,
        "owner": OWNER,
        "python": platform.python_version(),
        "system": platform.platform(),
        "machine": platform.machine(),
        "cpu_percent": cpu,
        "memory": mem,
        "disk": {"total": disk.total, "used": disk.used, "free": disk.free, "percent": disk_pct},
        "gpu": gpu,
        "battery": battery,
        "api_key_masked": mask_key(api_key),
        "model": load_settings().get("model", DEFAULT_MODEL),
        "openrouter": openrouter_probe,
        "google": google_probe,
        "config_dir": str(CONFIG_DIR),
    }


def print_status(full: bool = True) -> None:
    s = collect_status()
    cpu = s["cpu_percent"]
    mem = s["memory"]
    disk = s["disk"]
    print(color("\n╔═ Hipo System / AI Server Status ═══════════════════════════════╗", C.cyan + C.bold))
    print(f"  Time        : {s['time']}")
    print(f"  Owner       : {s['owner']}")
    print(f"  Model       : {s['model']}")
    print(f"  API Key     : {s['api_key_masked']}")
    print(f"  Python      : {s['python']} | Machine: {s['machine']}")
    cpu_txt = "unknown" if cpu is None else f"{cpu:5.1f}%  {bar(cpu)}"
    print(f"  CPU         : {cpu_txt}")
    print(f"  RAM         : {mem['percent']:5.1f}%  {bar(mem['percent'])}  {fmt_mb(mem['used_mb'])}/{fmt_mb(mem['total_mb'])}")
    print(f"  Disk HOME   : {disk['percent']:5.1f}%  {bar(disk['percent'])}  {disk['used']/1e9:.1f}/{disk['total']/1e9:.1f} GB")
    if full:
        gpu = s["gpu"]
        print(f"  GPU/SoC     : hardware={gpu['hardware']} | platform={gpu['platform']}")
        print(f"  OpenGLES    : {gpu['opengles']} | renderer={gpu['renderer']}")
        bat = s.get("battery") or {}
        if bat:
            print(f"  Battery     : {bat.get('percentage', '?')}% | {bat.get('status', '?')} | temp={bat.get('temperature', '?')}°C")
    op = s["openrouter"]
    gp = s["google"]
    print(f"  Hipo Cloud  : OpenRouter {'ONLINE' if op['ok'] else 'WATCH'} | HTTP {op['status']} | {op['latency_ms']:.0f}ms")
    print(f"  Net Probe   : Google {'OK' if gp['ok'] else 'FAIL'} | HTTP {gp['status']} | {gp['latency_ms']:.0f}ms")
    print(color("╚════════════════════════════════════════════════════════════════╝\n", C.cyan + C.bold))
    if full:
        print(color("Note: CPU/RAM/Disk/GPU adalah status device Termux. Status Hipo Cloud memakai public HTTP probe, bukan akses internal server provider.\n", C.dim))


def about() -> None:
    print_banner()
    print(textwrap.dedent(f"""
    {APP_NAME} adalah terminal AI assistant/agent untuk Termux.

    Fitur utama:
      • AI Chatbot via OpenRouter-compatible API
      • Agent mode untuk rencana coding, debugging, shell, dan file workflow
      • Hipo system status: CPU, RAM, Disk, GPU/SoC, battery, network probe
      • Command center interaktif mirip terminal AI tools
      • Local security gate: username/password hash lokal
      • Audit log lokal tanpa menyimpan password
      • Owner: {OWNER}

    Keamanan:
      • API key tidak ditanam di source code.
      • Password tidak dikirim ke email/API.
      • Gunakan environment variable OPENROUTER_API_KEY atau HIPO_API_KEY.
    """).strip())


def print_api_status() -> None:
    key = get_api_key()
    print(color("\nHipo API Key Status", C.cyan + C.bold))
    print(f"  OPENROUTER/HIPO API KEY : {mask_key(key)}")
    if not key:
        print(color("\nBelum diset. Jalankan di Termux:", C.yellow))
        print('  export OPENROUTER_API_KEY="ISI_KEY_KAMU"')
        print("\nAtau buat file .env di folder project:")
        print("  OPENROUTER_API_KEY=ISI_KEY_KAMU")
    else:
        print(color("  Status                 : READY", C.green))


def fetch_models(limit: int = 20) -> None:
    try:
        status, data, elapsed = http_json(MODELS_URL, timeout=20)
        models = data.get("data") or []
        print(color(f"\nOpenRouter Models ({len(models)} loaded, {elapsed:.0f}ms)", C.cyan + C.bold))
        for m in models[:limit]:
            mid = m.get("id", "unknown")
            ctx = m.get("context_length", "?")
            name = m.get("name", "")
            print(f"  - {mid} | ctx={ctx} | {name}")
    except Exception as exc:
        print(color(f"Gagal mengambil daftar model: {exc}", C.red))


def run_agent(username: str, task: str) -> str:
    cwd = pathlib.Path.cwd()
    files = []
    try:
        for p in list(cwd.iterdir())[:40]:
            files.append(("DIR " if p.is_dir() else "FILE") + " " + p.name)
    except Exception:
        pass
    agent_prompt = f"""Kamu adalah Hipo Agent, coding/shell planner mirip Claude Code tapi aman.
Buat rencana teknis untuk task user. Jika perlu command terminal, tulis command di blok bash.
Jangan menjalankan command, jangan meminta password/API key, jangan membuat exfiltration credential.

Context:
- cwd: {cwd}
- files: {', '.join(files) if files else 'no file context'}
- platform: {platform.platform()}

Task user:
{task}
"""
    messages = [
        {"role": "system", "content": system_prompt(username)},
        {"role": "user", "content": agent_prompt},
    ]
    try:
        answer = ai_complete(messages, max_tokens=2200)
    except Exception as exc:
        answer = textwrap.dedent(f"""
        Hipo Agent offline/error mode.

        Task: {task}

        Rencana awal:
        1. Pahami tujuan dan batasan project.
        2. Cek struktur folder dengan `ls -la`.
        3. Buat/ubah file yang dibutuhkan.
        4. Jalankan test kecil.
        5. Dokumentasikan cara penggunaan.

        Detail error AI: {exc}
        """).strip()
    print(color("\nHipo Agent Plan:", C.cyan + C.bold))
    type_print(answer)
    save_history("agent", f"TASK: {task}\n\n{answer}")
    return answer


def scan_path(path_text: str = ".") -> None:
    path = pathlib.Path(path_text).expanduser()
    if not path.exists():
        print(color("Path tidak ditemukan.", C.red))
        return
    if path.is_file():
        print(f"FILE {path} ({path.stat().st_size} bytes)")
        return
    print(color(f"\nScan: {path.resolve()}", C.cyan + C.bold))
    for p in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))[:120]:
        kind = "DIR " if p.is_dir() else "FILE"
        size = "" if p.is_dir() else f" {p.stat().st_size}B"
        print(f"  {kind}  {p.name}{size}")
    print()


def read_file(path_text: str, limit: int = 16000) -> None:
    path = pathlib.Path(path_text).expanduser()
    if not path.exists() or not path.is_file():
        print(color("File tidak ditemukan.", C.red))
        return
    data = path.read_text(encoding="utf-8", errors="replace")
    print(color(f"\n--- {path} ---", C.cyan + C.bold))
    print(data[:limit])
    if len(data) > limit:
        print(color(f"\n[terpotong: {len(data)-limit} karakter lagi]", C.dim))
    print(color("--- EOF ---\n", C.cyan + C.bold))


def execute_shell(command: str) -> None:
    print(color("Command akan dijalankan di device kamu.", C.yellow))
    print(color(f"$ {command}", C.bold))
    confirm = input("Lanjutkan? ketik yes: ").strip().lower()
    if confirm != "yes":
        print("Dibatalkan.")
        return
    audit("shell_run", "-", command)
    try:
        p = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
        if p.stdout:
            print(color("\n[stdout]", C.green))
            print(p.stdout)
        if p.stderr:
            print(color("\n[stderr]", C.yellow))
            print(p.stderr)
        print(color(f"Exit code: {p.returncode}\n", C.dim))
    except subprocess.TimeoutExpired:
        print(color("Command timeout.", C.red))
    except Exception as exc:
        print(color(f"Error menjalankan command: {exc}", C.red))


def shell_help() -> None:
    print(textwrap.dedent("""
    Hipo Command Center:
      help                      Bantuan command
      chat                      Masuk AI chatbot interaktif
      ask <prompt>              Tanya AI sekali jalan
      agent <task>              Hipo agent planner/coding assistant
      status                    Status CPU/RAM/Disk/Hipo Cloud
      server                    Sama seperti status full
      apikey                    Cek apakah API key sudah diset
      models [limit]            List model OpenRouter
      about                     Tentang Hipo Ai 5.1 Pro
      scan [path]               List file/folder
      read <file>               Baca file teks
      run <command>             Jalankan shell command dengan konfirmasi
      clear                     Bersihkan layar
      exit                      Keluar

    Chat slash commands:
      /help, /model [id], /status, /agent <task>, /clear, /save [file], /exit
    """).strip())


def interactive_shell(username: str) -> int:
    print_banner()
    print(color("Command center ready. Ketik `help` untuk bantuan.\n", C.green))
    while True:
        try:
            raw = input(color("hipo> ", C.green)).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return 0
        if not raw:
            continue
        if raw in {"exit", "quit", "q"}:
            print("Bye.")
            return 0
        if raw == "help":
            shell_help(); continue
        if raw == "clear":
            clear_screen(); print_banner(); continue
        if raw == "chat":
            chat_loop(username); continue
        if raw.startswith("ask "):
            chat_loop(username, raw[4:].strip()); continue
        if raw.startswith("agent "):
            run_agent(username, raw[6:].strip()); continue
        if raw in {"status", "server"}:
            print_status(full=True); continue
        if raw == "about":
            about(); continue
        if raw == "apikey":
            print_api_status(); continue
        if raw.startswith("models"):
            parts = raw.split()
            limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
            fetch_models(limit); continue
        if raw.startswith("scan"):
            parts = shlex.split(raw)
            scan_path(parts[1] if len(parts) > 1 else "."); continue
        if raw.startswith("read "):
            parts = shlex.split(raw)
            if len(parts) < 2:
                print("Usage: read <file>")
            else:
                read_file(parts[1])
            continue
        if raw.startswith("run "):
            execute_shell(raw[4:].strip()); continue
        print(color("Command tidak dikenal. Ketik `help`.", C.yellow))


def cmd_ask(args: argparse.Namespace, username: str) -> int:
    prompt = " ".join(args.prompt).strip()
    if not prompt:
        print("Masukkan prompt.")
        return 1
    return chat_loop(username, prompt)


def cmd_chat(args: argparse.Namespace, username: str) -> int:
    first = " ".join(args.message).strip() if getattr(args, "message", None) else ""
    return chat_loop(username, first)


def cmd_agent(args: argparse.Namespace, username: str) -> int:
    task = " ".join(args.task).strip()
    if not task:
        print("Masukkan task agent.")
        return 1
    run_agent(username, task)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hipo",
        description=f"{APP_NAME} — Termux terminal AI agent. Owner: {OWNER}",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    parser.add_argument("--no-color", action="store_true", help="Matikan warna ANSI")
    sub = parser.add_subparsers(dest="cmd")

    setup = sub.add_parser("setup", help="Setup/reset login lokal")
    setup.add_argument("--reset", action="store_true", help="Reset akun lokal")

    sub.add_parser("about", help="Tentang Hipo Ai")
    sub.add_parser("status", help="Status CPU/RAM/Disk/GPU/Hipo Cloud")
    sub.add_parser("server", help="Alias status")
    sub.add_parser("apikey", help="Cek API key")

    models = sub.add_parser("models", help="List model OpenRouter")
    models.add_argument("--limit", type=int, default=20)

    chat = sub.add_parser("chat", help="Masuk AI chatbot")
    chat.add_argument("message", nargs="*", help="Optional prompt sekali jalan")

    ask = sub.add_parser("ask", help="Tanya AI sekali jalan")
    ask.add_argument("prompt", nargs="+", help="Prompt")

    agent = sub.add_parser("agent", help="Hipo AI agent planner/coding")
    agent.add_argument("task", nargs="+", help="Task agent")

    scan = sub.add_parser("scan", help="Scan file/folder")
    scan.add_argument("path", nargs="?", default=".")

    read = sub.add_parser("read", help="Baca file teks")
    read.add_argument("file")

    run = sub.add_parser("run", help="Jalankan shell command dengan konfirmasi")
    run.add_argument("command", nargs=argparse.REMAINDER)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    global NO_COLOR
    ensure_dirs()
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    NO_COLOR = bool(getattr(args, "no_color", False))

    if args.cmd == "setup":
        return setup_auth(force=bool(args.reset))

    # Help/version handled by argparse without auth. All real actions require local login.
    username = authenticate()

    if args.cmd is None:
        return interactive_shell(username)
    if args.cmd == "about":
        about(); return 0
    if args.cmd in {"status", "server"}:
        print_status(full=True); return 0
    if args.cmd == "apikey":
        print_api_status(); return 0
    if args.cmd == "models":
        fetch_models(limit=args.limit); return 0
    if args.cmd == "chat":
        return cmd_chat(args, username)
    if args.cmd == "ask":
        return cmd_ask(args, username)
    if args.cmd == "agent":
        return cmd_agent(args, username)
    if args.cmd == "scan":
        scan_path(args.path); return 0
    if args.cmd == "read":
        read_file(args.file); return 0
    if args.cmd == "run":
        command = " ".join(args.command).strip()
        if not command:
            print("Usage: hipo run <command>")
            return 1
        execute_shell(command); return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
