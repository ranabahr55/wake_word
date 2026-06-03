#!/usr/bin/env python3
"""Hello Car — Voice Assistant Demo
Wake words and voice threshold are configurable and persist in config.json.
SPACE = manual wake  |  ESC = quit
"""

# ── Suppress ALSA noise before any audio import ───────────────────────────────
import ctypes, os
_EHANDLER = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int,
                              ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p)
_noop = _EHANDLER(lambda *_: None)
try:
    ctypes.cdll.LoadLibrary("libasound.so.2").snd_lib_error_set_handler(_noop)
except Exception:
    pass
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
import math, threading, queue, time, sys, json, asyncio, tempfile, audioop
import speech_recognition as sr
import edge_tts

# ── Config ────────────────────────────────────────────────────────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_DIR, "config.json")
DEFAULTS = {
    "wake_phrases":      ["hello car", "hey car"],
    "energy_threshold":  None,
    "voice":             "en-US-GuyNeural",
}

def load_cfg():
    try:
        with open(CONFIG_PATH) as f:
            return {**DEFAULTS, **json.load(f)}
    except Exception:
        return dict(DEFAULTS)

def save_cfg(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)

# ── Colors ────────────────────────────────────────────────────────────────────
BG_TOP     = (5,  10, 28)
BG_BOT     = (8,  20, 52)
ACCENT     = (58, 143, 255)
ACCENT_DK  = (20,  80, 200)
ACCENT_LT  = (120, 200, 255)
WHITE      = (255, 255, 255)
DIM        = (120, 160, 210)
W, H       = 860, 640

# ── States ────────────────────────────────────────────────────────────────────
SLEEPING  = "sleeping"
LISTENING = "listening"
SPEAKING  = "speaking"
TRAINING  = "training"

# ── Responses ─────────────────────────────────────────────────────────────────
_RESP = [
    (["navigate","direction","take me","where is","go to"],
     "Sure! Setting up navigation. Where would you like to go?"),
    (["music","play","song","radio","playlist"],
     "Playing your music now. Enjoy the ride!"),
    (["weather","rain","sunny"],
     "It's a perfect day to drive. Pulling up the weather for you."),
    (["call","phone","dial","ring"],
     "Connecting your call right now."),
    (["home","house"],
     "Starting navigation home. About fifteen minutes away."),
    (["gas","fuel","petrol"],
     "You have enough fuel for around eighty miles. Want me to find a station?"),
    (["temp","heat","cool","climate","ac","air"],
     "Setting cabin temperature to 72 degrees."),
    (["park","parking"],
     "Looking for nearby parking spots."),
    (["time","clock","what time"],
     f"It's {time.strftime('%I:%M %p')}."),
    (["volume","louder","quieter"],
     "Adjusting the volume for you."),
]

def pick_response(text: str) -> str:
    t = text.lower()
    for kws, reply in _RESP:
        if any(k in t for k in kws):
            return reply
    return "Hello! I'm your Car Assistant. How can I help you today?"


# ── TTS Worker (edge-tts neural voice) ───────────────────────────────────────
class TTSWorker(threading.Thread):
    def __init__(self, voice: str):
        super().__init__(daemon=True)
        self.voice = voice
        self._q: queue.Queue = queue.Queue()

    def say(self, text: str, done_cb=None):
        self._q.put((text, done_cb))

    def run(self):
        while True:
            text, cb = self._q.get()
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                fname = f.name
            try:
                asyncio.run(self._gen(text, fname))
                pygame.mixer.music.load(fname)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.04)
            except Exception as e:
                print(f"[TTS] {e}")
            finally:
                pygame.mixer.music.stop()
                try:
                    os.unlink(fname)
                except Exception:
                    pass
                if cb:
                    cb()

    async def _gen(self, text: str, fname: str):
        comm = edge_tts.Communicate(text, self.voice)
        await comm.save(fname)


