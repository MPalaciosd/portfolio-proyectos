#!/usr/bin/env python3
"""
JARVIS - Agente de escritorio activado por doble palmada
"""

import sounddevice as sd
import numpy as np
import time
import subprocess
import threading
import requests
import asyncio
import tempfile
import ctypes
import edge_tts
import pygame
import os
import sys
import win32gui
import win32con
import win32api
import win32com.client
from datetime import datetime

# ─── CONFIGURACIÓN ───────────────────────────────────────────────────────────
CLAP_THRESHOLD = 0.22     # Sensibilidad palmada (0.0-1.0). Sube si hay falsas activaciones.
CLAP_WINDOW    = 1.2      # Ventana máxima entre las dos palmadas (segundos)
CLAP_MIN_GAP   = 0.15     # Gap mínimo entre palmadas (evita doble detección)
COOLDOWN       = 60.0     # Segundos de espera tras activación (evita re-trigger por la música)

DEBUG_AUDIO    = True     # Muestra el nivel de audio al dar palmadas (para calibrar)

TTS_VOICE      = "es-ES-AlvaroNeural"  # Voz masculina natural de Microsoft Neural

SAMPLE_RATE    = 44100
BLOCK_SIZE     = 1024

FFMPEG_PATH    = r"C:\Users\Thiago\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"
CITY           = "Las+Rozas,Spain"
PROMT_FILE     = r"C:\Users\Thiago\Desktop\PROMT.txt"
SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))
MUSIC_FILE     = os.path.join(SCRIPT_DIR, "back_in_black.mp3")
CHROME_PATH    = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

# ─── ESTADO ──────────────────────────────────────────────────────────────────
first_clap_time      = 0.0
last_clap_time       = 0.0
last_trigger_time    = 0.0
state_lock           = threading.Lock()

tts_playing  = threading.Event()  # set() mientras la voz está sonando
speech_ch    = None               # Canal pygame activo del TTS

