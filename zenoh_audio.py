#!/usr/bin/env python3
"""zenoh_audio.py — Stream audio to another device using Zenoh."""

import zenoh
import threading
import time
import pyaudio
import queue

TOPIC = "uav/audio/stream"

# ── Sender ────────────────────────────────────────────────────────────────────
class ZenohSender:
    """Reads from a mic queue and publishes over Zenoh."""

    def __init__(self, mic_queue: queue.Queue):
        self._q      = mic_queue
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._thread.start()

    def _loop(self):
        cfg = zenoh.Config()
        z   = zenoh.open(cfg)
        pub = z.declare_publisher(TOPIC)
        print(f"[Zenoh] Streaming on '{TOPIC}'…")
        try:
            while True:
                try:
                    data = self._q.get(timeout=1)
                    pub.put(data)
                except queue.Empty:
                    continue
        except Exception as e:
            print(f"[Zenoh] Error: {e}")
        finally:
            z.close()


# ── Receiver ──────────────────────────────────────────────────────────────────
class ZenohReceiver:
    """Subscribes to Zenoh audio topic and plays it back."""

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        pa     = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=44100,
            output=True,
            frames_per_buffer=1024,
        )

        cfg = zenoh.Config()
        z   = zenoh.open(cfg)

        def on_sample(sample):
            stream.write(bytes(sample.payload))

        print(f"[Zenoh] Receiving on '{TOPIC}'…")
        sub = z.declare_subscriber(TOPIC, on_sample)

        try:
            while True:
                time.sleep(0.1)
        except Exception as e:
            print(f"[Zenoh] Receiver error: {e}")
        finally:
            sub.undeclare()
            stream.stop_stream()
            stream.close()
            pa.terminate()
            z.close()


# ── Standalone entry point ────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2 or sys.argv[1] not in ("send", "recv"):
        print("Usage: python3 zenoh_audio.py [send|recv]")
        sys.exit(1)

    if sys.argv[1] == "send":
        from mic_capture import MicCapture
        mic = MicCapture()
        q   = mic.register()
        mic.start()
        sender = ZenohSender(q)
        sender.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            mic.stop()
    else:
        recv = ZenohReceiver()
        recv.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass