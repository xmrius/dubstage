# -*- coding: utf-8 -*-
"""
dubstage_core.py  --  Spiel-Logik fuer DubStage / game logic.

Video laeuft, Zeile nachsprechen, am Ende laeuft die ganze Szene
mit der eigenen Stimme. Keine GUI hier drin.
"""

import os
import re
import glob
import shutil
import struct
import tempfile
import wave

import numpy as np

import dubforge_core as pc

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PACKS_DIR = os.path.join(APP_DIR, "packs")
CACHE_DIR = os.path.join(tempfile.gettempdir(), "dubstage_cache")

SR = 44100                 # Arbeits-Samplerate / working sample rate
FRAME_FPS = 25             # Bilder pro Sekunde fuer die Wiedergabe
FRAME_W = 960              # Breite der Einzelbilder - nie hochskalieren


# ==========================================================================
#  Packs finden / find packs
# ==========================================================================

class Line(object):
    """Eine Zeile des Dub-Packs / one line of a dub pack."""

    def __init__(self, path, start, index):
        self.path = path
        self.file = os.path.basename(path)
        self.start = float(start)
        self.index = index
        self.name = self._label()
        self.caption = ""       # Untertitel / subtitle
        self.audio = None       # Original-Sample / original sample
        self.duration = 0.0
        self.take = None        # Aufnahme des Spielers / player recording

    def _label(self):
        stem = os.path.splitext(self.file)[0]
        stem = re.sub(r"^\d+[_\-]", "", stem)
        stem = re.sub(r"_\d+-\d{1,3}$", "", stem)
        return stem.replace("_", " ").strip() or self.file

    @property
    def end(self):
        return self.start + self.duration


class DubPack(object):

    def __init__(self, folder):
        self.folder = folder
        self.name = os.path.basename(folder)
        self.video = None
        self.backing = None
        self.lines = []
        self.frames = []
        self.fps = FRAME_FPS
        self.video_duration = 0.0

    def __repr__(self):
        return "<DubPack %s, %d Zeilen>" % (self.name, len(self.lines))


_TS_IN_NAME = re.compile(r"_(\d+)-(\d{1,3})(?:\.[A-Za-z0-9]+)?$")


