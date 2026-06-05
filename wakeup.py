#!/usr/bin/env python3
"""Wakeup engine — audio recognition, TTS, and voice training."""

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
import threading, queue, time, json, asyncio, tempfile
import speech_recognition as sr   # still needed for training loop mic capture
import edge_tts
from speech_code import WhisperListener
from training import TrainingModule
from zenoh_audio import sender, receiver

# ── Config ────────────────────────────────────────────────────────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_DIR, "config.json")
DEFAULTS = {
    "wake_phrases": ["hello car", "hey car"],
    "voice":        "en-US-GuyNeural",
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

# ── States ────────────────────────────────────────────────────────────────────
SLEEPING  = "sleeping"
LISTENING = "listening"
SPEAKING  = "speaking"
TRAINING  = "training"

# ── TTS Worker ────────────────────────────────────────────────────────────────
class TTSWorker(threading.Thread):
    def __init__(self, voice: str, sr_pause_event: threading.Event):
        super().__init__(daemon=True)
        self.voice      = voice
        self._q         = queue.Queue()
        self._stop_flag = threading.Event()
        self._sr_pause  = sr_pause_event

    def say(self, text: str, done_cb=None):
        self._q.put((text, done_cb))

    def stop_speaking(self):
        self._stop_flag.set()
        pygame.mixer.music.stop()
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break

    def run(self):
        while True:
            text, cb = self._q.get()
            self._stop_flag.clear()
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                fname = f.name
            try:
                asyncio.run(self._gen(text, fname))
                if self._stop_flag.is_set():
                    os.unlink(fname)
                    continue

                self._sr_pause.set()

                pygame.mixer.music.load(fname)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    if self._stop_flag.is_set():
                        pygame.mixer.music.stop()
                        break
                    time.sleep(0.04)
            except Exception as e:
                print(f"[TTS] {e}")
            finally:
                try:
                    os.unlink(fname)
                except Exception:
                    pass
                time.sleep(0.3)
                self._sr_pause.clear()

                if cb and not self._stop_flag.is_set():
                    cb()

    async def _gen(self, text: str, fname: str):
        comm = edge_tts.Communicate(text, self.voice)
        await comm.save(fname)


# ── Wakeup Engine ─────────────────────────────────────────────────────────────
class WakeupEngine:

    _NOISE_POLL_INTERVAL = 10

    def __init__(self):
        self._lock          = threading.Lock()
        self.cfg            = load_cfg()
        self.state          = SLEEPING
        self.status_text    = "Say a wake phrase to activate"
        self.response_text  = ""
        self.transcript     = ""
        self.await_command  = False
        self.train_msg      = ""
        self.train_prog     = (0, 0)
        self.wake_phrases   = list(self.cfg.get("wake_phrases", DEFAULTS["wake_phrases"]))
        self.phrases_open   = False
        self.phrases_input  = ""
        self._sr_pause      = threading.Event()
        self.tts            = TTSWorker(
                                  voice=self.cfg.get("voice", "en-US-GuyNeural"),
                                  sr_pause_event=self._sr_pause)
        self.tts.start()

        # sr.Recognizer kept only for the training loop mic capture
        self._sr            = sr.Recognizer()
        self._sr.dynamic_energy_threshold = False
        self.trainer        = TrainingModule(self, self._sr, self._sr_pause, save_cfg)

        self._cmd_timer: threading.Timer | None = None
        self.running        = True
        self._listener      = WhisperListener(
                                  wake_phrases=self.wake_phrases,
                                  on_wake=lambda _: self._trigger_wake(),
                                  on_command=self._handle_command,
                                  on_partial=self._on_partial,
                                  pause_event=self._sr_pause,
                              )
        self.ready          = self._listener.ready

    def start(self):
        self._listener.start()

    # ── State helpers ─────────────────────────────────────────────────────────
    def _set(self, state=None, status=None, response=None, transcript=None,
             train_msg=None, train_prog=None):
        with self._lock:
            if state      is not None: self.state         = state
            if status     is not None: self.status_text   = status
            if response   is not None: self.response_text = response
            if transcript is not None: self.transcript    = transcript
            if train_msg  is not None: self.train_msg     = train_msg
            if train_prog is not None: self.train_prog    = train_prog

    def _go_sleep(self):
        self._listener.await_command = False
        if self._cmd_timer:
            self._cmd_timer.cancel()
        self._set(state=SLEEPING,
                  status="Say a wake phrase to activate",
                  response="", transcript="", train_msg="")

    # ── Wake / command ────────────────────────────────────────────────────────
    def _trigger_wake(self):
        if self.state == TRAINING:
            return
        self._listener.await_command = True
        self._set(state=LISTENING, status="Hello! What can I do for you?",
                  response="", transcript="")
        self.tts.say("Hello! What can I do for you?",
                     lambda: self._set(status="I'm listening…"))
        self._cmd_timer = threading.Timer(12, self._timeout_command)
        self._cmd_timer.start()

    def stop_speaking(self):
        self.tts.stop_speaking()
        self._sr_pause.clear()
        self._go_sleep()

    def _handle_command(self, text: str):
        if self._cmd_timer:
            self._cmd_timer.cancel()
        self._listener.await_command = False
        resp = "Hello! I'm your Car Assistant. How can I help you today?"
        self._set(state=SPEAKING, status="Responding…",
                  response=resp, transcript=f'You said: "{text}"')
        self.tts.say(resp, lambda: threading.Timer(2.5, self._go_sleep).start())

    def _timeout_command(self):
        self.tts.say(
            "I didn't catch that. Say a wake phrase whenever you need me.",
            self._go_sleep)

    # ── Training (still uses sr.Recognizer for controlled single captures) ────
    def start_training(self):
        self.trainer.start()

    # ── Phrases ───────────────────────────────────────────────────────────────
    def handle_phrase_key(self, event):
        if event.key == pygame.K_ESCAPE:
            self.phrases_open  = False
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

    def handle_phrase_click(self, pos, del_rects, add_rect, done_rect):
        for rect, idx in del_rects:
            if rect.collidepoint(pos) and len(self.wake_phrases) > 1:
                self.wake_phrases.pop(idx)
                self.cfg["wake_phrases"] = self.wake_phrases
                save_cfg(self.cfg)
                return
        if add_rect.collidepoint(pos):
            self._add_phrase()
            return
        if done_rect.collidepoint(pos):
            self.phrases_open  = False
            self.phrases_input = ""

    # ── Partial (non-wake) transcript display ─────────────────────────────────
    def _on_partial(self, text: str):
        with self._lock:
            self.transcript = f'"{text}"'
        threading.Timer(2, lambda: self._set(transcript="")).start()