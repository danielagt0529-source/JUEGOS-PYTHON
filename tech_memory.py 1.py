#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TECH MEMORY  ·  Humano vs Máquina
---------------------------------
Juego de memoria con iconos tecnológicos dibujados por código (sin imágenes
ni sonidos externos: todo se genera al vuelo). Juegas contra una IA que
recuerda cartas y se vuelve más astuta en cada nivel.

Requisitos: solo Python 3.8+ (tkinter viene incluido).
Ejecutar:   python tech_memory.py

Reglas
  * Voltea dos cartas por turno. Si son pareja, la ganas y repites turno.
  * Si fallas, le toca a la máquina.
  * Para superar el nivel debes conseguir MÁS parejas que la máquina.

Teclas
  M = sonido ON/OFF · F11 = pantalla completa · R = reiniciar nivel
  Esc = volver al menú · Enter/Espacio = continuar
"""
import array
import atexit
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import wave

DW, DH = 980, 740            # tamaño de diseño (coordenadas lógicas)
FONT = "Consolas"

C = dict(
    bg="#060914", grid="#0d1630", panel="#0e1530", panel2="#141e42",
    cyan="#00e5ff", magenta="#ff2bd6", green="#39ff88", yellow="#ffd400",
    orange="#ff8a1f", purple="#9b5cff", blue="#3d7bff", red="#ff4d6d",
    white="#e8f1ff", dim="#6b7aa8",
)
ICON_COLORS = [C["cyan"], C["magenta"], C["green"], C["yellow"],
               C["orange"], C["purple"], C["blue"], C["red"]]

# (columnas, filas) por nivel; a partir del último el tablero no crece,
# pero la máquina sigue mejorando.
LEVELS = [(4, 3), (4, 4), (5, 4), (6, 4), (6, 5), (6, 6)]

# nombre, memoria inicial, mejora por nivel, memoria máxima, color
DIFFS = [("FÁCIL", 0.10, 0.04, 0.45, C["green"]),
         ("NORMAL", 0.25, 0.06, 0.75, C["yellow"]),
         ("DIFÍCIL", 0.40, 0.08, 0.95, C["red"])]

CFG_PATH = os.path.join(os.path.expanduser("~"), ".tech_memory.json")


def load_cfg():
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_cfg(d):
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f)
    except Exception:
        pass


# ───────────────────────── utilidades de dibujo ─────────────────────────
def mix(a, b, t):
    """Mezcla dos colores hex. t=0 -> a, t=1 -> b."""
    a, b = a.lstrip("#"), b.lstrip("#")
    ra, ga, ba = int(a[0:2], 16), int(a[2:4], 16), int(a[4:6], 16)
    rb, gb, bb = int(b[0:2], 16), int(b[2:4], 16), int(b[4:6], 16)
    return "#%02x%02x%02x" % (int(ra + (rb - ra) * t),
                              int(ga + (gb - ga) * t),
                              int(ba + (bb - ba) * t))


class View:
    """Envuelve el Canvas: dibujamos en coordenadas lógicas (diseño 980x740)
    y esta capa las escala (posiciones, grosores y fuentes) a la pantalla."""

    def __init__(self, cv):
        self.cv = cv
        self.k = 1.0

    def _a(self, a):
        if len(a) == 1 and isinstance(a[0], (list, tuple)):
            a = a[0]
        return [v * self.k for v in a]

    def _kw(self, kw):
        if kw.get("width") is not None:
            kw["width"] = max(0.5, kw["width"] * self.k)
        f = kw.get("font")
        if f:
            kw["font"] = (f[0], -max(7, int(round(f[1] * 4 / 3 * self.k)))) + tuple(f[2:])
        return kw

    def create_line(self, *a, **kw):
        return self.cv.create_line(*self._a(a), **self._kw(kw))

    def create_polygon(self, *a, **kw):
        return self.cv.create_polygon(*self._a(a), **self._kw(kw))

    def create_oval(self, *a, **kw):
        return self.cv.create_oval(*self._a(a), **self._kw(kw))

    def create_rectangle(self, *a, **kw):
        return self.cv.create_rectangle(*self._a(a), **self._kw(kw))

    def create_arc(self, *a, **kw):
        return self.cv.create_arc(*self._a(a), **self._kw(kw))

    def create_text(self, *a, **kw):
        return self.cv.create_text(*self._a(a), **self._kw(kw))

    def scale(self, tag, x, y, sx, sy):
        self.cv.scale(tag, x * self.k, y * self.k, sx, sy)

    def delete(self, *a):
        self.cv.delete(*a)


def rrect(cv, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


# ───────────────────────── iconos tecnológicos ─────────────────────────
# Todos se dibujan centrados en (cx, cy) dentro de un cuadro de lado ~2*s.
def ic_chip(cv, cx, cy, s, col, tg, lw):
    b = s * 0.6
    cv.create_rectangle(cx - b, cy - b, cx + b, cy + b, outline=col, width=lw, tags=tg)
    i = b * 0.5
    cv.create_rectangle(cx - i, cy - i, cx + i, cy + i, fill=col, outline=col, tags=tg)
    for k in (-0.5, 0, 0.5):
        cv.create_line(cx + b * k, cy - b, cx + b * k, cy - b - s * 0.32, fill=col, width=lw, tags=tg)
        cv.create_line(cx + b * k, cy + b, cx + b * k, cy + b + s * 0.32, fill=col, width=lw, tags=tg)
        cv.create_line(cx - b, cy + b * k, cx - b - s * 0.32, cy + b * k, fill=col, width=lw, tags=tg)
        cv.create_line(cx + b, cy + b * k, cx + b + s * 0.32, cy + b * k, fill=col, width=lw, tags=tg)


def ic_wifi(cv, cx, cy, s, col, tg, lw):
    oy = cy + s * 0.6
    for r in (0.45, 0.8, 1.15):
        cv.create_arc(cx - s * r, oy - s * r, cx + s * r, oy + s * r, start=45, extent=90,
                      style=tk.ARC, outline=col, width=lw * 1.3, tags=tg)
    cv.create_oval(cx - s * 0.12, oy - s * 0.12, cx + s * 0.12, oy + s * 0.12,
                   fill=col, outline=col, tags=tg)


def ic_cloud(cv, cx, cy, s, col, tg, lw):
    for box in ((-0.95, -0.1, -0.2, 0.55), (-0.55, -0.65, 0.35, 0.25), (-0.1, -0.3, 0.95, 0.55)):
        cv.create_oval(cx + s * box[0], cy + s * box[1], cx + s * box[2], cy + s * box[3],
                       fill=col, outline=col, tags=tg)
    cv.create_rectangle(cx - s * 0.6, cy + s * 0.1, cx + s * 0.6, cy + s * 0.55,
                        fill=col, outline=col, tags=tg)
    cv.create_line(cx, cy + s * 0.42, cx, cy - s * 0.05, fill=C["bg"], width=lw * 1.2, tags=tg)
    cv.create_polygon(cx - s * 0.2, cy + s * 0.05, cx, cy - s * 0.25, cx + s * 0.2, cy + s * 0.05,
                      fill=C["bg"], outline=C["bg"], tags=tg)


def ic_gear(cv, cx, cy, s, col, tg, lw):
    n, R, r = 8, s * 0.95, s * 0.7
    pts = []
    for i in range(n):
        a0 = 2 * math.pi * i / n
        hw = math.pi / n * 0.45
        for rad, da in ((r, -hw * 1.6), (R, -hw), (R, hw), (r, hw * 1.6)):
            pts += [cx + rad * math.cos(a0 + da), cy + rad * math.sin(a0 + da)]
    cv.create_polygon(pts, fill=col, outline=col, tags=tg)
    cv.create_oval(cx - s * 0.32, cy - s * 0.32, cx + s * 0.32, cy + s * 0.32,
                   fill=C["bg"], outline=C["bg"], tags=tg)


def ic_lock(cv, cx, cy, s, col, tg, lw):
    cv.create_arc(cx - s * 0.42, cy - s * 0.8, cx + s * 0.42, cy + s * 0.1, start=0, extent=180,
                  style=tk.ARC, outline=col, width=lw * 1.4, tags=tg)
    cv.create_line(cx - s * 0.42, cy - s * 0.35, cx - s * 0.42, cy, fill=col, width=lw * 1.4, tags=tg)
    cv.create_line(cx + s * 0.42, cy - s * 0.35, cx + s * 0.42, cy, fill=col, width=lw * 1.4, tags=tg)
    cv.create_rectangle(cx - s * 0.65, cy - s * 0.05, cx + s * 0.65, cy + s * 0.85,
                        fill=col, outline=col, tags=tg)
    cv.create_oval(cx - s * 0.13, cy + s * 0.2, cx + s * 0.13, cy + s * 0.46,
                   fill=C["bg"], outline=C["bg"], tags=tg)
    cv.create_line(cx, cy + s * 0.4, cx, cy + s * 0.65, fill=C["bg"], width=lw, tags=tg)


def ic_battery(cv, cx, cy, s, col, tg, lw):
    cv.create_rectangle(cx - s * 0.9, cy - s * 0.45, cx + s * 0.75, cy + s * 0.45,
                        outline=col, width=lw, tags=tg)
    cv.create_rectangle(cx + s * 0.75, cy - s * 0.2, cx + s * 0.95, cy + s * 0.2,
                        fill=col, outline=col, tags=tg)
    for k in range(3):
        x1 = cx - s * 0.78 + k * s * 0.52
        cv.create_rectangle(x1, cy - s * 0.3, x1 + s * 0.4, cy + s * 0.3,
                            fill=col, outline=col, tags=tg)


def ic_code(cv, cx, cy, s, col, tg, lw):
    cv.create_text(cx, cy, text="</>", fill=col,
                   font=(FONT, max(8, int(s * 0.72)), "bold"), tags=tg)


def ic_database(cv, cx, cy, s, col, tg, lw):
    cv.create_rectangle(cx - s * 0.7, cy - s * 0.55, cx + s * 0.7, cy + s * 0.55,
                        fill=col, outline=col, tags=tg)
    cv.create_oval(cx - s * 0.7, cy + s * 0.25, cx + s * 0.7, cy + s * 0.85,
                   fill=col, outline=col, tags=tg)
    cv.create_oval(cx - s * 0.7, cy - s * 0.85, cx + s * 0.7, cy - s * 0.25,
                   fill=col, outline=C["bg"], width=lw * 0.7, tags=tg)
    for dy in (-0.25, 0.1):
        cv.create_arc(cx - s * 0.7, cy + s * dy, cx + s * 0.7, cy + s * (dy + 0.6), start=180,
                      extent=180, style=tk.ARC, outline=C["bg"], width=lw * 0.7, tags=tg)


def ic_robot(cv, cx, cy, s, col, tg, lw):
    rrect(cv, cx - s * 0.75, cy - s * 0.5, cx + s * 0.75, cy + s * 0.7, s * 0.2,
          fill="", outline=col, width=lw, tags=tg)
    for sx in (-1, 1):
        cv.create_oval(cx + sx * s * 0.3 - s * 0.15, cy - s * 0.15, cx + sx * s * 0.3 + s * 0.15, cy + s * 0.15,
                       fill=col, outline=col, tags=tg)
        cv.create_rectangle(cx + sx * s * 0.85 - s * 0.1, cy - s * 0.05, cx + sx * s * 0.85 + s * 0.1, cy + s * 0.35,
                            fill=col, outline=col, tags=tg)
    cv.create_line(cx - s * 0.4, cy + s * 0.45, cx + s * 0.4, cy + s * 0.45, fill=col, width=lw, tags=tg)
    cv.create_line(cx, cy - s * 0.5, cx, cy - s * 0.8, fill=col, width=lw, tags=tg)
    cv.create_oval(cx - s * 0.1, cy - s * 1.0, cx + s * 0.1, cy - s * 0.8, fill=col, outline=col, tags=tg)


def ic_rocket(cv, cx, cy, s, col, tg, lw):
    cv.create_polygon(cx - s * 0.35, cy + s * 0.1, cx - s * 0.8, cy + s * 0.7, cx - s * 0.35, cy + s * 0.5,
                      fill=col, outline=col, tags=tg)
    cv.create_polygon(cx + s * 0.35, cy + s * 0.1, cx + s * 0.8, cy + s * 0.7, cx + s * 0.35, cy + s * 0.5,
                      fill=col, outline=col, tags=tg)
    cv.create_polygon(cx, cy - s, cx + s * 0.38, cy - s * 0.3, cx + s * 0.38, cy + s * 0.55,
                      cx - s * 0.38, cy + s * 0.55, cx - s * 0.38, cy - s * 0.3,
                      fill=col, outline=col, tags=tg)
    cv.create_oval(cx - s * 0.17, cy - s * 0.35, cx + s * 0.17, cy, fill=C["bg"], outline=C["bg"], tags=tg)
    cv.create_polygon(cx - s * 0.22, cy + s * 0.6, cx, cy + s * 1.0, cx + s * 0.22, cy + s * 0.6,
                      fill=C["yellow"], outline=C["yellow"], tags=tg)


def ic_satellite(cv, cx, cy, s, col, tg, lw):
    cv.create_rectangle(cx - s * 0.25, cy - s * 0.25, cx + s * 0.25, cy + s * 0.25,
                        fill=col, outline=col, tags=tg)
    for sx in (-1, 1):
        x1, x2 = sorted((cx + sx * s * 0.4, cx + sx * s * 0.98))
        cv.create_rectangle(x1, cy - s * 0.22, x2, cy + s * 0.22, outline=col, width=lw, tags=tg)
        cv.create_line((x1 + x2) / 2, cy - s * 0.22, (x1 + x2) / 2, cy + s * 0.22, fill=col, width=lw, tags=tg)
        cv.create_line(cx + sx * s * 0.25, cy, cx + sx * s * 0.4, cy, fill=col, width=lw, tags=tg)
    cv.create_arc(cx - s * 0.32, cy + s * 0.2, cx + s * 0.32, cy + s * 0.85, start=180, extent=180,
                  style=tk.ARC, outline=col, width=lw * 1.3, tags=tg)
    cv.create_line(cx, cy + s * 0.25, cx, cy + s * 0.55, fill=col, width=lw, tags=tg)


def ic_mouse(cv, cx, cy, s, col, tg, lw):
    cv.create_oval(cx - s * 0.5, cy - s * 0.9, cx + s * 0.5, cy + s * 0.9, outline=col, width=lw, tags=tg)
    cv.create_line(cx, cy - s * 0.9, cx, cy - s * 0.1, fill=col, width=lw, tags=tg)
    cv.create_line(cx - s * 0.5, cy - s * 0.1, cx + s * 0.5, cy - s * 0.1, fill=col, width=lw, tags=tg)
    cv.create_rectangle(cx - s * 0.07, cy - s * 0.6, cx + s * 0.07, cy - s * 0.3, fill=col, outline=col, tags=tg)


def ic_headphones(cv, cx, cy, s, col, tg, lw):
    cv.create_arc(cx - s * 0.8, cy - s * 0.9, cx + s * 0.8, cy + s * 0.7, start=0, extent=180,
                  style=tk.ARC, outline=col, width=lw * 1.5, tags=tg)
    for sx in (-1, 1):
        x1, x2 = sorted((cx + sx * s * 0.55, cx + sx * s * 0.98))
        rrect(cv, x1, cy - s * 0.1, x2, cy + s * 0.65, s * 0.12, fill=col, outline=col, tags=tg)


def ic_shield(cv, cx, cy, s, col, tg, lw):
    cv.create_polygon(cx, cy - s, cx + s * 0.8, cy - s * 0.65, cx + s * 0.8, cy + s * 0.1, cx, cy + s,
                      cx - s * 0.8, cy + s * 0.1, cx - s * 0.8, cy - s * 0.65,
                      fill="", outline=col, width=lw, tags=tg)
    cv.create_line(cx - s * 0.35, cy, cx - s * 0.08, cy + s * 0.3, cx + s * 0.4, cy - s * 0.3,
                   fill=col, width=lw * 1.3, tags=tg)


def ic_bulb(cv, cx, cy, s, col, tg, lw):
    cv.create_oval(cx - s * 0.55, cy - s * 0.95, cx + s * 0.55, cy + s * 0.15, outline=col, width=lw, tags=tg)
    cv.create_rectangle(cx - s * 0.3, cy + s * 0.2, cx + s * 0.3, cy + s * 0.35, fill=col, outline=col, tags=tg)
    cv.create_rectangle(cx - s * 0.22, cy + s * 0.45, cx + s * 0.22, cy + s * 0.6, fill=col, outline=col, tags=tg)
    cv.create_line(cx - s * 0.2, cy - s * 0.1, cx - s * 0.08, cy - s * 0.4, cx + s * 0.08, cy - s * 0.1,
                   cx + s * 0.2, cy - s * 0.4, fill=col, width=lw, tags=tg)


def ic_monitor(cv, cx, cy, s, col, tg, lw):
    cv.create_rectangle(cx - s * 0.9, cy - s * 0.7, cx + s * 0.9, cy + s * 0.35, outline=col, width=lw, tags=tg)
    for k, ln in enumerate((0.9, 0.55, 0.75)):
        y = cy - s * 0.45 + k * s * 0.25
        cv.create_line(cx - s * 0.65, y, cx - s * 0.65 + s * ln, y, fill=col, width=lw, tags=tg)
    cv.create_line(cx, cy + s * 0.35, cx, cy + s * 0.65, fill=col, width=lw, tags=tg)
    cv.create_line(cx - s * 0.45, cy + s * 0.7, cx + s * 0.45, cy + s * 0.7, fill=col, width=lw * 1.3, tags=tg)


def ic_signal(cv, cx, cy, s, col, tg, lw):
    for k in range(4):
        h = s * 0.35 + s * 0.3 * k
        x1 = cx - s * 0.85 + k * s * 0.45
        y2 = cy + s * 0.8
        cv.create_rectangle(x1, y2 - h, x1 + s * 0.32, y2, fill=col, outline=col, tags=tg)


def ic_power(cv, cx, cy, s, col, tg, lw):
    cv.create_arc(cx - s * 0.7, cy - s * 0.65, cx + s * 0.7, cy + s * 0.75, start=120, extent=300,
                  style=tk.ARC, outline=col, width=lw * 1.5, tags=tg)
    cv.create_line(cx, cy - s * 0.85, cx, cy - s * 0.05, fill=col, width=lw * 1.5, tags=tg)


ICONS = [ic_chip, ic_wifi, ic_cloud, ic_gear, ic_lock, ic_battery, ic_code, ic_database,
         ic_robot, ic_rocket, ic_satellite, ic_mouse, ic_headphones, ic_shield, ic_bulb,
         ic_monitor, ic_signal, ic_power]


# ───────────────────────── sonido (sintetizado, sin archivos externos) ─────────────────────────
RATE = 22050


def tone(freq, dur, vol=0.4, shape="sine", slide=None, decay=None):
    """Genera una nota como lista de muestras en [-1, 1]."""
    n = max(1, int(RATE * dur))
    out = []
    phase = 0.0
    att = RATE * 0.006
    rel = RATE * min(0.05, dur * 0.5)
    for i in range(n):
        f = freq if slide is None else freq + (slide - freq) * (i / n)
        phase += 2 * math.pi * f / RATE
        if shape == "square":
            s = 1.0 if math.sin(phase) >= 0 else -1.0
        elif shape == "tri":
            s = 2 / math.pi * math.asin(math.sin(phase))
        elif shape == "saw":
            s = ((phase / (2 * math.pi)) % 1.0) * 2 - 1
        else:
            s = math.sin(phase)
        env = min(1.0, i / att) * min(1.0, (n - i) / rel)
        if decay:
            env *= math.exp(-decay * i / RATE)
        out.append(s * vol * env)
    return out


def seq(notes, shape="sine", vol=0.4, decay=None):
    out = []
    for f, d in notes:
        out += tone(f, d, vol, shape, decay=decay)
    return out


def write_wav(path, samples):
    data = array.array("h", (int(max(-1.0, min(1.0, x)) * 32767) for x in samples))
    if sys.byteorder == "big":
        data.byteswap()
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())


def build_music_samples():
    """Bucle chiptune tranquilo de ~13 s (Am - F - C - G, dos pasadas)."""
    step = 0.2
    chords = [(110.0, [220.0, 261.63, 329.63, 440.0]),
              (87.31, [174.61, 220.0, 261.63, 349.23]),
              (130.81, [261.63, 329.63, 392.0, 523.25]),
              (98.0, [196.0, 246.94, 293.66, 392.0])]
    pattern = [0, 1, 2, 3, 2, 1, 2, 1]
    out = []
    for lap in range(2):
        mult = 1 if lap == 0 else 2
        for root, notes in chords:
            bass = []
            for h in range(4):
                bass += tone(root * (1.5 if h == 2 else 1.0), step * 2, 0.30, "tri", decay=2.5)
            lead = []
            for idx in pattern:
                lead += tone(notes[idx] * mult, step, 0.09, "square", decay=6)
            out += [a + b for a, b in zip(bass, lead)]
    return out


class Sound:
    """Efectos y música generados por código. Funciona sin instalar nada:
    Windows (MCI/winsound), macOS (afplay) y Linux (paplay/aplay/play/ffplay)."""

    EFFECTS = {
        "flip": lambda: tone(620, 0.09, 0.35, "tri", slide=980),
        "match": lambda: seq([(523.25, .08), (659.25, .08), (783.99, .08), (1046.5, .20)], "square", 0.17),
        "cpu_match": lambda: seq([(392.0, .09), (493.88, .09), (587.33, .18)], "saw", 0.17),
        "fail": lambda: tone(300, 0.28, 0.28, "saw", slide=170),
        "miss": lambda: tone(420, 0.14, 0.22, "tri", slide=330),
        "click": lambda: tone(880, 0.05, 0.30, "sine"),
        "start": lambda: seq([(392.0, .07), (523.25, .07), (659.25, .14)], "tri", 0.40),
        "win": lambda: seq([(523.25, .12), (659.25, .12), (783.99, .12), (1046.5, .20),
                            (783.99, .10), (1046.5, .45)], "square", 0.17),
        "tie": lambda: seq([(440.0, .18), (440.0, .18), (392.0, .32)], "tri", 0.38),
        "lose": lambda: seq([(392.0, .20), (329.63, .20), (261.63, .20), (196.0, .55)], "saw", 0.20),
    }

    def __init__(self):
        self.enabled = True
        self.files = {}
        self.music_len = 13.0
        self.music_ready = False
        self.backend = None
        self.cmd = None
        self._mci = None
        self._mci_ok = set()
        self._proc = None
        self.dir = None
        try:
            self.dir = tempfile.mkdtemp(prefix="techmemory_")
            atexit.register(self.cleanup)
            for name, fn in self.EFFECTS.items():
                p = os.path.join(self.dir, name + ".wav")
                write_wav(p, fn())
                self.files[name] = p
            self._detect()
            if self.backend == "mci":
                for name, p in self.files.items():
                    if self._mci_send(f'open "{p}" type waveaudio alias fx_{name}') == 0:
                        self._mci_ok.add(name)
            threading.Thread(target=self._build_music, daemon=True).start()
        except Exception:
            self.backend = None

    def _build_music(self):
        try:
            samples = build_music_samples()
            p = os.path.join(self.dir, "music.wav")
            write_wav(p, samples)
            self.files["music"] = p
            self.music_len = len(samples) / RATE
            self.music_ready = True
        except Exception:
            pass

    def _detect(self):
        if sys.platform.startswith("win"):
            try:
                import ctypes
                self._mci = ctypes.windll.winmm.mciSendStringW
                self.backend = "mci"
                return
            except Exception:
                pass
            try:
                import winsound  # noqa: F401
                self.backend = "winsound"
            except Exception:
                self.backend = None
        elif sys.platform == "darwin":
            if shutil.which("afplay"):
                self.backend, self.cmd = "cmd", "afplay"
        else:
            for c in ("paplay", "aplay", "play", "ffplay"):
                if shutil.which(c):
                    self.backend, self.cmd = "cmd", c
                    break

    def _mci_send(self, s):
        try:
            return self._mci(s, None, 0, 0)
        except Exception:
            return -1

    def _cmdline(self, path, music=False):
        c = self.cmd
        if c == "afplay":
            return ["afplay", "-v", "0.6", path] if music else ["afplay", path]
        if c == "aplay":
            return ["aplay", "-q", path]
        if c == "play":
            return ["play", "-q", path]
        if c == "ffplay":
            return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]
        return [c, path]

    def play(self, name):
        if not self.enabled or not self.backend or name not in self.files:
            return
        try:
            if self.backend == "mci":
                if name in self._mci_ok:
                    self._mci_send(f"play fx_{name} from 0")
                else:
                    import winsound
                    winsound.PlaySound(self.files[name], winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif self.backend == "winsound":
                import winsound
                winsound.PlaySound(self.files[name], winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                subprocess.Popen(self._cmdline(self.files[name]),
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def start_music(self):
        if not self.enabled or not self.backend or "music" not in self.files:
            return
        try:
            if self.backend == "mci":
                self._mci_send("close bgm")
                self._mci_send(f'open "{self.files["music"]}" type waveaudio alias bgm')
                self._mci_send("setaudio bgm volume to 500")
                self._mci_send("play bgm from 0")
            elif self.backend == "cmd":
                self.stop_music()
                self._proc = subprocess.Popen(self._cmdline(self.files["music"], True),
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def stop_music(self):
        try:
            if self.backend == "mci":
                self._mci_send("stop bgm")
                self._mci_send("close bgm")
            if self._proc is not None:
                self._proc.terminate()
                self._proc = None
        except Exception:
            pass

    def cleanup(self):
        try:
            self.stop_music()
            if self.backend == "mci":
                self._mci_send("close all")
            if self.dir:
                shutil.rmtree(self.dir, ignore_errors=True)
                self.dir = None
        except Exception:
            pass


# ───────────────────────── juego ─────────────────────────
class Game:
    def __init__(self, root):
        self.root = root
        root.title("TECH MEMORY · Humano vs Máquina")
        root.configure(bg=C["bg"])
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"1100x800+{max(0, (sw - 1100) // 2)}+{max(0, (sh - 800) // 2 - 20)}")
        root.minsize(800, 600)
        self.raw = tk.Canvas(root, width=1100, height=800, bg=C["bg"], highlightthickness=0)
        self.raw.pack(fill=tk.BOTH, expand=True)
        self.cv = View(self.raw)

        self.cfg = load_cfg()
        self.diff_i = self.cfg.get("difficulty", 0)
        if not isinstance(self.diff_i, int) or not 0 <= self.diff_i < len(DIFFS):
            self.diff_i = 0
        self.sound = Sound()
        self.sound.enabled = bool(self.cfg.get("sound", True))
        self.music_token = 0

        self.state = "menu"          # menu | play | result
        self.buttons = []
        self.primary = None
        self.level = 1
        self.total = 0
        self.session = 0
        self.cards, self.pos = [], []
        self.particles = []
        self.stars = []
        self.mouse = (-1, -1)
        self.rw = self.rh = 0
        self.t0 = time.time()

        self.fullscreen = True
        try:
            root.attributes("-fullscreen", True)
        except Exception:
            self.fullscreen = False
        self.set_size(sw if self.fullscreen else 1100, sh if self.fullscreen else 800)

        self.raw.bind("<Button-1>", self.on_click)
        self.raw.bind("<Motion>", lambda e: setattr(self, "mouse", (e.x / self.k, e.y / self.k)))
        self.raw.bind("<Configure>", lambda e: self.set_size(e.width, e.height))
        root.bind("<Key>", self.on_key)
        root.protocol("WM_DELETE_WINDOW", self.quit)
        root.after(500, self.music_start)
        self.tick()

    # ── tamaño / pantalla completa ──
    def set_size(self, w, h):
        if w < 200 or h < 200 or (w, h) == (self.rw, self.rh):
            return
        self.rw, self.rh = w, h
        self.k = min(w / DW, h / DH)
        self.cv.k = self.k
        self.W, self.H = w / self.k, h / self.k
        self.ox = (self.W - DW) / 2
        n = min(120, int(45 * self.W * self.H / (DW * DH)))
        self.stars = [[random.uniform(0, self.W), random.uniform(0, self.H), random.uniform(0.1, 0.5),
                       random.choice((1, 1, 2)), random.choice(ICON_COLORS), random.uniform(0, 6.28)]
                      for _ in range(n)]
        self.draw_background()
        if self.cards:
            self.layout()

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        try:
            self.root.attributes("-fullscreen", self.fullscreen)
        except Exception:
            pass

    def quit(self):
        self.sound.cleanup()
        self.root.destroy()

    # ── fondo estático ──
    def draw_background(self):
        cv = self.cv
        self.raw.delete("bg")
        for x in range(0, int(self.W) + 41, 40):
            cv.create_line(x, 0, x, self.H, fill=C["grid"], tags="bg")
        for y in range(0, int(self.H) + 41, 40):
            cv.create_line(0, y, self.W, y, fill=C["grid"], tags="bg")
        rnd = random.Random(7)
        trace = mix(C["bg"], C["cyan"], 0.16)
        for _ in range(int(16 * self.W / DW) + 4):
            x = rnd.choice((0, int(self.W) // 40 * 40))
            y = rnd.randrange(40, max(80, int(self.H) - 40), 40)
            d = 1 if x == 0 else -1
            pts = [x, y]
            for _ in range(3):
                x += d * rnd.randrange(40, 120, 40)
                pts += [x, y]
                y += rnd.choice((-1, 1)) * rnd.randrange(40, 120, 40)
                pts += [x, y]
            cv.create_line(*pts, fill=trace, width=2, tags="bg")
            cv.create_oval(pts[-2] - 4, pts[-1] - 4, pts[-2] + 4, pts[-1] + 4, outline=trace, width=2, tags="bg")
        self.raw.tag_lower("bg")

    # ── sonido ──
    def music_start(self):
        self.music_token += 1
        self.music_cycle(self.music_token)

    def music_cycle(self, tok):
        if tok != self.music_token or not self.sound.enabled:
            return
        if not self.sound.music_ready:
            self.root.after(500, lambda: self.music_cycle(tok))
            return
        self.sound.start_music()
        self.root.after(int(self.sound.music_len * 1000) + 20, lambda: self.music_cycle(tok))

    def toggle_sound(self):
        self.sound.enabled = not self.sound.enabled
        self.cfg["sound"] = self.sound.enabled
        save_cfg(self.cfg)
        if self.sound.enabled:
            self.sound.play("click")
            self.music_start()
        else:
            self.music_token += 1
            self.sound.stop_music()

    def next_diff(self):
        self.diff_i = (self.diff_i + 1) % len(DIFFS)
        self.cfg["difficulty"] = self.diff_i
        save_cfg(self.cfg)

    # ── control de partida ──
    def start(self):
        self.level, self.total = 1, 0
        self.new_level()

    def new_level(self):
        self.session += 1
        cols, rows = LEVELS[min(self.level, len(LEVELS)) - 1]
        n = cols * rows // 2
        vals = random.sample(range(len(ICONS)), n) * 2
        random.shuffle(vals)
        self.cols, self.rows, self.npairs = cols, rows, n
        self.cards = [dict(v=v, p=0.0, tgt=0.0, owner=None, pulse=0.0) for v in vals]
        _, base, slope, cap, _ = DIFFS[self.diff_i]
        self.ai_p = min(cap, base + slope * (self.level - 1))   # probabilidad de memorizar una carta vista
        self.score = {"player": 0, "cpu": 0}
        self.turn = "player"
        self.flipped, self.mem = [], {}
        self.busy = False
        self.tries = 0
        self.msg, self.msg_col = "TU TURNO · elige una carta", C["cyan"]
        self.state = "play"
        self.layout()
        self.sound.play("start")

    def layout(self):
        gap = 14
        x0, x1, y0, y1 = 40, self.W - 40, 205, self.H - 28
        cw = min((x1 - x0 - gap * (self.cols - 1)) / self.cols,
                 (y1 - y0 - gap * (self.rows - 1)) / self.rows)
        gw = self.cols * cw + (self.cols - 1) * gap
        gh = self.rows * cw + (self.rows - 1) * gap
        ox, oy = (self.W - gw) / 2, y0 + ((y1 - y0) - gh) / 2
        self.cw = cw
        self.pos = [(ox + (i % self.cols) * (cw + gap), oy + (i // self.cols) * (cw + gap))
                    for i in range(len(self.cards))]

    def card_at(self, mx, my):
        for i, (x, y) in enumerate(self.pos):
            if x <= mx <= x + self.cw and y <= my <= y + self.cw:
                return i
        return None

    def ai_see(self, i):
        if random.random() < self.ai_p:
            self.mem[i] = self.cards[i]["v"]

    def reveal(self, i):
        c = self.cards[i]
        if c["owner"] is not None or c["tgt"] == 1:
            return
        c["tgt"] = 1
        self.flipped.append(i)
        self.ai_see(i)
        self.sound.play("flip")
        s = self.session
        if len(self.flipped) == 2:
            self.busy = True
            self.root.after(1000, lambda: self.resolve(s))
        elif self.turn == "cpu":
            self.root.after(900, lambda: self.cpu_second(s))
        else:
            self.msg, self.msg_col = "Ahora elige la segunda carta", C["cyan"]

    def resolve(self, s):
        if s != self.session or self.state != "play":
            return
        a, b = self.flipped
        ca, cb = self.cards[a], self.cards[b]
        who = self.turn
        if ca["v"] == cb["v"]:
            col = C["cyan"] if who == "player" else C["magenta"]
            for i in (a, b):
                self.cards[i]["owner"] = who
                self.cards[i]["pulse"] = 1.0
                self.mem.pop(i, None)
                x, y = self.pos[i]
                self.burst(x + self.cw / 2, y + self.cw / 2, col)
            self.score[who] += 1
            self.flipped = []
            self.sound.play("match" if who == "player" else "cpu_match")
            if self.score["player"] + self.score["cpu"] == self.npairs:
                self.busy = True
                self.root.after(1000, lambda: self.finish(s))
                return
            self.busy = False
            if who == "player":
                self.msg, self.msg_col = "¡Pareja! Repites turno", C["green"]
            else:
                self.msg, self.msg_col = "¡La máquina acertó! Vuelve a jugar", C["magenta"]
                self.root.after(800, lambda: self.cpu_first(s))
        else:
            ca["tgt"] = cb["tgt"] = 0
            self.flipped = []
            self.busy = False
            if who == "player":
                self.sound.play("fail")
                self.tries += 1
                self.turn = "cpu"
                self.msg, self.msg_col = "La máquina está pensando…", C["magenta"]
                self.root.after(900, lambda: self.cpu_first(s))
            else:
                self.sound.play("miss")
                self.turn = "player"
                self.msg, self.msg_col = "La máquina falló · TU TURNO", C["cyan"]

    # ── IA de la máquina ──
    def _available(self):
        return [i for i, c in enumerate(self.cards) if c["owner"] is None and c["tgt"] == 0]

    def cpu_first(self, s):
        if s != self.session or self.state != "play" or self.turn != "cpu" or self.flipped:
            return
        avail = self._available()
        if not avail:
            return
        by_val = {}
        for i, v in self.mem.items():
            if i in avail:
                by_val.setdefault(v, []).append(i)
        known = [lst for lst in by_val.values() if len(lst) >= 2]
        if known:
            pick = random.choice(known)[0]
        else:
            unknown = [i for i in avail if i not in self.mem]
            pick = random.choice(unknown or avail)
        self.msg, self.msg_col = "La máquina elige…", C["magenta"]
        self.reveal(pick)

    def cpu_second(self, s):
        if s != self.session or self.state != "play" or self.turn != "cpu" or len(self.flipped) != 1:
            return
        v = self.cards[self.flipped[0]]["v"]
        avail = self._available()
        match = [i for i in avail if self.mem.get(i) == v]
        if match:
            pick = match[0]
        else:
            unknown = [i for i in avail if i not in self.mem]
            pick = random.choice(unknown or avail)
        self.reveal(pick)

    def finish(self, s):
        if s != self.session:
            return
        pp, cp = self.score["player"], self.score["cpu"]
        if pp > cp:
            kind = "win"
            pts = pp * 100 + (pp - cp) * 50 + self.level * 150
            self.total += pts
            for _ in range(8):
                self.burst(random.uniform(150, self.W - 150), random.uniform(120, 420),
                           random.choice(ICON_COLORS), 14)
        elif pp == cp:
            kind, pts = "tie", 0
        else:
            kind, pts = "lose", 0
        self.result = (kind, pts)
        self.state = "result"
        self.sound.play(kind)

    def next_level(self):
        self.level += 1
        self.new_level()

    def to_menu(self):
        self.session += 1
        self.state = "menu"

    # ── entrada ──
    def on_click(self, e):
        lx, ly = e.x / self.k, e.y / self.k
        for x1, y1, x2, y2, cb in self.buttons:
            if x1 <= lx <= x2 and y1 <= ly <= y2:
                self.sound.play("click")
                cb()
                return
        if self.state == "play" and self.turn == "player" and not self.busy:
            i = self.card_at(lx, ly)
            if i is not None:
                self.reveal(i)

    def on_key(self, e):
        k = e.keysym
        if k == "Escape":
            if self.state != "menu":
                self.to_menu()
        elif k.lower() == "m":
            self.toggle_sound()
        elif k == "F11" or k.lower() == "f":
            self.toggle_fullscreen()
        elif k.lower() == "r" and self.state in ("play", "result"):
            self.new_level()
        elif k in ("Return", "space"):
            if self.state == "menu":
                self.start()
            elif self.state == "result" and self.primary:
                self.primary()

    # ── animación ──
    def burst(self, x, y, col, n=16):
        for _ in range(n):
            a, sp = random.uniform(0, 6.283), random.uniform(2, 7)
            self.particles.append([x, y, math.cos(a) * sp, math.sin(a) * sp, 1.0, col])

    def update(self):
        for c in self.cards:
            if c["p"] < c["tgt"]:
                c["p"] = min(c["tgt"], c["p"] + 0.14)
            elif c["p"] > c["tgt"]:
                c["p"] = max(c["tgt"], c["p"] - 0.14)
            c["pulse"] = max(0.0, c["pulse"] - 0.025)
        for p in self.particles:
            p[0] += p[2]
            p[1] += p[3]
            p[3] += 0.15
            p[4] -= 0.03
        self.particles = [p for p in self.particles if p[4] > 0]
        for st in self.stars:
            st[1] -= st[2]
            if st[1] < -5:
                st[0], st[1] = random.uniform(0, self.W), self.H + 5

    def tick(self):
        now = time.time() - self.t0
        self.update()
        self.draw(now)
        self.root.after(30, self.tick)

    # ── dibujo: helpers ──
    def text(self, x, y, s, size, col, anchor="center", bold=True):
        return self.cv.create_text(x, y, text=s, fill=col, anchor=anchor,
                                   font=(FONT, size, "bold" if bold else "normal"), tags="dyn")

    def gtext(self, x, y, s, size, col, anchor="center"):
        g = mix(C["bg"], col, 0.30)
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)):
            self.text(x + dx, y + dy, s, size, g, anchor)
        self.text(x, y, s, size, col, anchor)

    def draw_icon(self, kind, x, y, col):
        cv = self.cv
        if kind in ("snd_on", "snd_off"):
            cv.create_polygon(x - 9, y - 4, x - 4, y - 4, x + 2, y - 9, x + 2, y + 9, x - 4, y + 4, x - 9, y + 4,
                              fill=col, outline=col, tags="dyn")
            if kind == "snd_on":
                for r in (6, 10):
                    cv.create_arc(x + 2 - r, y - r, x + 2 + r, y + r, start=-50, extent=100,
                                  style=tk.ARC, outline=col, width=2, tags="dyn")
            else:
                cv.create_line(x + 5, y - 5, x + 13, y + 5, fill=col, width=2, tags="dyn")
                cv.create_line(x + 5, y + 5, x + 13, y - 5, fill=col, width=2, tags="dyn")
        elif kind == "scr":
            cv.create_rectangle(x - 9, y - 6, x + 9, y + 6, outline=col, width=2, tags="dyn")
            for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                cv.create_line(x + sx * 9, y + sy * 2, x + sx * 9, y + sy * 6, fill=col, width=3, tags="dyn")
                cv.create_line(x + sx * 5, y + sy * 6, x + sx * 9, y + sy * 6, fill=col, width=3, tags="dyn")

    def button(self, cx, cy, w, h, label, col, cb, size=16, icon=None):
        x1, y1, x2, y2 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
        hov = x1 <= self.mouse[0] <= x2 and y1 <= self.mouse[1] <= y2
        if hov:
            rrect(self.cv, x1 - 4, y1 - 4, x2 + 4, y2 + 4, 18, fill="",
                  outline=mix(C["bg"], col, 0.5), width=5, tags="dyn")
        rrect(self.cv, x1, y1, x2, y2, 14, fill=mix(C["bg"], col, 0.30 if hov else 0.14),
              outline=col, width=3, tags="dyn")
        if icon:
            self.draw_icon(icon, x1 + 24, cy, C["white"] if hov else col)
        self.text(cx + (12 if icon else 0), cy, label, size, C["white"] if hov else col)
        self.buttons.append((x1, y1, x2, y2, cb))

    def toolbar(self, cx, cy, in_game):
        on = self.sound.enabled
        items = [("SONIDO: " + ("ON" if on else "OFF"), C["green"] if on else C["red"],
                  self.toggle_sound, "snd_on" if on else "snd_off", 180),
                 ("PANTALLA", C["cyan"], self.toggle_fullscreen, "scr", 160)]
        if in_game:
            items.append(("MENÚ", C["dim"], self.to_menu, None, 100))
        gap = 12
        x = cx - (sum(it[4] for it in items) + gap * (len(items) - 1)) / 2
        for label, col, cb, ic, w in items:
            self.button(x + w / 2, cy, w, 32, label, col, cb, 11, icon=ic)
            x += w + gap

    def panel(self, x1, y1, x2, y2, col, active, now):
        pulse = 0.5 + 0.5 * math.sin(now * 5)
        if active:
            rrect(self.cv, x1 - 4, y1 - 4, x2 + 4, y2 + 4, 22, fill="",
                  outline=mix(C["bg"], col, 0.25 + 0.35 * pulse), width=6, tags="dyn")
        rrect(self.cv, x1, y1, x2, y2, 18, fill=C["panel"],
              outline=col if active else mix(C["bg"], col, 0.4), width=3 if active else 2, tags="dyn")

    # ── dibujo: pantallas ──
    def draw(self, now):
        cv = self.cv
        cv.delete("dyn")
        self.buttons = []
        self.primary = None
        for x, y, _, sz, col, ph in self.stars:
            t = 0.35 + 0.35 * math.sin(now * 2 + ph)
            cv.create_oval(x, y, x + sz, y + sz, fill=mix(C["bg"], col, t), outline="", tags="dyn")
        if self.state == "menu":
            self.draw_menu(now)
        else:
            self.draw_hud(now)
            for i in range(len(self.cards)):
                self.draw_card(i)
        for x, y, _, _, life, col in self.particles:
            r = 2 + 3 * life
            cv.create_oval(x - r, y - r, x + r, y + r, fill=mix(C["bg"], col, life), outline="", tags="dyn")
        if self.state == "result":
            self.draw_result(now)

    def draw_menu(self, now):
        ox, cx = self.ox, self.W / 2
        oy = max(0, (self.H - DH) / 2)
        self.gtext(cx, 120 + oy, "TECH MEMORY", 54, C["cyan"])
        self.gtext(cx, 178 + oy, "HUMANO  VS  MÁQUINA", 20, C["magenta"])
        n = 6
        for k in range(n):
            x = cx + (k - (n - 1) / 2) * 125
            y = 262 + oy + math.sin(now * 2 + k) * 9
            col = ICON_COLORS[k % len(ICON_COLORS)]
            rrect(self.cv, x - 48, y - 48, x + 48, y + 48, 14, fill=C["panel2"],
                  outline=col, width=2, tags="dyn")
            ICONS[[0, 8, 9, 3, 13, 1][k]](self.cv, x, y, 30, col, "dyn", 3)
        rrect(self.cv, ox + 120, 335 + oy, ox + 860, 485 + oy, 16, fill=C["panel"],
              outline=mix(C["bg"], C["cyan"], 0.4), width=2, tags="dyn")
        lines = [
            "▸ Encuentra las parejas de iconos tecnológicos. Si aciertas, repites.",
            "▸ La máquina juega contra ti: recuerda cartas y mejora cada nivel.",
            "▸ Para superar un nivel debes lograr MÁS parejas que la máquina.",
            "▸ Atajos: R reinicia · Esc menú · M sonido · F11 pantalla completa",
        ]
        for k, ln in enumerate(lines):
            self.text(ox + 150, 362 + oy + k * 34, ln, 12, C["white"], "w", bold=False)
        self.toolbar(cx, 520 + oy, False)
        name, _, _, _, dcol = DIFFS[self.diff_i]
        self.button(cx, 575 + oy, 380, 44, f"DIFICULTAD: {name}  ▸", dcol, self.next_diff, 14)
        self.button(cx, 640 + oy, 280, 58, "▶  JUGAR", C["green"], self.start, 20)
        self.button(cx, 704 + oy, 160, 36, "SALIR", C["red"], self.quit, 13)

    def draw_hud(self, now):
        cv = self.cv
        ox, cx = self.ox, self.W / 2
        pl_active = self.turn == "player" and self.state == "play"
        cp_active = self.turn == "cpu" and self.state == "play"
        # jugador
        self.panel(ox + 30, 18, ox + 290, 148, C["cyan"], pl_active, now)
        cv.create_oval(ox + 58, 48, ox + 86, 76, fill=C["cyan"], outline=C["cyan"], tags="dyn")
        cv.create_arc(ox + 44, 82, ox + 100, 138, start=0, extent=180, fill=C["cyan"], outline=C["cyan"], tags="dyn")
        self.text(ox + 112, 44, "TÚ", 17, C["cyan"], "w")
        self.text(ox + 112, 70, "PAREJAS", 9, C["dim"], "w")
        self.text(ox + 112, 106, str(self.score["player"]), 38, C["white"], "w")
        if pl_active:
            self.text(ox + 275, 34, "● TURNO", 9, C["cyan"], "e")
        # máquina
        self.panel(ox + 690, 18, ox + 950, 148, C["magenta"], cp_active, now)
        ic_robot(cv, ox + 735, 88, 26, C["magenta"], "dyn", 3)
        self.text(ox + 780, 44, "MÁQUINA", 17, C["magenta"], "w")
        self.text(ox + 780, 70, "PAREJAS", 9, C["dim"], "w")
        self.text(ox + 780, 106, str(self.score["cpu"]), 38, C["white"], "w")
        self.text(ox + 935, 134, f"IA {DIFFS[self.diff_i][0].lower()} · memoria {int(self.ai_p * 100)}%",
                  8, C["dim"], "e", bold=False)
        if cp_active:
            self.text(ox + 935, 34, "TURNO ●", 9, C["magenta"], "e")
        # centro
        rrect(cv, cx - 180, 18, cx + 180, 148, 18, fill=C["panel"],
              outline=mix(C["bg"], C["yellow"], 0.4), width=2, tags="dyn")
        self.gtext(cx, 44, f"NIVEL {self.level}", 22, C["yellow"])
        self.text(cx, 82, self.msg, 12, self.msg_col)
        left = self.npairs - self.score["player"] - self.score["cpu"]
        self.text(cx, 118, f"Puntos {self.total}  ·  Intentos {self.tries}  ·  Quedan {left}",
                  10, C["dim"], bold=False)
        self.toolbar(cx, 174, True)

    def draw_card(self, i):
        cv = self.cv
        c = self.cards[i]
        x, y = self.pos[i]
        cw = self.cw
        p = c["p"]
        face = p >= 0.5
        sx = max(0.03, abs(1 - 2 * p))
        mx, my = self.mouse
        hover = (self.state == "play" and self.turn == "player" and not self.busy
                 and c["owner"] is None and c["tgt"] == 0 and self.card_at(mx, my) == i)
        if hover:
            y -= 4
        cx, cy = x + cw / 2, y + cw / 2
        tag = f"card{i}"
        tg = ("dyn", tag)
        r = cw * 0.12
        icol = ICON_COLORS[c["v"] % len(ICON_COLORS)]

        if face:
            if c["owner"]:
                oc = C["cyan"] if c["owner"] == "player" else C["magenta"]
                border, fill, glow = oc, mix(C["bg"], oc, 0.14), oc
                gw, ga = 6 + 8 * c["pulse"], 0.35 + 0.5 * c["pulse"]
            else:
                border, fill, glow, gw, ga = icol, "#0b1330", icol, 6, 0.45
            rrect(cv, x - 3, y - 3, x + cw + 3, y + cw + 3, r + 3, fill="",
                  outline=mix(C["bg"], glow, ga), width=gw, tags=tg)
            rrect(cv, x, y, x + cw, y + cw, r, fill=fill, outline=border, width=3, tags=tg)
            ICONS[c["v"]](cv, cx, cy, cw * 0.31, icol, tg, max(2, cw * 0.035))
            if c["owner"]:
                cv.create_oval(x + cw * 0.08, y + cw * 0.08, x + cw * 0.17, y + cw * 0.17,
                               fill=border, outline=border, tags=tg)
        else:
            border = C["cyan"] if hover else mix(C["bg"], C["cyan"], 0.45)
            if hover:
                rrect(cv, x - 3, y - 3, x + cw + 3, y + cw + 3, r + 3, fill="",
                      outline=mix(C["bg"], C["cyan"], 0.4), width=6, tags=tg)
            rrect(cv, x, y, x + cw, y + cw, r, fill=C["panel2"], outline=border, width=2, tags=tg)
            rrect(cv, x + cw * 0.06, y + cw * 0.06, x + cw * 0.94, y + cw * 0.94, r * 0.8,
                  fill="", outline=mix(C["bg"], C["cyan"], 0.18), width=1, tags=tg)
            trace = mix(C["panel2"], C["cyan"], 0.35)
            for pts in (((0.12, 0.28), (0.32, 0.28), (0.32, 0.14), (0.5, 0.14)),
                        ((0.88, 0.72), (0.68, 0.72), (0.68, 0.86), (0.5, 0.86)),
                        ((0.12, 0.62), (0.28, 0.62), (0.28, 0.78)),
                        ((0.88, 0.38), (0.72, 0.38), (0.72, 0.22))):
                flat = []
                for px, py in pts:
                    flat += [x + px * cw, y + py * cw]
                cv.create_line(*flat, fill=trace, width=2, tags=tg)
                ex, ey = flat[-2], flat[-1]
                d = cw * 0.015
                cv.create_oval(ex - d * 2, ey - d * 2, ex + d * 2, ey + d * 2, fill=trace, outline=trace, tags=tg)
            ic_chip(cv, cx, cy, cw * 0.17, mix(C["panel2"], C["cyan"], 0.55), tg, max(2, cw * 0.025))

        cv.scale(tag, cx, cy, sx, 1)

    def draw_result(self, now):
        cv = self.cv
        kind, pts = self.result
        pp, cp = self.score["player"], self.score["cpu"]
        if kind == "win":
            col, title = C["green"], "¡NIVEL SUPERADO!"
        elif kind == "tie":
            col, title = C["yellow"], "¡EMPATE!"
        else:
            col, title = C["red"], "LA MÁQUINA GANÓ"
        cx, cy = self.W / 2, self.H / 2
        px1, py1, px2, py2 = cx - 290, cy - 170, cx + 290, cy + 170
        rrect(cv, px1 + 8, py1 + 10, px2 + 8, py2 + 10, 24, fill="#02040a", outline="", tags="dyn")
        pulse = 0.5 + 0.5 * math.sin(now * 4)
        rrect(cv, px1 - 4, py1 - 4, px2 + 4, py2 + 4, 26, fill="",
              outline=mix(C["bg"], col, 0.25 + 0.3 * pulse), width=6, tags="dyn")
        rrect(cv, px1, py1, px2, py2, 22, fill="#080d22", outline=col, width=3, tags="dyn")
        self.gtext(cx, py1 + 55, title, 30, col)
        self.text(cx, py1 + 110, f"TÚ  {pp}   ·   MÁQUINA  {cp}", 20, C["white"])
        if kind == "win":
            self.text(cx, py1 + 150, f"+{pts} puntos   (total {self.total})", 14, C["yellow"])
            self.primary = self.next_level
            self.button(cx, py1 + 220, 330, 54, "SIGUIENTE NIVEL  ▶", C["green"], self.next_level, 16)
        else:
            msg = "Necesitas más parejas que la máquina para avanzar." if kind == "lose" \
                else "Para avanzar debes superar a la máquina."
            self.text(cx, py1 + 150, msg, 12, C["dim"], bold=False)
            self.primary = self.new_level
            self.button(cx, py1 + 220, 330, 54, "REINTENTAR  ↻", col, self.new_level, 16)
        self.button(cx, py1 + 290, 170, 40, "MENÚ", C["dim"], self.to_menu, 12)


def main():
    root = tk.Tk()
    Game(root)
    root.mainloop()


if __name__ == "__main__":
    main()