def timestamp_from_name(filename):
    """'07_MyClip_44-048.wav' -> 44.048 ; sonst None."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    m = _TS_IN_NAME.search(stem)
    if not m:
        return None
    whole, frac = m.group(1), m.group(2)
    return float(whole) + float(frac) / (10 ** len(frac))


def timestamps_from_txt(folder):
    """Liest _TIMESTAMPS.txt als Rueckfallebene / fallback."""
    path = os.path.join(folder, "_TIMESTAMPS.txt")
    out = {}
    if not os.path.isfile(path):
        return out
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.match(r"(\S+\.wav)\s+(-?[\d.]+)", line)
                if m:
                    out[m.group(1)] = float(m.group(2))
    except Exception:
        pass
    return out


AUDIO_EXT = (".wav", ".mp3", ".ogg", ".flac")
VIDEO_EXT = (".mp4", ".ogv", ".mkv", ".webm", ".mov", ".avi")


def load_pack(folder):
    """Baut ein DubPack aus einem Ordner. None, wenn kein Dub-Pack."""
    if not os.path.isdir(folder):
        return None
    video = None
    for ext in VIDEO_EXT:                       # mp4 bevorzugt, ogv weiter ok
        cand = os.path.join(folder, "dub_video" + ext)
        if os.path.isfile(cand):
            video = cand
            break
    if not video:
        return None

    pack = DubPack(folder)
    pack.video = video

    from_txt = timestamps_from_txt(folder)
    entries = []
    for f in sorted(os.listdir(folder)):
        low = f.lower()
        if not low.endswith(AUDIO_EXT):
            continue
        if low.startswith("_backing_track"):
            pack.backing = os.path.join(folder, f)
            continue
        if f.startswith("_"):
            continue
        ts = timestamp_from_name(f)
        if ts is None:
            ts = from_txt.get(f)
        entries.append((f, ts))

    known = [e for e in entries if e[1] is not None]
    if not known:
        # Ohne Zeitstempel koennen wir nicht synchronisieren.
        return None

    known.sort(key=lambda e: e[1])
    captions = pc.read_captions(folder)
    for i, (f, ts) in enumerate(known):
        line = Line(os.path.join(folder, f), ts, i)
        line.caption = captions.get(f, "")
        pack.lines.append(line)
    return pack


def find_packs(extra_dirs=None):
    """Sucht Dub-Packs im eigenen packs-Ordner und in zusaetzlichen Ordnern."""
    roots = []

    def add_root(p):
        if p and os.path.isdir(p) and os.path.normpath(p) not in \
                [os.path.normpath(r) for r in roots]:
            roots.append(p)

    add_root(PACKS_DIR)
    for p in (extra_dirs or []):
        add_root(p)

    packs = []
    seen = set()
    for root in roots:
        for entry in sorted(os.listdir(root)):
            folder = os.path.join(root, entry)
            key = os.path.normpath(folder).lower()
            if key in seen or not os.path.isdir(folder):
                continue
            seen.add(key)
            p = load_pack(folder)
            if p:
                packs.append(p)
    return packs


# ==========================================================================
#  Audio
# ==========================================================================

def read_wav_mono(path, sr=SR):
    """Liest beliebiges Audio als Mono-Float-Array (ueber ffmpeg)."""
    tmp = tempfile.mktemp(suffix=".wav")
    try:
        pc.run([pc.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
                "-i", path, "-ac", "1", "-ar", str(sr),
                "-c:a", "pcm_s16le", tmp], check=True)
        with wave.open(tmp, "rb") as w:
            raw = w.readframes(w.getnframes())
        return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def write_wav_mono(path, data, sr=SR):
    data = np.clip(np.asarray(data, dtype=np.float32), -1.0, 1.0)
    pcm = (data * 32767.0).astype("<i2").tobytes()
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)
    return path


def normalize(data, peak=0.97):
    data = np.asarray(data, dtype=np.float32)
    m = float(np.max(np.abs(data))) if len(data) else 0.0
    if m < 1e-6:
        return data
    return data * (peak / m)


def load_pack_audio(pack, sr=SR, progress=None):
    """Laedt alle Original-Samples und den Backing Track."""
    total = len(pack.lines) + 1
    for i, line in enumerate(pack.lines):
        line.audio = read_wav_mono(line.path, sr)
        line.duration = len(line.audio) / float(sr)
        if progress:
            progress((i + 1) / float(total))
    pack.backing_audio = (read_wav_mono(pack.backing, sr)
                          if pack.backing else None)
    pack.video_duration = pc.probe_duration(pack.video)
    if progress:
        progress(1.0)
    return pack


# ==========================================================================
#  Analyse / analysis
# ==========================================================================

def trim_silence(data, sr=SR, rel=0.08, pad=0.04, frame_ms=20):
    """
    Schneidet Stille vorn und hinten weg. Damit kostet ein spaeter
    Einsatz keine Punkte - nur der Verlauf selbst zaehlt.
    """
    data = np.asarray(data, dtype=np.float32)
    hop = max(1, int(sr * frame_ms / 1000.0))
    usable = (len(data) // hop) * hop
    if usable < hop * 2:
        return data
    rms = np.sqrt((data[:usable].reshape(-1, hop) ** 2).mean(axis=1))
    peak = float(rms.max())
    if peak < 1e-6:
        return data
    active = np.nonzero(rms >= peak * rel)[0]
    if not len(active):
        return data
    a = max(0, int(active[0] * hop - pad * sr))
    b = min(len(data), int((active[-1] + 1) * hop + pad * sr))
    return data[a:b]


def rms_db(data):
    data = np.asarray(data, dtype=np.float32)
    if not len(data):
        return -120.0
    r = float(np.sqrt((data ** 2).mean()))
    return 20.0 * np.log10(max(r, 1e-9))


# ==========================================================================
#  Video-Frames
# ==========================================================================

def frames_dir_for(pack):
    key = re.sub(r"[^\w]+", "_", os.path.normpath(pack.folder))[-90:]
    return os.path.join(CACHE_DIR, key)


def pack_duration(pack):
    """Laenge des Videos - einmal ermittelt, danach gemerkt."""
    if not pack.video_duration:
        try:
            pack.video_duration = pc.probe_duration(pack.video)
        except Exception:
            pack.video_duration = 0.0
    return pack.video_duration


def thumb_path(pack):
    return os.path.join(CACHE_DIR, "thumbs", os.path.basename(frames_dir_for(pack)) + ".jpg")


def make_thumb(pack, width=320):
    """Vorschaubild fuer das Menue. Gibt den Pfad zurueck oder None."""
    path = thumb_path(pack)
    try:
        if os.path.isfile(path) and \
                os.path.getmtime(path) >= os.path.getmtime(pack.video):
            return path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Nicht das allererste Bild - das ist oft schwarz.
        at = min(2.0, pack_duration(pack) / 3.0)
        pc.run([pc.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
                "-ss", "%.3f" % at, "-i", pack.video, "-frames:v", "1",
                "-vf", "scale=%d:-2" % int(width), "-q:v", "4", path])
        return path if os.path.isfile(path) else None
    except Exception:
        return None


def extract_frames(pack, fps=FRAME_FPS, width=FRAME_W, log=None, force=False):
    """
    Zerlegt das OGV vorab in JPEGs. Umgeht damit jede Codec-Frage
    bei der Wiedergabe - genau der Punkt, an dem das Original haengt.
    """
    outdir = frames_dir_for(pack)
    stamp = os.path.join(outdir, "done.txt")
    want = "%d %d" % (int(fps), int(width))
    if force and os.path.isdir(outdir):
        shutil.rmtree(outdir, ignore_errors=True)
    if os.path.isfile(stamp):
        try:
            with open(stamp, "r", encoding="utf-8") as f:
                have = f.read().strip()
        except Exception:
            have = ""
        if have == want:
            pack.frames = sorted(glob.glob(os.path.join(outdir, "f*.jpg")))
            pack.fps = float(fps)
            if pack.frames:
                return pack.frames
        # andere Aufloesung -> neu erzeugen
        shutil.rmtree(outdir, ignore_errors=True)
    os.makedirs(outdir, exist_ok=True)
    pc.run([pc.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
            "-i", pack.video,
            "-vf", "fps=%d,scale=%d:-2" % (int(fps), int(width)),
            "-q:v", "5", os.path.join(outdir, "f%05d.jpg")], log=log)
    pack.frames = sorted(glob.glob(os.path.join(outdir, "f*.jpg")))
    pack.fps = float(fps)
    with open(stamp, "w", encoding="utf-8") as f:
        f.write(want)
    return pack.frames


def frame_at(pack, seconds):
    """Index des Bildes zum Zeitpunkt / frame index for a time."""
    if not pack.frames:
        return None
    i = int(round(seconds * pack.fps))
    return max(0, min(len(pack.frames) - 1, i))


# ==========================================================================
#  Dub-Mix rendern
# ==========================================================================

def fit_len(data, n):
    """
    Bringt ein Array auf genau n Werte. Noetig, weil
    int(len(x)/sr*sr) nicht immer wieder len(x) ergibt - sonst knallt
    das Mischen von Aufnahme und Backing Track bei ~8% aller Cliplaengen.
    """
    data = np.asarray(data, dtype=np.float32)
    n = max(0, int(n))
    if len(data) == n:
        return data
    out = np.zeros(n, dtype=np.float32)
    m = min(n, len(data))
    out[:m] = data[:m]
    return out


def slice_audio(data, start, duration, sr=SR):
    """Schneidet einen Bereich heraus, mit Nullen aufgefuellt."""
    if data is None:
        return np.zeros(int(duration * sr), dtype=np.float32)
    a = int(max(0.0, start) * sr)
    n = int(duration * sr)
    out = np.zeros(n, dtype=np.float32)
    chunk = data[a:a + n]
    out[:len(chunk)] = chunk
    return out


def render_dub(pack, sr=SR, duck=0.18, log=None):
    """
    Legt alle Aufnahmen an ihre Zeitstempel ueber den Backing Track.
    Zeilen ohne Aufnahme behalten das Original - so wie es der
    Dub-Guide fuer nicht gewaehlte Figuren beschreibt.
    """
    total = max(pack.video_duration, 0.1)
    for line in pack.lines:
        total = max(total, line.end + 1.0)
    n = int(total * sr) + sr

    backing = getattr(pack, "backing_audio", None)
    if backing is not None:
        base = np.zeros(n, dtype=np.float32)
        base[:min(n, len(backing))] = backing[:n]
        have_backing = True
    else:
        original = read_wav_mono(pack.video, sr)
        base = np.zeros(n, dtype=np.float32)
        base[:min(n, len(original))] = original[:n]
        have_backing = False

    for line in pack.lines:
        a = int(line.start * sr)
        if line.take is not None and len(line.take):
            take = normalize(np.asarray(line.take, dtype=np.float32), 0.92)
            if not have_backing:
                # Original an dieser Stelle leiser ziehen
                b = min(n, a + max(len(take), int(line.duration * sr)))
                base[a:b] *= duck
            b = min(n, a + len(take))
            base[a:b] += take[:b - a]
        elif line.audio is not None and have_backing:
            b = min(n, a + len(line.audio))
            base[a:b] += line.audio[:b - a] * 0.9

    return normalize(base, 0.97)


def export_dub_video(pack, mixed_audio, out_path, sr=SR, log=None):
    """Schreibt Video + eigener Tonspur als MP4 zum Weitergeben."""
    tmp_wav = tempfile.mktemp(suffix=".wav")
    write_wav_mono(tmp_wav, mixed_audio, sr)
    try:
        pc.run([pc.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
                "-i", pack.video, "-i", tmp_wav,
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
                "-c:a", "aac", "-b:a", "192k", "-shortest", out_path], log=log)
    finally:
        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)
    return out_path


# ==========================================================================
#  Mikrofon / microphone
# ==========================================================================

def audio_backend():
    """Gibt das sounddevice-Modul zurueck oder None."""
    try:
        import sounddevice as sd
        return sd
    except Exception:
        return None


ENV_MS = 20          # Aufloesung der laufenden Huellkurve / live envelope


class Mic(object):
    """Aufnahme, optional mit gleichzeitiger Wiedergabe des Backing Tracks."""

    def __init__(self, sr=SR):
        self.sr = sr
        self.sd = audio_backend()
        self._stream = None
        self._chunks = []
        self._env = []                                  # Spitzenwerte je Fenster
        self._env_step = max(1, int(sr * ENV_MS / 1000.0))
        self._buf = np.zeros(0, dtype=np.float32)
        self._total = 0
        self._mark = None

    @property
    def available(self):
        return self.sd is not None

    def devices(self):
        if not self.sd:
            return []
        out = []
        for i, d in enumerate(self.sd.query_devices()):
            if d.get("max_input_channels", 0) > 0:
                out.append((i, d.get("name", "?")))
        return out

    def arm(self, device=None):
        """
        Mikrofon oeffnen, ohne schon aufzunehmen - waehrend des Countdowns.

        Viele Geraete (USB, vor allem Bluetooth) liefern nach dem Oeffnen
        einige hundert Millisekunden lang Stille oder einen Anlauf, Bluetooth
        schaltet dabei ausserdem das Profil um. Passiert das erst beim
        Aufnahmestart, fehlt der Anfang der Zeile. Vorab geoeffnet ist das
        Geraet warm, wenn begin() die Startmarke setzt.
        """
        if not self.sd:
            raise RuntimeError("sounddevice fehlt / missing")
        self._close()
        self._chunks = []
        self._total = 0               # bisher empfangene Samples
        self._mark = None             # Index des ersten Samples der Aufnahme
        self._env = []
        self._env_step = max(1, int(self.sr * ENV_MS / 1000.0))
        self._buf = np.zeros(0, dtype=np.float32)

        def cb(indata, frames, time_info, status):
            data = np.asarray(indata[:, 0], dtype=np.float32).copy()
            self._chunks.append(data)
            first = self._total
            self._total += len(data)
            mark = self._mark
            if mark is None or self._total <= mark:
                return
            # Spitzenwert je 20-ms-Fenster ab der Startmarke mitschreiben,
            # damit die Oberflaeche die Aufnahme live zeichnen kann.
            data = data[max(0, mark - first):]
            buf = data if not len(self._buf) else \
                np.concatenate([self._buf, data])
            step = self._env_step
            k = len(buf) // step
            if k:
                blocks = buf[:k * step].reshape(k, step)
                self._env.extend(np.abs(blocks).max(axis=1).tolist())
                buf = buf[k * step:]
            self._buf = buf

        kwargs = {"samplerate": self.sr, "channels": 1, "callback": cb,
                  "dtype": "float32"}
        if device is not None:
            kwargs["device"] = device
        self._stream = self.sd.InputStream(**kwargs)
        self._stream.start()

    @property
    def armed(self):
        return self._stream is not None

    def begin(self, playback=None):
        """
        Ab jetzt zaehlt die Aufnahme. playback: Float-Array, das dabei laufen
        soll (Backing Track).

        Was der Treiber gerade noch puffert, wurde vor diesem Moment
        aufgenommen - die Eingangslatenz wird deshalb uebersprungen, sonst
        laege die Aufnahme um genau diese Zeit zu spaet.
        """
        if self._stream is None:
            raise RuntimeError("Mikrofon nicht bereit / microphone not armed")
        try:
            latency = float(self._stream.latency)
        except Exception:
            latency = 0.0
        self._mark = self._total + int(round(max(0.0, latency) * self.sr))
        if playback is not None and len(playback):
            try:
                self.sd.play(np.asarray(playback, dtype=np.float32), self.sr)
            except Exception:
                pass

    def start(self, playback=None, device=None):
        """Oeffnen und sofort aufnehmen - fuer den Mikrofontest."""
        self.arm(device=device)
        self.begin(playback=playback)

    def _close(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def stop(self):
        """Aufnahme beenden, Mikrofon schliessen, Samples ab der Marke."""
        self._close()
        try:
            if self.sd:
                self.sd.stop()
        except Exception:
            pass
        mark = self._mark
        chunks, self._chunks = self._chunks, []
        self._mark = None
        if mark is None or not chunks:
            return np.zeros(0, dtype=np.float32)
        data = np.concatenate(chunks).astype(np.float32)
        return data[min(mark, len(data)):]

    def envelope(self):
        """Bisher aufgenommene Huellkurve und ihre Schrittweite in Sekunden."""
        return list(self._env), self._env_step / float(self.sr)

    def level(self):
        """Aktueller Pegel 0..1 fuer die Aussteuerungsanzeige."""
        if not self._env:
            return 0.0
        return float(min(1.0, max(self._env[-5:]) * 1.4))

    def play(self, data):
        if not self.sd or data is None or not len(data):
            return
        try:
            self.sd.play(np.asarray(data, dtype=np.float32), self.sr)
        except Exception:
            pass

    def stop_play(self):
        try:
            if self.sd:
                self.sd.stop()
        except Exception:
            pass
