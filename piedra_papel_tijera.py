#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=====================================================================
  PIEDRA · PAPEL · TIJERA  —  ARENA DE LEYENDAS
=====================================================================
  * 2 a 6 jugadores (en el mismo equipo, por turnos y en secreto)
    o 1 jugador contra 1-5 CPUs.
  * Pantalla completa, 8 niveles con dificultad creciente.
  * Sonidos y música generados por código (no necesita archivos).
  * Botones: JUGAR, SONIDO (ON/OFF), PAUSA, MENÚ y SALIR.

  Requisitos:   pip install pygame
  Ejecutar:     python piedra_papel_tijera.py

  Controles:
    Ratón ............ pulsar botones y elegir cartas
    1 / 2 / 3 ........ Piedra / Papel / Tijera  (también R / P / T)
    ESPACIO / ENTER .. continuar
    M ................ sonido ON/OFF
    ESC .............. pausa (en el menú: salir)
    F11 .............. pantalla completa / ventana
=====================================================================
"""
import array
import math
import random
import sys

import pygame

W, H = 1280, 720
FPS = 60

CHOICES = ["piedra", "papel", "tijera"]
BEATS = {"piedra": "tijera", "papel": "piedra", "tijera": "papel"}  # clave vence a valor
NAMES = {"piedra": "PIEDRA", "papel": "PAPEL", "tijera": "TIJERA"}
REASONS = {
    "piedra": "¡LA PIEDRA APLASTA A LA TIJERA!",
    "papel": "¡EL PAPEL ENVUELVE A LA PIEDRA!",
    "tijera": "¡LA TIJERA CORTA EL PAPEL!",
}
CHOICE_COL = {"piedra": (150, 165, 200), "papel": (90, 170, 255), "tijera": (255, 110, 140)}
PLAYER_COLS = [(255, 95, 100), (90, 175, 255), (95, 230, 145),
               (255, 215, 90), (195, 125, 255), (255, 155, 75)]

WHITE = (255, 255, 255)
GOLD = (255, 214, 70)
DARK = (12, 10, 36)

LEVELS = [
    dict(name="DESIERTO", target=3, time=10, smart=0.00,
         top=(255, 176, 80), bottom=(190, 60, 70), accent=(255, 225, 140)),
    dict(name="BOSQUE", target=3, time=9, smart=0.10,
         top=(70, 200, 140), bottom=(20, 90, 100), accent=(190, 255, 170)),
    dict(name="OCÉANO", target=4, time=8, smart=0.20,
         top=(60, 170, 255), bottom=(20, 50, 150), accent=(160, 230, 255)),
    dict(name="VOLCÁN", target=4, time=7, smart=0.30,
         top=(255, 110, 60), bottom=(110, 15, 45), accent=(255, 205, 100)),
    dict(name="CIUDAD NEÓN", target=4, time=6, smart=0.40,
         top=(255, 60, 200), bottom=(50, 10, 110), accent=(120, 255, 240)),
    dict(name="HIELO ETERNO", target=5, time=5, smart=0.50,
         top=(150, 220, 255), bottom=(60, 90, 190), accent=(255, 255, 255)),
    dict(name="ESPACIO", target=5, time=5, smart=0.60,
         top=(110, 70, 220), bottom=(10, 10, 45), accent=(255, 230, 120)),
    dict(name="LEYENDA", target=6, time=4, smart=0.70,
         top=(255, 215, 80), bottom=(120, 20, 150), accent=(255, 255, 255)),
]
MENU_THEME = dict(name="MENÚ", top=(125, 65, 225), bottom=(18, 14, 70), accent=(255, 225, 120))

BTN_GREEN = ((100, 235, 145), (30, 150, 90))
BTN_BLUE = ((100, 180, 255), (45, 95, 205))
BTN_RED = ((255, 110, 120), (190, 35, 75))
BTN_PURPLE = ((200, 130, 255), (110, 50, 190))
BTN_GOLD = ((255, 225, 100), (235, 140, 30))

GAME_STATES = {"intro", "pass", "choose", "reveal", "level_done", "level_lost"}


# ======================================================================
#  UTILIDADES
# ======================================================================
def lerp(a, b, t):
    return a + (b - a) * t


def lerp_col(c1, c2, t):
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))


_fonts = {}


def font(size):
    size = int(size)
    f = _fonts.get(size)
    if f is None:
        f = pygame.font.SysFont("arialblack,impact,verdana,dejavusans,arial", size, bold=True)
        _fonts[size] = f
    return f


def draw_text(surf, text, size, x, y, color=WHITE, anchor="center", shadow=True):
    f = font(size)
    img = f.render(text, True, color)
    r = img.get_rect()
    setattr(r, anchor, (x, y))
    if shadow:
        sh = f.render(text, True, (0, 0, 0))
        sh.set_alpha(120)
        surf.blit(sh, r.move(3, 4))
    surf.blit(img, r)
    return r


def draw_wave_text(surf, text, size, cx, cy, t, amp=7):
    """Texto con letras que suben y bajan y cambian de color."""
    f = font(size)
    widths = [f.size(ch)[0] for ch in text]
    x = cx - sum(widths) / 2
    for i, ch in enumerate(text):
        if ch != " ":
            c = pygame.Color(0)
            c.hsva = ((t * 50 + i * 16) % 360, 70, 100, 100)
            img = f.render(ch, True, (c.r, c.g, c.b))
            sh = f.render(ch, True, (0, 0, 0))
            sh.set_alpha(130)
            y = cy + math.sin(t * 3 + i * 0.5) * amp - img.get_height() / 2
            surf.blit(sh, (x + 3, y + 5))
            surf.blit(img, (x, y))
        x += widths[i]


_cache = {}


def grad_rect(w, h, c1, c2, radius):
    """Rectángulo redondeado con degradado vertical (con caché)."""
    w, h = max(2, int(w)), max(2, int(h))
    key = ("g", w, h, c1, c2, radius)
    s = _cache.get(key)
    if s is None:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(h):
            col = lerp_col(c1, c2, y / max(1, h - 1))
            pygame.draw.line(s, col, (0, y), (w, y))
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, w, h), border_radius=radius)
        s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        _cache[key] = s
    return s


def glow_surf(r, color, strength=120):
    r = int(r)
    key = ("glow", r, color, strength)
    s = _cache.get(key)
    if s is None:
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        steps = 26
        for i in range(steps, 0, -1):
            a = int(strength * (1 - i / steps) ** 1.6)
            pygame.draw.circle(s, (color[0], color[1], color[2], a), (r, r), int(r * i / steps))
        _cache[key] = s
    return s


def draw_star(surf, cx, cy, r, color, outline=None):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.42
        pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
    pygame.draw.polygon(surf, color, pts)
    if outline:
        pygame.draw.polygon(surf, outline, pts, 2)


def draw_heart(surf, cx, cy, r, color):
    pygame.draw.circle(surf, color, (cx - r * 0.5, cy - r * 0.3), r * 0.55)
    pygame.draw.circle(surf, color, (cx + r * 0.5, cy - r * 0.3), r * 0.55)
    pygame.draw.polygon(surf, color, [(cx - r * 1.02, cy - r * 0.05), (cx + r * 1.02, cy - r * 0.05),
                                      (cx, cy + r * 1.05)])


def draw_btn_icon(surf, kind, cx, cy, s, color, muted=False):
    if kind == "sound":
        pygame.draw.polygon(surf, color, [(cx - s * .6, cy - s * .25), (cx - s * .2, cy - s * .25),
                                          (cx + s * .25, cy - s * .65), (cx + s * .25, cy + s * .65),
                                          (cx - s * .2, cy + s * .25), (cx - s * .6, cy + s * .25)])
        if muted:
            pygame.draw.line(surf, color, (cx + s * .45, cy - s * .35), (cx + s * .95, cy + s * .35), 3)
            pygame.draw.line(surf, color, (cx + s * .95, cy - s * .35), (cx + s * .45, cy + s * .35), 3)
        else:
            for k in (1, 2):
                rect = pygame.Rect(0, 0, s * .6 * k, s * .8 * k)
                rect.center = (cx + s * .25, cy)
                pygame.draw.arc(surf, color, rect, -0.9, 0.9, 3)
    elif kind == "exit":
        rect = pygame.Rect(0, 0, s * 1.3, s * 1.3)
        rect.center = (cx, cy + 2)
        pygame.draw.arc(surf, color, rect, math.radians(-50), math.radians(230), 3)
        pygame.draw.line(surf, color, (cx, cy - s * .7), (cx, cy), 3)
    elif kind == "pause":
        pygame.draw.rect(surf, color, (cx - s * .5, cy - s * .6, s * .35, s * 1.2), border_radius=2)
        pygame.draw.rect(surf, color, (cx + s * .15, cy - s * .6, s * .35, s * 1.2), border_radius=2)
    elif kind == "play":
        pygame.draw.polygon(surf, color, [(cx - s * .45, cy - s * .7), (cx - s * .45, cy + s * .7),
                                          (cx + s * .7, cy)])
    elif kind == "home":
        pygame.draw.polygon(surf, color, [(cx - s * .8, cy), (cx, cy - s * .75), (cx + s * .8, cy)])
        pygame.draw.rect(surf, color, (cx - s * .5, cy, s, s * .7))


# ======================================================================
#  ICONOS DE PIEDRA / PAPEL / TIJERA (dibujados por código)
# ======================================================================
def _draw_rock(s, S):
    c = S // 2
    rnd = random.Random(7)
    n = 15
    cy = c + 0.06 * S
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        r = S * 0.40 * (0.86 + 0.16 * rnd.random())
        pts.append((c + math.cos(a) * r * 1.08, cy + math.sin(a) * r * 0.88))
    pygame.draw.polygon(s, (0, 0, 0, 70), [(x + S * .03, y + S * .04) for x, y in pts])
    pygame.draw.polygon(s, (88, 94, 114), pts)
    mid = [(c + (x - c) * .90 - S * .015, cy + (y - cy) * .90 - S * .02) for x, y in pts]
    pygame.draw.polygon(s, (132, 140, 160), mid)
    hi = [(c + (x - c) * .60 - S * .07, cy + (y - cy) * .52 - S * .09) for x, y in pts]
    pygame.draw.polygon(s, (186, 194, 212), hi)
    hi2 = [(c + (x - c) * .28 - S * .10, cy + (y - cy) * .25 - S * .13) for x, y in pts]
    pygame.draw.polygon(s, (225, 230, 242), hi2)
    wd = max(2, S // 55)
    pygame.draw.lines(s, (62, 68, 88), False,
                      [(c + S * .08, c - S * .06), (c + S * .14, c + S * .05), (c + S * .08, c + S * .17)], wd)
    pygame.draw.lines(s, (62, 68, 88), False,
                      [(c - S * .17, c + S * .12), (c - S * .10, c + S * .20)], wd)
    pygame.draw.polygon(s, (50, 55, 75), pts, max(2, S // 45))


def _draw_paper(s, S):
    c = S // 2
    w, h = S * 0.62, S * 0.78
    r = pygame.Rect(0, 0, int(w), int(h))
    r.center = (c, c)
    br = S // 18
    pygame.draw.rect(s, (0, 0, 0, 70), r.move(int(S * .03), int(S * .04)), border_radius=br)
    pygame.draw.rect(s, (250, 250, 255), r, border_radius=br)
    for i in range(6):
        y = r.top + h * (0.24 + 0.115 * i)
        x2 = r.right - w * 0.15 - (w * 0.25 if i == 5 else 0)
        pygame.draw.line(s, (110, 165, 235), (r.left + w * .15, y), (x2, y), max(2, S // 70))
    pygame.draw.line(s, (255, 130, 140), (r.left + w * .08, r.top + h * .06),
                     (r.left + w * .08, r.bottom - h * .06), max(2, S // 90))
    fold = S * 0.18
    pygame.draw.polygon(s, (0, 0, 0, 0), [(r.right - fold, r.top - 2), (r.right + 2, r.top - 2),
                                           (r.right + 2, r.top + fold)])
    pygame.draw.polygon(s, (196, 212, 242), [(r.right - fold, r.top), (r.right - fold, r.top + fold),
                                              (r.right, r.top + fold)])
    pygame.draw.lines(s, (150, 170, 210), False, [(r.right - fold, r.top), (r.right - fold, r.top + fold),
                                                   (r.right, r.top + fold)], max(2, S // 80))
    pygame.draw.line(s, (150, 170, 210), (r.right - fold, r.top), (r.right, r.top + fold), max(2, S // 80))
    pygame.draw.rect(s, (150, 170, 210), r, max(2, S // 70), border_radius=br)


def _draw_scissors(s, S):
    c = S // 2
    piv = (c, c + S * 0.05)

    def arm(angle, handle_col):
        a = math.radians(angle)
        dx, dy = math.cos(a), math.sin(a)
        px, py = -dy, dx
        L, wd = S * 0.50, S * 0.075
        tip = (piv[0] + dx * L, piv[1] + dy * L)
        hc = (piv[0] - dx * S * 0.31, piv[1] - dy * S * 0.31)
        # mango (anillo)
        pygame.draw.line(s, handle_col, piv, hc, max(4, int(S * .07)))
        rr = S * 0.135
        pygame.draw.circle(s, handle_col, hc, rr)
        pygame.draw.circle(s, (0, 0, 0, 0), hc, rr * 0.58)
        pygame.draw.circle(s, (40, 30, 60), hc, rr, max(2, S // 70))
        # hoja
        blade = [(piv[0] + px * wd, piv[1] + py * wd), tip, (piv[0] - px * wd * 0.9, piv[1] - py * wd * 0.9)]
        pygame.draw.polygon(s, (205, 212, 226), blade)
        pygame.draw.line(s, (255, 255, 255), (piv[0] + px * wd * .35, piv[1] + py * wd * .35),
                         (tip[0] - dx * S * .02, tip[1] - dy * S * .02), max(2, S // 60))
        pygame.draw.polygon(s, (90, 98, 120), blade, max(2, S // 80))

    arm(-62, (255, 85, 100))
    arm(-118, (255, 170, 60))
    pygame.draw.circle(s, (70, 76, 100), piv, S * 0.045)
    pygame.draw.circle(s, (230, 235, 245), piv, S * 0.03)


def get_icon(kind, size):
    size = max(8, int(size) // 4 * 4)
    key = ("icon", kind, size)
    img = _cache.get(key)
    if img is None:
        S = size * 2
        raw = pygame.Surface((S, S), pygame.SRCALPHA)
        {"piedra": _draw_rock, "papel": _draw_paper, "tijera": _draw_scissors}[kind](raw, S)
        img = pygame.transform.smoothscale(raw, (size, size))
        _cache[key] = img
    return img


# ======================================================================
#  AUDIO (todo generado con matemáticas, sin archivos)
# ======================================================================
def wave(kind, ph):
    if kind == "sine":
        return math.sin(ph)
    if kind == "square":
        return 1.0 if math.sin(ph) >= 0 else -1.0
    if kind == "saw":
        return ((ph / 6.283185307) % 1.0) * 2 - 1
    # triangle
    return 2 * abs(((ph / 6.283185307) % 1.0) * 2 - 1) - 1


def nf(semi):
    """Frecuencia a 'semi' semitonos de La4 (440 Hz)."""
    return 440.0 * 2 ** (semi / 12.0)


class Audio:
    def __init__(self):
        self.ok = False
        self.muted = False
        self.sfx = {}
        self.music = {}
        self.cur_music = None
        self.rate, self.ch = 44100, 1
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(44100, -16, 1, 512)
            info = pygame.mixer.get_init()
            if not info or info[1] != -16 or info[2] not in (1, 2):
                return
            self.rate, _, self.ch = info
            pygame.mixer.set_num_channels(16)
            pygame.mixer.set_reserved(1)
            self.music_ch = pygame.mixer.Channel(0)
            self.build_sfx()
            self.ok = True
        except Exception as exc:  # sin audio disponible: el juego sigue funcionando
            print("Audio desactivado:", exc)
            self.ok = False

    # ---- generadores ------------------------------------------------
    def _snd(self, samples, vol=0.7):
        data = array.array("h")
        for s in samples:
            v = int(max(-1.0, min(1.0, s * vol)) * 32767)
            data.append(v)
            if self.ch == 2:
                data.append(v)
        return pygame.mixer.Sound(buffer=data.tobytes())

    def tone(self, freq, dur, kind="sine", vol=1.0, slide=None, decay=4.0, attack=0.004):
        r = self.rate
        n = max(1, int(r * dur))
        out = [0.0] * n
        ph = 0.0
        att = r * attack + 1
        for i in range(n):
            t = i / n
            f = freq if slide is None else freq + (slide - freq) * t
            ph += 6.283185307 * f / r
            env = min(1.0, i / att) * math.exp(-decay * t)
            out[i] = wave(kind, ph) * env * vol
        return out

    def noise(self, dur, vol=1.0, lp0=0.3, lp1=None, shape=1.0):
        n = max(1, int(self.rate * dur))
        out = [0.0] * n
        y = 0.0
        lp1 = lp0 if lp1 is None else lp1
        for i in range(n):
            t = i / n
            y += (random.uniform(-1, 1) - y) * (lp0 + (lp1 - lp0) * t)
            out[i] = y * (math.sin(math.pi * t) ** shape) * vol * 2.0
        return out

    @staticmethod
    def mix(*tracks):
        n = max(len(t) for t in tracks)
        out = [0.0] * n
        for t in tracks:
            for i, v in enumerate(t):
                out[i] += v
        return out

    @staticmethod
    def cat(*tracks):
        out = []
        for t in tracks:
            out += t
        return out

    def silence(self, dur):
        return [0.0] * int(self.rate * dur)

    def build_sfx(self):
        T, N, mix, cat = self.tone, self.noise, self.mix, self.cat

        def mk(name, samples, vol=0.7):
            self.sfx[name] = self._snd(samples, vol)

        mk("click", T(880, 0.07, "square", 0.5, decay=7), 0.5)
        mk("hover", T(1300, 0.035, "sine", 0.6, decay=5), 0.3)
        mk("back", T(520, 0.12, "tri", 0.9, slide=260, decay=4), 0.6)
        mk("tick", T(1000, 0.06, "square", 0.5, decay=8), 0.45)
        mk("go", mix(T(660, 0.3, "square", 0.4, slide=1320, decay=3),
                     T(330, 0.3, "saw", 0.3, slide=660, decay=3)), 0.6)
        # un sonido distinto para cada elección
        mk("piedra", mix(T(150, 0.35, "sine", 1.0, slide=40, decay=5),
                         N(0.18, 0.7, 0.12, 0.05)), 0.9)
        mk("papel", N(0.42, 0.9, 0.08, 0.6, 1.2), 0.8)
        snip = lambda f: mix(T(f, 0.06, "square", 0.3, decay=8), N(0.05, 0.4, 0.9))
        mk("tijera", cat(snip(2400), self.silence(0.05), snip(3000)), 0.6)
        mk("reveal", mix(T(300, 0.35, "saw", 0.4, slide=1200, decay=2), N(0.3, 0.5, 0.4)), 0.6)
        mk("win", cat(*[T(nf(s), 0.13, "tri", 0.9, decay=3) for s in (3, 7, 10, 15)],
                      T(nf(15), 0.45, "saw", 0.4, decay=3)), 0.7)
        mk("lose", cat(T(nf(3), 0.2, "saw", 0.5, decay=2), T(nf(0), 0.2, "saw", 0.5, decay=2),
                       T(nf(-4), 0.5, "saw", 0.5, slide=nf(-9), decay=2)), 0.6)
        mk("tie", cat(T(nf(0), 0.14, "tri", 0.9), T(nf(0), 0.24, "tri", 0.9)), 0.7)
        mk("levelup", cat(*[T(nf(s), d, "square", 0.4, decay=2.5) for s, d in
                            ((3, .1), (3, .1), (3, .1), (7, .28), (5, .12), (10, .12), (15, .5))]), 0.6)
        mk("champion", cat(*[T(nf(s), d, "saw", 0.4, decay=2) for s, d in
                             ((3, .14), (7, .14), (10, .14), (15, .28), (10, .14), (15, .14), (19, .6))],
                           T(nf(22), 0.8, "tri", 0.7, decay=2)), 0.65)
        mk("gameover", cat(T(nf(0), 0.25, "saw", 0.5, decay=2), T(nf(-3), 0.25, "saw", 0.5, decay=2),
                           T(nf(-7), 0.25, "saw", 0.5, decay=2), T(nf(-12), 0.8, "saw", 0.5, decay=2)), 0.6)

    def _note(self, buf, freq, start, dur, vol, kind, decay):
        r = self.rate
        s0 = int(start * r)
        m = int(dur * r)
        ph = 0.0
        n = len(buf)
        step = 6.283185307 * freq / r
        for i in range(m):
            j = s0 + i
            if j >= n:
                break
            ph += step
            env = min(1.0, i / 150.0) * math.exp(-decay * i / m)
            buf[j] += wave(kind, ph) * env * vol

    def _kick(self, buf, start):
        r = self.rate
        s0 = int(start * r)
        m = int(0.12 * r)
        ph = 0.0
        for i in range(m):
            j = s0 + i
            if j >= len(buf):
                break
            t = i / m
            ph += 6.283185307 * (45 + 90 * (1 - t) ** 2) / r
            buf[j] += math.sin(ph) * (1 - t) * 0.7

    def make_music(self, idx):
        """Música en bucle: cada nivel tiene su tono y velocidad."""
        bpm = 96 + idx * 9
        beat = 60.0 / bpm
        n = int(16 * beat * self.rate)
        buf = [0.0] * n
        root = [0, 0, 2, -2, 3, 5, -4, 7, 1][idx]
        prog = [(0, (0, 3, 7)), (-4, (0, 4, 7)), (3, (0, 4, 7)), (-2, (0, 4, 7))]
        pattern = (0, 1, 2, 1, 0, 1, 2, 1)
        for bar, (r, chord) in enumerate(prog):
            b0 = bar * 4 * beat
            f_root = 220.0 * 2 ** ((root + r) / 12.0)
            for k in range(4):
                self._note(buf, f_root / 2, b0 + k * beat, beat * 0.6, 0.45, "tri", 5)
                self._kick(buf, b0 + k * beat)
            for k in range(8):
                f = f_root * 2 ** ((chord[pattern[k]] + 12) / 12.0)
                self._note(buf, f, b0 + k * beat / 2, min(0.22, beat * 0.5), 0.22, "square", 4)
        peak = max(1e-6, max(abs(v) for v in buf))
        buf = [v / peak * 0.9 for v in buf]
        return self._snd(buf, 1.0)

    # ---- reproducción -----------------------------------------------
    def play(self, name):
        if self.ok and not self.muted:
            s = self.sfx.get(name)
            if s:
                s.play()

    def play_music(self, idx):
        if not self.ok:
            return
        if idx not in self.music:
            self.music[idx] = self.make_music(idx)
        snd = self.music[idx]
        if self.cur_music is not snd:
            self.music_ch.play(snd, loops=-1)
            self.cur_music = snd
        self.apply_volume()

    def apply_volume(self):
        if self.ok and self.cur_music:
            self.cur_music.set_volume(0.0 if self.muted else 0.33)

    def toggle(self):
        self.muted = not self.muted
        self.apply_volume()
        self.play("click")


# ======================================================================
#  FONDO ANIMADO, CONFETI Y BOTONES
# ======================================================================
class Background:
    def __init__(self):
        rnd = random.Random(3)
        self.t = 0.0
        self.blobs = [[rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(.15, .5),
                       rnd.uniform(160, 260), rnd.uniform(0, 6.28)] for _ in range(4)]
        self.stars = [[rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(8, 30),
                       rnd.uniform(1, 3), rnd.uniform(0, 6.28)] for _ in range(80)]
        self.floaters = [[rnd.uniform(0, W), rnd.uniform(0, H), rnd.choice(CHOICES),
                          rnd.uniform(15, 40), rnd.choice((70, 90, 110)),
                          rnd.uniform(0, 360), rnd.uniform(-25, 25)] for _ in range(10)]

    def gradient(self, top, bottom):
        key = ("bg", top, bottom)
        s = _cache.get(key)
        if s is None:
            s = pygame.Surface((W, H))
            for y in range(H):
                pygame.draw.line(s, lerp_col(top, bottom, y / H), (0, y), (W, y))
            _cache[key] = s
        return s

    def update(self, dt):
        self.t += dt
        for b in self.blobs:
            b[0] += math.cos(b[4] + self.t * .2) * 18 * dt
            b[1] += math.sin(b[4] + self.t * .25) * 14 * dt
        for st in self.stars:
            st[1] -= st[2] * dt
            if st[1] < -5:
                st[1] = H + 5
                st[0] = random.uniform(0, W)
        for f in self.floaters:
            f[1] -= f[3] * dt
            f[5] += f[6] * dt
            if f[1] < -120:
                f[1] = H + 120
                f[0] = random.uniform(0, W)

    def draw(self, surf, th):
        surf.blit(self.gradient(th["top"], th["bottom"]), (0, 0))
        acc = th["accent"]
        for b in self.blobs:
            g = glow_surf(b[3], acc, int(70 * b[2] + 20))
            surf.blit(g, (b[0] - b[3], b[1] - b[3]))
        for st in self.stars:
            tw = 0.5 + 0.5 * math.sin(self.t * 2 + st[4])
            col = lerp_col(lerp_col(th["top"], th["bottom"], st[1] / H), acc, 0.35 + 0.5 * tw)
            pygame.draw.circle(surf, col, (st[0], st[1]), st[3] * (0.7 + 0.5 * tw))
        for f in self.floaters:
            ic = pygame.transform.rotozoom(get_icon(f[2], f[4]), f[5], 1.0)
            ic.set_alpha(45)
            surf.blit(ic, ic.get_rect(center=(f[0], f[1])))


class Confetti:
    COLS = [(255, 90, 100), (90, 175, 255), (95, 230, 145), (255, 215, 90), (195, 125, 255), (255, 255, 255)]

    def __init__(self):
        self.p = []

    def burst(self, n=120):
        for _ in range(n):
            self.p.append([random.uniform(0, W), random.uniform(-200, 0), random.uniform(-60, 60),
                           random.uniform(120, 360), random.choice(self.COLS), random.uniform(7, 14),
                           random.uniform(0, 6.28), random.uniform(-8, 8)])

    def update(self, dt):
        for q in self.p:
            q[0] += q[2] * dt
            q[1] += q[3] * dt
            q[2] += math.sin(q[6] * 2) * 40 * dt
            q[6] += q[7] * dt
        self.p = [q for q in self.p if q[1] < H + 30]

    def draw(self, surf):
        for q in self.p:
            c, s = math.cos(q[6]), math.sin(q[6])
            w, h = q[5], q[5] * 0.55
            pts = [(q[0] + x * c - y * s, q[1] + x * s + y * c)
                   for x, y in ((-w, -h), (w, -h), (w, h), (-w, h))]
            pygame.draw.polygon(surf, q[4], pts)


class Button:
    def __init__(self, label, cx, cy, w, h, colors, action, size=30, icon=None):
        self.label = label
        self.base = pygame.Rect(0, 0, w, h)
        self.base.center = (cx, cy)
        self.rect = self.base.copy()
        self.colors = colors
        self.action = action
        self.size = size
        self.icon = icon
        self.s = 1.0
        self.hover = False

    def text(self):
        return self.label() if callable(self.label) else self.label

    def update(self, dt, mouse, audio):
        over = self.base.collidepoint(mouse)
        if over and not self.hover:
            audio.play("hover")
        self.hover = over
        self.s += ((1.08 if over else 1.0) - self.s) * min(1.0, dt * 14)
        self.rect = pygame.Rect(0, 0, int(self.base.w * self.s), int(self.base.h * self.s))
        self.rect.center = self.base.center

    def draw(self, surf, audio):
        r = self.rect
        rad = r.h // 2
        sh = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        pygame.draw.rect(sh, (0, 0, 0, 90), sh.get_rect(), border_radius=rad)
        surf.blit(sh, (r.x + 3, r.y + 7))
        c1, c2 = self.colors
        if self.hover:
            c1, c2 = lerp_col(c1, WHITE, .25), lerp_col(c2, WHITE, .15)
        surf.blit(grad_rect(r.w, r.h, c1, c2, rad), r)
        pygame.draw.line(surf, lerp_col(c1, WHITE, .5), (r.x + rad, r.y + 6), (r.right - rad, r.y + 6), 2)
        pygame.draw.rect(surf, WHITE, r, 3, border_radius=rad)
        tx = r.centerx
        if self.icon:
            draw_btn_icon(surf, self.icon, r.x + r.h * 0.62, r.centery, r.h * 0.26, WHITE, audio.muted)
            tx += r.h * 0.28
        draw_text(surf, self.text(), self.size * self.s, tx, r.centery + 1, WHITE)


# ======================================================================
#  JUEGO
# ======================================================================
def resolve(choices):
    """Devuelve (índices ganadores, tipo ganador). Sin ganadores = empate."""
    kinds = set(choices)
    if len(kinds) != 2:
        return [], None
    a, b = list(kinds)
    win = a if BEATS[a] == b else b
    return [i for i, c in enumerate(choices) if c == win], win


class Game:
    def __init__(self):
        pygame.mixer.pre_init(44100, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption("Piedra · Papel · Tijera — Arena de Leyendas")
        try:
            self.screen = pygame.display.set_mode((W, H), pygame.FULLSCREEN | pygame.SCALED)
        except pygame.error:
            self.screen = pygame.display.set_mode((W, H), pygame.FULLSCREEN)
        pygame.mouse.set_visible(True)
        self.clock = pygame.time.Clock()
        self.audio = Audio()
        self.bg = Background()
        self.confetti = Confetti()
        self.fade_surf = pygame.Surface((W, H))
        self.fade_surf.fill((0, 0, 0))
        self.dim_surf = pygame.Surface((W, H), pygame.SRCALPHA)
        self.dim_surf.fill((0, 0, 20, 170))

        self.n = 2
        self.vs_cpu = False
        self.level = 0
        self.lives = 3
        self.scores = []
        self.level_wins = []
        self.choices = []
        self.history = []
        self.winners = []
        self.win_kind = None
        self.cur = 0
        self.timer = 0.0
        self.lock = 0.0
        self.last_tick = 99
        self.hover_card = None
        self.beat = 0
        self.revealed = False
        self.round_no = 0
        self.time = 0.0
        self.t = 0.0
        self.fade = 1.0
        self.paused = False
        self.music_pending = None
        self.state = "menu"
        self.buttons = []

        self.hud_buttons = [
            Button(lambda: "SONIDO: " + ("OFF" if self.audio.muted else "ON"), 880, 42, 200, 46,
                   BTN_BLUE, lambda b: self.audio.toggle(), 20, "sound"),
            Button("PAUSA", 1052, 42, 130, 46, BTN_PURPLE, lambda b: self.set_pause(True), 20, "pause"),
            Button("SALIR", 1190, 42, 130, 46, BTN_RED, lambda b: self.quit(), 20, "exit"),
        ]
        self.pause_buttons = [
            Button("CONTINUAR", W // 2, 300, 380, 66, BTN_GREEN, lambda b: self.set_pause(False), 28, "play"),
            Button(lambda: "SONIDO: " + ("OFF" if self.audio.muted else "ON"), W // 2, 385, 380, 66,
                   BTN_BLUE, lambda b: self.audio.toggle(), 28, "sound"),
            Button("MENÚ PRINCIPAL", W // 2, 470, 380, 66, BTN_GOLD, lambda b: self.go_menu(), 26, "home"),
            Button("SALIR DEL JUEGO", W // 2, 555, 380, 66, BTN_RED, lambda b: self.quit(), 26, "exit"),
        ]
        self.enter("menu")
        self.music_pending = 0

    # ------------------------------------------------------------------
    #  Flujo general
    # ------------------------------------------------------------------
    def quit(self):
        pygame.quit()
        sys.exit()

    def set_pause(self, v):
        self.paused = v
        self.audio.play("back" if v else "click")

    def go_menu(self):
        self.paused = False
        self.enter("menu")
        self.music_pending = 0

    def pname(self, i):
        if self.vs_cpu:
            return "TÚ" if i == 0 else "CPU %d" % i
        return "JUGADOR %d" % (i + 1)

    def humans(self):
        return [0] if self.vs_cpu else list(range(self.n))

    def theme(self):
        if self.state in GAME_STATES:
            return LEVELS[self.level]
        return MENU_THEME

    def enter(self, state):
        self.state = state
        self.t = 0.0
        self.fade = 1.0
        self.buttons = []
        B = self.buttons
        cx = W // 2
        if state == "menu":
            B.append(Button("JUGAR", cx, 450, 420, 82, BTN_GREEN, lambda b: self.start_game(), 44, "play"))
            B.append(Button(lambda: "JUGADORES: %d" % self.n, cx - 190, 545, 360, 62, BTN_BLUE,
                            self.cycle_players, 24))
            B.append(Button(lambda: "MODO: " + ("VS CPU" if self.vs_cpu else "AMIGOS"), cx + 190, 545,
                            360, 62, BTN_PURPLE, lambda b: self.toggle_mode(), 24))
            B.append(Button(lambda: "SONIDO: " + ("OFF" if self.audio.muted else "ON"), cx - 190, 625,
                            360, 62, BTN_GOLD, lambda b: self.audio.toggle(), 24, "sound"))
            B.append(Button("SALIR", cx + 190, 625, 360, 62, BTN_RED, lambda b: self.quit(), 24, "exit"))
        elif state == "pass":
            B.append(Button("¡LISTO!", cx, 505, 300, 70, BTN_GREEN, lambda b: self.enter("choose"), 34, "play"))
        elif state == "choose":
            self.timer = float(LEVELS[self.level]["time"])
            self.lock = 0.0
            self.last_tick = 99
            self.hover_card = None
        elif state == "reveal":
            for i in range(self.n):
                if self.choices[i] is None:
                    self.choices[i] = self.cpu_pick()
            self.winners, self.win_kind = resolve(self.choices)
            self.beat = 0
            self.revealed = False
        elif state == "level_done":
            last = self.level == len(LEVELS) - 1
            B.append(Button("VER RESULTADO FINAL" if last else "SIGUIENTE NIVEL", cx, 470, 480, 72, BTN_GREEN,
                            lambda b: self.next_level(), 30, "play"))
            self.audio.play("levelup")
            self.confetti.burst(160)
        elif state == "level_lost":
            B.append(Button("REINTENTAR NIVEL", cx, 470, 440, 72, BTN_GOLD,
                            lambda b: self.begin_level(), 30, "play"))
            self.audio.play("lose")
        elif state == "gameover":
            B.append(Button("REINTENTAR", cx, 400, 420, 72, BTN_GREEN, lambda b: self.start_game(), 30, "play"))
            B.append(Button("MENÚ PRINCIPAL", cx, 490, 420, 66, BTN_GOLD, lambda b: self.go_menu(), 26, "home"))
            B.append(Button("SALIR", cx, 575, 420, 66, BTN_RED, lambda b: self.quit(), 26, "exit"))
            self.audio.play("gameover")
        elif state == "champion":
            B.append(Button("JUGAR DE NUEVO", cx, 470, 440, 72, BTN_GREEN, lambda b: self.start_game(), 30, "play"))
            B.append(Button("MENÚ PRINCIPAL", cx, 555, 440, 62, BTN_GOLD, lambda b: self.go_menu(), 24, "home"))
            B.append(Button("SALIR", cx, 630, 440, 58, BTN_RED, lambda b: self.quit(), 24, "exit"))
            self.audio.play("champion")
            self.confetti.burst(240)

    def cycle_players(self, btn):
        # clic izquierdo: +1   |   clic derecho: -1
        step = -1 if getattr(btn, "last_button", 1) == 3 else 1
        self.n = (self.n - 2 + step) % 5 + 2

    def toggle_mode(self):
        self.vs_cpu = not self.vs_cpu

    # ------------------------------------------------------------------
    #  Reglas, niveles y rondas
    # ------------------------------------------------------------------
    def start_game(self):
        self.level = 0
        self.lives = 3
        self.level_wins = [0] * self.n
        self.history = []
        self.begin_level()

    def begin_level(self):
        self.scores = [0] * self.n
        self.choices = [None] * self.n
        self.round_no = 0
        self.enter("intro")
        self.music_pending = self.level + 1

    def new_round(self):
        self.round_no += 1
        self.choices = [None] * self.n
        self.next_chooser()

    def next_chooser(self):
        pending = [i for i in self.humans() if self.choices[i] is None]
        if pending:
            self.cur = pending[0]
            self.enter("choose" if self.vs_cpu else "pass")
        else:
            self.enter("reveal")

    def pick(self, kind):
        self.choices[self.cur] = kind
        if self.cur == 0:
            self.history.append(kind)
        self.audio.play(kind)
        self.lock = 0.55

    def cpu_pick(self):
        smart = LEVELS[self.level]["smart"]
        if self.history and random.random() < smart:
            counts = {c: self.history.count(c) for c in CHOICES}
            predicted = max(CHOICES, key=lambda c: (counts[c] + (1.5 if self.history[-1] == c else 0),
                                                    random.random()))
            for c in CHOICES:
                if BEATS[c] == predicted:
                    return c
        return random.choice(CHOICES)

    def do_reveal(self):
        self.revealed = True
        for k in set(self.choices):
            self.audio.play(k)
        self.audio.play("reveal")
        for w in self.winners:
            self.scores[w] += 1
        if self.vs_cpu:
            sound = "win" if 0 in self.winners else ("tie" if not self.winners else "lose")
        else:
            sound = "win" if self.winners else "tie"
        self.audio.play(sound)
        if sound == "win":
            self.confetti.burst(70)

    def after_reveal(self):
        target = LEVELS[self.level]["target"]
        done = [i for i in range(self.n) if self.scores[i] >= target]
        if not done:
            self.new_round()
            return
        best = max(self.scores[i] for i in done)
        lvl_winners = [i for i in done if self.scores[i] == best]
        self.level_winners = lvl_winners
        if self.vs_cpu:
            if 0 in lvl_winners:
                self.level_wins[0] += 1
                self.enter("level_done")
            else:
                self.lives -= 1
                self.enter("level_lost" if self.lives > 0 else "gameover")
        else:
            for w in lvl_winners:
                self.level_wins[w] += 1
            self.enter("level_done")

    def next_level(self):
        if self.level == len(LEVELS) - 1:
            self.enter("champion")
        else:
            self.level += 1
            self.begin_level()

    # ------------------------------------------------------------------
    #  Entrada
    # ------------------------------------------------------------------
    def active_buttons(self):
        if self.paused:
            return self.pause_buttons
        if self.state in GAME_STATES:
            return self.buttons + self.hud_buttons
        return self.buttons

    def handle(self, e):
        if e.type == pygame.QUIT:
            self.quit()
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_F11:
                pygame.display.toggle_fullscreen()
            elif e.key == pygame.K_m:
                self.audio.toggle()
            elif e.key == pygame.K_ESCAPE:
                if self.state == "menu":
                    self.quit()
                elif self.paused:
                    self.set_pause(False)
                elif self.state in GAME_STATES:
                    self.set_pause(True)
                else:
                    self.go_menu()
            elif not self.paused:
                self.key_state(e.key)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3):
            for b in reversed(self.active_buttons()):
                if b.rect.collidepoint(e.pos):
                    if e.button == 3 and not self.paused and self.state == "menu":
                        b.last_button = 3
                    else:
                        b.last_button = 1
                    self.audio.play("click")
                    b.action(b)
                    return
            if not self.paused and e.button == 1:
                self.click_state(e.pos)

    def key_state(self, key):
        st = self.state
        if st == "choose" and self.lock <= 0:
            keymap = {pygame.K_1: "piedra", pygame.K_2: "papel", pygame.K_3: "tijera",
                      pygame.K_r: "piedra", pygame.K_p: "papel", pygame.K_t: "tijera",
                      pygame.K_KP1: "piedra", pygame.K_KP2: "papel", pygame.K_KP3: "tijera"}
            if key in keymap:
                self.pick(keymap[key])
        elif key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
            if st == "menu":
                self.start_game()
            elif st == "intro":
                self.new_round()
            elif st == "pass":
                self.audio.play("click")
                self.enter("choose")
            elif st == "reveal" and self.t > 3.0:
                self.after_reveal()
            elif st in ("level_done", "level_lost", "gameover", "champion") and self.buttons:
                self.audio.play("click")
                self.buttons[0].action(self.buttons[0])

    def click_state(self, pos):
        st = self.state
        if st == "intro":
            self.new_round()
        elif st == "choose" and self.lock <= 0:
            for kind, r in self.card_rects():
                if r.collidepoint(pos):
                    self.pick(kind)
                    break
        elif st == "reveal" and self.t > 3.0:
            self.after_reveal()

    # ------------------------------------------------------------------
    #  Actualización
    # ------------------------------------------------------------------
    def update(self, dt):
        self.time += dt
        self.bg.update(dt)
        self.confetti.update(dt)
        self.fade = max(0.0, self.fade - dt * 3.5)
        mouse = pygame.mouse.get_pos()
        for b in self.active_buttons():
            b.update(dt, mouse, self.audio)
        if self.paused:
            return
        self.t += dt
        st = self.state
        if st == "intro":
            if self.t > 4.5:
                self.new_round()
        elif st == "choose":
            self.update_choose(dt, mouse)
        elif st == "reveal":
            self.update_reveal()
        elif st == "champion" and random.random() < 0.05:
            self.confetti.burst(25)

    def update_choose(self, dt, mouse):
        if self.lock > 0:
            self.lock -= dt
            if self.lock <= 0:
                self.next_chooser()
            return
        self.timer -= dt
        sec = math.ceil(self.timer)
        if self.timer <= 3 and 0 < sec != self.last_tick:
            self.last_tick = sec
            self.audio.play("tick")
        hv = None
        for k, (_, r) in enumerate(self.card_rects()):
            if r.collidepoint(mouse):
                hv = k
        if hv is not None and hv != self.hover_card:
            self.audio.play("hover")
        self.hover_card = hv
        if self.timer <= 0:
            self.pick(random.choice(CHOICES))

    def update_reveal(self):
        while self.beat < 3 and self.t >= (0.0, 0.8, 1.6)[self.beat]:
            self.audio.play("tick" if self.beat < 2 else "go")
            self.beat += 1
        if self.t >= 2.4 and not self.revealed:
            self.do_reveal()

    # ------------------------------------------------------------------
    #  Dibujo
    # ------------------------------------------------------------------
    def draw(self):
        s = self.screen
        self.bg.draw(s, self.theme())
        getattr(self, "draw_" + self.state)()
        if self.state in GAME_STATES:
            self.draw_hud()
        self.confetti.draw(s)
        if self.paused:
            s.blit(self.dim_surf, (0, 0))
            draw_text(s, "PAUSA", 90, W // 2, 160, GOLD)
            draw_text(s, "El juego está detenido", 26, W // 2, 225, WHITE)
        for b in self.active_buttons():
            b.draw(s, self.audio)
        if self.fade > 0:
            self.fade_surf.set_alpha(int(255 * self.fade))
            s.blit(self.fade_surf, (0, 0))

    # ---- piezas comunes -------------------------------------------------
    def draw_hud(self):
        s = self.screen
        th = LEVELS[self.level]
        draw_text(s, "NIVEL %d/%d" % (self.level + 1, len(LEVELS)), 34, 28, 20, th["accent"], "topleft")
        draw_text(s, th["name"], 26, 28, 64, WHITE, "topleft")
        draw_text(s, "META: %d PUNTOS" % th["target"], 20, 28, 98, WHITE, "topleft")
        if self.vs_cpu:
            draw_text(s, "VIDAS", 18, 28, 128, WHITE, "topleft")
            for k in range(3):
                draw_heart(s, 120 + k * 32, 138, 11, (255, 80, 110) if k < self.lives else (90, 80, 110))

    def draw_scoreboard(self, highlight=None):
        s = self.screen
        n = self.n
        gap = 12
        cw = min(190, (W - 60 - (n - 1) * gap) // n)
        x0 = (W - (n * cw + (n - 1) * gap)) // 2
        y, h = 590, 94
        target = LEVELS[self.level]["target"]
        for i in range(n):
            r = pygame.Rect(x0 + i * (cw + gap), y, cw, h)
            col = PLAYER_COLS[i]
            s.blit(grad_rect(cw, h, lerp_col(col, DARK, .6), lerp_col(col, DARK, .85), 18), r)
            pygame.draw.rect(s, WHITE if highlight == i else col, r, 5 if highlight == i else 3, border_radius=18)
            draw_text(s, self.pname(i), 20 if cw >= 150 else 15, r.centerx, r.y + 20, col)
            pw = min(24, (cw - 30) // target)
            px0 = r.centerx - (target - 1) * pw / 2
            for k in range(target):
                c = (px0 + k * pw, r.y + 52)
                if k < self.scores[i]:
                    pygame.draw.circle(s, col, c, 8)
                    pygame.draw.circle(s, WHITE, c, 8, 2)
                else:
                    pygame.draw.circle(s, (130, 130, 165), c, 8, 2)
            draw_star(s, r.centerx - 16, r.y + 77, 9, GOLD, (120, 80, 0))
            draw_text(s, "x%d" % self.level_wins[i], 18, r.centerx + 2, r.y + 77, WHITE, "midleft")

    def card_rects(self):
        out = []
        for k, kind in enumerate(CHOICES):
            r = pygame.Rect(0, 0, 250, 300)
            r.center = (W // 2 + (k - 1) * 290, 365)
            out.append((kind, r))
        return out

    def draw_card(self, rect, kind, hover=False, hidden=False, dim=False, glowing=False, num=None):
        s = self.screen
        sc = 1.06 if hover else 1.0
        r = rect.inflate(int(rect.w * (sc - 1)), int(rect.h * (sc - 1)))
        col = (130, 115, 190) if hidden else CHOICE_COL[kind]
        if glowing:
            s.blit(glow_surf(r.w * 0.85, GOLD, 200), glow_surf(r.w * 0.85, GOLD, 200).get_rect(center=r.center))
        sh = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        pygame.draw.rect(sh, (0, 0, 0, 90), sh.get_rect(), border_radius=26)
        s.blit(sh, (r.x + 4, r.y + 9))
        s.blit(grad_rect(r.w, r.h, lerp_col(col, WHITE, .3), lerp_col(col, DARK, .7), 26), r)
        pygame.draw.rect(s, GOLD if glowing else WHITE, r, 5 if glowing else 4, border_radius=26)
        if hidden:
            draw_text(s, "?", int(r.h * .6), r.centerx, r.centery - 6, WHITE)
        else:
            size = int(min(r.w - 30, r.h - 80))
            ic = get_icon(kind, size)
            s.blit(ic, ic.get_rect(center=(r.centerx, r.y + r.h * 0.42)))
            draw_text(s, NAMES[kind], max(18, int(r.w * 0.115)), r.centerx, r.bottom - r.h * 0.11, WHITE)
        if num:
            pygame.draw.circle(s, DARK, (r.x + 30, r.y + 30), 20)
            pygame.draw.circle(s, WHITE, (r.x + 30, r.y + 30), 20, 3)
            draw_text(s, str(num), 24, r.x + 30, r.y + 31, WHITE, shadow=False)
        if dim:
            dm = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
            pygame.draw.rect(dm, (0, 0, 20, 150), dm.get_rect(), border_radius=26)
            s.blit(dm, r)

    # ---- pantallas -----------------------------------------------------
    def draw_menu(self):
        s, t = self.screen, self.time
        draw_wave_text(s, "PIEDRA · PAPEL · TIJERA", 62, W // 2, 85, t)
        draw_text(s, "— ARENA DE LEYENDAS —", 32, W // 2, 152, MENU_THEME["accent"])
        for k, kind in enumerate(CHOICES):
            cx = W // 2 + (k - 1) * 230
            cy = 285 + math.sin(t * 2 + k * 1.3) * 10
            g = glow_surf(125, CHOICE_COL[kind], 150)
            s.blit(g, g.get_rect(center=(cx, cy)))
            ic = pygame.transform.rotozoom(get_icon(kind, 150), math.sin(t * 1.5 + k) * 8, 1.0)
            s.blit(ic, ic.get_rect(center=(cx, cy)))
        draw_text(s, "Clic derecho en JUGADORES para bajar  ·  M: sonido  ·  F11: pantalla  ·  ESC: salir",
                  18, W // 2, 690, WHITE)
        if self.vs_cpu:
            draw_text(s, "Tú contra %d CPU%s" % (self.n - 1, "s" if self.n > 2 else ""), 22, W // 2, 380,
                      MENU_THEME["accent"])
        else:
            draw_text(s, "%d jugadores en el mismo equipo, por turnos" % self.n, 22, W // 2, 380,
                      MENU_THEME["accent"])

    def draw_intro(self):
        s, th = self.screen, LEVELS[self.level]
        pulse = 1 + 0.04 * math.sin(self.time * 4)
        draw_text(s, "NIVEL %d" % (self.level + 1), int(120 * pulse), W // 2, 210, th["accent"])
        draw_text(s, th["name"], 62, W // 2, 315, WHITE)
        draw_text(s, "Gana quien llegue primero a %d puntos" % th["target"], 30, W // 2, 395, WHITE)
        draw_text(s, "Tiempo para elegir: %d segundos" % th["time"], 30, W // 2, 440, WHITE)
        draw_text(s, "DIFICULTAD", 22, W // 2, 495, th["accent"])
        for k in range(len(LEVELS)):
            draw_star(s, W // 2 + (k - 3.5) * 40, 535, 15,
                      GOLD if k <= self.level else (110, 100, 140), (90, 60, 0))
        if int(self.time * 2) % 2 == 0:
            draw_text(s, "Pulsa ESPACIO o haz clic para empezar", 26, W // 2, 600, WHITE)

    def draw_pass(self):
        s, i = self.screen, self.cur
        col = PLAYER_COLS[i]
        draw_text(s, "¡PASA EL DISPOSITIVO!", 44, W // 2, 135, WHITE)
        g = glow_surf(160, col, 190)
        s.blit(g, g.get_rect(center=(W // 2, 265)))
        pygame.draw.circle(s, col, (W // 2, 265), 85)
        pygame.draw.circle(s, WHITE, (W // 2, 265), 85, 6)
        draw_text(s, str(i + 1), 100, W // 2, 268, WHITE)
        draw_text(s, "TURNO DE " + self.pname(i), 54, W // 2, 385, col)
        draw_text(s, "Elige en secreto: que nadie más mire la pantalla", 24, W // 2, 435, WHITE)
        self.draw_scoreboard(i)

    def draw_choose(self):
        s, i = self.screen, self.cur
        col = PLAYER_COLS[i]
        if self.lock > 0:
            draw_text(s, "¡ELECCIÓN GUARDADA!", 60, W // 2, 330, GOLD)
            draw_text(s, "Shhh... es un secreto", 28, W // 2, 395, WHITE)
            self.draw_scoreboard(i)
            return
        txt = "¡ELIGE!" if self.vs_cpu else self.pname(i) + ", ¡ELIGE!"
        draw_text(s, txt, 56, W // 2, 125, col)
        total = float(LEVELS[self.level]["time"])
        frac = max(0.0, self.timer / total)
        bar = pygame.Rect(0, 0, 640, 24)
        bar.center = (W // 2 - 20, 185)
        pygame.draw.rect(s, (0, 0, 30), bar.inflate(8, 8), border_radius=18)
        fill = bar.copy()
        fill.w = max(10, int(bar.w * frac))
        pygame.draw.rect(s, lerp_col((255, 70, 70), (90, 235, 130), min(1.0, frac * 1.4)), fill, border_radius=14)
        draw_text(s, str(max(0, math.ceil(self.timer))), 36, bar.right + 45, bar.centery, WHITE)
        for k, (kind, r) in enumerate(self.card_rects()):
            self.draw_card(r, kind, hover=(self.hover_card == k), num=k + 1)
        draw_text(s, "Haz clic en una carta  ·  o pulsa 1, 2, 3", 22, W // 2, 548, WHITE)
        self.draw_scoreboard(i if not self.vs_cpu else 0)

    def draw_reveal(self):
        s, n, t = self.screen, self.n, self.t
        cw = min(210, (W - 100) // n - 16)
        ch = int(cw * 1.25)
        gap = 16
        x0 = (W - (n * cw + (n - 1) * gap)) // 2
        for i in range(n):
            r = pygame.Rect(x0 + i * (cw + gap), 0, cw, ch)
            r.centery = 355
            if t < 2.4:
                r.y -= int(abs(math.sin(t * math.pi / 0.8)) * 45)
                self.draw_card(r, "piedra", hidden=True)
            else:
                rt = t - 2.4
                pop = 0.28 * max(0.0, 1 - rt * 3)
                rr = r.inflate(int(cw * pop), int(ch * pop))
                win = i in self.winners
                self.draw_card(rr, self.choices[i], glowing=win, dim=bool(self.winners) and not win)
            draw_text(s, self.pname(i), 22 if cw > 150 else 16, r.centerx, r.bottom + 30, PLAYER_COLS[i])
        if t < 2.4:
            words = ["¡PIEDRA!", "¡PAPEL!", "¡TIJERA!"]
            if self.beat > 0:
                k = self.beat - 1
                sz = 90 + int(20 * max(0, 1 - (t - (0.0, 0.8, 1.6)[k]) * 5))
                draw_text(s, words[k], sz, W // 2, 140, GOLD)
        else:
            if self.vs_cpu:
                if 0 in self.winners:
                    msg, col = "¡GANASTE LA RONDA!", GOLD
                elif self.winners:
                    msg, col = "¡LA CPU GANA LA RONDA!", (255, 120, 120)
                else:
                    msg, col = "¡EMPATE!", WHITE
            elif not self.winners:
                msg, col = "¡EMPATE!", WHITE
            elif len(self.winners) <= 3:
                msg, col = "¡GANA " + " Y ".join(self.pname(w) for w in self.winners) + "!", GOLD
            else:
                msg, col = "¡GANAN %d JUGADORES!" % len(self.winners), GOLD
            draw_text(s, msg, 56 if len(msg) < 30 else 42, W // 2, 105, col)
            sub = REASONS[self.win_kind] if self.win_kind else "Nadie suma puntos en esta ronda"
            draw_text(s, sub, 28, W // 2, 162, WHITE)
            if t > 3.0 and int(self.time * 2) % 2 == 0:
                draw_text(s, "ESPACIO o clic para continuar", 22, W // 2, 560, WHITE)
        self.draw_scoreboard()

    def draw_level_done(self):
        s = self.screen
        th = LEVELS[self.level]
        pulse = 1 + 0.05 * math.sin(self.time * 5)
        draw_text(s, "¡NIVEL SUPERADO!", int(80 * pulse), W // 2, 190, GOLD)
        if self.vs_cpu:
            who = "¡Le ganaste a la CPU!"
        else:
            who = "Ganador: " + " y ".join(self.pname(w) for w in self.level_winners)
        draw_text(s, who, 44, W // 2, 285, WHITE)
        for k in range(3):
            draw_star(s, W // 2 + (k - 1) * 90, 365, 34 if k == 1 else 28, GOLD, (130, 85, 0))
        if self.level < len(LEVELS) - 1:
            nxt = LEVELS[self.level + 1]
            draw_text(s, "Próximo: NIVEL %d · %s" % (self.level + 2, nxt["name"]), 26, W // 2, 415, th["accent"])
        self.draw_scoreboard()

    def draw_level_lost(self):
        s = self.screen
        draw_text(s, "¡NIVEL PERDIDO!", 80, W // 2, 190, (255, 120, 120))
        draw_text(s, "La CPU fue más rápida esta vez", 36, W // 2, 285, WHITE)
        draw_text(s, "Vidas restantes", 26, W // 2, 345, WHITE)
        for k in range(3):
            draw_heart(s, W // 2 + (k - 1) * 60, 395, 20, (255, 80, 110) if k < self.lives else (90, 80, 110))
        self.draw_scoreboard()

    def draw_gameover(self):
        s = self.screen
        draw_text(s, "FIN DEL JUEGO", 88, W // 2, 150, (255, 110, 110))
        draw_text(s, "Llegaste hasta el NIVEL %d · %s" % (self.level + 1, LEVELS[self.level]["name"]),
                  32, W // 2, 235, WHITE)
        draw_text(s, "¡Inténtalo otra vez, tú puedes!", 28, W // 2, 290, MENU_THEME["accent"])

    def draw_champion(self):
        s = self.screen
        draw_wave_text(s, "¡CAMPEÓN DE LA ARENA!", 66, W // 2, 110, self.time)
        if self.vs_cpu:
            msg = "¡Completaste los %d niveles!" % len(LEVELS)
            draw_text(s, msg, 40, W // 2, 205, WHITE)
            draw_text(s, "Niveles ganados: %d  ·  Vidas: %d" % (self.level_wins[0], self.lives), 28, W // 2, 262,
                      GOLD)
        else:
            m = max(self.level_wins)
            champs = [i for i, v in enumerate(self.level_wins) if v == m]
            draw_text(s, " y ".join(self.pname(c) for c in champs), 52, W // 2, 205, GOLD)
            draw_text(s, "con %d niveles ganados" % m, 28, W // 2, 262, WHITE)
        for k in range(5):
            draw_star(s, W // 2 + (k - 2) * 70, 340 + math.sin(self.time * 3 + k) * 8, 28, GOLD, (130, 85, 0))
        # ranking
        if not self.vs_cpu:
            order = sorted(range(self.n), key=lambda i: -self.level_wins[i])
            txt = "   ".join("%s: %d" % (self.pname(i), self.level_wins[i]) for i in order[:3])
            draw_text(s, txt, 22, W // 2, 395, WHITE)


# ======================================================================
def main():
    game = Game()
    audio_ready = game.audio.ok
    if not audio_ready:
        print("Aviso: sin dispositivo de audio, el juego funcionará en silencio.")
    while True:
        dt = min(game.clock.tick(FPS) / 1000.0, 0.05)
        for e in pygame.event.get():
            game.handle(e)
        game.update(dt)
        game.draw()
        pygame.display.flip()
        # La música se genera DESPUÉS de dibujar el frame (así la pantalla no se ve congelada)
        if game.music_pending is not None:
            idx, game.music_pending = game.music_pending, None
            game.audio.play_music(idx)


if __name__ == "__main__":
    main()
