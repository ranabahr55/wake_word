# Hello Car — Voice Assistant

A wake-word voice assistant with a Siri-style animated UI built in Python using pygame. Say **"Hello Car"** (or any custom phrase) to activate it, speak a command, and it responds with a neural text-to-speech voice.

Speech recognition uses Google's API. Text-to-speech uses Microsoft Edge TTS. Both require an internet connection.

---

## Requirements

- Python 3.10+
- A working microphone
- Internet connection (for speech recognition and TTS)

Install dependencies:

```bash
pip install pygame speechrecognition edge-tts
```

---

## Run

```bash
python3 main.py
```

Startup sequence:
1. **Calibrating microphone…** — measures room noise floor
2. **Say a wake phrase to activate** — ready

---

## How it works

### Speech recognition — Google (online)
Voice is captured via `SpeechRecognition`. When speech is detected the audio is sent to Google Speech Recognition and transcribed. Energy threshold calibration on startup reduces false triggers from background noise.

### Text-to-speech — Edge TTS (online)
Responses are spoken using Microsoft's `en-US-GuyNeural` neural voice via `edge-tts`. Audio is streamed to a temp file and played through pygame's mixer.

---

## How to use

### Wake it up
Say **"Hello Car"** or **"Hey Car"** out loud. The orb lights up, the wave animation appears, and the assistant greets you.

### Give a command
After it wakes, speak a command. The assistant will acknowledge what you said and respond with **"Hello! I'm your Car Assistant. How can I help you today?"**

If no command is given within 12 seconds the assistant goes back to sleep automatically.

### Keyboard shortcuts

| Key | Action |
|---|---|
| `SPACE` | Manually trigger wake |
| `S` | Stop speaking |
| `ESC` | Quit |

---

## Train Voice (bottom-left button)

Calibrates the microphone energy threshold so the assistant responds to your voice and ignores background noise.

1. Click **⚙ Train Voice** on the home screen
2. Stay quiet for 2 seconds — the room noise floor is measured
3. Say a wake phrase **10 times** when prompted
4. The threshold is saved to `config.json` and applied automatically on every future run

> Training is fully isolated — the main recognition loop is blocked while training owns the microphone, so the assistant cannot be accidentally woken mid-session.

---

## Wake Phrases (bottom-right button)

Manage which phrases activate the assistant.

1. Click **⊞ Wake Phrases** on the home screen
2. View current phrases (defaults: `"hello car"` and `"hey car"`)
3. Type a new phrase and press **Enter** or click **ADD**
4. Click **✕** next to a phrase to remove it (at least one must always remain)

All changes save instantly to `config.json`.

---

## Config file

Settings persist in `config.json` next to the scripts:

```json
{
  "wake_phrases": ["hello car", "hey car"],
  "energy_threshold": 400,
  "voice": "en-US-GuyNeural"
}
```

| Key | Description |
|---|---|
| `wake_phrases` | List of phrases that wake the assistant |
| `energy_threshold` | Integer — mic sensitivity set by training. Lower = more sensitive |
| `voice` | Edge TTS voice ID |

Delete `config.json` to reset everything to defaults.

---

## Files

| File | Purpose |
|---|---|
| `main.py` | Entry point — initialises pygame, runs the loading screen, and drives the main event loop |
| `wakeup.py` | Engine — speech recognition, wake word detection, TTS, voice training, phrase management, and all app state |
| `gui.py` | Rendering — loading screen, animated orb, Siri-style wave, RC car icon, buttons, and overlays |
| `config.json` | Saved settings (auto-created on first run or after training) |
| `requirements.txt` | Python dependencies |
