#!/usr/bin/env python3
"""Hello Car — Voice Assistant entry point.

SPACE = manual wake  |  S = stop speaking  |  ESC = quit
"""

import sys
import threading
import pygame

from wakeup import WakeupEngine, SLEEPING, SPEAKING
from gui import CarGUI, LoadingScreen, W, H


def main():
    pygame.init()
    pygame.mixer.pre_init(44100, -16, 2, 1024)
    pygame.mixer.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Hello Car — Voice Assistant")
    clock = pygame.time.Clock()

    engine = WakeupEngine()
    loading = LoadingScreen(screen)

    # Start SR calibration in background; show loading screen until ready
    engine.start()
    while not engine.ready.is_set():
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                engine.running = False
                pygame.quit()
                sys.exit(0)
        loading.draw()
        clock.tick(60)

    engine.start_training()
    gui = CarGUI(screen)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if engine.phrases_open:
                    engine.handle_phrase_key(event)
                elif event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE and engine.state == SLEEPING:
                    threading.Thread(target=engine._trigger_wake, daemon=True).start()
                elif event.key == pygame.K_s and engine.state == SPEAKING:
                    engine.stop_speaking()

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if engine.phrases_open:
                    engine.handle_phrase_click(
                        event.pos, gui._del_rects, gui._add_rect, gui._done_rect)
                elif engine.state == SLEEPING:
                    if gui.btn_train.collidepoint(event.pos):
                        engine.start_training()
                    elif gui.btn_phrases.collidepoint(event.pos):
                        engine.phrases_open = True
                elif engine.state == SPEAKING:
                    if gui.btn_stop.collidepoint(event.pos):
                        engine.stop_speaking()

        gui.draw(engine)
        clock.tick(60)

    engine.running = False
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
