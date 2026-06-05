# Hello Car — Voice Assistant

A wake-word voice assistant with a Siri-style animated UI built in Python using pygame.
Say a registered wake phrase to activate the assistant, then speak a command. The assistant responds using Microsoft Edge TTS.

Speech recognition runs through Google Speech Recognition, and text-to-speech uses `edge-tts`, so an internet connection is required for both.

---

## Requirements

- Python 3.10+
- A working microphone
- Internet access for speech recognition and TTS

Install dependencies:

```bash
pip install -r requirements.txt edge-tts
```

> `requirements.txt` includes `pygame`, `SpeechRecognition`, and `pyaudio` for microphone capture.

---

## Run

```bash
python3 main.py
```

The app starts with a loading screen while the microphone calibrates. Once ready, it waits for a wake phrase.

---

## Controls

- `SPACE` — Manually trigger wake while sleeping
- `S` — Stop speaking
- `ESC` — Quit the app or close the phrase editor

---

## How it works

### Speech recognition
The app uses `speech_code.py` with `SpeechRecognition` to listen continuously via the microphone.
It sends audio to Google Speech Recognition and then:
- triggers a wake phrase when the assistant is sleeping
- accepts a command when the assistant is listening
- displays partial non-wake transcripts in the UI

Wake phrase matching is fuzzy, so similar phrasing can still trigger the assistant.

### Text-to-speech
Responses are generated through `edge-tts` and played using `pygame.mixer`.
While speaking, the app pauses microphone capture to avoid hearing itself, then resumes after playback completes.

### Training and noise handling
`training.py` measures ambient background noise, then captures 10 wake phrase samples to compute a new energy threshold.
That threshold is saved to `config.json` and reused on future launches.

---

## User interface

### Wake phrase editor
Click **⊞ Wake Phrases** to edit the wake phrase list.
You can:
- type a new phrase and press `Enter` or click **ADD**
- remove existing phrases using `✕`
- close the editor with `ESC`

### Train voice button
Click **⚙ Train Voice** to begin noise and voice calibration.
The app prompts for 10 clear wake phrase samples and saves the result automatically.

### Visual feedback
The main UI shows:
- a glowing orb and animated Siri-style wave
- current app state and status text
- response text while speaking
- transcript previews for heard speech
- training progress during calibration

---

## Configuration

`config.json` stores your wake phrases, voice selection, and microphone energy threshold.
If it is missing, the app falls back to default values.

Example `config.json`:

```json
{
  "wake_phrases": [
    "hey type s",
    "hey car",
    "hey man",
    "hello car",
    "hey bro",
    "hey trump"
  ],
  "voice": "en-US-GuyNeural",
  "energy_threshold": 300
}
```

| Key | Purpose |
|---|---|
| `wake_phrases` | Phrases that can wake the assistant |
| `voice` | Edge TTS voice identifier |
| `energy_threshold` | Microphone sensitivity threshold used by speech recognition |

Delete `config.json` to reset the app to defaults.

---

## Files

| File | Purpose |
|---|---|
| `main.py` | Application entry point and event loop |
| `wakeup.py` | Core engine, state management, TTS worker, phrase editing, and training orchestration |
| `gui.py` | Pygame rendering for the loading screen, orb, waveform, buttons, and overlays |
| `speech_code.py` | Continuous microphone listener and fuzzy wake phrase matcher |
| `training.py` | Microphone training workflow and energy threshold tuning |
| `config.json` | Saved wake phrases, voice, and energy threshold |
| `requirements.txt` | Base Python dependencies |
| `livekit-wakeword/` | Placeholder folder for future LiveKit wake-word integration |
