#!/usr/bin/env python3
"""GUI rendering for the Car Assistant."""

import pygame
import math, time

from wakeup import LISTENING, SPEAKING, TRAINING, SLEEPING

# ── Colors & dimensions ───────────────────────────────────────────────────────
BG_TOP    = (5,  10, 28)
BG_BOT    = (8,  20, 52)
ACCENT    = (58, 143, 255)
ACCENT_DK = (20,  80, 200)
ACCENT_LT = (120, 200, 255)
WHITE     = (255, 255, 255)
DIM       = (120, 160, 210)
W, H      = 860, 640


# ── Loading screen ────────────────────────────────────────────────────────────
class LoadingScreen:
    """Animated screen shown while the engine calibrates the microphone."""

    def __init__(self, screen):
        self.screen      = screen
        self.spin_angle  = 0
        self.start_t     = time.time()
        self.f_title     = pygame.font.SysFont("Arial", 42, bold=False)
        self.f_sub       = pygame.font.SysFont("Arial", 16)
        self.f_hint      = pygame.font.SysFont("Arial", 13)

    def draw(self):
        for y in range(H):
            t = y / H
            r = int(BG_TOP[0] + t * (BG_BOT[0] - BG_TOP[0]))
            g = int(BG_TOP[1] + t * (BG_BOT[1] - BG_TOP[1]))
            b = int(BG_TOP[2] + t * (BG_BOT[2] - BG_TOP[2]))
            pygame.draw.line(self.screen, (r, g, b), (0, y), (W, y))

        cx, cy = W // 2, H // 2 - 40

        self.spin_angle = (self.spin_angle - 3) % 360
        for i in range(10):
            a   = math.radians(self.spin_angle + i * 36)
            pct = i / 9
            dot_r   = int(2 + pct * 4)
            alpha   = int(20 + pct * 235)
            dot_x   = cx + int(42 * math.cos(a))
            dot_y   = cy + int(42 * math.sin(a))
            dot_s   = pygame.Surface((dot_r * 2 + 2, dot_r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(dot_s, (*ACCENT_LT, alpha),
                               (dot_r + 1, dot_r + 1), dot_r)
            self.screen.blit(dot_s, (dot_x - dot_r - 1, dot_y - dot_r - 1))

        pulse = 0.65 + 0.35 * math.sin(time.time() * 4)
        pr = int(26 * pulse)
        glow = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*ACCENT, int(50 * pulse)), (40, 40), 38)
        self.screen.blit(glow, (cx - 40, cy - 40))
        pygame.draw.circle(self.screen, (8, 22, 70), (cx, cy), pr)
        pygame.draw.circle(self.screen, ACCENT_LT, (cx, cy), pr, 2)

        title = self.f_title.render("Car", True, (65, 125, 218))
        self.screen.blit(title, title.get_rect(center=(cx, cy + 72)))

        dots = "." * (int(time.time() * 2) % 4)
        sub  = self.f_sub.render(f"Loading{dots}", True, DIM)
        self.screen.blit(sub, sub.get_rect(center=(cx, cy + 104)))

        elapsed  = time.time() - self.start_t
        hint_txt = "Calibrating microphone…" if elapsed > 0.6 else "Starting up…"
        hint     = self.f_hint.render(hint_txt, True, (42, 72, 118))
        self.screen.blit(hint, hint.get_rect(center=(cx, cy + 126)))

        pygame.display.flip()


