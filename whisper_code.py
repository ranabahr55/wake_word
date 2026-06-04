#!/usr/bin/env python3
"""whisper_listener.py — Faster-whisper mic capture and transcription module.

Handles continuous microphone capture, energy-based VAD, and transcription
via faster-whisper. Dispatches recognised text to callbacks.

Usage
-----
    from whisper_listener import WhisperListener

    listener = WhisperListener(
        wake_phrases=["hello car", "hey car"],
        on_wake=lambda text: ...,
        on_command=lambda text: ...,
        on_partial=lambda text: ...,
        pause_event=some_threading_event,
    )
    listener.start()
    listener.await_command = True   # switch to command mode
    listener.stop()

Dependencies
------------
    pip install faster-whisper sounddevice numpy
"""

import threading
import time
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

# ── Audio / VAD constants ─────────────────────────────────────────────────────
_SAMPLE_RATE          = 16_000   # Whisper expects 16 kHz mono
_CHANNELS             = 1
_CHUNK_SECS           = 0.03     # 30 ms read blocks
_PHRASE_MAX_SECS      = 7.0      # discard runaway phrases
_SILENCE_SECS         = 0.9      # trailing silence that closes a phrase
_ENERGY_FLOOR         = 0.002    # RMS below this is silence
_MIN_WORDS            = 2        # ignore single-word hits


class WhisperListener:
    """Continuous whisper-based listener with wake-phrase / command dispatch.

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
        When set, the loop idles and drains the mic (e.g. while TTS plays).
    model_size : str
        faster-whisper model: "tiny", "base", "small", "medium".
    """

    def __init__(
        self,
        wake_phrases: list[str],
        on_wake=None,
        on_command=None,
        on_partial=None,
        pause_event: threading.Event | None = None,
        model_size: str = "base",
    ):
        self.wake_phrases  = wake_phrases
        self.on_wake       = on_wake
        self.on_command    = on_command
        self.on_partial    = on_partial
        self._pause        = pause_event or threading.Event()
        self.await_command = False   # caller flips this to switch modes

        print(f"[Whisper] Loading model '{model_size}' on CPU…")
        self._model = WhisperModel(model_size, device="cpu", compute_type="int8")
        print("[Whisper] Model ready.")

        self.ready    = threading.Event()
        self._running = False
        self._thread  = threading.Thread(target=self._loop, daemon=True)

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self):
        """Begin capture + transcription in a background thread."""
        self._running = True
        self._thread.start()

    def stop(self):
        """Signal the loop to exit."""
        self._running = False

    # ── Transcription ──────────────────────────────────────────────────────────

    def _transcribe(self, audio: np.ndarray) -> str:
        segments, _ = self._model.transcribe(
            audio,
            language="en",
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
        )
        return " ".join(s.text for s in segments).lower().strip()

    # ── Capture loop ───────────────────────────────────────────────────────────

    def _loop(self):
        chunk_size   = int(_SAMPLE_RATE * _CHUNK_SECS)
        sil_needed   = int(_SILENCE_SECS / _CHUNK_SECS)
        max_chunks   = int(_PHRASE_MAX_SECS / _CHUNK_SECS)

        print("[Whisper] Opening microphone…")
        try:
            with sd.InputStream(
                samplerate=_SAMPLE_RATE,
                channels=_CHANNELS,
                dtype="float32",
                blocksize=chunk_size,
            ) as mic:
                print("[Whisper] Listening.")
                self.ready.set()

                phrase_buf: list[np.ndarray] = []
                silence_count = 0
                in_phrase     = False

                while self._running:
                    # ── Idle while paused ─────────────────────────────────
                    if self._pause.is_set():
                        mic.read(chunk_size)   # drain so stale audio doesn't bleed in
                        phrase_buf.clear()
                        in_phrase     = False
                        silence_count = 0
                        time.sleep(0.05)
                        continue

                    chunk, _ = mic.read(chunk_size)
                    chunk    = chunk[:, 0]     # stereo → mono
                    rms      = float(np.sqrt(np.mean(chunk ** 2)))

                    if rms > _ENERGY_FLOOR:
                        phrase_buf.append(chunk)
                        silence_count = 0
                        in_phrase     = True
                    elif in_phrase:
                        phrase_buf.append(chunk)   # keep trailing silence
                        silence_count += 1

                        if silence_count >= sil_needed or len(phrase_buf) >= max_chunks:
                            audio         = np.concatenate(phrase_buf)
                            phrase_buf.clear()
                            in_phrase     = False
                            silence_count = 0
                            self._process(audio)

        except Exception as e:
            print(f"[Whisper] Mic error: {e}")

    def _process(self, audio: np.ndarray):
        if self._pause.is_set():
            print("[Whisper] Discarding — paused before transcription")
            return

        try:
            text = self._transcribe(audio)
        except Exception as e:
            print(f"[Whisper] Transcription error: {e}")
            return

        if not text or len(text.split()) < _MIN_WORDS:
            return

        if self._pause.is_set():
            print("[Whisper] Discarding — paused after transcription")
            return

        print(f"[Heard] {text}")

        if self.await_command:
            if self.on_command:
                self.on_command(text)
        else:
            if any(p in text for p in self.wake_phrases):
                if self.on_wake:
                    self.on_wake(text)
            else:
                if self.on_partial:
                    self.on_partial(text)