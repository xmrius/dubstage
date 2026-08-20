# -*- coding: utf-8 -*-
"""
DubStage  --  Szenen nachsprechen und am Stueck mit eigener Stimme abspielen.
DubStage  --  dub a scene line by line and play it back with your own voice.

Passt zu den Dub-Packs, die DubForge baut.
"""

import os
import sys
import json
import time
import queue
import textwrap
import tempfile
import threading
import traceback
import webbrowser

import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dubforge_core as pc
import dubstage_core as ds
import updater as upd

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(APP_DIR, "dubstage_settings.json")
OUT_DIR = os.path.join(APP_DIR, "dubs")

try:
    from PIL import Image, ImageTk
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

# ------------------------------------------------------------------ Palette
BG_TOP = "#171a2e"
BG_BOT = "#0a0b12"
PANEL = "#1a1e30"
PANEL_HI = "#242a42"
EDGE = "#333a5c"
TXT = "#eef1ff"
DIM = "#8a92b4"
ACC = "#7c5cff"
ACC_HI = "#9b83ff"
TEAL = "#25d3a4"
TEAL_HI = "#4ee5bb"
RED = "#ff4f6d"
RED_HI = "#ff7b92"
GOLD = "#ffc861"
BAN = "#332e5e"          # Update-Banner / update banner
BAN_TXT = "#241f47"
WAVE_ORIG = "#3c4470"          # Silhouette des Originals
WAVE_ORIG_TXT = "#7079ad"

TAIL = 0.7            # Nachlauf der Aufnahme / recording tail in seconds


# ==========================================================================
LANG = "de"


def set_lang(code):
    global LANG
    LANG = "en" if str(code).lower().startswith("en") else "de"
    pc.set_lang(LANG)


T = {
    "title":      ("DubStage", "DubStage"),
    "tagline":    ("Sprich die Szene selbst ein.", "Dub the scene yourself."),
    "pick":       ("Waehle einen Dub-Pack", "Choose a dub pack"),
    "no_packs":   ("Kein Dub-Pack gefunden.",
                   "No dub pack found."),
    "no_packs_2": ("Ein Dub-Pack braucht ein dub_video (mp4 oder ogv) und "
                   "Clips mit\nZeitstempel im Namen - genau das, was DubForge "
                   "mit Haken bei\n'Mit Video' erzeugt.",
                   "A dub pack needs a dub_video (mp4 or ogv) and clips with "
                   "a\ntimestamp in the name - exactly what DubForge produces "
                   "with\n'With video' ticked."),
    "lines_n":    ("%d Zeilen", "%d lines"),
    "with_back":  ("mit Backing", "with backing"),
    "no_back":    ("ohne Backing", "no backing"),
    "rescan":     ("Neu suchen", "Rescan"),
    "add_folder": ("Ordner hinzufuegen", "Add folder"),
    "mic":        ("Mikrofon", "Microphone"),
    "mic_test":   ("Testen", "Test"),
    "mic_run":    ("Sprich jetzt ...", "Speak now ..."),
    "mic_ok":     ("Pegel %.0f dB - passt", "Level %.0f dB - good"),
    "mic_low":    ("Pegel %.0f dB - zu leise", "Level %.0f dB - too quiet"),
    "mic_none":   ("Nichts angekommen - anderes Geraet waehlen",
                   "Nothing arrived - pick another device"),
    "start":      ("Loslegen", "Start"),
    "loading":    ("Pack wird vorbereitet ...", "Preparing the pack ..."),
    "no_sd":      ("Mikrofon nicht nutzbar: Paket 'sounddevice' fehlt. "
                   "Bitte Setup.bat ausfuehren.",
                   "Microphone unavailable: package 'sounddevice' missing. "
                   "Please run Setup.bat."),
    "no_pil":     ("Videoanzeige braucht 'Pillow'. Bitte Setup.bat ausfuehren.",
                   "Video display needs 'Pillow'. Please run Setup.bat."),

    "menu":       ("Menue", "Menu"),
    "line_of":    ("Zeile %d / %d", "Line %d / %d"),
    "play_orig":  ("Original", "Original"),
    "rec":        ("Aufnehmen", "Record"),
    "rec_again":  ("Nochmal aufnehmen", "Record again"),
    "play_take":  ("Meine Aufnahme", "My take"),
    "stop":       ("Stopp", "Stop"),
    "skip":       ("Zeile leer lassen", "Leave line empty"),
    "prev":       ("Zurueck", "Back"),
    "next":       ("Weiter", "Next"),
    "finish":     ("Fertig", "Done"),
    "recording":  ("AUFNAHME", "RECORDING"),
    "go":         ("LOS", "GO"),
    "hint":       ("Original anhoeren, dann aufnehmen. Beliebig oft.",
                   "Listen to the original, then record. As often as you like."),
    "no_take":    ("noch nichts aufgenommen", "nothing recorded yet"),
    "take_len":   ("Aufnahme %.1f s", "Take %.1f s"),
    "legend_orig": ("Original", "Original"),
    "legend_take": ("Deine Aufnahme", "Your take"),
    "recorded_n": ("%d von %d Zeilen aufgenommen",
                   "%d of %d lines recorded"),

    "finale":     ("Deine Szene", "Your scene"),
    "play_all":   ("Abspielen", "Play"),
    "save":       ("Als Video speichern", "Save as video"),
    "back_edit":  ("Zurueck zu den Zeilen", "Back to the lines"),
    "saving":     ("Video wird geschrieben ...", "Writing the video ..."),
    "saved":      ("Gespeichert:\n%s", "Saved:\n%s"),
    "leave_q":    ("Zurueck zum Menue? Die Aufnahmen gehen verloren.",
                   "Back to the menu? The takes will be lost."),
    "err":        ("Fehler", "Error"),
    "quiet_hint": ("sehr leise - lauter sprechen", "very quiet - speak up"),

    # --- Update
    "upd_head":   ("Version %s ist da", "Version %s is out"),
    "upd_sub":    ("Du hast %s", "You have %s"),
    "upd_more":   ("Was ist neu", "What's new"),
    "upd_less":   ("Zuklappen", "Collapse"),
    "upd_now":    ("Aktualisieren", "Update"),
    "upd_later":  ("Spaeter", "Later"),
    "upd_nonotes": ("Zu dieser Version wurde kein Text hinterlegt.",
                    "No description was published for this version."),
    "upd_ask_t":  ("Update einspielen?", "Install update?"),
    "upd_ask":    ("DubForge und DubStage werden auf %s aktualisiert.\n\n"
                   "Die App schliesst sich, die Dateien werden getauscht "
                   "und die App startet neu.\n"
                   "Packs, Aufnahmen und Einstellungen bleiben unberuehrt.\n\n"
                   "Fortfahren?",
                   "DubForge and DubStage will be updated to %s.\n\n"
                   "The app closes, the files are replaced and the app "
                   "starts again.\n"
                   "Packs, recordings and settings are left untouched.\n\n"
                   "Continue?"),
    "upd_dl":     ("Lade ... %d%%", "Downloading ... %d%%"),
    "upd_check":  ("Pruefe das Archiv ...", "Checking the archive ..."),
    "upd_swap":   ("Tausche Dateien - gleich geht es weiter ...",
                   "Replacing files - back in a moment ..."),
    "upd_fail_t": ("Update fehlgeschlagen", "Update failed"),
    "upd_fail":   ("Es hat nicht geklappt:\n\n%s\n\n"
                   "Du kannst die Version auch von Hand von der "
                   "Release-Seite laden.",
                   "It did not work:\n\n%s\n\n"
                   "You can also download the version by hand from the "
                   "release page."),
}


def t(key, *args):
    pair = T.get(key)
    if not pair:
        return key
    val = pair[1] if LANG == "en" else pair[0]
    return val % args if args else val


