#!/usr/bin/env python3
"""mic_capture.py — Single mic capture that fans out to multiple consumers."""

import pyaudio
import threading
import queue

# ── Config ────────────────────────────────────────────────────────────────────
SAMPLE_RATE  = 44100
CHANNELS     = 2
CHUNK        = 1024
FORMAT       = pyaudio.paInt16
DEVICE_INDEX = 7

class MicCapture:
    """Opens the mic once and distributes chunks to registered queues."""

    def __init__(self):
        self._pa      = pyaudio.PyAudio()
        self._queues  = []
        self._lock    = threading.Lock()
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._running = False

    def register(self, maxsize=50) -> queue.Queue:
        q = queue.Queue(maxsize=maxsize)
        with self._lock:
            self._queues.append(q)
        return q

    def start(self):
        self._running = True
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self):
        stream = self._pa.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            input_device_index=DEVICE_INDEX,
            frames_per_buffer=CHUNK,
        )
        print("[Mic] Capture started")
        try:
            while self._running:
                data = stream.read(CHUNK, exception_on_overflow=False)
                with self._lock:
                    for q in self._queues:
                        if not q.full():
                            q.put_nowait(data)
        except Exception as e:
            print(f"[Mic] Error: {e}")
        finally:
            stream.stop_stream()
            stream.close()
            self._pa.terminate()
            print("[Mic] Capture stopped")