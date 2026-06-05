#!/usr/bin/env python3
"""zenoh_audio.py — Stream audio between devices using Zenoh."""

import zenoh
import pyaudio
import numpy as np
import threading
import time

# ── Config ────────────────────────────────────────────────────────────────────
TOPIC           = "uav/audio/stream"
SAMPLE_RATE     = 44100
CHANNELS        = 2
CHUNK           = 1024
FORMAT          = pyaudio.paInt16

# ── Sender ────────────────────────────────────────────────────────────────────
def sender():
    """Capture mic audio and publish over Zenoh."""
    pa  = pyaudio.PyAudio()
    cfg = zenoh.Config()
    z   = zenoh.open(cfg)
    pub = z.declare_publisher(TOPIC)

    stream = pa.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        input_device_index=0,
        frames_per_buffer=CHUNK,
    )

    print(f"[Sender] Streaming audio on '{TOPIC}'…")
    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            pub.put(data)
    except KeyboardInterrupt:
        print("[Sender] Stopped.")
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()
        z.close()


# ── Receiver ──────────────────────────────────────────────────────────────────
def receiver():
    """Subscribe to Zenoh audio topic and play it."""
    pa      = pyaudio.PyAudio()
    cfg     = zenoh.Config()
    z       = zenoh.open(cfg)

    stream  = pa.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        output=True,
        frames_per_buffer=CHUNK,
    )

    def on_sample(sample):
        stream.write(bytes(sample.payload))

    print(f"[Receiver] Listening on '{TOPIC}'…")
    sub = z.declare_subscriber(TOPIC, on_sample)

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("[Receiver] Stopped.")
    finally:
        sub.undeclare()
        stream.stop_stream()
        stream.close()
        pa.terminate()
        z.close()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2 or sys.argv[1] not in ("send", "recv"):
        print("Usage: python3 zenoh_audio.py [send|recv]")
        sys.exit(1)

    if sys.argv[1] == "send":
        sender()
    else:
        receiver()