# ─── MÚSICA ──────────────────────────────────────────────────────────────────
def download_music():
    if os.path.exists(MUSIC_FILE):
        return
    print("[Jarvis] Descargando Back in Black de AC/DC (primera vez)...")
    try:
        import yt_dlp
        opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(SCRIPT_DIR, 'back_in_black.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'ffmpeg_location': FFMPEG_PATH,
            'quiet': True,
            'noplaylist': True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download(['ytsearch1:AC/DC Back in Black official audio'])
        for f in os.listdir(SCRIPT_DIR):
            if f.startswith('back_in_black') and not f.endswith('.mp3') and f != 'back_in_black.mp3':
                os.rename(os.path.join(SCRIPT_DIR, f), MUSIC_FILE)
                break
        print("[Jarvis] Música lista.")
    except Exception as e:
        print(f"[Jarvis] No se pudo descargar la música: {e}")

def play_music():
    if not os.path.exists(MUSIC_FILE):
        print("[Jarvis] Archivo de música no encontrado, omitiendo.")
        return
    try:
        pygame.mixer.music.load(MUSIC_FILE)
        pygame.mixer.music.set_volume(0.30)
        pygame.mixer.music.play(loops=-1)
        print("[Jarvis] Música iniciada. Pulsa cualquier tecla para detenerla.")
    except Exception as e:
        print(f"[Jarvis] Error reproduciendo música: {e}")

def stop_all_audio():
    """Para voz y desvanece la música."""
    # Parar canal de voz
    global speech_ch
    if speech_ch is not None:
        try:
            speech_ch.stop()
        except Exception:
            pass
        speech_ch = None
    tts_playing.clear()
    # Fade out de la música
    try:
        if not pygame.mixer.get_init() or not pygame.mixer.music.get_busy():
            return
        steps = 25
        start_vol = pygame.mixer.music.get_volume()
        for i in range(steps):
            vol = start_vol * (1.0 - (i + 1) / steps)
            pygame.mixer.music.set_volume(max(0.0, vol))
            time.sleep(2.5 / steps)
        pygame.mixer.music.stop()
        pygame.mixer.music.set_volume(0.30)
        print("[Jarvis] Audio detenido.")
    except Exception as e:
        print(f"[Jarvis] Error deteniendo audio: {e}")

def start_music_stop_listener():
    """Espera una tecla física y para música + voz."""
    def _listener():
        user32 = ctypes.windll.user32
        try:
            # Esperar a que toda la actividad de arranque se estabilice
            time.sleep(12)
            # Limpiar bits acumulados durante el arranque
            for vk in range(8, 256):
                user32.GetAsyncKeyState(vk)
            # Detectar pulsación física real
            while True:
                music_active = pygame.mixer.get_init() and pygame.mixer.music.get_busy()
                if not music_active:
                    return
                for vk in range(8, 256):
                    if user32.GetAsyncKeyState(vk) & 0x0001:
                        stop_all_audio()
                        return
                time.sleep(0.05)
        except Exception as e:
            print(f"[Jarvis] Listener de teclado error: {e}")
    threading.Thread(target=_listener, daemon=True).start()

# ─── CLIMA ───────────────────────────────────────────────────────────────────
def get_weather():
    try:
        r = requests.get(f"https://wttr.in/{CITY}?format=j1&lang=es", timeout=6)
        r.raise_for_status()
        data = r.json()
        current = data["current_condition"][0]
        temp = current["temp_C"]
        try:
            desc = current["lang_es"][0]["value"].lower()
        except (KeyError, IndexError):
            desc = current["weatherDesc"][0]["value"].lower()
        return temp, desc
    except Exception as e:
        print(f"[Jarvis] Error obteniendo clima: {e}")
        # Fallback: Open-Meteo (no requiere API key)
        try:
            r2 = requests.get(
                "https://api.open-meteo.com/v1/forecast"
                "?latitude=40.49&longitude=-3.87&current_weather=true",
                timeout=6
            )
            r2.raise_for_status()
            d2 = r2.json()
            temp = str(int(d2["current_weather"]["temperature"]))
            return temp, "parcialmente nublado"
        except Exception:
            return "?", "desconocida"

# ─── VOZ ─────────────────────────────────────────────────────────────────────
def speak(text):
    global speech_ch
    tmp_mp3 = os.path.join(tempfile.gettempdir(), "jarvis_tts.mp3")
    tmp_wav = os.path.join(tempfile.gettempdir(), "jarvis_tts.wav")
    try:
        # Generar TTS como MP3
        asyncio.run(edge_tts.Communicate(text, TTS_VOICE).save(tmp_mp3))

        # Convertir a WAV con ffmpeg (pygame.mixer.Sound es más fiable con WAV)
        ffmpeg_exe = os.path.join(FFMPEG_PATH, "ffmpeg.exe")
        audio_file = tmp_mp3
        if os.path.exists(ffmpeg_exe):
            result = subprocess.run(
                [ffmpeg_exe, "-y", "-i", tmp_mp3, tmp_wav],
                capture_output=True
            )
            if result.returncode == 0 and os.path.exists(tmp_wav):
                audio_file = tmp_wav
            else:
                print(f"[Jarvis] ffmpeg error: {result.stderr.decode(errors='replace')[:200]}")

        # Bajar música mientras habla (ducking)
        music_was_playing = pygame.mixer.get_init() and pygame.mixer.music.get_busy()
        if music_was_playing:
            pygame.mixer.music.set_volume(0.15)

        sound = pygame.mixer.Sound(audio_file)
        sound.set_volume(1.0)
        ch = pygame.mixer.find_channel(True)
        speech_ch = ch
        tts_playing.set()
        ch.play(sound)
        while ch.get_busy():
            time.sleep(0.05)
        tts_playing.clear()
        speech_ch = None

        # Restaurar volumen de música
        if music_was_playing and pygame.mixer.get_init() and pygame.mixer.music.get_busy():
            pygame.mixer.music.set_volume(0.30)

    except Exception as e:
        tts_playing.clear()
        speech_ch = None
        print(f"[Jarvis] Error TTS: {e}")
    finally:
        for f in (tmp_mp3, tmp_wav):
            try:
                if os.path.exists(f):
                    os.unlink(f)
            except Exception:
                pass

def build_greeting():
    now = datetime.now()
    h, m = now.hour, now.minute
    months   = ["enero","febrero","marzo","abril","mayo","junio",
                "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    days_es  = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]
    weekday  = days_es[now.weekday()]
    month    = months[now.month - 1]

    if h < 12:
        saludo = "Buenos días"
    elif h < 20:
        saludo = "Buenas tardes"
    else:
        saludo = "Buenas noches"

    if m == 0:
        time_str = f"las {h} en punto"
    elif m == 1:
        time_str = f"la una y un minuto" if h == 1 else f"las {h} y un minuto"
    else:
        time_str = f"las {h} y {m} minutos"

    temp, desc = get_weather()

    return (
        f"{saludo} Palace. Son {time_str} del {weekday} {now.day} de {month}. "
        f"La temperatura en Las Rozas es de {temp} grados y está {desc}."
    )

# ─── VENTANAS ─────────────────────────────────────────────────────────────────
def get_monitors():
    """Devuelve (primary, secondary) como (left, top, right, bottom) o None."""
    primary   = None
    secondary = None
    for hMon, _hDC, _rect in win32api.EnumDisplayMonitors():
        info = win32api.GetMonitorInfo(hMon)
        if info['Flags'] & 1:
            primary = info['Monitor']
        else:
            secondary = info['Monitor']
    return primary, secondary

def find_hwnd(title_fragment, timeout=10):
    """Espera hasta 'timeout' segundos a que aparezca una ventana con ese título."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        found = []
        def cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                if title_fragment.lower() in win32gui.GetWindowText(hwnd).lower():
                    found.append(hwnd)
        win32gui.EnumWindows(cb, None)
        if found:
            return found[0]
        time.sleep(0.3)
    return None

def force_foreground(hwnd):
    """Fuerza el foco a una ventana usando AttachThreadInput."""
    try:
        user32 = ctypes.windll.user32
        fg = user32.GetForegroundWindow()
        if fg == hwnd:
            return
        fg_tid = user32.GetWindowThreadProcessId(fg, None)
        my_tid = ctypes.windll.kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(fg_tid, my_tid, True)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.AttachThreadInput(fg_tid, my_tid, False)
    except Exception as e:
        print(f"[Jarvis] Error force_foreground: {e}")

def move_window(hwnd, x, y, w, h):
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.MoveWindow(hwnd, x, y, w, h, True)
    except Exception as e:
        print(f"[Jarvis] No se pudo mover ventana: {e}")

def open_and_arrange():
    # Crear PROMT.txt si no existe
    if not os.path.exists(PROMT_FILE):
        try:
            open(PROMT_FILE, 'w', encoding='utf-8').close()
        except Exception as e:
            print(f"[Jarvis] No se pudo crear PROMT.txt: {e}")

    primary, secondary = get_monitors()

    # 1) Terminal — claude se lanza después
    subprocess.Popen(
        ["cmd.exe", "/K", "title JARVIS_TERMINAL"],
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )

    if secondary is not None:
        # DOS PANTALLAS: Chrome izquierda pantalla 2, Notepad derecha pantalla 2
        if os.path.exists(CHROME_PATH):
            subprocess.Popen([CHROME_PATH])
        else:
            subprocess.Popen(["start", "chrome"], shell=True)

    # Notepad con PROMT.txt (siempre)
    subprocess.Popen(["notepad.exe", PROMT_FILE])

    def arrange():
        primary, secondary = get_monitors()

        # Buscar terminal antes de que nada cambie el título
        time.sleep(0.8)
        term_hwnd = find_hwnd("JARVIS_TERMINAL", timeout=5)

        # Lanzar claude en la terminal
        if term_hwnd:
            def launch_and_confirm():
                time.sleep(0.5)
                force_foreground(term_hwnd)
                time.sleep(0.3)
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.AppActivate("JARVIS_TERMINAL")
                time.sleep(0.3)
                shell.SendKeys("claude{ENTER}", 0)
                print("[Jarvis] Claude lanzado en terminal.")
            threading.Thread(target=launch_and_confirm, daemon=True).start()

        # Esperar a que las ventanas abran
        time.sleep(2.5)

        if secondary is None:
            # UNA SOLA PANTALLA: Claude izquierda, Notepad derecha
            pl, pt, pr, pb = primary
            pw = pr - pl
            ph = pb - pt
            half = pw // 2

            if term_hwnd:
                move_window(term_hwnd, pl, pt, half, ph)
                print("[Jarvis] Terminal (Claude) posicionado a la izquierda.")

            notepad_hwnd = (find_hwnd("PROMT") or
                            find_hwnd("Bloc de notas") or
                            find_hwnd("Notepad"))
            if notepad_hwnd:
                move_window(notepad_hwnd, pl + half, pt, half, ph)
                print("[Jarvis] Notepad posicionado a la derecha.")
        else:
            # DOS PANTALLAS: Terminal maximizada en pantalla 1
            if term_hwnd:
                win32gui.ShowWindow(term_hwnd, win32con.SW_MAXIMIZE)
                force_foreground(term_hwnd)
                print("[Jarvis] Terminal al frente en pantalla 1.")

            sl, st, sr, sb = secondary
            sw = sr - sl
            sh = sb - st
            half = sw // 2

            # Chrome a la IZQUIERDA del segundo monitor
            chrome_hwnd = find_hwnd("Chrome")
            if chrome_hwnd:
                move_window(chrome_hwnd, sl, st, half, sh)
                print("[Jarvis] Chrome posicionado en pantalla 2 (izquierda).")

            # Notepad a la DERECHA del segundo monitor
            notepad_hwnd = (find_hwnd("PROMT") or
                            find_hwnd("Bloc de notas") or
                            find_hwnd("Notepad"))
            if notepad_hwnd:
                move_window(notepad_hwnd, sl + half, st, half, sh)
                print("[Jarvis] Notepad posicionado en pantalla 2 (derecha).")

    threading.Thread(target=arrange, daemon=True).start()

# ─── ACTIVACIÓN ──────────────────────────────────────────────────────────────
def activate_jarvis():
    print("[Jarvis] ¡Activado!")
    threading.Thread(target=play_music, daemon=True).start()
    start_music_stop_listener()
    threading.Thread(target=open_and_arrange, daemon=True).start()
    time.sleep(1.8)
    msg = build_greeting()
    print(f"[Jarvis] {msg}")
    speak(msg)

# ─── DETECCIÓN DE PALMADAS ───────────────────────────────────────────────────
def audio_callback(indata, frames, time_info, status):
    global first_clap_time, last_clap_time, last_trigger_time

    peak = float(np.max(np.abs(indata)))
    now  = time.time()

    if DEBUG_AUDIO and peak > 0.05:
        print(f"[DEBUG] peak={peak:.3f}  (umbral={CLAP_THRESHOLD})", flush=True)

    if peak < CLAP_THRESHOLD:
        return

    with state_lock:
        if now - last_clap_time < CLAP_MIN_GAP:
            return

        last_clap_time = now

        if first_clap_time == 0 or (now - first_clap_time) > CLAP_WINDOW:
            first_clap_time = now
            print(f"[Jarvis] Palmada 1... (peak={peak:.2f})")
        else:
            if now - last_trigger_time > COOLDOWN:
                last_trigger_time = now
                first_clap_time   = 0
                print(f"[Jarvis] ¡Doble palmada! (peak={peak:.2f})")
                threading.Thread(target=activate_jarvis, daemon=True).start()

# ─── MAIN ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    print("===================================")
    print("         J A R V I S              ")
    print("   Esperando doble palmada...     ")
    print("===================================")
    print(f"  Umbral de palmada: {CLAP_THRESHOLD}")
    print(f"  Ventana:           {CLAP_WINDOW}s")
    print()

    threading.Thread(target=download_music, daemon=True).start()

    pygame.init()
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    pygame.mixer.set_num_channels(8)

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            dtype='float32',
            channels=1,
            callback=audio_callback
        ):
            print("[Jarvis] Micrófono activo. Ctrl+C para salir.\n")
            while True:
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[Jarvis] Apagado.")
    except Exception as e:
        print(f"[Jarvis] Error crítico: {e}")
        sys.exit(1)
