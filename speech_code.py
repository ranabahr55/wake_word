#!/usr/bin/env python3
"""speech_code.py — Speech recognition module for the wakeup engine."""

import threading
import time
from difflib import SequenceMatcher
import speech_recognition as sr

# ── Fuzzy matching ────────────────────────────────────────────────────────────
_FUZZY_THRESHOLD = 0.7

def _fuzzy_match(text: str, phrases: list[str]) -> bool:
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


class WhisperListener:
    _MAX_API_RETRIES = 3

    def __init__(
        self,
        wake_phrases: list[str],
        on_wake=None,
        on_command=None,
        on_partial=None,
        pause_event: threading.Event | None = None,
        energy_threshold: int | None = None,
        min_words: int = 2,
    ):
        self.wake_phrases     = wake_phrases
        self.on_wake          = on_wake
        self.on_command       = on_command
        self.on_partial       = on_partial
        self._pause           = pause_event or threading.Event()
        self._saved_threshold = energy_threshold
        self._min_words       = min_words
        self.await_command    = False

        self._recognizer = sr.Recognizer()
        self._recognizer.dynamic_energy_threshold = False

        self.ready    = threading.Event()
        self._running = False
        self._thread  = threading.Thread(target=self._loop, daemon=True)

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        self._running = True
        self._thread.start()

    def stop(self):
        self._running = False

    def adjust_for_ambient_noise(self, duration: float = 0.8) -> float:
        with sr.Microphone() as src:
            self._recognizer.adjust_for_ambient_noise(src, duration=duration)
        return self._recognizer.energy_threshold

    @property
    def energy_threshold(self) -> float:
        return self._recognizer.energy_threshold

    @energy_threshold.setter
    def energy_threshold(self, value: float):
        self._recognizer.energy_threshold = value

    # ── Calibration + loop ────────────────────────────────────────────────────

    def _calibrate(self, src) -> bool:
        print("[SR] Calibrating microphone…")
        try:
            self._recognizer.adjust_for_ambient_noise(src, duration=1.5)
            if self._saved_threshold:
                self._recognizer.energy_threshold = self._saved_threshold
            else:
                self._recognizer.energy_threshold = max(
                    self._recognizer.energy_threshold * 1.3, 400
                )
            print(f"[SR] Ready  (threshold={self._recognizer.energy_threshold:.0f})")
            return True
        except Exception as e:
            print(f"[SR] Mic init failed: {e}")
            return False

    def _loop(self):
        try:
            with sr.Microphone() as src:
                if not self._calibrate(src):
                    self.ready.set()
                    return

                self.ready.set()
                api_retries = 0

                while self._running:
                    while self._pause.is_set() and self._running:
                        time.sleep(0.15)
                    if not self._running:
                        break

                    try:
                        audio = self._recognizer.listen(
                            src, timeout=2, phrase_time_limit=3
                        )

                        if self._pause.is_set():
                            print("[SR] Discarding — paused during recognition")
                            continue

                        text = (
                            self._recognizer.recognize_google(audio)
                            .lower()
                            .strip()
                        )
                        api_retries = 0  # reset on success

                        if len(text.split()) < self._min_words:
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
                        api_retries += 1
                        print(f"[SR] API error: {e} (attempt {api_retries}/{self._MAX_API_RETRIES})")
                        if api_retries >= self._MAX_API_RETRIES:
                            print("[SR] Max API retries reached — pausing 30 s")
                            time.sleep(30)
                            api_retries = 0
                        else:
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