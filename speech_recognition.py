
#!/usr/bin/env python3
"""speech_code.py — Speech recognition module for the wakeup engine.
 
Handles continuous microphone capture, VAD, and transcription via
Google Speech Recognition. Dispatches recognised text to callbacks.
 
Usage
-----
    from whisper_code import WhisperListener
 
    listener = WhisperListener(
        wake_phrases=["hello car", "hey car"],
        on_wake=lambda text: ...,
        on_command=lambda text: ...,
        on_partial=lambda text: ...,
        pause_event=some_threading_event,
        energy_threshold=400,
    )
    listener.start()
    listener.await_command = True   # switch to command mode
    listener.stop()
 
Dependencies
------------
    pip install SpeechRecognition
"""
 
import threading
import time
from difflib import SequenceMatcher
import speech_recognition as sr
 
# ── Fuzzy matching ────────────────────────────────────────────────────────────
_FUZZY_THRESHOLD = 0.7
 
def _fuzzy_match(text: str, phrases: list[str]) -> bool:
    """Return True if any wake phrase is a close enough match to text."""
    for phrase in phrases:
        if phrase in text:
            return True
        words   = text.split()
        p_words = phrase.split()
        win     = len(p_words)
        for i in range(max(1, len(words) - win + 1)):
            window = " ".join(words[i : i + win])
            ratio  = SequenceMatcher(None, window, phrase).ratio()
            if ratio >= _FUZZY_THRESHOLD:
                print(f"[SR] Fuzzy wake match: '{window}' ~ '{phrase}' ({ratio:.2f})")
                return True
    return False
 
 
_MIN_WORDS = 2
 
 
class WhisperListener:
    """Continuous Google-SR listener with wake-phrase / command dispatch.
 
    Parameters
    ----------
    wake_phrases : list[str]
        Lower-case phrases that trigger ``on_wake``.
    on_wake : callable(text) | None
        Fired when a wake phrase is heard while not awaiting a command.
    on_command : callable(text) | None
        Fired when speech is heard while ``await_command`` is True.
    on_partial : callable(text) | None
        Fired for any heard utterance that matches neither — display only.
    pause_event : threading.Event | None
        When set, the loop idles (e.g. while TTS plays).
    energy_threshold : int | None
        Saved threshold from config. None = auto-calibrate only.
    """
 
    def __init__(
        self,
        wake_phrases: list[str],
        on_wake=None,
        on_command=None,
        on_partial=None,
        pause_event: threading.Event | None = None,
        energy_threshold: int | None = None,
    ):
        self.wake_phrases     = wake_phrases
        self.on_wake          = on_wake
        self.on_command       = on_command
        self.on_partial       = on_partial
        self._pause           = pause_event or threading.Event()
        self._saved_threshold = energy_threshold
        self.await_command    = False
 
        self._recognizer = sr.Recognizer()
        self._recognizer.dynamic_energy_threshold = False
 
        self.ready    = threading.Event()
        self._running = False
        self._thread  = threading.Thread(target=self._loop, daemon=True)
 
    # ── Public API ─────────────────────────────────────────────────────────────
 
    def start(self):
        self._running = True
        self._thread.start()
 
    def stop(self):
        self._running = False
 
    def adjust_for_ambient_noise(self, duration: float = 0.8) -> float:
        """Blocking ambient calibration — called by the engine's noise thread."""
        with sr.Microphone() as src:
            self._recognizer.adjust_for_ambient_noise(src, duration=duration)
        return self._recognizer.energy_threshold
 
    @property
    def energy_threshold(self) -> float:
        return self._recognizer.energy_threshold
 
    @energy_threshold.setter
    def energy_threshold(self, value: float):
        self._recognizer.energy_threshold = value
 
    # ── Calibration + loop ─────────────────────────────────────────────────────
 
    def _calibrate(self) -> bool:
        print("[SR] Calibrating microphone…")
        try:
            with sr.Microphone() as src:
                self._recognizer.adjust_for_ambient_noise(src, duration=1.5)
            if self._saved_threshold:
                self._recognizer.energy_threshold = self._saved_threshold
            else:
                self._recognizer.energy_threshold = max(
                    self._recognizer.energy_threshold * 1.3, 400
                )
            print(f"[SR] Ready  (threshold={self._recognizer.energy_threshold:.0f})")
        except Exception as e:
            print(f"[SR] Mic init failed: {e}")
            self.ready.set()
            return False
        return True
 
    def _loop(self):
        if not self._calibrate():
            return
 
        self.ready.set()
 
        try:
            with sr.Microphone() as src:
                while self._running:
                    while self._pause.is_set() and self._running:
                        time.sleep(0.15)
                    if not self._running:
                        break
 
                    try:
                        audio = self._recognizer.listen(
                            src, timeout=5, phrase_time_limit=7
                        )
 
                        if self._pause.is_set():
                            print("[SR] Discarding — paused during recognition")
                            continue
 
                        text = (
                            self._recognizer.recognize_google(audio)
                            .lower()
                            .strip()
                        )
 
                        if len(text.split()) < _MIN_WORDS:
                            continue
 
                        if self._pause.is_set():
                            print("[SR] Discarding — paused after network call")
                            continue
 
                        print(f"[Heard] {text}")
                        self._dispatch(text)
 
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
 
        except Exception as e:
            print(f"[SR] Mic open failed: {e}")
 
    def _dispatch(self, text: str):
        if self.await_command:
            if self.on_command:
                self.on_command(text)
        else:
            if _fuzzy_match(text, self.wake_phrases):
                if self.on_wake:
                    self.on_wake(text)
            else:
                if self.on_partial:
                    self.on_partial(text)