# ── Wave renderer (Siri-style) ────────────────────────────────────────────────
class WaveRenderer:
    _WAVES = [
        {"f": 0.022, "a": 44, "s": 0.058, "p": 0.0, "rgb": (58,  143, 255), "al": 200},
        {"f": 0.015, "a": 32, "s": 0.036, "p": 1.8, "rgb": (100, 200, 255), "al": 170},
        {"f": 0.034, "a": 25, "s": 0.074, "p": 3.5, "rgb": (20,   80, 200), "al": 185},
        {"f": 0.019, "a": 36, "s": 0.049, "p": 5.1, "rgb": (80,  160, 255), "al": 160},
        {"f": 0.028, "a": 19, "s": 0.065, "p": 2.4, "rgb": (140, 220, 255), "al": 140},
    ]

    def __init__(self):
        self.amp    = 0.0
        self.target = 0.0

    def set_active(self, on: bool):
        self.target = 1.0 if on else 0.0

    def update(self):
        for w in self._WAVES:
            w["p"] += w["s"]
        self.amp += (self.target - self.amp) * 0.07

    def draw(self, surf, cx: int, cy: int, width=460, height=90):
        if self.amp < 0.01:
            return
        ws = pygame.Surface((width, height), pygame.SRCALPHA)
        for wv in self._WAVES:
            pts = []
            for px in range(0, width, 2):
                t   = (px / width - 0.5) * 4.2
                env = math.exp(-t * t)
                py  = height // 2 + math.sin(px * wv["f"] + wv["p"]) * wv["a"] * self.amp * env
                pts.append((px, int(py)))
            if len(pts) > 1:
                r, g, b = wv["rgb"]
                a = int(wv["al"] * self.amp)
                pygame.draw.aalines(ws, (r, g, b, a), False, pts)
                ghost = [(p[0], p[1] - 1) for p in pts]
                pygame.draw.aalines(ws, (r, g, b, a // 3), False, ghost)
        surf.blit(ws, (cx - width // 2, cy - height // 2))


# ── RC car icon (simple flat side-view) ──────────────────────────────────────
def draw_rc_car(surf, cx: int, cy: int):
    """Simple flat 2-D RC car icon."""
    BODY  = (48, 110, 200)
    CAB   = (70, 145, 230)
    GLASS = (140, 210, 255)
    TIRE  = (20,  20,  30)
    RIM   = (180, 185, 200)
    EDGE  = (6,   14,  40)

    # Body
    body = pygame.Rect(cx - 40, cy - 6, 80, 18)
    pygame.draw.rect(surf, BODY, body, border_radius=5)
    pygame.draw.rect(surf, EDGE, body, 1, border_radius=5)

    # Cab bump
    cab = [
        (cx - 18, cy - 6),
        (cx - 10, cy - 24),
        (cx + 14, cy - 24),
        (cx + 20, cy - 6),
    ]
    pygame.draw.polygon(surf, CAB, cab)
    pygame.draw.polygon(surf, EDGE, cab, 1)

    # Windshield
    wind = [
        (cx - 8,  cy - 8),
        (cx - 2,  cy - 22),
        (cx + 10, cy - 22),
        (cx + 15, cy - 8),
    ]
    ws = pygame.Surface((surf.get_width(), surf.get_height()), pygame.SRCALPHA)
    pygame.draw.polygon(ws, (*GLASS, 100), wind)
    surf.blit(ws, (0, 0))

    # Rear spoiler
    pygame.draw.line(surf, BODY,  (cx - 36, cy - 6),  (cx - 36, cy - 16), 4)
    pygame.draw.rect(surf, BODY,  pygame.Rect(cx - 46, cy - 19, 22, 5), border_radius=2)
    pygame.draw.rect(surf, EDGE,  pygame.Rect(cx - 46, cy - 19, 22, 5), 1, border_radius=2)

    # Wheels
    for wx, wy, wr in [(cx + 26, cy + 14, 12), (cx - 24, cy + 14, 12)]:
        pygame.draw.circle(surf, TIRE, (wx, wy), wr)
        pygame.draw.circle(surf, EDGE, (wx, wy), wr, 1)
        pygame.draw.circle(surf, RIM,  (wx, wy), 6)
        pygame.draw.circle(surf, EDGE, (wx, wy), 6, 1)
        pygame.draw.circle(surf, EDGE, (wx, wy), 2)


# ── Main GUI class ────────────────────────────────────────────────────────────
class CarGUI:

    def __init__(self, screen):
        self.screen = screen
        self.wave   = WaveRenderer()

        self.f_sm    = pygame.font.SysFont("Arial", 11)
        self.f_title = pygame.font.SysFont("Arial", 50, bold=False)
        self.f_body  = pygame.font.SysFont("Arial", 17)
        self.f_small = pygame.font.SysFont("Arial", 13)

        self.orb_pulse = 0.0

        import random; random.seed(7)
        self.stars = [(random.randint(0, W), random.randint(0, H),
                       random.uniform(0.4, 1.8), random.uniform(0, math.pi * 2),
                       random.uniform(0.008, 0.025)) for _ in range(200)]

        # Button rects — updated each frame during draw
        self.btn_train   = pygame.Rect(0, 0, 0, 0)
        self.btn_phrases = pygame.Rect(0, 0, 0, 0)
        self.btn_stop    = pygame.Rect(0, 0, 0, 0)

        # Phrase overlay rects — updated each frame
        self._del_rects: list[tuple[pygame.Rect, int]] = []
        self._done_rect = pygame.Rect(0, 0, 0, 0)
        self._add_rect  = pygame.Rect(0, 0, 0, 0)

    # ── Background ────────────────────────────────────────────────────────────
    def _draw_gradient(self):
        for y in range(H):
            t = y / H
            r = int(BG_TOP[0] + t * (BG_BOT[0] - BG_TOP[0]))
            g = int(BG_TOP[1] + t * (BG_BOT[1] - BG_TOP[1]))
            b = int(BG_TOP[2] + t * (BG_BOT[2] - BG_TOP[2]))
            pygame.draw.line(self.screen, (r, g, b), (0, y), (W, y))

    def _draw_stars(self):
        new = []
        for x, y, r, ph, spd in self.stars:
            ph += spd
            a  = int(255 * max(0, 0.25 + 0.45 * math.sin(ph)))
            s  = pygame.Surface((int(r * 2) + 2, int(r * 2) + 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (140, 190, 255, a),
                               (int(r) + 1, int(r) + 1), max(1, int(r)))
            self.screen.blit(s, (x - r, y - r))
            new.append((x, y, r, ph, spd))
        self.stars = new

    # ── Orb ───────────────────────────────────────────────────────────────────
    def _draw_orb(self, cx, cy, r, state):
        listening = state in (LISTENING, SPEAKING, TRAINING)
        spd = 0.06 if listening else 0.022
        self.orb_pulse += spd

        for i in range(3):
            ph = (self.orb_pulse + i * 0.55) % (math.pi * 2)
            a  = int((0.35 + 0.55 * abs(math.sin(ph))) * 255) if listening \
                 else int((0.08 + 0.22 * math.sin(ph) ** 2) * 255)
            rr = r + 14 + i * 17 + int(5 * math.sin(ph))
            rs = pygame.Surface((rr * 2 + 4, rr * 2 + 4), pygame.SRCALPHA)
            col = (*ACCENT_LT, a) if listening else (*ACCENT, a)
            pygame.draw.circle(rs, col, (rr + 2, rr + 2), rr, 1)
            self.screen.blit(rs, (cx - rr - 2, cy - rr - 2))

        gr = r + (38 if listening else 26)
        gs = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
        for k in range(gr, r, -1):
            ga = int(60 * (1 - (k - r) / (gr - r)) * (1.8 if listening else 1.0))
            pygame.draw.circle(gs, (*ACCENT, ga), (gr, gr), k)
        self.screen.blit(gs, (cx - gr, cy - gr))

        pygame.draw.circle(self.screen, (8, 22, 70), (cx, cy), r)
        hl = pygame.Surface((r, r), pygame.SRCALPHA)
        pygame.draw.circle(hl, (40, 90, 185, 100), (r // 3, r // 3), r // 3)
        self.screen.blit(hl, (cx - r // 2, cy - r // 2))
        border_col = ACCENT_LT if listening else (60, 110, 210)
        pygame.draw.circle(self.screen, border_col, (cx, cy), r, 2)

        draw_rc_car(self.screen, cx - 2, cy - 4)

    # ── Text helpers ──────────────────────────────────────────────────────────
    def _centered(self, font, text, color, y, alpha=255):
        s = font.render(text, True, color)
        if alpha < 255:
            s.set_alpha(alpha)
        self.screen.blit(s, s.get_rect(center=(W // 2, y)))

    def _draw_response_box(self, text, y):
        if not text:
            return
        words = text.split()
        lines, line = [], []
        for w in words:
            test = " ".join(line + [w])
            if self.f_body.size(test)[0] > 540:
                lines.append(" ".join(line)); line = [w]
            else:
                line.append(w)
        if line:
            lines.append(" ".join(line))

        pad, lh = 16, 26
        bw = 580
        bh = len(lines) * lh + pad * 2
        bx = W // 2 - bw // 2

        box = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.rect(box, (30, 80, 180, 45),  (0, 0, bw, bh), border_radius=14)
        pygame.draw.rect(box, (*ACCENT, 60),       (0, 0, bw, bh), 1, border_radius=14)
        self.screen.blit(box, (bx, y))
        for i, ln in enumerate(lines):
            s = self.f_body.render(ln, True, WHITE)
            self.screen.blit(s, s.get_rect(center=(W // 2, y + pad + i * lh + lh // 2)))

    # ── Training UI ───────────────────────────────────────────────────────────
    def _draw_training_ui(self, train_msg, train_prog):
        hdr = self.f_sm.render("TRAINING MODE", True, ACCENT_LT)
        hdr.set_alpha(200)
        self.screen.blit(hdr, hdr.get_rect(center=(W // 2, 38)))

        if train_msg:
            self._centered(self.f_body, train_msg, ACCENT_LT, H // 2 + 80)

        done, total = train_prog
        bw, bh = 280, 8
        bx, by = W // 2 - bw // 2, H // 2 + 110
        bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.rect(bg, (40, 80, 160, 120), (0, 0, bw, bh), border_radius=4)
        self.screen.blit(bg, (bx, by))
        if done > 0 and total > 0:
            fw = int(bw * done / total)
            fg = pygame.Surface((fw, bh), pygame.SRCALPHA)
            pygame.draw.rect(fg, (*ACCENT, 220), (0, 0, fw, bh), border_radius=4)
            self.screen.blit(fg, (bx, by))

        pip_r   = 7
        spacing = 22
        total_w = (total - 1) * spacing
        start_x = W // 2 - total_w // 2
        dy = by + 26
        for k in range(total):
            dx  = start_x + k * spacing
            pip = pygame.Surface((pip_r * 2 + 2, pip_r * 2 + 2), pygame.SRCALPHA)
            if k < done:
                pygame.draw.circle(pip, (*ACCENT_LT, 255), (pip_r + 1, pip_r + 1), pip_r)
            else:
                pygame.draw.circle(pip, (50, 90, 160, 180), (pip_r + 1, pip_r + 1), pip_r)
                pygame.draw.circle(pip, (*ACCENT, 120),     (pip_r + 1, pip_r + 1), pip_r, 1)
            self.screen.blit(pip, (dx - pip_r - 1, dy - pip_r - 1))

    # ── Buttons ───────────────────────────────────────────────────────────────
    def _draw_buttons(self):
        by = H - 56
        self.btn_train = pygame.Rect(W // 2 - 136, by, 118, 36)
        bs = pygame.Surface((118, 36), pygame.SRCALPHA)
        pygame.draw.rect(bs, (20, 58, 140, 190), (0, 0, 118, 36), border_radius=10)
        pygame.draw.rect(bs, (*ACCENT, 90),       (0, 0, 118, 36), 1, border_radius=10)
        self.screen.blit(bs, self.btn_train.topleft)
        tt = self.f_small.render("⚙  Train Voice", True, DIM)
        self.screen.blit(tt, tt.get_rect(center=self.btn_train.center))

        self.btn_phrases = pygame.Rect(W // 2 + 18, by, 118, 36)
        ps = pygame.Surface((118, 36), pygame.SRCALPHA)
        pygame.draw.rect(ps, (20, 58, 140, 190), (0, 0, 118, 36), border_radius=10)
        pygame.draw.rect(ps, (*ACCENT, 90),       (0, 0, 118, 36), 1, border_radius=10)
        self.screen.blit(ps, self.btn_phrases.topleft)
        pt = self.f_small.render("⊞  Wake Phrases", True, DIM)
        self.screen.blit(pt, pt.get_rect(center=self.btn_phrases.center))

    def _draw_stop_button(self):
        self.btn_stop = pygame.Rect(W // 2 - 76, H - 56, 152, 36)
        bs = pygame.Surface((152, 36), pygame.SRCALPHA)
        pygame.draw.rect(bs, (140, 30, 30, 210), (0, 0, 152, 36), border_radius=10)
        pygame.draw.rect(bs, (220, 80, 80, 140), (0, 0, 152, 36), 1, border_radius=10)
        self.screen.blit(bs, self.btn_stop.topleft)
        tt = self.f_small.render("■  Stop Speaking", True, WHITE)
        self.screen.blit(tt, tt.get_rect(center=self.btn_stop.center))

    # ── Phrases overlay ───────────────────────────────────────────────────────
    def _draw_phrases_overlay(self, engine):
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((4, 10, 28, 215))
        self.screen.blit(ov, (0, 0))

        bw = 500
        bh = min(120 + len(engine.wake_phrases) * 50 + 140, H - 80)
        bx, by = (W - bw) // 2, (H - bh) // 2
        box = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.rect(box, (10, 28, 72, 245), (0, 0, bw, bh), border_radius=16)
        pygame.draw.rect(box, (*ACCENT, 110),     (0, 0, bw, bh), 1, border_radius=16)
        self.screen.blit(box, (bx, by))

        title = self.f_sm.render("WAKE PHRASES", True, ACCENT_LT)
        self.screen.blit(title, title.get_rect(center=(W // 2, by + 26)))

        self._del_rects = []
        for idx, phrase in enumerate(engine.wake_phrases):
            py   = by + 52 + idx * 48
            chip = pygame.Surface((bw - 60, 38), pygame.SRCALPHA)
            pygame.draw.rect(chip, (28, 76, 180, 90), (0, 0, bw - 60, 38), border_radius=9)
            pygame.draw.rect(chip, (*ACCENT, 70),     (0, 0, bw - 60, 38), 1, border_radius=9)
            self.screen.blit(chip, (bx + 30, py))
            pt = self.f_body.render(f'"{phrase}"', True, WHITE)
            self.screen.blit(pt, (bx + 46, py + 9))

            if len(engine.wake_phrases) > 1:
                del_rect = pygame.Rect(bx + bw - 55, py + 6, 26, 26)
                self._del_rects.append((del_rect, idx))
                ds = pygame.Surface((26, 26), pygame.SRCALPHA)
                pygame.draw.rect(ds, (160, 50, 50, 180), (0, 0, 26, 26), border_radius=7)
                self.screen.blit(ds, del_rect.topleft)
                xt = self.f_small.render("✕", True, WHITE)
                self.screen.blit(xt, xt.get_rect(center=del_rect.center))

        inp_y    = by + 52 + len(engine.wake_phrases) * 48 + 10
        inp_rect = pygame.Rect(bx + 30, inp_y, bw - 120, 38)
        inp_s    = pygame.Surface((inp_rect.width, 38), pygame.SRCALPHA)
        pygame.draw.rect(inp_s, (18, 48, 120, 160), (0, 0, inp_rect.width, 38), border_radius=9)
        pygame.draw.rect(inp_s, (*ACCENT, 130),     (0, 0, inp_rect.width, 38), 1, border_radius=9)
        self.screen.blit(inp_s, inp_rect.topleft)

        cursor   = "|" if int(time.time() * 2) % 2 == 0 else " "
        inp_text = (engine.phrases_input + cursor) if engine.phrases_input else "type new phrase…"
        inp_col  = WHITE if engine.phrases_input else (80, 120, 170)
        it = self.f_body.render(inp_text, True, inp_col)
        self.screen.blit(it, (inp_rect.x + 10, inp_rect.y + 9))

        self._add_rect = pygame.Rect(bx + bw - 82, inp_y, 52, 38)
        ad = pygame.Surface((52, 38), pygame.SRCALPHA)
        pygame.draw.rect(ad, (*ACCENT_DK, 210), (0, 0, 52, 38), border_radius=9)
        self.screen.blit(ad, self._add_rect.topleft)
        at = self.f_small.render("ADD", True, WHITE)
        self.screen.blit(at, at.get_rect(center=self._add_rect.center))

        self._done_rect = pygame.Rect(W // 2 - 55, by + bh - 48, 110, 36)
        ds2 = pygame.Surface((110, 36), pygame.SRCALPHA)
        pygame.draw.rect(ds2, (28, 100, 210, 220), (0, 0, 110, 36), border_radius=10)
        self.screen.blit(ds2, self._done_rect.topleft)
        dt = self.f_body.render("Done", True, WHITE)
        self.screen.blit(dt, dt.get_rect(center=self._done_rect.center))

        hint = self.f_small.render("Enter to add  ·  Esc to close", True, (70, 110, 170))
        self.screen.blit(hint, hint.get_rect(center=(W // 2, by + bh - 10)))

    # ── Main draw ─────────────────────────────────────────────────────────────
    def draw(self, engine):
        self._draw_gradient()
        self._draw_stars()

        with engine._lock:
            state    = engine.state
            status   = engine.status_text
            response = engine.response_text
            trans    = engine.transcript
            tmsg     = engine.train_msg
            tprog    = engine.train_prog

        cx, cy = W // 2, 218
        orb_r  = 75

        self._draw_orb(cx, cy, orb_r, state)

        brand = self.f_sm.render("VOICE ASSISTANT", True, (80, 140, 210))
        brand.set_alpha(130)
        self.screen.blit(brand, brand.get_rect(center=(cx, cy - orb_r - 46)))

        tc = ACCENT_LT if state in (LISTENING, SPEAKING) else (65, 125, 218)
        self._centered(self.f_title, "Car", tc, cy + orb_r + 30)

        if state == TRAINING:
            self.wave.set_active(True)
            self.wave.update()
            self.wave.draw(self.screen, cx, cy + orb_r + 88, width=460, height=90)
            self._draw_training_ui(tmsg, tprog)
        else:
            self.wave.set_active(state in (LISTENING, SPEAKING))
            self.wave.update()
            self.wave.draw(self.screen, cx, cy + orb_r + 88, width=460, height=90)

            sc = ACCENT_LT if state in (LISTENING, SPEAKING) else (95, 148, 212)
            self._centered(self.f_body, status, sc, cy + orb_r + 158)

            self._draw_response_box(response, cy + orb_r + 190)

            if trans:
                self._centered(self.f_small, trans, (85, 118, 175), H - 34, alpha=160)

            if state == SLEEPING:
                self._draw_buttons()
            elif state == SPEAKING:
                self._draw_stop_button()

        if engine.phrases_open:
            self._draw_phrases_overlay(engine)

        hint_key = "SPACE = wake  |  S = stop  |  ESC = quit"
        hint = self.f_small.render(hint_key, True, (42, 72, 118))
        self.screen.blit(hint, hint.get_rect(bottomright=(W - 10, H - 6)))

        pygame.display.flip()