def load_cfg():
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cfg(cfg):
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ==========================================================================
#  Zeichen-Helfer / drawing helpers
# ==========================================================================

def lerp_color(c1, c2, f):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(
        int(a[i] + (b[i] - a[i]) * f) for i in range(3))


def round_rect(cv, x0, y0, x1, y1, r=14, **kw):
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
           x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return cv.create_polygon(pts, smooth=True, **kw)


class Button(object):
    """Selbstgezeichneter Knopf mit Hover- und Sperrzustand."""

    STYLES = {
        "primary": (ACC, ACC_HI, "#ffffff"),
        "record":  (RED, RED_HI, "#2b0710"),
        "go":      (TEAL, TEAL_HI, "#062a20"),
        "ghost":   (PANEL_HI, EDGE, TXT),
        "flat":    ("", "", DIM),
    }

    def __init__(self, cv, x, y, w, h, text, command, kind="ghost",
                 font=("Segoe UI Semibold", 11), radius=None):
        self.cv = cv
        self.box = (x, y, x + w, y + h)
        self.command = command
        self.kind = kind
        self.enabled = True
        self.hover = False
        r = radius if radius is not None else min(16, h / 2)
        if kind == "flat":
            self.rect = None
        else:
            self.rect = round_rect(cv, x, y, x + w, y + h, r=r,
                                   fill=self.STYLES[kind][0], outline="")
        self.label = cv.create_text(x + w / 2, y + h / 2, text=text,
                                    fill=self.STYLES[kind][2], font=font)
        self.refresh()

    def refresh(self):
        base, hi, fg = self.STYLES[self.kind]
        if not self.enabled:
            fill, txt = PANEL, "#565d7d"
        elif self.hover:
            fill, txt = (hi if self.kind != "flat" else "", TXT)
        else:
            fill, txt = base, fg
        if self.rect is not None:
            self.cv.itemconfigure(self.rect, fill=fill)
        self.cv.itemconfigure(self.label, fill=txt)

    def set_enabled(self, value):
        value = bool(value)
        if value != self.enabled:
            self.enabled = value
            self.refresh()

    def set_text(self, text):
        self.cv.itemconfigure(self.label, text=text)

    def hit(self, x, y):
        x0, y0, x1, y1 = self.box
        return x0 <= x <= x1 and y0 <= y <= y1

    def set_hover(self, value):
        if value != self.hover:
            self.hover = value
            self.refresh()


