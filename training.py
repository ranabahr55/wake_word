#!/usr/bin/env python3
"""Wakeup training module."""

import threading
import time
import audioop

import speech_recognition as sr


class TrainingModule:
    def __init__(self, engine, recognizer, pause_event, save_cfg):
        self.engine = engine
        self._sr = recognizer
        self._sr_pause = pause_event
        self._save_cfg = save_cfg

    def start(self):
        if self.engine.state != "sleeping":
            return
        threading.Thread(target=self._training_loop, daemon=True).start()

    def _training_loop(self):
        STEPS = 10
        self._sr_pause.set()
        self.engine._set(
            state="training",
            train_msg="Stay quiet — listening to the room…",
            train_prog=(0, STEPS),
        )
        time.sleep(0.4)

        try:
            with sr.Microphone() as src:
                self._sr.adjust_for_ambient_noise(src, duration=2.0)
            noise_thresh = self._sr.energy_threshold
        except Exception as exc:
            self.engine._set(train_msg=f"Mic error: {exc}")
            time.sleep(2)
            self._sr_pause.clear()
            self.engine._go_sleep()
            return

        samples = []
        i = 0
        while i < STEPS:
            self.engine._set(
                train_msg=f"Say a wake phrase clearly  ({i+1} / {STEPS})",
                train_prog=(i, STEPS),
            )
            time.sleep(0.4)
            try:
                self._sr.energy_threshold = noise_thresh * 0.6
                with sr.Microphone() as src:
                    audio = self._sr.listen(src, timeout=8, phrase_time_limit=5)
                rms = audioop.rms(audio.get_raw_data(), audio.sample_width)
                samples.append(rms)
                self.engine._set(
                    train_msg=f"Got it!  ✓  ({i+1} / {STEPS})",
                    train_prog=(i+1, STEPS),
                )
                time.sleep(0.9)
                i += 1
            except sr.WaitTimeoutError:
                self.engine._set(train_msg=f"Didn't hear you — try again  ({i+1} / {STEPS})")
                time.sleep(0.8)

        if samples:
            avg_voice = sum(samples) / len(samples)
            new_thresh = int(noise_thresh + (avg_voice - noise_thresh) * 0.28)
            new_thresh = max(new_thresh, int(noise_thresh * 1.25), 300)
            self._sr.energy_threshold = new_thresh
            self.engine.cfg["energy_threshold"] = new_thresh
            self._save_cfg(self.engine.cfg)
            self.engine._set(
                train_msg=f"Training complete!  Threshold → {new_thresh}",
                train_prog=(STEPS, STEPS),
            )
        else:
            self.engine._set(train_msg="Training failed — please try again.")

        time.sleep(2.8)
        self._sr_pause.clear()
        self.engine._go_sleep()
