# Hello Car — Voice Assistant Demo

A wake-word voice assistant with a Siri-style animated UI built in Python using pygame. Say **"Hello Car"** (or any custom phrase) to activate it, speak a command, and it responds with a neural text-to-speech voice.

Speech recognition runs **fully offline** using OpenAI Whisper (`base.en` model). Only text-to-speech requires an internet connection.

---

## Requirements

- Python 3.10+
- A working microphone
- Internet connection (Microsoft Edge TTS for voice output only)

Install dependencies:

```bash
pip install pygame faster-whisper pyaudio numpy edge-tts
```

> On first run the `base.en` Whisper model (~74 MB) is downloaded automatically and cached locally. Every subsequent run is fully offline for recognition.

---

## Run

```bash
python3 car_assistant.py
```

The window will show **"Loading Whisper model…"** for a few seconds on first run, then **"Calibrating microphone…"**, then it's ready.

---

## How it works

### Speech recognition — Whisper (offline)
Voice is captured directly via PyAudio using energy-based voice activity detection (VAD). When speech is detected, the audio is transcribed locally by [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (`base.en`, int8 quantised). No audio ever leaves the machine.

### Text-to-speech — Edge TTS (online)
Responses are spoken using Microsoft's `en-US-GuyNeural` neural voice via [edge-tts](https://github.com/rany2/edge-tts). This requires an internet connection only when the assistant speaks.

---

## How to use

### Wake it up
Say **"Hello Car"** or **"Hey Car"** out loud. The orb lights up, the wave animation appears, and the assistant greets you.

### Give a command
After it wakes, speak a command. Supported topics:

| What you say | What it does |
|---|---|
| "Navigate to…" / "Take me to…" | Navigation |
| "Play music" / "Radio" | Music |
| "Weather" | Weather |
| "Call…" / "Dial…" | Phone call |
| "Home" / "House" | Navigate home |
| "Gas" / "Fuel" | Find a gas station |
| "Temperature" / "AC" / "Heat" | Climate control |
| "Parking" | Find parking |
| "What time is it" | Current time |
| "Volume" / "Louder" / "Quieter" | Volume control |

If no command is given within 12 seconds the assistant goes back to sleep automatically.

### Keyboard shortcuts

| Key | Action |
|---|---|
| `SPACE` | Manually trigger wake (useful for testing without mic) |
| `ESC` | Quit |

---

## Train Voice (bottom-left button)

Calibrates the microphone energy threshold so the assistant responds to your voice level and ignores background noise.

1. Click **⚙ Train Voice** on the home screen
2. Stay quiet for 2 seconds — the room noise floor is measured
3. Say a wake phrase **10 times** when prompted
4. Each attempt is transcribed by Whisper to confirm the phrase was heard correctly — mismatches prompt a retry rather than counting silently
5. The threshold is saved to `config.json` and applied automatically on every future run

> Training is fully isolated — the main recognition loop is blocked while training owns the microphone, so the assistant cannot be accidentally woken mid-session.

---

## Wake Phrases (bottom-right button)

Manage which phrases activate the assistant.

1. Click **⊞ Wake Phrases** on the home screen
2. View current phrases (defaults: `"hello car"` and `"hey car"`)
3. Type a new phrase and press **Enter** or click **ADD**
4. Click **✕** next to a phrase to remove it (at least one phrase must always remain)

All changes save instantly to `config.json`.

---

## Config file

Settings persist in `config.json` next to the script:

```json
{
  "wake_phrases": ["hello car", "hey car"],
  "energy_threshold": 0.018,
  "voice": "en-US-GuyNeural",
  "whisper_model": "base.en"
}
```

| Key | Description |
|---|---|
| `wake_phrases` | List of phrases that wake the assistant |
| `energy_threshold` | Float (0–1 scale) — mic sensitivity set by training. Lower = more sensitive |
| `voice` | Edge TTS voice ID |
| `whisper_model` | Whisper model size: `tiny.en`, `base.en`, `small.en`, `medium.en` |

Delete `config.json` to reset everything to defaults.

### Changing the Whisper model

Edit `whisper_model` in `config.json` to trade speed for accuracy:

| Model | Size | Speed (CPU) | Accuracy |
|---|---|---|---|
| `tiny.en` | 39 MB | ~0.5 s | Good |
| `base.en` | 74 MB | ~1 s | Better (default) |
| `small.en` | 244 MB | ~3 s | Best for most use |
| `medium.en` | 769 MB | ~8 s | Highest |

---

## Voice

Uses **Microsoft Edge TTS** (`en-US-GuyNeural` by default) — a natural-sounding American male neural voice in his 30s. No API key required. Requires an internet connection to generate audio at response time.

To use a different voice, update `"voice"` in `config.json` with any [Edge TTS voice name](https://github.com/rany2/edge-tts).

---

## Files

| File | Purpose |
|---|---|
| `car_assistant.py` | Main application |
| `config.json` | Saved settings (auto-created on first run or after training) |
| `requirements.txt` | Python dependencies |
