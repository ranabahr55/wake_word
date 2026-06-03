# Hello Car — Voice Assistant Demo

A wake-word voice assistant with a Siri-style animated UI built in Python using pygame. Say **"Hello Car"** (or any custom phrase) to activate it, speak a command, and it responds with a neural text-to-speech voice.

---

## Requirements

- Python 3.10+
- Internet connection (Google Speech Recognition + Microsoft Edge TTS)
- A working microphone

Install dependencies:

```bash
pip install pygame SpeechRecognition pyttsx3 pyaudio edge-tts
```

---

## Run

```bash
python3 car_assistant.py
```

---

## How to use

### Wake it up
Say **"Hello Car"** or **"Hey Car"** out loud. The orb lights up, the wave animation appears, and the assistant asks how it can help.

### Give a command
After it wakes, speak a command. Supported topics:

| What you say | What it does |
|---|---|
| "Navigate to..." / "Take me to..." | Navigation |
| "Play music" / "Radio" | Music |
| "Weather" | Weather |
| "Call..." / "Dial..." | Phone call |
| "Home" / "House" | Navigate home |
| "Gas" / "Fuel" | Find a gas station |
| "Temperature" / "AC" / "Heat" | Climate control |
| "Parking" | Find parking |
| "What time is it" | Current time |
| "Volume" / "Louder" / "Quieter" | Volume control |

If it doesn't recognise the command after 12 seconds it goes back to sleep automatically.

### Keyboard shortcuts

| Key | Action |
|---|---|
| `SPACE` | Manually trigger wake (useful for testing) |
| `ESC` | Quit |

---

## Train Voice (bottom-left button)

Calibrates the microphone sensitivity to your voice so the assistant only reacts to you and not to background noise.

1. Click **⚙ Train Voice** on the home screen
2. Stay quiet for 2 seconds while it measures the room noise
3. Say a wake phrase **10 times** when prompted
4. The threshold is saved to `config.json` and loaded automatically next time

> Training is fully isolated — the assistant cannot be accidentally woken during a training session.

---

## Wake Phrases (bottom-right button)

Manage which phrases activate the assistant.

1. Click **⊞ Wake Phrases** on the home screen
2. View current phrases (default: `"hello car"` and `"hey car"`)
3. Type a new phrase and press **Enter** or click **ADD**
4. Click **✕** next to a phrase to remove it (at least one phrase must remain)

All changes save instantly to `config.json`.

---

## Config file

Settings persist in `config.json` next to the script:

```json
{
  "wake_phrases": ["hello car", "hey car"],
  "energy_threshold": 520,
  "voice": "en-US-GuyNeural"
}
```

| Key | Description |
|---|---|
| `wake_phrases` | List of phrases that wake the assistant |
| `energy_threshold` | Microphone sensitivity (set by training, higher = less sensitive) |
| `voice` | Edge TTS voice ID |

Delete `config.json` to reset everything to defaults.

---

## Voice

Uses **Microsoft Edge TTS** (`en-US-GuyNeural` by default) — a natural-sounding American male neural voice, no API key required. Requires an internet connection to generate audio.

---

## Files

| File | Purpose |
|---|---|
| `car_assistant.py` | Main application |
| `config.json` | Saved settings (auto-created on first run or after training) |
| `requirements.txt` | Python dependencies |