# ── Wave renderer (Siri-style) ────────────────────────────────────────────────
class WaveRenderer:
    _WAVES = [
        {"f": 0.022, "a": 44, "s": 0.058, "p": 0.0, "rgb": (58,  143, 255), "al": 200},
        {"f": 0.015, "a": 32, "s": 0.036, "p": 1.8, "rgb": (100, 200, 255), "al": 170},
        {"f": 0.034, "a": 25, "s": 0.074, "p": 3.5, "rgb": (20,   80, 200), "al": 185},
        {"f": 0.019, "a": 36, "s": 0.049, "p": 5.1, "rgb": (80,  160, 255), "al": 160},
        {"f": 0.028, "a": 19, "s": 0.065, "p": 2.4, "rgb": (140, 220, 255), "al": 140},
    ]

    def __init__(self):
        self.amp    = 0.0
        self.target = 0.0

    def set_active(self, on: bool):
        self.target = 1.0 if on else 0.0

    def update(self):
        for w in self._WAVES:
            w["p"] += w["s"]
        self.amp += (self.target - self.amp) * 0.07

    def draw(self, surf, cx: int, cy: int, width=460, height=90):
        if self.amp < 0.01:
            return
        ws = pygame.Surface((width, height), pygame.SRCALPHA)
        for wv in self._WAVES:
            pts = []
            for px in range(0, width, 2):
                t   = (px / width - 0.5) * 4.2
                env = math.exp(-t * t)
                py  = height // 2 + math.sin(px * wv["f"] + wv["p"]) * wv["a"] * self.amp * env
                pts.append((px, int(py)))
            if len(pts) > 1:
                r, g, b = wv["rgb"]
                a = int(wv["al"] * self.amp)
                pygame.draw.aalines(ws, (r, g, b, a), False, pts)
                ghost = [(p[0], p[1] - 1) for p in pts]
                pygame.draw.aalines(ws, (r, g, b, a // 3), False, ghost)
        surf.blit(ws, (cx - width // 2, cy - height // 2))


# ── RC car drawing ────────────────────────────────────────────────────────────
def draw_rc_car(surf, cx: int, cy: int):
    """Side-view RC buggy centered at (cx, cy)."""
    # Body
    body = pygame.Rect(cx - 40, cy - 10, 80, 26)
    pygame.draw.rect(surf, (18, 70, 160), body, border_radius=6)
    pygame.draw.rect(surf, (50, 130, 230), body, 1, border_radius=6)

    # Cab (trapezoid → polygon)
    cab = [
        (cx - 16, cy - 10),  # bottom-left
        (cx - 4,  cy - 30),  # top-left
        (cx + 16, cy - 30),  # top-right
        (cx + 23, cy - 10),  # bottom-right
    ]
    pygame.draw.polygon(surf, (15, 58, 140), cab)
    pygame.draw.polygon(surf, (40, 100, 200), cab, 1)

    # Windshield (lighter tint, drawn on temp surface for alpha)
    ws = pygame.Surface((W, H), pygame.SRCALPHA)
    wind = [
        (cx - 10, cy - 12),
        (cx -  1, cy - 27),
        (cx + 12, cy - 27),
        (cx + 19, cy - 12),
    ]
    pygame.draw.polygon(ws, (80, 170, 255, 110), wind)
    surf.blit(ws, (0, 0))

    # Spoiler post + wing (rear = left side)
    pygame.draw.rect(surf, (30, 90, 180), pygame.Rect(cx - 42, cy - 18, 5, 12))
    pygame.draw.rect(surf, (40, 110, 200), pygame.Rect(cx - 50, cy - 22, 26, 5), border_radius=2)

    # Front splitter
    pygame.draw.rect(surf, (12, 45, 110), pygame.Rect(cx + 38, cy - 2, 9, 15), border_radius=3)

    # Wheels (chunky off-road style)
    for wx, label in [(cx + 23, "f"), (cx - 25, "r")]:
        wy, wr = cy + 18, 17
        pygame.draw.circle(surf, (14, 14, 22), (wx, wy), wr)          # tire
        pygame.draw.circle(surf, (28, 28, 48), (wx, wy), wr, 2)       # tire outline
        pygame.draw.circle(surf, (38, 108, 218), (wx, wy), 10)        # rim
        pygame.draw.circle(surf, (60, 150, 255), (wx, wy), 5)         # hub
        # Tread lines
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            x1  = int(wx + 11 * math.cos(rad))
            y1  = int(wy + 11 * math.sin(rad))
            x2  = int(wx + 16 * math.cos(rad))
            y2  = int(wy + 16 * math.sin(rad))
            pygame.draw.line(surf, (22, 22, 38), (x1, y1), (x2, y2), 1)
        # Wheel arch cutout shadow
        arch = pygame.Surface((42, 42), pygame.SRCALPHA)
        pygame.draw.arc(arch, (8, 30, 80, 160), (1, 1, 40, 40),
                        math.radians(15), math.radians(165), 3)
        surf.blit(arch, (wx - 21, wy - 21))

    # Headlight
    pygame.draw.rect(surf, (255, 245, 180), pygame.Rect(cx + 34, cy - 7, 6, 5), border_radius=1)
    # Taillight
    pygame.draw.rect(surf, (255, 55, 55), pygame.Rect(cx - 42, cy - 7, 5, 5), border_radius=1)

    # Antenna
    pygame.draw.line(surf, (100, 165, 255), (cx - 14, cy - 10), (cx - 20, cy - 50), 2)
    pygame.draw.circle(surf, (160, 220, 255), (cx - 20, cy - 50), 3)

    # Roll-cage bar (optional detail)
    pygame.draw.line(surf, (30, 90, 180), (cx - 14, cy - 30), (cx + 14, cy - 30), 2)


# ── Main app ──────────────────────────────────────────────────────────────────
class CarAssistant:

    # ── Init ──────────────────────────────────────────────────────────────────
    def __init__(self):
        pygame.init()
        pygame.mixer.pre_init(44100, -16, 2, 1024)
        pygame.mixer.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("Hello Car — Voice Assistant")
        self.clock  = pygame.time.Clock()
        self.wave   = WaveRenderer()

        # Fonts
        self.f_sm    = pygame.font.SysFont("Arial", 11)
        self.f_title = pygame.font.SysFont("Arial", 50, bold=False)
        self.f_body  = pygame.font.SysFont("Arial", 17)
        self.f_small = pygame.font.SysFont("Arial", 13)

        # State
        self._lock         = threading.Lock()
        self.state         = SLEEPING
        self.status_text   = 'Say a wake phrase to activate'
        self.response_text = ""
        self.transcript    = ""
        self.await_command = False
        self.orb_pulse     = 0.0

        # Training
        self.train_msg  = ""
        self.train_prog = (0, 3)   # (done, total)

        # Phrases overlay
        self.phrases_open    = False
        self.phrases_input   = ""
        self._del_rects: list[tuple[pygame.Rect, int]] = []  # (rect, index)
        self._done_rect      = pygame.Rect(0, 0, 0, 0)
        self._add_rect       = pygame.Rect(0, 0, 0, 0)

        # Button rects (set during draw)
        self.btn_train   = pygame.Rect(0, 0, 0, 0)
        self.btn_phrases = pygame.Rect(0, 0, 0, 0)

        # Config / phrases
        self.cfg          = load_cfg()
        self.wake_phrases = list(self.cfg["wake_phrases"])

        # Stars
        import random; random.seed(7)
        self.stars = [(random.randint(0, W), random.randint(0, H),
                       random.uniform(0.4, 1.8), random.uniform(0, math.pi*2),
                       random.uniform(0.008, 0.025)) for _ in range(200)]

        # TTS
        self.tts = TTSWorker(voice=self.cfg.get("voice", "en-US-GuyNeural"))
        self.tts.start()

        # SR
        self.recognizer   = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = False
        self._sr_pause    = threading.Event()   # set = SR loop blocked
        self._cmd_timer: threading.Timer | None = None
        self._sr_thread   = threading.Thread(target=self._sr_loop, daemon=True)
        self._sr_thread.start()

        self.running = True

    # ── State helpers ─────────────────────────────────────────────────────────
    def _set(self, state=None, status=None, response=None, transcript=None,
             train_msg=None, train_prog=None):
        with self._lock:
            if state     is not None: self.state         = state
            if status    is not None: self.status_text   = status
            if response  is not None: self.response_text = response
            if transcript is not None: self.transcript   = transcript
            if train_msg  is not None: self.train_msg    = train_msg
            if train_prog is not None: self.train_prog   = train_prog
        if state is not None:
            self.wave.set_active(state in (LISTENING, SPEAKING))

    def _go_sleep(self):
        self.await_command = False
        if self._cmd_timer:
            self._cmd_timer.cancel()
        self._set(state=SLEEPING,
                  status='Say a wake phrase to activate',
                  response="", transcript="", train_msg="")

    # ── Wake word / command ───────────────────────────────────────────────────
    def _trigger_wake(self):
        if self.state == TRAINING:
            return
        self.await_command = True
        self._set(state=LISTENING, status="Hello! What can I do for you?",
                  response="", transcript="")
        self.tts.say("Hello! What can I do for you?",
                     lambda: self._set(status="I'm listening…"))
        self._cmd_timer = threading.Timer(12, self._timeout_command)
        self._cmd_timer.start()

    def _handle_command(self, text: str):
        if self._cmd_timer:
            self._cmd_timer.cancel()
        self.await_command = False
        resp = pick_response(text)
        self._set(state=SPEAKING, status="Responding…",
                  response=resp, transcript=f'You said: "{text}"')
        self.tts.say(resp, lambda: threading.Timer(2.5, self._go_sleep).start())

    def _timeout_command(self):
        self.tts.say(
            "I didn't catch that. Say a wake phrase whenever you need me.",
            self._go_sleep)

    # ── Training ──────────────────────────────────────────────────────────────
    def _start_training(self):
        if self.state != SLEEPING:
            return
        threading.Thread(target=self._training_loop, daemon=True).start()

    def _training_loop(self):
        STEPS = 10
        self._sr_pause.set()   # block main SR loop
        self._set(state=TRAINING, train_msg="Stay quiet — listening to the room…",
                  train_prog=(0, STEPS))
        time.sleep(0.4)

        try:
            with sr.Microphone() as src:
                self.recognizer.adjust_for_ambient_noise(src, duration=2.0)
            noise_thresh = self.recognizer.energy_threshold
        except Exception as e:
            self._set(train_msg=f"Mic error: {e}")
            time.sleep(2)
            self._sr_pause.clear()
            self._go_sleep()
            return

        samples = []
        i = 0
        while i < STEPS:
            self._set(train_msg=f"Say a wake phrase clearly  ({i+1} / {STEPS})",
                      train_prog=(i, STEPS))
            time.sleep(0.4)
            try:
                # Listen with a very low threshold so it catches even soft voices
                self.recognizer.energy_threshold = noise_thresh * 0.6
                with sr.Microphone() as src:
                    audio = self.recognizer.listen(src, timeout=8, phrase_time_limit=5)
                rms = audioop.rms(audio.get_raw_data(), audio.sample_width)
                samples.append(rms)
                self._set(train_msg=f"Got it!  ✓  ({i+1} / {STEPS})",
                          train_prog=(i+1, STEPS))
                time.sleep(0.9)
                i += 1
            except sr.WaitTimeoutError:
                self._set(train_msg=f"Didn't hear you — try again  ({i+1} / {STEPS})")
                time.sleep(0.8)

        if samples:
            avg_voice = sum(samples) / len(samples)
            # Set threshold between noise floor and typical voice level
            new_thresh = int(noise_thresh + (avg_voice - noise_thresh) * 0.28)
            new_thresh = max(new_thresh, int(noise_thresh * 1.25), 300)
            self.recognizer.energy_threshold = new_thresh
            self.cfg["energy_threshold"] = new_thresh
            save_cfg(self.cfg)
            self._set(train_msg=f"Training complete!  Threshold → {new_thresh}",
                      train_prog=(STEPS, STEPS))
        else:
            self._set(train_msg="Training failed — please try again.")

        time.sleep(2.8)
        self._sr_pause.clear()
        self._go_sleep()

    # ── Phrases modal ─────────────────────────────────────────────────────────
    def _phrases_key(self, event):
        if event.key == pygame.K_ESCAPE:
            self.phrases_open = False
            self.phrases_input = ""
        elif event.key == pygame.K_RETURN:
            self._add_phrase()
        elif event.key == pygame.K_BACKSPACE:
            self.phrases_input = self.phrases_input[:-1]
        elif event.unicode and event.unicode.isprintable():
            if len(self.phrases_input) < 40:
                self.phrases_input += event.unicode

    def _add_phrase(self):
        p = self.phrases_input.strip().lower()
        if p and p not in self.wake_phrases:
            self.wake_phrases.append(p)
            self.cfg["wake_phrases"] = self.wake_phrases
            save_cfg(self.cfg)
        self.phrases_input = ""

    def _phrases_click(self, pos):
        for rect, idx in self._del_rects:
            if rect.collidepoint(pos) and len(self.wake_phrases) > 1:
                self.wake_phrases.pop(idx)
                self.cfg["wake_phrases"] = self.wake_phrases
                save_cfg(self.cfg)
                return
        if self._add_rect.collidepoint(pos):
            self._add_phrase()
            return
        if self._done_rect.collidepoint(pos):
            self.phrases_open = False
            self.phrases_input = ""

    # ── SR loop ───────────────────────────────────────────────────────────────
    def _sr_loop(self):
        print("[SR] Calibrating microphone…")
        try:
            with sr.Microphone() as src:
                self.recognizer.adjust_for_ambient_noise(src, duration=1.5)
            # Apply saved threshold if one was trained
            saved = self.cfg.get("energy_threshold")
            if saved:
                self.recognizer.energy_threshold = saved
            else:
                self.recognizer.energy_threshold = max(
                    self.recognizer.energy_threshold * 1.3, 400)
            print(f"[SR] Ready  (threshold={self.recognizer.energy_threshold:.0f})")
        except Exception as e:
            print(f"[SR] Mic init failed: {e}")
            return

        while self.running:
            # Block when training owns the mic
            while self._sr_pause.is_set() and self.running:
                time.sleep(0.15)
            if not self.running:
                break

            try:
                with sr.Microphone() as src:
                    audio = self.recognizer.listen(src, timeout=5, phrase_time_limit=7)

                text = self.recognizer.recognize_google(audio).lower().strip()
                if len(text.split()) < 2:   # ignore single-word noise bursts
                    continue

                # Discard audio captured during a training window (race condition)
                if self._sr_pause.is_set() or self.state == TRAINING:
                    continue

                print(f"[Heard] {text}")

                if not self.await_command:
                    with self._lock:
                        self.transcript = f'"{text}"'
                    if any(p in text for p in self.wake_phrases):
                        self._trigger_wake()
                    else:
                        threading.Timer(2, lambda: self._set(transcript="")).start()
                else:
                    self._handle_command(text)

            except sr.WaitTimeoutError:
                pass
            except sr.UnknownValueError:
                pass
            except sr.RequestError as e:
                print(f"[SR] API error: {e} — retrying in 3 s")
                time.sleep(3)
            except Exception as e:
                print(f"[SR] Unexpected: {e}")
                time.sleep(1)

    # ── Drawing ───────────────────────────────────────────────────────────────
    def _draw_gradient(self):
        for y in range(H):
            t = y / H
            r = int(BG_TOP[0] + t * (BG_BOT[0] - BG_TOP[0]))
            g = int(BG_TOP[1] + t * (BG_BOT[1] - BG_TOP[1]))
            b = int(BG_TOP[2] + t * (BG_BOT[2] - BG_TOP[2]))
            pygame.draw.line(self.screen, (r, g, b), (0, y), (W, y))

    def _draw_stars(self):
        new = []
        for x, y, r, ph, spd in self.stars:
            ph += spd
            a = int(255 * max(0, 0.25 + 0.45 * math.sin(ph)))
            s = pygame.Surface((int(r*2)+2, int(r*2)+2), pygame.SRCALPHA)
            pygame.draw.circle(s, (140, 190, 255, a), (int(r)+1, int(r)+1), max(1, int(r)))
            self.screen.blit(s, (x - r, y - r))
            new.append((x, y, r, ph, spd))
        self.stars = new

    def _draw_orb(self, cx, cy, r):
        listening = self.state in (LISTENING, SPEAKING, TRAINING)
        spd = 0.06 if listening else 0.022
        self.orb_pulse += spd

        # Rings
        for i in range(3):
            ph = (self.orb_pulse + i * 0.55) % (math.pi * 2)
            a  = int((0.35 + 0.55 * abs(math.sin(ph))) * 255) if listening \
                 else int((0.08 + 0.22 * math.sin(ph)**2) * 255)
            rr = r + 14 + i * 17 + int(5 * math.sin(ph))
            rs = pygame.Surface((rr*2+4, rr*2+4), pygame.SRCALPHA)
            col = (*ACCENT_LT, a) if listening else (*ACCENT, a)
            pygame.draw.circle(rs, col, (rr+2, rr+2), rr, 1)
            self.screen.blit(rs, (cx - rr - 2, cy - rr - 2))

        # Glow
        gr = r + (38 if listening else 26)
        gs = pygame.Surface((gr*2, gr*2), pygame.SRCALPHA)
        for k in range(gr, r, -1):
            ga = int(60 * (1 - (k-r)/(gr-r)) * (1.8 if listening else 1.0))
            pygame.draw.circle(gs, (*ACCENT, ga), (gr, gr), k)
        self.screen.blit(gs, (cx - gr, cy - gr))

        # Body
        pygame.draw.circle(self.screen, (8, 22, 70), (cx, cy), r)
        hl = pygame.Surface((r, r), pygame.SRCALPHA)
        pygame.draw.circle(hl, (40, 90, 185, 100), (r//3, r//3), r//3)
        self.screen.blit(hl, (cx - r//2, cy - r//2))
        border_col = ACCENT_LT if listening else (60, 110, 210)
        pygame.draw.circle(self.screen, border_col, (cx, cy), r, 2)

        # RC car logo
        draw_rc_car(self.screen, cx - 2, cy - 4)

    def _centered(self, font, text, color, y, alpha=255):
        s = font.render(text, True, color)
        if alpha < 255:
            s.set_alpha(alpha)
        self.screen.blit(s, s.get_rect(center=(W // 2, y)))

    def _draw_response_box(self, text, y):
        if not text:
            return
        words = text.split()
        lines, line = [], []
        for w in words:
            test = " ".join(line + [w])
            if self.f_body.size(test)[0] > 540:
                lines.append(" ".join(line)); line = [w]
            else:
                line.append(w)
        if line:
            lines.append(" ".join(line))

        pad, lh = 16, 26
        bw = 580
        bh = len(lines) * lh + pad * 2
        bx = W // 2 - bw // 2

        box = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.rect(box, (30, 80, 180, 45), (0, 0, bw, bh), border_radius=14)
        pygame.draw.rect(box, (*ACCENT, 60), (0, 0, bw, bh), 1, border_radius=14)
        self.screen.blit(box, (bx, y))
        for i, ln in enumerate(lines):
            s = self.f_body.render(ln, True, WHITE)
            self.screen.blit(s, s.get_rect(center=(W // 2, y + pad + i * lh + lh // 2)))

    def _draw_training_ui(self, train_msg, train_prog):
        # Header
        hdr = self.f_sm.render("TRAINING MODE", True, ACCENT_LT)
        hdr.set_alpha(200)
        self.screen.blit(hdr, hdr.get_rect(center=(W // 2, 38)))

        # Message
        if train_msg:
            self._centered(self.f_body, train_msg, ACCENT_LT, H // 2 + 80)

        # Progress bar
        done, total = train_prog
        bw, bh = 280, 8
        bx, by = W // 2 - bw // 2, H // 2 + 110
        bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.rect(bg, (40, 80, 160, 120), (0, 0, bw, bh), border_radius=4)
        self.screen.blit(bg, (bx, by))
        if done > 0 and total > 0:
            fw = int(bw * done / total)
            fg = pygame.Surface((fw, bh), pygame.SRCALPHA)
            pygame.draw.rect(fg, (*ACCENT, 220), (0, 0, fw, bh), border_radius=4)
            self.screen.blit(fg, (bx, by))

        # Step pips (works for any count — no numbers inside the dots)
        pip_r   = 7
        spacing = 22
        total_w = (total - 1) * spacing
        start_x = W // 2 - total_w // 2
        dy = by + 26
        for k in range(total):
            dx = start_x + k * spacing
            pip = pygame.Surface((pip_r*2+2, pip_r*2+2), pygame.SRCALPHA)
            if k < done:
                pygame.draw.circle(pip, (*ACCENT_LT, 255), (pip_r+1, pip_r+1), pip_r)
            else:
                pygame.draw.circle(pip, (50, 90, 160, 180), (pip_r+1, pip_r+1), pip_r)
                pygame.draw.circle(pip, (*ACCENT, 120), (pip_r+1, pip_r+1), pip_r, 1)
            self.screen.blit(pip, (dx - pip_r - 1, dy - pip_r - 1))

    def _draw_buttons(self):
        by = H - 56
        # Train button
        self.btn_train = pygame.Rect(W // 2 - 136, by, 118, 36)
        bs = pygame.Surface((118, 36), pygame.SRCALPHA)
        pygame.draw.rect(bs, (20, 58, 140, 190), (0, 0, 118, 36), border_radius=10)
        pygame.draw.rect(bs, (*ACCENT, 90), (0, 0, 118, 36), 1, border_radius=10)
        self.screen.blit(bs, self.btn_train.topleft)
        tt = self.f_small.render("⚙  Train Voice", True, DIM)
        self.screen.blit(tt, tt.get_rect(center=self.btn_train.center))

        # Phrases button
        self.btn_phrases = pygame.Rect(W // 2 + 18, by, 118, 36)
        ps = pygame.Surface((118, 36), pygame.SRCALPHA)
        pygame.draw.rect(ps, (20, 58, 140, 190), (0, 0, 118, 36), border_radius=10)
        pygame.draw.rect(ps, (*ACCENT, 90), (0, 0, 118, 36), 1, border_radius=10)
        self.screen.blit(ps, self.btn_phrases.topleft)
        pt = self.f_small.render("⊞  Wake Phrases", True, DIM)
        self.screen.blit(pt, pt.get_rect(center=self.btn_phrases.center))

    def _draw_phrases_overlay(self):
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((4, 10, 28, 215))
        self.screen.blit(ov, (0, 0))

        bw, bh = 500, min(120 + len(self.wake_phrases) * 50 + 140, H - 80)
        bx, by = (W - bw) // 2, (H - bh) // 2
        box = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.rect(box, (10, 28, 72, 245), (0, 0, bw, bh), border_radius=16)
        pygame.draw.rect(box, (*ACCENT, 110), (0, 0, bw, bh), 1, border_radius=16)
        self.screen.blit(box, (bx, by))

        # Title
        title = self.f_sm.render("WAKE PHRASES", True, ACCENT_LT)
        self.screen.blit(title, title.get_rect(center=(W // 2, by + 26)))

        # Phrase chips
        self._del_rects = []
        for idx, phrase in enumerate(self.wake_phrases):
            py = by + 52 + idx * 48

            chip = pygame.Surface((bw - 60, 38), pygame.SRCALPHA)
            pygame.draw.rect(chip, (28, 76, 180, 90), (0, 0, bw-60, 38), border_radius=9)
            pygame.draw.rect(chip, (*ACCENT, 70), (0, 0, bw-60, 38), 1, border_radius=9)
            self.screen.blit(chip, (bx + 30, py))

            pt = self.f_body.render(f'"{phrase}"', True, WHITE)
            self.screen.blit(pt, (bx + 46, py + 9))

            # Delete [×]
            if len(self.wake_phrases) > 1:
                del_rect = pygame.Rect(bx + bw - 55, py + 6, 26, 26)
                self._del_rects.append((del_rect, idx))
                ds = pygame.Surface((26, 26), pygame.SRCALPHA)
                pygame.draw.rect(ds, (160, 50, 50, 180), (0, 0, 26, 26), border_radius=7)
                self.screen.blit(ds, del_rect.topleft)
                xt = self.f_small.render("✕", True, WHITE)
                self.screen.blit(xt, xt.get_rect(center=del_rect.center))

        # Input row
        inp_y = by + 52 + len(self.wake_phrases) * 48 + 10
        inp_rect = pygame.Rect(bx + 30, inp_y, bw - 120, 38)
        inp_s = pygame.Surface((inp_rect.width, 38), pygame.SRCALPHA)
        pygame.draw.rect(inp_s, (18, 48, 120, 160), (0, 0, inp_rect.width, 38), border_radius=9)
        pygame.draw.rect(inp_s, (*ACCENT, 130), (0, 0, inp_rect.width, 38), 1, border_radius=9)
        self.screen.blit(inp_s, inp_rect.topleft)

        cursor = "|" if int(time.time() * 2) % 2 == 0 else " "
        inp_text = (self.phrases_input + cursor) if self.phrases_input else "type new phrase…"
        inp_col  = WHITE if self.phrases_input else (80, 120, 170)
        it = self.f_body.render(inp_text, True, inp_col)
        self.screen.blit(it, (inp_rect.x + 10, inp_rect.y + 9))

        # Add button
        self._add_rect = pygame.Rect(bx + bw - 82, inp_y, 52, 38)
        ad = pygame.Surface((52, 38), pygame.SRCALPHA)
        pygame.draw.rect(ad, (*ACCENT_DK, 210), (0, 0, 52, 38), border_radius=9)
        self.screen.blit(ad, self._add_rect.topleft)
        at = self.f_small.render("ADD", True, WHITE)
        self.screen.blit(at, at.get_rect(center=self._add_rect.center))

        # Done button
        self._done_rect = pygame.Rect(W // 2 - 55, by + bh - 48, 110, 36)
        ds2 = pygame.Surface((110, 36), pygame.SRCALPHA)
        pygame.draw.rect(ds2, (28, 100, 210, 220), (0, 0, 110, 36), border_radius=10)
        self.screen.blit(ds2, self._done_rect.topleft)
        dt = self.f_body.render("Done", True, WHITE)
        self.screen.blit(dt, dt.get_rect(center=self._done_rect.center))

        hint = self.f_small.render("Enter to add  ·  Esc to close", True, (70, 110, 170))
        self.screen.blit(hint, hint.get_rect(center=(W // 2, by + bh - 10)))

    def draw(self):
        self._draw_gradient()
        self._draw_stars()

        with self._lock:
            state    = self.state
            status   = self.status_text
            response = self.response_text
            trans    = self.transcript
            tmsg     = self.train_msg
            tprog    = self.train_prog

        cx, cy = W // 2, 218
        orb_r  = 75

        self._draw_orb(cx, cy, orb_r)

        # Brand
        brand = self.f_sm.render("VOICE ASSISTANT", True, (80, 140, 210))
        brand.set_alpha(130)
        self.screen.blit(brand, brand.get_rect(center=(cx, cy - orb_r - 46)))

        # Title
        tc = ACCENT_LT if state in (LISTENING, SPEAKING) else (65, 125, 218)
        self._centered(self.f_title, "Car", tc, cy + orb_r + 30)

        if state == TRAINING:
            self.wave.set_active(True)
            self.wave.update()
            self.wave.draw(self.screen, cx, cy + orb_r + 88, width=460, height=90)
            self._draw_training_ui(tmsg, tprog)
        else:
            self.wave.update()
            self.wave.draw(self.screen, cx, cy + orb_r + 88, width=460, height=90)

            sc = ACCENT_LT if state in (LISTENING, SPEAKING) else (95, 148, 212)
            self._centered(self.f_body, status, sc, cy + orb_r + 158)

            self._draw_response_box(response, cy + orb_r + 190)

            if trans:
                self._centered(self.f_small, trans, (85, 118, 175), H - 34, alpha=160)

            if state == SLEEPING:
                self._draw_buttons()

        if self.phrases_open:
            self._draw_phrases_overlay()

        hint = self.f_small.render("SPACE = wake  |  ESC = quit", True, (42, 72, 118))
        self.screen.blit(hint, hint.get_rect(bottomright=(W - 10, H - 6)))

        pygame.display.flip()

    # ── Main loop ─────────────────────────────────────────────────────────────
    def run(self):
        print(f"[App] {W}×{H}  |  voice={self.cfg.get('voice')}  "
              f"|  phrases={self.wake_phrases}")
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                elif event.type == pygame.KEYDOWN:
                    if self.phrases_open:
                        self._phrases_key(event)
                    elif event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_SPACE and self.state == SLEEPING:
                        threading.Thread(target=self._trigger_wake, daemon=True).start()

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.phrases_open:
                        self._phrases_click(event.pos)
                    elif self.state == SLEEPING:
                        if self.btn_train.collidepoint(event.pos):
                            self._start_training()
                        elif self.btn_phrases.collidepoint(event.pos):
                            self.phrases_open = True

            self.draw()
            self.clock.tick(60)

        pygame.quit()
        sys.exit(0)


if __name__ == "__main__":
    CarAssistant().run()