# ==========================================================================
class Game(tk.Tk):

    def __init__(self):
        super().__init__()
        self.cfg = load_cfg()
        set_lang(self.cfg.get("lang", "de"))
        self.title(t("title"))
        # Nicht groesser oeffnen als der Bildschirm hergibt - sonst liegt
        # die untere Knopfleiste hinter der Taskleiste.
        sh = self.winfo_screenheight()
        self.geometry("1200x%d" % min(900, max(780, sh - 130)))
        self.minsize(1020, 780)
        self.configure(bg=BG_BOT)

        self.msgq = queue.Queue()
        self.mic = ds.Mic(ds.SR)
        self.packs = []
        self.pack = None
        self.line_i = 0
        self.mix = None
        self.screen = "menu"
        self.phase = "idle"           # idle | listen | record | play
        self._phase_deadline = None
        self.sel_pack = 0
        self.menu_scroll = 0
        self._scanned = False
        self._busy = False
        self._photo = None
        self._imgcache = {}
        self._frame_size = None
        self._last_idx = None
        self._play = None             # laufende Wiedergabe / running playback
        self._rec_guard = None
        self._rec_done = True
        self._resize_job = None
        self._embedded = []
        self.buttons = []
        self.chips = []

        self.upd_info = None          # gefundenes Release / found release
        self.upd_open = False         # Changelog aufgeklappt?
        self.upd_busy = False
        self.upd_dismissed = False
        self.upd_sub_item = None
        self.upd_scroll = 0           # Zeile oben im Changelog
        self.upd_maxscroll = 0
        self.upd_rect = None          # Flaeche des Changelog-Feldes

        self.cv = tk.Canvas(self, bg=BG_BOT, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Configure>", self._on_resize)
        self.cv.bind("<Motion>", self._on_motion)
        self.cv.bind("<Button-1>", self._on_click)
        self.cv.bind("<MouseWheel>", self._on_wheel)
        self.bind("<Escape>", lambda e: self._on_escape())
        self.bind("<space>", lambda e: self._on_space())

        self._style()
        self.after(50, self.show_menu)
        self.after(60, self._pump)
        self.after(1400, self._check_update)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure("Mic.TCombobox", fieldbackground=PANEL_HI,
                    background=PANEL_HI, foreground=TXT, arrowcolor=TXT,
                    bordercolor=EDGE, lightcolor=PANEL_HI, darkcolor=PANEL_HI,
                    selectbackground=PANEL_HI, selectforeground=TXT)
        # "readonly" hat eigene Farben, die configure() nicht erreicht
        s.map("Mic.TCombobox",
              fieldbackground=[("readonly", PANEL_HI), ("disabled", PANEL)],
              background=[("readonly", PANEL_HI), ("active", PANEL_HI)],
              foreground=[("readonly", TXT), ("disabled", DIM)],
              selectbackground=[("readonly", PANEL_HI), ("focus", PANEL_HI)],
              selectforeground=[("readonly", TXT), ("focus", TXT)],
              arrowcolor=[("readonly", TXT), ("disabled", DIM)])
        # Die aufklappende Liste ist ein Tk-Widget, das ttk nicht gestaltet
        self.option_add("*TCombobox*Listbox.background", PANEL_HI)
        self.option_add("*TCombobox*Listbox.foreground", TXT)
        self.option_add("*TCombobox*Listbox.selectBackground", ACC)
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.option_add("*TCombobox*Listbox.borderWidth", 0)

    # ------------------------------------------------------------- Basics
    def size(self):
        w = self.cv.winfo_width()
        h = self.cv.winfo_height()
        return (w if w > 300 else 1200), (h if h > 300 else 900)

    def _clear_canvas(self):
        for w in self._embedded:
            try:
                w.destroy()
            except Exception:
                pass
        self._embedded = []
        self.buttons = []
        self.chips = []
        self.cv.delete("all")
        self._photo = None

    def _backdrop(self):
        w, h = self.size()
        steps = 46
        for i in range(steps):
            y0 = h * i / steps
            y1 = h * (i + 1) / steps + 1
            self.cv.create_rectangle(
                0, y0, w, y1, width=0,
                fill=lerp_color(BG_TOP, BG_BOT, i / float(steps - 1)))
        # weicher Lichtkegel oben mittig
        for i in range(9):
            f = i / 9.0
            rw = w * (0.18 + 0.42 * f)
            self.cv.create_oval(w / 2 - rw, -h * 0.42 + f * 40,
                                w / 2 + rw, h * (0.16 + 0.30 * f),
                                fill=lerp_color(BG_TOP, "#2a2f55", 0.5 - f * 0.5),
                                outline="")

    def _btn(self, *a, **kw):
        b = Button(self.cv, *a, **kw)
        self.buttons.append(b)
        return b

    def _on_resize(self, _e=None):
        if self._resize_job:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.after(140, self._rebuild)

    def _rebuild(self):
        self._resize_job = None
        if self.screen == "menu":
            self.show_menu()
        elif self.screen == "stage":
            self.build_stage()
        elif self.screen == "finale":
            self.build_finale()

    def _on_motion(self, e):
        for b in self.buttons:
            b.set_hover(b.enabled and b.hit(e.x, e.y))

    def _on_click(self, e):
        for b in self.buttons:
            if b.enabled and b.hit(e.x, e.y):
                b.command()
                return
        if self.screen == "menu":
            for i, (x0, y0, x1, y1) in enumerate(self.chips):
                if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                    self.sel_pack = self.menu_scroll + i
                    self.show_menu()
                    return
        elif self.screen == "stage" and self.phase == "idle":
            for i, (x0, y0, x1, y1) in enumerate(self.chips):
                if x0 <= e.x <= x1 and y0 - 8 <= e.y <= y1 + 8:
                    self.goto_line(i)
                    return

    def _on_wheel(self, e):
        if self.screen != "menu":
            return
        step = -1 if e.delta > 0 else 1
        # Ueber dem Changelog blaettert das Rad im Changelog.
        r = self.upd_rect
        if r and r[0] <= e.x <= r[2] and r[1] <= e.y <= r[3]:
            new = max(0, min(self.upd_maxscroll, self.upd_scroll + step * 3))
            if new != self.upd_scroll:
                self.upd_scroll = new
                self.show_menu()
            return
        self.menu_scroll = max(0, self.menu_scroll - (1 if e.delta > 0 else -1))
        self.show_menu()

    def _on_escape(self):
        if self.screen == "stage":
            self.leave_round()
        elif self.screen == "finale":
            self.show_menu()

    def _on_space(self):
        if self.screen == "stage" and self.phase == "idle":
            self.do_record()
        elif self.screen == "finale":
            self.toggle_finale_play()

    # ==================================================================
    #  MENUE
    # ==================================================================
    def show_menu(self):
        self.screen = "menu"
        self._set_phase("idle")
        self._stop_audio()
        if not self._scanned:
            self._scanned = True
            self.packs = ds.find_packs(
                extra_dirs=self.cfg.get("extra_dirs") or [])
            self.sel_pack = min(self.sel_pack, max(0, len(self.packs) - 1))
        self._clear_canvas()
        self._backdrop()
        w, h = self.size()
        cv = self.cv

        cv.create_text(w / 2, 62, text="DUBSTAGE", fill=TXT,
                       font=("Segoe UI Black", 40))
        cv.create_rectangle(w / 2 - 90, 92, w / 2 + 90, 95, fill=ACC, width=0)
        cv.create_text(w / 2, 116, text=t("tagline"), fill=DIM,
                       font=("Segoe UI", 12))

        # Sprachumschalter
        for i, (code, label) in enumerate((("de", "DE"), ("en", "EN"))):
            x = w - 120 + i * 52
            active = (LANG == code)
            round_rect(cv, x, 26, x + 46, 54, r=14,
                       fill=ACC if active else PANEL, outline="")
            cv.create_text(x + 23, 40, text=label,
                           fill="#ffffff" if active else DIM,
                           font=("Segoe UI Semibold", 10))
        self._btn(w - 120, 26, 46, 28, "", lambda: self._set_lang("de"), "flat")
        self._btn(w - 68, 26, 46, 28, "", lambda: self._set_lang("en"), "flat")

        off = self._draw_update_banner(cv, w, h)

        cv.create_text(70, 168 + off, text=t("pick"), fill=TXT, anchor="w",
                       font=("Segoe UI Semibold", 14))

        # ---- Pack-Karten
        list_x0, list_x1 = 70, w - 70
        card_h, gap = 74, 12
        top = 196 + off
        avail = h - top - 210
        per_page = max(1, int(avail // (card_h + gap)))
        self.menu_scroll = max(0, min(self.menu_scroll,
                                      max(0, len(self.packs) - per_page)))
        visible = self.packs[self.menu_scroll:self.menu_scroll + per_page]

        if not self.packs:
            round_rect(cv, list_x0, top, list_x1, top + 150, r=18,
                       fill=PANEL, outline=EDGE)
            cv.create_text((list_x0 + list_x1) / 2, top + 52,
                           text=t("no_packs"), fill=GOLD,
                           font=("Segoe UI Semibold", 14))
            cv.create_text((list_x0 + list_x1) / 2, top + 100,
                           text=t("no_packs_2"), fill=DIM,
                           font=("Segoe UI", 10), justify="center")
        for i, p in enumerate(visible):
            gi = self.menu_scroll + i
            y = top + i * (card_h + gap)
            sel = (gi == self.sel_pack)
            round_rect(cv, list_x0, y, list_x1, y + card_h, r=16,
                       fill=PANEL_HI if sel else PANEL,
                       outline=ACC if sel else EDGE)
            cv.create_text(list_x0 + 26, y + 26, anchor="w", text=p.name,
                           fill=TXT if sel else "#c9cfe8",
                           font=("Segoe UI Semibold", 14))
            dur = pc.probe_duration(p.video)
            meta = "%s   -   %s   -   %s" % (
                t("lines_n", len(p.lines)), pc.fmt_time(dur)[:-4],
                t("with_back") if p.backing else t("no_back"))
            cv.create_text(list_x0 + 26, y + 50, anchor="w", text=meta,
                           fill=DIM, font=("Segoe UI", 10))
            if sel:
                cv.create_text(list_x1 - 26, y + card_h / 2, anchor="e",
                               text="▶", fill=ACC,
                               font=("Segoe UI", 18))
            self.chips.append((list_x0, y, list_x1, y + card_h))

        if len(self.packs) > per_page:
            cv.create_text(w / 2, top + per_page * (card_h + gap) + 6,
                           text="%d / %d" % (self.menu_scroll + len(visible),
                                             len(self.packs)),
                           fill=DIM, font=("Segoe UI", 9))

        # ---- Mikrofonzeile
        my = h - 168
        round_rect(cv, 70, my, w - 70, my + 66, r=16, fill=PANEL, outline=EDGE)
        cv.create_text(96, my + 33, anchor="w", text=t("mic"), fill=DIM,
                       font=("Segoe UI Semibold", 11))
        if self.mic.available:
            devs = self.mic.devices()
            names = ["%d  %s" % (i, n) for i, n in devs]
            self.mic_var = tk.StringVar(
                value=self.cfg.get("mic") if self.cfg.get("mic") in names
                else (names[0] if names else ""))
            box = ttk.Combobox(self, textvariable=self.mic_var, width=44,
                               state="readonly", values=names,
                               style="Mic.TCombobox")
            self._embedded.append(box)
            cv.create_window(180, my + 33, window=box, anchor="w")
            self._btn(w - 250, my + 17, 100, 32, t("mic_test"),
                      self.test_mic, "ghost")
            self.mic_msg = cv.create_text(w - 270, my + 33, anchor="e",
                                          text="", fill=DIM,
                                          font=("Segoe UI", 10))
        else:
            cv.create_text(180, my + 33, anchor="w", text=t("no_sd"),
                           fill=RED, font=("Segoe UI", 10))
            self.mic_msg = None

        # ---- untere Knopfleiste
        by = h - 78
        self._btn(70, by, 140, 44, t("rescan"), self.scan_packs, "ghost")
        self._btn(222, by, 176, 44, t("add_folder"), self.add_folder, "ghost")
        start = self._btn(w - 250, by, 180, 44, t("start"), self.start_round,
                          "go", font=("Segoe UI Semibold", 13))
        start.set_enabled(bool(self.packs) and self.mic.available and HAVE_PIL)
        self.status_item = cv.create_text(w / 2, by + 22, text="", fill=DIM,
                                          font=("Segoe UI", 10))

    # ==================================================================
    #  UPDATE
    # ==================================================================
    def _draw_update_banner(self, cv, w, h):
        """Banner im Menue. Gibt zurueck, um wieviel alles darunter rutscht."""
        info = self.upd_info
        self.upd_rect = None
        self.upd_sub_item = None
        if not info or self.upd_dismissed:
            return 0

        x0, x1 = 70, w - 70
        y0 = 140
        strip = 62
        notes_h = 0
        if self.upd_open:
            # nie so hoch, dass von der Packliste nichts mehr uebrig bleibt
            notes_h = max(70, min(190, h - 560))
        bh = strip + (notes_h + 12 if self.upd_open else 0)

        round_rect(cv, x0, y0, x1, y0 + bh, r=16, fill=BAN, outline=ACC)
        cv.create_text(x0 + 24, y0 + 22, anchor="w",
                       text=t("upd_head", info.get("version", "?")),
                       fill="#ffffff", font=("Segoe UI Semibold", 13))
        self.upd_sub_item = cv.create_text(
            x0 + 24, y0 + 44, anchor="w",
            text=t("upd_sub", upd.VERSION), fill="#b6b1dc",
            font=("Segoe UI", 10))

        # Knoepfe von rechts nach links
        bx = x1 - 22
        for label, cmd, style, bw in (
                (t("upd_later"), self._hide_banner, "flat", 92),
                (t("upd_now"), self._do_update, "go", 150),
                (t("upd_less") if self.upd_open else t("upd_more"),
                 self._toggle_notes, "ghost", 140)):
            bx -= bw
            b = self._btn(bx, y0 + 15, bw, 32, label, cmd, style)
            if style == "go" and self.upd_busy:
                b.set_enabled(False)
            bx -= 8

        self.upd_rect = None
        if self.upd_open:
            ny = y0 + strip
            round_rect(cv, x0 + 16, ny, x1 - 16, ny + notes_h, r=12,
                       fill=BAN_TXT, outline="")
            text = upd.plain_notes(info.get("notes")) or t("upd_nonotes")
            # Der Canvas bricht selbst um, blaettern muessen wir selbst.
            cols = max(20, int((x1 - x0 - 68) / 6.9))
            rows = max(3, int((notes_h - 18) / 17))
            lines = []
            for para in text.split("\n"):
                lines.extend(textwrap.wrap(para, cols) or [""])

            top_line = max(0, min(self.upd_scroll, max(0, len(lines) - rows)))
            self.upd_scroll = top_line
            self.upd_rect = (x0 + 16, ny, x1 - 16, ny + notes_h)
            self.upd_maxscroll = max(0, len(lines) - rows)

            cv.create_text(x0 + 32, ny + 10, anchor="nw",
                           text="\n".join(lines[top_line:top_line + rows]),
                           fill="#ded9ff", font=("Segoe UI", 10),
                           justify="left", width=x1 - x0 - 64)
            if self.upd_maxscroll:
                cv.create_text(x1 - 30, ny + notes_h - 12, anchor="se",
                               text="%d / %d  -  Mausrad"
                                    % (top_line + rows, len(lines)),
                               fill="#8c86bb", font=("Segoe UI", 8))
        return bh + 16

    def _check_update(self):
        cache = self.cfg.get("upd_cache") or {}
        if cache.get("tag") and upd.is_newer(cache["tag"]):
            self.upd_info = cache
            if self.screen == "menu":
                self.show_menu()
        if not upd.due(self.cfg):
            return

        def work():
            try:
                info = upd.check_latest()
            except Exception:
                return                      # kein Netz, kein Drama
            self.msgq.put(("update", info))

        threading.Thread(target=work, daemon=True).start()

    def _toggle_notes(self):
        self.upd_open = not self.upd_open
        self.show_menu()

    def _hide_banner(self):
        self.upd_dismissed = True
        self.show_menu()

    def _upd_say(self, text):
        if self.upd_sub_item is None:
            return
        try:
            self.cv.itemconfigure(self.upd_sub_item, text=text, fill=GOLD)
        except Exception:
            pass

    def _do_update(self):
        info = self.upd_info
        if not info or self.upd_busy:
            return
        if not info.get("zip"):
            webbrowser.open(info.get("page") or upd.RELEASES_PAGE)
            return
        if not messagebox.askyesno(t("upd_ask_t"),
                                   t("upd_ask", info.get("tag", "?"))):
            return

        self.upd_busy = True
        self.show_menu()
        self._upd_say(t("upd_dl", 0))

        def work():
            wd = tempfile.mkdtemp(prefix="dubstage_upd_")
            try:
                zp = os.path.join(wd, "release.zip")

                def prog(done, total):
                    pct = int(done * 100 / total) if total else 0
                    self.msgq.put(("upd_say", t("upd_dl", pct)))

                upd.download_zip(info["zip"], zp, progress=prog)
                self.msgq.put(("upd_say", t("upd_check")))
                root = upd.stage(zp, os.path.join(wd, "neu"))
                self.msgq.put(("upd_say", t("upd_swap")))
                upd.apply(root, APP_DIR, which="DubStage",
                          tag=info.get("tag", ""))
                self.msgq.put(("upd_quit", None))
            except Exception as e:
                self.msgq.put(("upd_error", "%s" % e))

        threading.Thread(target=work, daemon=True).start()

    def _set_lang(self, code):
        if code == LANG:
            return
        set_lang(code)
        self.cfg["lang"] = LANG
        save_cfg(self.cfg)
        self.show_menu()

    def scan_packs(self):
        self._scanned = False
        self.show_menu()

    def add_folder(self):
        d = filedialog.askdirectory(title=t("add_folder"))
        if not d:
            return
        extra = self.cfg.get("extra_dirs") or []
        if d not in extra:
            extra.append(d)
        self.cfg["extra_dirs"] = extra
        save_cfg(self.cfg)
        self._scanned = False
        self.show_menu()

    def test_mic(self):
        if not self.mic.available or self._busy:
            return
        self._busy = True
        if self.mic_msg:
            self.cv.itemconfigure(self.mic_msg, text=t("mic_run"), fill=GOLD)
        try:
            self.mic.start(device=self._mic_device())
        except Exception as ex:
            self._busy = False
            messagebox.showerror(t("err"), str(ex))
            return
        self.after(2200, self._finish_mic_test)

    def _finish_mic_test(self):
        data = self.mic.stop()
        self._busy = False
        lvl = ds.rms_db(data)
        if self.mic_msg is None:
            return
        if not len(data) or lvl < -70:
            self.cv.itemconfigure(self.mic_msg, text=t("mic_none"), fill=RED)
        elif lvl < -40:
            self.cv.itemconfigure(self.mic_msg, text=t("mic_low", lvl),
                                  fill=GOLD)
        else:
            self.cv.itemconfigure(self.mic_msg, text=t("mic_ok", lvl),
                                  fill=TEAL)
            self.mic.play(ds.normalize(data, 0.9))
        self.cfg["mic"] = self.mic_var.get()
        save_cfg(self.cfg)

    def _mic_device(self):
        try:
            return int(self.mic_var.get().split()[0])
        except Exception:
            return None

    # ==================================================================
    #  RUNDE VORBEREITEN
    # ==================================================================
    def start_round(self):
        if not self.packs:
            return
        if not self.mic.available:
            messagebox.showerror(t("err"), t("no_sd"))
            return
        if not HAVE_PIL:
            messagebox.showerror(t("err"), t("no_pil"))
            return
        self.pack = self.packs[self.sel_pack]
        self.cfg["mic"] = self.mic_var.get()
        save_cfg(self.cfg)
        self.cv.itemconfigure(self.status_item, text=t("loading"), fill=GOLD)
        for b in self.buttons:
            b.set_enabled(False)
        self.update_idletasks()

        fps = int(self.cfg.get("video_fps") or ds.FRAME_FPS)

        def work():
            ds.load_pack_audio(self.pack)
            ds.extract_frames(self.pack, fps=max(8, min(30, fps)))

        def done():
            for l in self.pack.lines:
                l.take = None
            self.line_i = 0
            self._imgcache = {}
            self._probe_frame_size()
            self.build_stage()
        self._run_bg(work, done)

    # ==================================================================
    #  BUEHNE
    # ==================================================================
    def build_stage(self):
        self.screen = "stage"
        self._clear_canvas()
        self._backdrop()
        cv = self.cv
        w, h = self.size()
        pad = 34

        # Kopfzeile
        self._btn(pad, 24, 110, 38, "‹  " + t("menu"), self.leave_round,
                  "flat", font=("Segoe UI", 11))
        cv.create_text(w / 2, 43, text=self.pack.name, fill=TXT,
                       font=("Segoe UI Semibold", 15))
        self.hdr_count = cv.create_text(w - pad, 43, anchor="e", text="",
                                        fill=DIM,
                                        font=("Segoe UI Semibold", 12))

        # Videoflaeche
        top = 82
        bottom_needed = 382          # Leiste, Untertitel, Vergleich, Knoepfe
        vw, vh = self._video_size(w, h - top - bottom_needed, pad)
        vx = (w - vw) / 2
        vy = top
        self.video_box = (vx, vy, vw, vh)
        self._last_idx = None
        round_rect(cv, vx - 8, vy - 8, vx + vw + 8, vy + vh + 8, r=18,
                   fill="#05060a", outline=EDGE)
        self.video_item = cv.create_image(vx + vw / 2, vy + vh / 2,
                                          anchor="center")
        self.overlay_rect = round_rect(cv, vx, vy, vx + vw, vy + vh, r=12,
                                       fill="#000000", stipple="gray50",
                                       outline="", state="hidden")
        self.overlay_text = cv.create_text(vx + vw / 2, vy + vh / 2, text="",
                                           fill=GOLD,
                                           font=("Segoe UI Black", 68),
                                           state="hidden")

        # Zeitleiste der Zeilen
        ty = vy + vh + 18
        self.timeline_y = ty
        self._build_timeline(vx, vw, ty)

        # Untertitel - das, was gesprochen werden soll
        cy = ty + 28
        self.caption_item = cv.create_text(
            vx + vw / 2, cy, anchor="n", text="", fill=GOLD,
            font=("Segoe UI Semibold", 16), width=vw - 40, justify="center")

        # Zeilenname und Zeitbereich, klein darunter
        ny = cy + 54
        self.line_title = cv.create_text(vx, ny, anchor="w", text="", fill=DIM,
                                         font=("Segoe UI", 10))
        self.line_time = cv.create_text(vx + vw, ny, anchor="e", text="",
                                        fill=DIM, font=("Consolas", 10))

        # Vergleichsstreifen: Original als Silhouette, Aufnahme darueber
        sy = ny + 16
        sh = 78
        self.strip_box = (vx, sy, vw, sh)
        round_rect(cv, vx, sy, vx + vw, sy + sh, r=10, fill="#11141f",
                   outline=EDGE)
        cv.create_line(vx + 10, sy + sh / 2, vx + vw - 10, sy + sh / 2,
                       fill="#252b47")
        self.strip_orig = cv.create_polygon(0, 0, 0, 0, 0, 0, fill=WAVE_ORIG,
                                            outline="", state="hidden")
        self.strip_take = cv.create_polygon(0, 0, 0, 0, 0, 0, fill=TEAL,
                                            outline="", stipple="gray50",
                                            state="hidden")
        self.strip_head = cv.create_line(0, 0, 0, 0, fill=GOLD, width=1,
                                         state="hidden")
        self.strip_msg = cv.create_text(vx + vw / 2, sy + sh / 2, text="",
                                        fill=DIM, font=("Segoe UI", 10))
        cv.create_text(vx + 12, sy + 12, anchor="w", text=t("legend_orig"),
                       fill=WAVE_ORIG_TXT, font=("Segoe UI Semibold", 9))
        self.legend_take = cv.create_text(vx + vw - 12, sy + 12, anchor="e",
                                          text=t("legend_take"), fill=TEAL,
                                          font=("Segoe UI Semibold", 9))
        self.strip_info = cv.create_text(vx + vw - 12, sy + sh - 12,
                                         anchor="e", text="", fill=DIM,
                                         font=("Segoe UI", 9))

        # Knopfreihe
        by = sy + sh + 20
        bw, bh = 190, 52
        gapx = 16
        total = bw * 3 + gapx * 2
        bx = (w - total) / 2
        self.b_orig = self._btn(bx, by, bw, bh, "▶  " + t("play_orig"),
                                self.play_original, "ghost",
                                font=("Segoe UI Semibold", 12))
        self.b_rec = self._btn(bx + bw + gapx, by, bw, bh,
                               "●  " + t("rec"), self.do_record, "record",
                               font=("Segoe UI Semibold", 13))
        self.b_take = self._btn(bx + 2 * (bw + gapx), by, bw, bh,
                                "▶  " + t("play_take"), self.play_take,
                                "ghost", font=("Segoe UI Semibold", 12))

        # Navigationsreihe
        ny2 = by + bh + 18
        self.b_prev = self._btn(bx, ny2, 130, 42, "‹  " + t("prev"),
                                self.prev_line, "ghost",
                                font=("Segoe UI", 11))
        self.b_skip = self._btn(bx + 146, ny2, 200, 42, t("skip"),
                                self.clear_take, "ghost",
                                font=("Segoe UI", 11))
        self.b_next = self._btn(bx + total - 170, ny2, 170, 42,
                                t("next") + "  ›", self.next_line,
                                "primary", font=("Segoe UI Semibold", 12))

        self.hint_item = cv.create_text(w / 2, ny2 + 62, text=t("hint"),
                                        fill=DIM, font=("Segoe UI", 10))
        self.sync()

    def _build_timeline(self, vx, vw, ty):
        cv = self.cv
        n = max(1, len(self.pack.lines))
        gap = 4 if n <= 60 else 2
        cw = max(3.0, (vw - gap * (n - 1)) / float(n))
        self.chips = []
        self.chip_items = []
        for i in range(n):
            x0 = vx + i * (cw + gap)
            item = round_rect(cv, x0, ty, x0 + cw, ty + 10,
                              r=min(5, cw / 2), fill=PANEL_HI, outline="")
            self.chip_items.append(item)
            self.chips.append((x0, ty, x0 + cw, ty + 10))

    # ---------------------------------------------------- Zustand anzeigen
    def current_line(self):
        if not self.pack or not (0 <= self.line_i < len(self.pack.lines)):
            return None
        return self.pack.lines[self.line_i]

    def sync(self):
        """Setzt Beschriftungen und Knopfzustaende passend zur Lage."""
        if self.screen != "stage":
            return
        line = self.current_line()
        n = len(self.pack.lines)
        busy = self.phase != "idle"
        has_take = line is not None and line.take is not None and len(line.take)
        last = self.line_i >= n - 1

        # --- Knopfzustaende zuerst: die duerfen nie von der Anzeige abhaengen.
        # Aufnehmen ist auf jeder Zeile moeglich, auch auf der letzten.
        self.b_orig.set_enabled(not busy)
        self.b_rec.set_enabled(not busy and line is not None)
        self.b_rec.set_text("●  " + (t("rec_again") if has_take else t("rec")))
        self.b_take.set_enabled(not busy and bool(has_take))
        self.b_prev.set_enabled(not busy and self.line_i > 0)
        self.b_skip.set_enabled(not busy and bool(has_take))
        self.b_next.set_enabled(not busy)
        self.b_next.set_text((t("finish") if last else t("next")) + "  ›")

        # --- ab hier nur noch Kosmetik
        try:
            self.cv.itemconfigure(self.hdr_count,
                                  text=t("line_of", self.line_i + 1, n))
            if line is not None:
                self.cv.itemconfigure(self.line_title, text=line.name)
                self.cv.itemconfigure(
                    self.line_time,
                    text="%s  –  %s" % (pc.fmt_time(line.start)[:-2],
                                        pc.fmt_time(line.end)[:-2]))
                self.cv.itemconfigure(
                    self.caption_item,
                    text=line.caption or "",
                    fill=GOLD if line.caption else DIM)
            for i, l in enumerate(self.pack.lines):
                if i >= len(self.chip_items):
                    break
                if i == self.line_i:
                    col = GOLD
                elif l.take is not None and len(l.take):
                    col = TEAL
                else:
                    col = PANEL_HI
                self.cv.itemconfigure(self.chip_items[i], fill=col)
            done = sum(1 for l in self.pack.lines
                       if l.take is not None and len(l.take))
            self.cv.itemconfigure(
                self.hint_item,
                text=t("recorded_n", done, n) if done else t("hint"))
            self._refresh_strip()
            if not busy and line is not None:
                self.show_frame(line.start)
        except Exception:
            traceback.print_exc()

    # ------------------------------------------- Vergleichsstreifen zeichnen
    STRIP_COLS = 320          # Aufloesung der Silhouetten

    def _strip_span(self, line):
        """Zeitachse des Streifens: Cliplaenge plus Nachlauf der Aufnahme."""
        return max(0.3, line.duration + TAIL)

    def _strip_geo(self):
        x0, y0, sw, sh = self.strip_box
        return (x0 + 12, sw - 24, y0 + sh / 2.0, sh / 2.0 - 16)

    def _polygon(self, xs, tops, bots):
        """Punkteliste fuer eine gefuellte Silhouette."""
        pts = []
        for x, y in zip(xs, tops):
            pts += [x, y]
        for x, y in zip(reversed(xs), reversed(bots)):
            pts += [x, y]
        return pts

    def _draw_strip_original(self):
        """Silhouette des Originalclips - Grundlage fuer den Vergleich."""
        cv = self.cv
        line = self.current_line()
        if line is None or line.audio is None or not len(line.audio):
            cv.itemconfigure(self.strip_orig, state="hidden")
            return
        left, width, mid, amp = self._strip_geo()
        span = self._strip_span(line)
        cols = self.STRIP_COLS
        n = max(4, int(cols * min(1.0, line.duration / span)))
        peaks = pc.waveform_peaks(line.audio, n)
        if not peaks:
            cv.itemconfigure(self.strip_orig, state="hidden")
            return
        m = max(1e-6, max(max(abs(a), abs(b)) for a, b in peaks))
        xs, tops, bots = [], [], []
        for i, (lo, hi) in enumerate(peaks):
            xs.append(left + width * (i / float(cols)))
            tops.append(mid - (hi / m) * amp)
            bots.append(mid - (lo / m) * amp)
        cv.coords(self.strip_orig, *self._polygon(xs, tops, bots))
        cv.itemconfigure(self.strip_orig, state="normal")

    def _draw_strip_take(self, live=False):
        """Aufnahme darueber - waehrend der Aufnahme live mitwachsend."""
        cv = self.cv
        line = self.current_line()
        if line is None:
            cv.itemconfigure(self.strip_take, state="hidden")
            return
        left, width, mid, amp = self._strip_geo()
        span = self._strip_span(line)
        cols = self.STRIP_COLS
        xs, tops, bots = [], [], []

        if live:
            env, step = self.mic.envelope()
            if not env:
                cv.itemconfigure(self.strip_take, state="hidden")
                return
            m = max(1e-4, max(env))
            done = len(env) * step
            n = max(2, int(cols * min(1.0, done / span)))
            for i in range(n):
                sec = span * (i / float(cols))
                k = int(sec / step)
                v = (env[k] / m) if k < len(env) else 0.0
                xs.append(left + width * (i / float(cols)))
                tops.append(mid - v * amp)
                bots.append(mid + v * amp)
        else:
            take = line.take
            if take is None or not len(take):
                cv.itemconfigure(self.strip_take, state="hidden")
                return
            dur = len(take) / float(ds.SR)
            n = max(4, int(cols * min(1.0, dur / span)))
            peaks = pc.waveform_peaks(take, n)
            if not peaks:
                cv.itemconfigure(self.strip_take, state="hidden")
                return
            m = max(1e-6, max(max(abs(a), abs(b)) for a, b in peaks))
            for i, (lo, hi) in enumerate(peaks):
                xs.append(left + width * (i / float(cols)))
                tops.append(mid - (hi / m) * amp)
                bots.append(mid - (lo / m) * amp)

        if len(xs) < 2:
            cv.itemconfigure(self.strip_take, state="hidden")
            return
        cv.coords(self.strip_take, *self._polygon(xs, tops, bots))
        cv.itemconfigure(self.strip_take, state="normal",
                         fill=RED if live else TEAL)
        cv.itemconfigure(self.legend_take, fill=RED if live else TEAL)

    def _strip_head(self, seconds=None):
        """Senkrechte Marke fuer die aktuelle Stelle."""
        line = self.current_line()
        if seconds is None or line is None:
            self.cv.itemconfigure(self.strip_head, state="hidden")
            return
        left, width, mid, amp = self._strip_geo()
        x0, y0, sw, sh = self.strip_box
        f = max(0.0, min(1.0, seconds / self._strip_span(line)))
        x = left + width * f
        self.cv.coords(self.strip_head, x, y0 + 6, x, y0 + sh - 6)
        self.cv.itemconfigure(self.strip_head, state="normal")

    def _refresh_strip(self):
        """Beschriftung und beide Silhouetten neu setzen."""
        cv = self.cv
        line = self.current_line()
        recording = (self.phase == "record")
        self._draw_strip_original()
        self._draw_strip_take(live=recording)
        if not recording:
            self._strip_head(None)

        if line is None:
            cv.itemconfigure(self.strip_msg, text="", fill=DIM)
            cv.itemconfigure(self.strip_info, text="")
            return
        if recording:
            cv.itemconfigure(self.strip_msg, text="", fill=RED)
            cv.itemconfigure(self.strip_info, text=t("recording"), fill=RED)
            return
        has = line.take is not None and len(line.take)
        cv.itemconfigure(self.strip_msg,
                         text="" if has else t("no_take"), fill=DIM)
        if has:
            lvl = ds.rms_db(line.take)
            info = t("take_len", len(line.take) / float(ds.SR))
            if lvl < -40:
                info += "   -   " + t("quiet_hint")
            cv.itemconfigure(self.strip_info, text=info,
                             fill=GOLD if lvl < -40 else DIM)
        else:
            cv.itemconfigure(self.strip_info, text="")

    # ------------------------------------------------------------- Video
    def show_frame(self, seconds):
        """Zeigt das Bild zum Zeitpunkt an."""
        if self.pack:
            self._show_index(ds.frame_at(self.pack, seconds))

    def _show_index(self, idx):
        """
        Zeigt ein bestimmtes Einzelbild. Wirft nie eine Ausnahme:
        ein Anzeigefehler darf den Ablauf niemals einfrieren.
        """
        try:
            if idx is None or not HAVE_PIL or not self.pack \
                    or not self.pack.frames:
                return
            if idx == self._last_idx:
                return                      # gleiches Bild, nichts zu tun
            photo = self._frame_photo(idx)
            if photo is not None:
                self._photo = photo
                self._last_idx = idx
                self.cv.itemconfigure(self.video_item, image=photo)
        except Exception:
            traceback.print_exc()

    def _frame_photo(self, idx):
        vx, vy, vw, vh = self.video_box
        key = (idx, int(vw), int(vh))
        photo = self._imgcache.get(key)
        if photo is not None:
            return photo
        try:
            im = Image.open(self.pack.frames[idx]).convert("RGB")
            iw, ih = im.size
            s = min(vw / float(iw), vh / float(ih), 1.0)   # nie vergroessern
            target = (max(1, int(iw * s)), max(1, int(ih * s)))
            if target != im.size:
                im = im.resize(target, Image.BILINEAR)
            photo = ImageTk.PhotoImage(im)
        except Exception:
            return None
        # aelteste Eintraege verwerfen statt alles auf einmal
        while len(self._imgcache) >= 48:
            self._imgcache.pop(next(iter(self._imgcache)))
        self._imgcache[key] = photo
        return photo

    def _video_size(self, win_w, avail_h, pad):
        """
        Bildflaeche im Seitenverhaeltnis der Einzelbilder und nie breiter
        als diese - so entfaellt jedes Hochskalieren.
        """
        fw, fh = self._frame_size or (ds.FRAME_W, int(ds.FRAME_W * 9 / 16))
        aspect = fw / float(max(1, fh))
        vw = int(min(fw, win_w - 2 * pad, max(120, avail_h) * aspect))
        vw = max(320, vw)
        return vw, int(round(vw / aspect))

    def _probe_frame_size(self):
        """Native Groesse der Einzelbilder, damit nie hochskaliert wird."""
        self._frame_size = None
        self._last_idx = None
        if HAVE_PIL and self.pack and self.pack.frames:
            try:
                with Image.open(self.pack.frames[0]) as im:
                    self._frame_size = im.size
            except Exception:
                traceback.print_exc()

    def _overlay(self, text=None, colour=GOLD, size=68):
        state = "hidden" if text is None else "normal"
        self.cv.itemconfigure(self.overlay_rect, state=state)
        self.cv.itemconfigure(self.overlay_text, state=state)
        if text is not None:
            self.cv.itemconfigure(self.overlay_text, text=text, fill=colour,
                                  font=("Segoe UI Black", size))

    # -------------------------------------------------- Wiedergabe-Schleife
    def _play_from(self, start, duration, on_end=None):
        """Bildschleife. Faellt nie aus - das Ende wird garantiert erreicht."""
        self._play = {"start": float(start), "dur": float(duration),
                      "t0": time.perf_counter(), "cb": on_end}
        self._frame_tick()

    def _frame_tick(self):
        job = self._play
        if not job or self.phase == "idle":
            return
        now = time.perf_counter()
        elapsed = now - job["t0"]
        if elapsed >= job["dur"]:
            self._play = None
            cb = job["cb"]
            if cb:
                cb()
            return
        fps = max(1.0, float(self.pack.fps))
        try:
            self._show_index(ds.frame_at(self.pack, job["start"] + elapsed))
            if self.screen == "stage":
                if self.phase == "record":
                    self._draw_strip_take(live=True)
                self._strip_head(elapsed)
        except Exception:
            traceback.print_exc()      # darf die Schleife nicht abbrechen
        # Naechsten Termin aus der Startzeit ableiten, nicht aus "jetzt" -
        # sonst summiert sich die Rechenzeit auf und es ruckelt.
        n = int(elapsed * fps) + 1
        delay = int((job["t0"] + n / fps - time.perf_counter()) * 1000)
        self.after(max(1, min(delay, int(1000 / fps))), self._frame_tick)

    def _stop_audio(self):
        self._play = None
        try:
            self.mic.stop_play()
        except Exception:
            pass

    # ------------------------------------------------ Phasen mit Notausgang
    def _set_phase(self, name, expected=0.0):
        """
        Setzt die Phase und merkt sich, wann sie spaetestens vorbei sein muss.
        Laeuft sie ueber, raeumt die Notbremse in _pump() auf - egal was
        schiefgegangen ist, die Bedienung kommt zurueck.
        """
        self.phase = name
        self._phase_deadline = (None if name == "idle"
                                else time.perf_counter() + expected + 5.0)

    def _force_idle(self):
        """Bringt das Spiel aus jedem Zustand zurueck in die Bedienbarkeit."""
        self._phase_deadline = None
        self._play = None
        self._rec_done = True
        if self._rec_guard is not None:
            try:
                self.after_cancel(self._rec_guard)
            except Exception:
                pass
            self._rec_guard = None
        for fn in (self.mic.stop, self.mic.stop_play):
            try:
                fn()
            except Exception:
                pass
        self.phase = "idle"
        try:
            if self.screen == "stage":
                self._overlay(None)
                self.sync()
            elif self.screen == "finale":
                self.b_play.set_text("▶  " + t("play_all"))
        except Exception:
            traceback.print_exc()

    # ------------------------------------------------------------ Aktionen
    def _with_backing(self, audio, start, level=0.6):
        """Legt den Backing Track unter den Ton - laengengenau."""
        back = getattr(self.pack, "backing_audio", None)
        audio = np.asarray(audio, dtype=np.float32)
        if back is None or not len(audio):
            return ds.normalize(audio, 0.95)
        seg = ds.slice_audio(back, start, len(audio) / float(ds.SR))
        seg = ds.fit_len(seg, len(audio))
        return ds.normalize(audio * 0.95 + seg * level, 0.95)

    def play_original(self):
        line = self.current_line()
        if line is None or self.phase != "idle":
            return
        self._set_phase("listen", line.duration)
        self.sync()
        try:
            self.mic.play(self._with_backing(line.audio, line.start, 0.6))
        except Exception:
            traceback.print_exc()
            self._force_idle()
            return
        self._play_from(line.start, line.duration, self._end_playback)

    def play_take(self):
        line = self.current_line()
        if line is None or self.phase != "idle" or line.take is None:
            return
        dur = len(line.take) / float(ds.SR)
        self._set_phase("listen", dur)
        self.sync()
        try:
            self.mic.play(self._with_backing(line.take, line.start, 0.5))
        except Exception:
            traceback.print_exc()
            self._force_idle()
            return
        self._play_from(line.start, dur, self._end_playback)

    def _end_playback(self):
        self._set_phase("idle")
        self._stop_audio()
        self.sync()

    def do_record(self):
        line = self.current_line()
        if line is None or self.phase != "idle":
            return
        self._set_phase("countdown", 3.0)
        self.sync()
        self._count = 3
        self._countdown()

    def _countdown(self):
        if self.phase != "countdown":
            return
        # Erst zeichnen (darf scheitern), dann auf jeden Fall weiterschalten.
        try:
            line = self.current_line()
            if line is not None:
                self.show_frame(line.start)
            if self._count > 0:
                self._overlay(str(self._count), GOLD, 76)
            else:
                self._overlay(t("go"), TEAL, 60)
        except Exception:
            traceback.print_exc()
        if self._count > 0:
            self._count -= 1
            self.after(650, self._countdown)
        else:
            self.after(300, self._begin_record)

    def _begin_record(self):
        if self.phase != "countdown":
            return
        line = self.current_line()
        dur = line.duration + TAIL
        playback = None
        if getattr(self.pack, "backing_audio", None) is not None:
            playback = ds.slice_audio(self.pack.backing_audio, line.start, dur)
        try:
            self.mic.start(playback=playback, device=self._mic_device())
        except Exception as ex:
            self._force_idle()
            messagebox.showerror(t("err"), str(ex))
            return
        self._set_phase("record", dur)
        self._rec_done = False
        try:
            self._overlay(t("recording"), RED, 34)
            self.sync()
        except Exception:
            traceback.print_exc()
        self._play_from(line.start, dur, self._finish_record)
        # Sicherheitsnetz: beendet die Aufnahme auch, wenn die Bildschleife
        # aus irgendeinem Grund nicht bis zum Ende kommt.
        self._rec_guard = self.after(int(dur * 1000) + 500,
                                     self._finish_record)

    def _finish_record(self):
        if self._rec_done:
            return
        self._rec_done = True
        if self._rec_guard is not None:
            try:
                self.after_cancel(self._rec_guard)
            except Exception:
                pass
            self._rec_guard = None
        try:
            data = self.mic.stop()
        except Exception:
            traceback.print_exc()
            data = None
        line = self.current_line()
        if line is not None and data is not None and len(data):
            line.take = data
        self._play = None
        self._set_phase("idle")
        try:
            self._overlay(None)
            self.sync()
        except Exception:
            traceback.print_exc()

    def clear_take(self):
        line = self.current_line()
        if line is None or self.phase != "idle":
            return
        line.take = None
        self.sync()

    def goto_line(self, index):
        if self.phase != "idle":
            return
        self.line_i = max(0, min(len(self.pack.lines) - 1, index))
        self._stop_audio()
        self.sync()

    def prev_line(self):
        if self.phase == "idle" and self.line_i > 0:
            self.goto_line(self.line_i - 1)

    def next_line(self):
        if self.phase != "idle":
            return
        if self.line_i >= len(self.pack.lines) - 1:
            self.build_finale()
            return
        self.goto_line(self.line_i + 1)

    def leave_round(self):
        if messagebox.askyesno(t("title"), t("leave_q")):
            self._stop_audio()
            self._set_phase("idle")
            self.show_menu()

    # ==================================================================
    #  FINALE
    # ==================================================================
    def build_finale(self):
        self.screen = "finale"
        self._set_phase("idle")
        self._stop_audio()
        self.mix = ds.render_dub(self.pack)
        self._clear_canvas()
        self._backdrop()
        cv = self.cv
        w, h = self.size()
        pad = 34

        self._btn(pad, 24, 150, 38, "‹  " + t("back_edit"),
                  self.back_to_stage, "flat", font=("Segoe UI", 11))
        cv.create_text(w / 2, 46, text=t("finale"), fill=TXT,
                       font=("Segoe UI Black", 26))
        done = sum(1 for l in self.pack.lines
                   if l.take is not None and len(l.take))
        cv.create_text(w / 2, 76, fill=DIM, font=("Segoe UI", 11),
                       text=t("recorded_n", done, len(self.pack.lines)))

        top = 104
        vw, vh = self._video_size(w, h - top - 226, pad)
        vx = (w - vw) / 2
        self.video_box = (vx, top, vw, vh)
        self._last_idx = None
        round_rect(cv, vx - 8, top - 8, vx + vw + 8, top + vh + 8, r=18,
                   fill="#05060a", outline=EDGE)
        self.video_item = cv.create_image(vx + vw / 2, top + vh / 2,
                                          anchor="center")
        self.overlay_rect = round_rect(cv, vx, top, vx + vw, top + vh, r=12,
                                       fill="#000000", stipple="gray50",
                                       outline="", state="hidden")
        self.overlay_text = cv.create_text(vx + vw / 2, top + vh / 2, text="",
                                           fill=GOLD, state="hidden",
                                           font=("Segoe UI Black", 40))

        # mitlaufender Untertitel
        cy = top + vh + 18
        self.fin_caption = cv.create_text(
            vx + vw / 2, cy, anchor="n", text="", fill=GOLD,
            font=("Segoe UI Semibold", 16), width=vw - 40, justify="center")

        py = cy + 56
        round_rect(cv, vx, py, vx + vw, py + 8, r=4, fill=PANEL_HI,
                   outline="")
        self.prog_item = cv.create_rectangle(vx, py, vx, py + 8, fill=ACC,
                                             width=0)
        self.prog_geo = (vx, py, vw)

        by = py + 34
        bw, bh, gapx = 210, 52, 16
        total = bw * 2 + gapx
        bx = (w - total) / 2
        self.b_play = self._btn(bx, by, bw, bh, "▶  " + t("play_all"),
                                self.toggle_finale_play, "go",
                                font=("Segoe UI Semibold", 13))
        self.b_save = self._btn(bx + bw + gapx, by, bw, bh, t("save"),
                                self.export, "ghost",
                                font=("Segoe UI Semibold", 12))
        self.fin_msg = cv.create_text(w / 2, by + bh + 28, text="", fill=DIM,
                                      font=("Segoe UI", 10))
        self.show_frame(0.0)
        self.after(350, self.toggle_finale_play)

    def back_to_stage(self):
        self._stop_audio()
        self._set_phase("idle")
        self.line_i = min(self.line_i, len(self.pack.lines) - 1)
        self.build_stage()

    def toggle_finale_play(self):
        if self.screen != "finale":
            return
        if self.phase == "play":
            self._finale_stop()
            return
        if self.mix is None or not len(self.mix):
            return
        self._set_phase("play", len(self.mix) / float(ds.SR))
        self.b_play.set_text("■  " + t("stop"))
        self.mic.play(self.mix)
        self._play_from(0.0, len(self.mix) / float(ds.SR), self._finale_stop)
        self._finale_progress()

    def _caption_at(self, seconds):
        """Untertitel der Zeile, die gerade laeuft."""
        text = ""
        for l in self.pack.lines:
            if not l.caption:
                continue
            if l.start - 0.2 <= seconds <= l.start + max(l.duration, 0.4) + 0.5:
                text = l.caption
        return text

    def _finale_progress(self):
        if self.phase != "play" or not self._play:
            return
        elapsed = time.perf_counter() - self._play["t0"]
        vx, py, vw = self.prog_geo
        f = min(1.0, elapsed / max(0.01, self._play["dur"]))
        try:
            self.cv.coords(self.prog_item, vx, py, vx + vw * f, py + 8)
            self.cv.itemconfigure(self.fin_caption,
                                  text=self._caption_at(elapsed))
        except Exception:
            traceback.print_exc()
        self.after(80, self._finale_progress)

    def _finale_stop(self):
        self._set_phase("idle")
        self._stop_audio()
        if self.screen == "finale":
            self.b_play.set_text("▶  " + t("play_all"))
            vx, py, _vw = self.prog_geo
            self.cv.coords(self.prog_item, vx, py, vx, py + 8)
            self.cv.itemconfigure(self.fin_caption, text="")

    def export(self):
        os.makedirs(OUT_DIR, exist_ok=True)
        default = "%s_dub.mp4" % pc.safe_name(self.pack.name, "dub")
        path = filedialog.asksaveasfilename(
            initialfile=default, initialdir=OUT_DIR, defaultextension=".mp4",
            filetypes=[("MP4", "*.mp4")])
        if not path:
            return
        self._finale_stop()
        self.b_save.set_enabled(False)
        self.cv.itemconfigure(self.fin_msg, text=t("saving"), fill=GOLD)
        self.update_idletasks()

        def work():
            ds.export_dub_video(self.pack, self.mix, path)

        def done():
            self.b_save.set_enabled(True)
            self.cv.itemconfigure(self.fin_msg, text="", fill=DIM)
            messagebox.showinfo(t("title"), t("saved", path))
        self._run_bg(work, done)

    # ------------------------------------------------------- Hintergrund
    def _run_bg(self, fn, on_done):
        def wrapper():
            try:
                fn()
                self.msgq.put(("done", on_done))
            except Exception as ex:
                traceback.print_exc()
                self.msgq.put(("error", str(ex)))
        threading.Thread(target=wrapper, daemon=True).start()

    def _pump(self):
        try:
            while True:
                kind, payload = self.msgq.get_nowait()
                if kind == "done":
                    payload()
                elif kind == "error":
                    messagebox.showerror(t("err"), payload)
                    self.show_menu()
                elif kind == "update":
                    upd.note_checked(self.cfg)
                    self.cfg["upd_cache"] = payload
                    save_cfg(self.cfg)
                    if payload.get("newer") and not self.upd_dismissed:
                        self.upd_info = payload
                        if self.screen == "menu":
                            self.show_menu()
                elif kind == "upd_say":
                    self._upd_say(payload)
                elif kind == "upd_quit":
                    self._upd_say(t("upd_swap"))
                    self.after(700, self._on_close)
                elif kind == "upd_error":
                    self.upd_busy = False
                    self.show_menu()
                    messagebox.showerror(t("upd_fail_t"), t("upd_fail", payload))
        except queue.Empty:
            pass
        # Notbremse: haengt eine Phase laenger als erwartet, aufraeumen.
        if (self._phase_deadline is not None
                and time.perf_counter() > self._phase_deadline):
            print("DubStage: Phase '%s' haengt - wird zurueckgesetzt."
                  % self.phase)
            self._force_idle()
        self.after(60, self._pump)

    def _on_close(self):
        # Siehe DubForge: beim Update haengt ein Skript am Prozessende.
        for step in (self._stop_audio, lambda: save_cfg(self.cfg)):
            try:
                step()
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    Game().mainloop()
