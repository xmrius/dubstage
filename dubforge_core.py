# -*- coding: utf-8 -*-
"""
dubforge_core.py  --  Kernlogik fuer DubForge / core logic.
Keine GUI hier drin, damit sich alles einzeln testen laesst.
"""

import io
import os
import re
import sys
import json
import math
import shutil
import struct
import subprocess
import tempfile
import wave

APP_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(APP_DIR, "tools")

IS_WIN = os.name == "nt"
_NOWINDOW = subprocess.CREATE_NO_WINDOW if IS_WIN else 0


# --------------------------------------------------------------------------
# Sprache / language
# --------------------------------------------------------------------------

LANG = "de"


def set_lang(code):
    """'de' oder 'en'."""
    global LANG
    LANG = "en" if str(code).lower().startswith("en") else "de"


_MSG = {
    "no_ffmpeg": (
        "ffmpeg wurde nicht gefunden.\n\n"
        "Bitte einmal Setup.bat ausfuehren, oder ffmpeg manuell installieren.",
        "ffmpeg was not found.\n\n"
        "Please run Setup.bat once, or install ffmpeg manually."),
    "no_ffprobe": (
        "ffprobe wurde nicht gefunden. Bitte Setup.bat ausfuehren.",
        "ffprobe was not found. Please run Setup.bat."),
    "no_ytdlp": (
        "yt-dlp wurde nicht gefunden. Bitte Setup.bat ausfuehren.",
        "yt-dlp was not found. Please run Setup.bat."),
    "cmd_failed": (
        "Befehl fehlgeschlagen (%s):\n%s",
        "Command failed (%s):\n%s"),
    "dl_empty": (
        "Download hat keine Datei erzeugt.",
        "The download produced no file."),
    "no_vocals": (
        "Demucs hat keine Vocals-Datei erzeugt.",
        "Demucs did not produce a vocals file."),
    "no_theora": (
        "Dieser ffmpeg kann kein OGV schreiben (libtheora/libvorbis fehlt).\n"
        "Bitte Setup.bat ausfuehren oder MP4 als Format waehlen.",
        "This ffmpeg cannot write OGV (libtheora/libvorbis missing).\n"
        "Please run Setup.bat or choose MP4 as the format."),
    "bad_time": (
        "Zeitangabe nicht verstanden: %r",
        "Could not understand the time value: %r"),
    "no_target": (
        "Zielordner existiert nicht: %s",
        "Target folder does not exist: %s"),
    "pack_exists": (
        "Pack existiert bereits: %s",
        "Pack already exists: %s"),
    "file_missing": (
        "Datei nicht gefunden: %s",
        "File not found: %s"),
    "cut_failed": (
        "Direkter Schnitt ging nicht, kodiere neu ...",
        "Direct cut failed, re-encoding ..."),
    "cut_off": (
        "Kopier-Schnitt ungenau (%.2fs statt %.2fs), kodiere neu ...",
        "Stream-copy cut was inaccurate (%.2fs instead of %.2fs), re-encoding ..."),
    "span": (
        "Zeitspanne: %.2f s",
        "Time span: %.2f s"),
    "no_frame": (
        "Konnte kein Einzelbild bei %s s aus dem Video holen.",
        "Could not grab a still frame at %s s from the video."),
    "dl_section_fail": (
        "Der Ausschnitt-Download ging nicht. Das passiert, wenn ffmpeg die\n"
        "Videodaten selbst holen soll und dabei abgewiesen wird. Ich lade\n"
        "jetzt das ganze Video und schneide es hier - das dauert laenger.",
        "Downloading just the section failed. That happens when ffmpeg has to\n"
        "fetch the video data itself and gets refused. Downloading the whole\n"
        "video now and cutting it here - this takes longer."),
    "dl_trim_local": (
        "Download fertig, schneide auf die gewaehlte Zeitspanne ...",
        "Download finished, cutting to the chosen time span ..."),
    "ytdlp_at": (
        "Benutztes yt-dlp: %s",
        "yt-dlp in use: %s"),
    "ytdlp_mod": (
        "Benutztes yt-dlp: Modul in %s",
        "yt-dlp in use: module in %s"),
    "ytdlp_self": (
        "Eigenstaendige Datei - erneuert sich selbst.",
        "Standalone file - updating itself."),
    "ytdlp_wrap": (
        "Das ist ein pip-Starter, kein eigenstaendiges Programm. "
        "Ich nehme pip aus derselben Installation: %s",
        "This is a pip launcher, not a standalone build. "
        "Using pip from the same installation: %s"),
    "ytdlp_shadow": (
        "Achtung: pip hat %s aktualisiert, benutzt wird aber %s.\n"
        "Die aeltere Datei liegt im PATH und hat Vorrang - entfernen oder "
        "erneuern, sonst bleibt der alte Stand aktiv.",
        "Note: pip updated %s, but %s is what actually runs.\n"
        "The older file sits in PATH and wins - remove or update it, "
        "otherwise the old version stays in charge."),
}


def M(key, *args):
    pair = _MSG.get(key)
    if not pair:
        return key
    text = pair[1] if LANG == "en" else pair[0]
    return text % args if args else text


# --------------------------------------------------------------------------
# Externe Programme finden / locate external tools
# --------------------------------------------------------------------------

def _exe(name):
    return name + ".exe" if IS_WIN else name


def find_tool(name):
    """Sucht erst im mitgelieferten tools/-Ordner, dann im System-PATH."""
    local = os.path.join(TOOLS_DIR, _exe(name))
    if os.path.isfile(local):
        return local
    for root, _dirs, files in os.walk(TOOLS_DIR):
        if _exe(name) in files:
            return os.path.join(root, _exe(name))
    found = shutil.which(name)
    if found:
        return found
    return None


def ffmpeg():
    p = find_tool("ffmpeg")
    if not p:
        raise RuntimeError(M("no_ffmpeg"))
    return p


def ffprobe():
    p = find_tool("ffprobe")
    if not p:
        raise RuntimeError(M("no_ffprobe"))
    return p


def ffplay():
    return find_tool("ffplay")


def ytdlp():
    p = find_tool("yt-dlp")
    if p:
        return [p]
    try:
        subprocess.run([sys.executable, "-m", "yt_dlp", "--version"],
                       check=True, capture_output=True, creationflags=_NOWINDOW)
        return [sys.executable, "-m", "yt_dlp"]
    except Exception:
        return None


def ytdlp_version():
    """
    Gibt (Version, Alter in Tagen) zurueck. yt-dlp versioniert nach Datum,
    daraus laesst sich das Alter direkt ablesen.
    """
    yt = ytdlp()
    if not yt:
        return None, None
    out = capture(list(yt) + ["--version"]).strip()
    ver = None
    for line in out.splitlines():
        line = line.strip()
        if re.match(r"^\d{4}\.\d{2}\.\d{2}", line):
            ver = line
            break
    if not ver:
        return None, None
    m = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", ver)
    try:
        import datetime
        d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return ver, (datetime.date.today() - d).days
    except Exception:
        return ver, None


def _python_beside(exe):
    """Zu einem Scripts\\yt-dlp.exe den zugehoerigen Interpreter finden."""
    d = os.path.dirname(exe)
    for cand in (os.path.join(d, _exe("python")),
                 os.path.join(os.path.dirname(d), _exe("python")),
                 os.path.join(d, _exe("pythonw")),
                 os.path.join(os.path.dirname(d), _exe("pythonw"))):
        if os.path.isfile(cand):
            return cand
    return None


def update_ytdlp(log=None):
    """
    Aktualisiert genau das yt-dlp, das beim Download auch wirklich laeuft.

    Wichtig: pip erneuert nur die Installation des aufrufenden Interpreters.
    Liegt eine eigenstaendige yt-dlp.exe im PATH, hat die Vorrang - dann
    laeuft pip ins Leere und die Version aendert sich scheinbar nicht.
    """
    yt = ytdlp()
    if not yt:
        run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
            log=log, check=False)
        return ytdlp_version()

    if len(yt) == 1:                      # eigenstaendige Datei im PATH
        exe = yt[0]
        if log:
            log(M("ytdlp_at", exe))
            log(M("ytdlp_self"))
        out = capture([exe, "-U"])
        if log:
            for line in out.splitlines():
                if line.strip():
                    log(line.rstrip())
        # Ein von pip erzeugter Starter kann sich nicht selbst erneuern.
        if re.search(r"package manager|not.*(standalone|binar)|"
                     r"use that to update|pip.*install", out, re.I) \
                or not out.strip():
            py = _python_beside(exe) or sys.executable
            if log:
                log(M("ytdlp_wrap", py))
            run([py, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                log=log, check=False)
    else:                                 # als Modul der laufenden Python
        if log:
            log(M("ytdlp_mod", os.path.dirname(sys.executable)))
        run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
            log=log, check=False)

    return ytdlp_version()


def run(cmd, log=None, check=True):
    """Fuehrt ein Kommando aus und streamt die Ausgabe an log(text)."""
    if log:
        log("$ " + " ".join(os.path.basename(str(c)) if i == 0 else str(c)
                            for i, c in enumerate(cmd)))
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True, encoding="utf-8", errors="replace",
        creationflags=_NOWINDOW,
    )
    tail = []
    for line in proc.stdout:
        line = line.rstrip()
        tail.append(line)
        if len(tail) > 40:
            tail.pop(0)
        if log:
            log(line)
    proc.wait()
    if check and proc.returncode != 0:
        raise RuntimeError(M("cmd_failed", os.path.basename(str(cmd[0])),
                             "\n".join(tail[-15:])))
    return "\n".join(tail)


def capture(cmd):
    r = subprocess.run(cmd, capture_output=True, universal_newlines=True,
                       encoding="utf-8", errors="replace", creationflags=_NOWINDOW)
    return (r.stdout or "") + (r.stderr or "")


def check_encoders():
    """Prueft, ob der gefundene ffmpeg OGV (Theora+Vorbis) schreiben kann."""
    out = capture([ffmpeg(), "-hide_banner", "-encoders"])
    return ("libtheora" in out), ("libvorbis" in out)


# --------------------------------------------------------------------------
# Quelle beschaffen / obtain source
# --------------------------------------------------------------------------

def probe_duration(path):
    out = capture([ffprobe(), "-v", "error", "-show_entries", "format=duration",
                   "-of", "default=nw=1:nk=1", path]).strip().splitlines()
    for line in out:
        try:
            return float(line.strip())
        except ValueError:
            continue
    return 0.0


def parse_time(text):
    """Akzeptiert '90', '1:30', '01:02:03.5', '1m30s'. Gibt Sekunden zurueck."""
    text = (text or "").strip()
    if not text:
        return None
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", text, re.I)
    if m and any(m.groups()):
        h, mi, s = m.groups()
        return int(h or 0) * 3600 + int(mi or 0) * 60 + float(s or 0)
    parts = text.replace(",", ".").split(":")
    try:
        parts = [float(p) for p in parts]
    except ValueError:
        raise ValueError(M("bad_time", text))
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def fmt_time(sec):
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    if h:
        return "%d:%02d:%06.3f" % (h, m, s)
    return "%d:%06.3f" % (m, s)


def _source_file(workdir, stem="source."):
    # Nach dem Zusammenfuehren liegt eine .mkv da. Sollten Reste der
    # Einzelspuren uebrig sein, haette sortiert() sonst die erwischt.
    merged = os.path.join(workdir, stem + "mkv")
    if os.path.isfile(merged):
        return merged
    for f in sorted(os.listdir(workdir)):
        if f.startswith(stem) and not f.endswith(".part"):
            return os.path.join(workdir, f)
    return None


def _clear_source(workdir, stem="source."):
    """Reste eines abgebrochenen Downloads wegraeumen."""
    for f in os.listdir(workdir):
        if f.startswith(stem):
            try:
                os.remove(os.path.join(workdir, f))
            except OSError:
                pass


def download_youtube(url, start, end, workdir, log=None):
    """
    Laedt den gewaehlten Ausschnitt.

    Zuerst der schnelle Weg ueber --download-sections, der nur den Ausschnitt
    holt. Dabei laedt aber ffmpeg die Daten selbst, und seine Anfrage passt
    nicht immer zu der URL, die yt-dlp ausgehandelt hat - dann kommt ein 403
    zurueck. Klappt das nicht, wird das ganze Video geladen und lokal
    geschnitten: langsamer, aber verlaesslich.
    """
    yt = ytdlp()
    if not yt:
        raise RuntimeError(M("no_ytdlp"))

    base = list(yt) + [
        "--no-playlist",
        "--ffmpeg-location", os.path.dirname(ffmpeg()),
        "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
        "--merge-output-format", "mkv",
    ]
    out_tmpl = os.path.join(workdir, "source.%(ext)s")
    want_cut = start is not None or end is not None

    if want_cut:
        s = 0.0 if start is None else float(start)
        e = "inf" if end is None else "%.3f" % float(end)
        try:
            run(base + ["-o", out_tmpl,
                        "--download-sections", "*%.3f-%s" % (s, e),
                        "--force-keyframes-at-cuts", url], log=log)
            f = _source_file(workdir)
            if f:
                return f
        except Exception:
            pass
        if log:
            log(M("dl_section_fail"))
        _clear_source(workdir)

    # Ganzes Video laden - hier holt yt-dlp die Daten selbst.
    full_tmpl = os.path.join(workdir, "full.%(ext)s")
    run(base + ["-o", full_tmpl, url], log=log)
    full = _source_file(workdir, "full.")
    if not full:
        raise RuntimeError(M("dl_empty"))
    if not want_cut:
        return full
    if log:
        log(M("dl_trim_local"))
    return trim_local(full, start, end, workdir, log=log)


def trim_local(path, start, end, workdir, log=None):
    """Schneidet einen lokalen Film auf die gewaehlte Zeitspanne."""
    if start is None and end is None:
        return path
    out = os.path.join(workdir, "source.mkv")
    src_dur = probe_duration(path)
    want = None
    if end is not None:
        want = max(0.05, float(end) - float(start or 0))
    elif src_dur > 0:
        want = max(0.05, src_dur - float(start or 0))

    cmd = [ffmpeg(), "-y", "-hide_banner"]
    if start:
        cmd += ["-ss", "%.3f" % float(start)]
    cmd += ["-i", path]
    if end is not None:
        cmd += ["-t", "%.3f" % want]
    cmd += ["-map", "0:v:0", "-map", "0:a:0?", "-c", "copy",
            "-avoid_negative_ts", "make_zero", "-reset_timestamps", "1", out]
    try:
        run(cmd, log=log)
        got = probe_duration(out)
        # Der Kopier-Schnitt springt nur auf Keyframes und liegt manchmal
        # komplett daneben. Dann lieber sauber neu kodieren.
        if got > 0.1 and want and abs(got - want) <= max(0.75, want * 0.05):
            return out
        if log:
            log(M("cut_off", got, want or 0))
    except RuntimeError:
        if log:
            log(M("cut_failed"))

    cmd = [ffmpeg(), "-y", "-hide_banner"]
    if start:
        cmd += ["-ss", "%.3f" % float(start)]
    cmd += ["-i", path]
    if end is not None:
        cmd += ["-t", "%.3f" % max(0.05, float(end) - float(start or 0))]
    cmd += ["-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-crf", "18",
            "-preset", "veryfast", "-c:a", "pcm_s16le",
            "-avoid_negative_ts", "make_zero", out]
    run(cmd, log=log)
    if log:
        log(M("span", probe_duration(out)))
    return out


def extract_audio(video, out_wav, log=None):
    run([ffmpeg(), "-y", "-hide_banner", "-i", video, "-vn",
         "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", out_wav], log=log)
    return out_wav


# --------------------------------------------------------------------------
# Vocals trennen (Demucs)
# --------------------------------------------------------------------------

def separate_vocals(wav_path, workdir, log=None, model="htdemucs"):
    """Gibt (vocals_wav, no_vocals_wav) zurueck."""
    outdir = os.path.join(workdir, "demucs")
    os.makedirs(outdir, exist_ok=True)
    cmd = [sys.executable, "-m", "demucs", "--two-stems", "vocals",
           "-n", model, "-o", outdir, wav_path]
    run(cmd, log=log)
    stem = os.path.splitext(os.path.basename(wav_path))[0]
    for root, _dirs, files in os.walk(outdir):
        if "vocals.wav" in files and os.path.basename(root) == stem:
            return (os.path.join(root, "vocals.wav"),
                    os.path.join(root, "no_vocals.wav"))
    for root, _dirs, files in os.walk(outdir):
        if "vocals.wav" in files:
            return (os.path.join(root, "vocals.wav"),
                    os.path.join(root, "no_vocals.wav"))
    raise RuntimeError(M("no_vocals"))


# --------------------------------------------------------------------------
# Audio einlesen / analysieren
# --------------------------------------------------------------------------

def load_mono(path, sr=8000):
    """Dekodiert nach Mono-Float-Liste. Nutzt numpy wenn vorhanden."""
    tmp = tempfile.mktemp(suffix=".wav")
    try:
        run([ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-i", path,
             "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", tmp], check=True)
        with wave.open(tmp, "rb") as w:
            n = w.getnframes()
            raw = w.readframes(n)
        try:
            import numpy as np
            data = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
        except ImportError:
            data = [v / 32768.0 for v in struct.unpack("<%dh" % (len(raw) // 2), raw)]
        return data, sr
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def frame_rms(data, sr, frame_ms=20):
    """Liefert (rms_liste, frame_dauer_in_sekunden)."""
    hop = max(1, int(sr * frame_ms / 1000.0))
    try:
        import numpy as np
        arr = np.asarray(data, dtype="float32")
        usable = (len(arr) // hop) * hop
        if usable == 0:
            return [], hop / float(sr)
        blocks = arr[:usable].reshape(-1, hop)
        rms = np.sqrt((blocks ** 2).mean(axis=1))
        return rms, hop / float(sr)
    except ImportError:
        out = []
        for i in range(0, len(data) - hop + 1, hop):
            chunk = data[i:i + hop]
            out.append(math.sqrt(sum(v * v for v in chunk) / len(chunk)))
        return out, hop / float(sr)


def detect_clips(data, sr, min_silence=0.35, min_clip=0.30, max_clip=6.0,
                 pad=0.08, sensitivity=1.0):
    """
    Findet Sprechabschnitte. sensitivity: >1 = empfindlicher (mehr Clips).
    Gibt Liste von (start_s, end_s) zurueck.
    """
    rms, fdur = frame_rms(data, sr)
    if len(rms) == 0:
        return []

    try:
        import numpy as np
        r = np.asarray(rms, dtype="float32")
        peak = float(r.max())
        if peak <= 1e-6:
            return []
        floor = float(np.percentile(r, 20))
        loud = float(np.percentile(r, 95))
    except ImportError:
        r = list(rms)
        peak = max(r)
        if peak <= 1e-6:
            return []
        srt = sorted(r)
        floor = srt[int(len(srt) * 0.20)]
        loud = srt[int(len(srt) * 0.95)]

    thresh = max(floor * 2.5, loud * 0.10, peak * 0.015) / max(0.2, sensitivity)

    segs = []
    start = None
    silence_frames = 0
    need_silence = max(1, int(min_silence / fdur))
    for i, v in enumerate(r):
        if v >= thresh:
            if start is None:
                start = i
            silence_frames = 0
        else:
            if start is not None:
                silence_frames += 1
                if silence_frames >= need_silence:
                    segs.append((start, i - silence_frames + 1))
                    start = None
                    silence_frames = 0
    if start is not None:
        segs.append((start, len(r)))

    out = []
    for a, b in segs:
        s = max(0.0, a * fdur - pad)
        e = min(len(r) * fdur, b * fdur + pad)
        if e - s < min_clip:
            continue
        out.extend(_split_long(s, e, r, fdur, max_clip, min_clip))
    return out


def _split_long(s, e, r, fdur, max_clip, min_clip):
    """Zerlegt zu lange Abschnitte an der leisesten Stelle in der Mitte."""
    if e - s <= max_clip:
        return [(s, e)]
    a = int(s / fdur)
    b = int(e / fdur)
    lo = a + int((b - a) * 0.30)
    hi = a + int((b - a) * 0.70)
    if hi <= lo:
        mid = (s + e) / 2.0
        return _split_long(s, mid, r, fdur, max_clip, min_clip) + \
               _split_long(mid, e, r, fdur, max_clip, min_clip)
    window = list(r[lo:hi])
    cut = lo + window.index(min(window))
    cut_s = cut * fdur
    if cut_s - s < min_clip or e - cut_s < min_clip:
        return [(s, e)]
    return _split_long(s, cut_s, r, fdur, max_clip, min_clip) + \
           _split_long(cut_s, e, r, fdur, max_clip, min_clip)


def waveform_peaks(data, columns):
    """Liefert [(min,max), ...] fuer die Wellenform-Darstellung."""
    n = len(data)
    if n == 0 or columns <= 0:
        return []
    step = n / float(columns)
    peaks = []
    try:
        import numpy as np
        arr = np.asarray(data, dtype="float32")
        for c in range(columns):
            a = int(c * step)
            b = max(a + 1, int((c + 1) * step))
            chunk = arr[a:b]
            peaks.append((float(chunk.min()), float(chunk.max())))
    except ImportError:
        for c in range(columns):
            a = int(c * step)
            b = max(a + 1, int((c + 1) * step))
            chunk = data[a:b]
            peaks.append((min(chunk), max(chunk)))
    return peaks


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

def measure_peak_db(path):
    out = capture([ffmpeg(), "-hide_banner", "-i", path, "-af", "volumedetect",
                   "-f", "null", "-"])
    m = re.search(r"max_volume:\s*(-?[\d.]+) dB", out)
    return float(m.group(1)) if m else None


def export_clip(src_wav, start, end, out_path, target_lufs=-12.0, log=None):
    """Schneidet einen Clip heraus und macht ihn laut."""
    tmp = out_path + ".tmp.wav"
    dur = max(0.05, float(end) - float(start))
    run([ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
         "-ss", "%.3f" % float(start), "-i", src_wav, "-t", "%.3f" % dur,
         "-af", "loudnorm=I=%.1f:TP=-1.0:LRA=11" % target_lufs,
         "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", tmp], log=log)
    peak = measure_peak_db(tmp)
    if peak is not None and peak < -1.5:
        gain = min(12.0, -1.0 - peak)
        run([ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-i", tmp,
             "-af", "volume=%.2fdB" % gain,
             "-c:a", "pcm_s16le", out_path], log=log)
        os.remove(tmp)
    else:
        if os.path.exists(out_path):
            os.remove(out_path)
        os.replace(tmp, out_path)
    return out_path


def export_backing_track(no_vocals_wav, out_path, log=None):
    run([ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-i", no_vocals_wav,
         "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", out_path], log=log)
    return out_path


def convert_video(video, out_path, max_height=720, quality=20, log=None):
    """
    Schreibt das Video fuer den Pack. MP4/H.264 ist Standard: schnell,
    klein und scharf. Endet der Pfad auf .ogv, wird Theora+Vorbis
    geschrieben - fuer Packs, die das brauchen.
    """
    scale = "scale=-2:'min(%d,ih)'" % int(max_height)
    if out_path.lower().endswith(".ogv"):
        has_theora, has_vorbis = check_encoders()
        if not has_theora or not has_vorbis:
            raise RuntimeError(M("no_theora"))
        args = ["-c:v", "libtheora", "-q:v", "6",
                "-c:a", "libvorbis", "-q:a", "4"]
    else:
        args = ["-c:v", "libx264", "-crf", str(int(quality)),
                "-preset", "veryfast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
    run([ffmpeg(), "-y", "-hide_banner", "-i", video, "-vf", scale]
        + args + ["-map", "0:v:0", "-map", "0:a:0?", out_path], log=log)
    return out_path


def grab_frame(video, seconds, out_png, max_height=480, log=None):
    """Ein Einzelbild aus dem Video holen - fuer Figurenbilder und Symbole."""
    scale = "scale=-2:'min(%d,ih)'" % int(max_height)
    run([ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
         "-ss", "%.3f" % max(0.0, float(seconds)), "-i", video,
         "-frames:v", "1", "-vf", scale, out_png], log=log)
    if not os.path.isfile(out_png):
        raise RuntimeError(M("no_frame", "%.3f" % float(seconds)))
    return out_png


# --------------------------------------------------------------------------
# Choicer-Voicer-Profil / Choicer Voicer export profile
# --------------------------------------------------------------------------
#
# Das Format ist nirgends dokumentiert - diese Umsetzung ist aus einem
# echten Pack ausgelesen ("You Are A Toy"):
#   [data], Leerzeile, dann Schluessel; UTF-8, CRLF, KEIN Umbruch am Ende.
#   Zeitstempel zweistellig aufgefuellt mit drei Nachkommastellen.
#   Listen ohne Leerzeichen nach dem Komma.
#   Anfuehrungszeichen im Text sind typografisch - so muss nie maskiert
#   werden, und genau daran haelt sich der Export.

CV_META_EXT = ".txt"
CV_PACK_INFO = "_pack_info.ini"


def cv_text(text):
    """Text fuer eine Wertzeile aufbereiten."""
    s = str(text or "")
    # Zeilenumbrueche wuerden das zeilenbasierte Format zerreissen.
    s = re.sub(r"[\r\n\t]+", " ", s)
    s = "".join(ch for ch in s if ch >= " " or ch == " ")
    # Gerade Anfuehrungszeichen abwechselnd in typografische wandeln.
    out, opening = [], True
    for ch in s:
        if ch == '"':
            out.append("“" if opening else "”")
            opening = not opening
        else:
            out.append(ch)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _cv_str(value):
    return '"%s"' % cv_text(value)


def _cv_list(values):
    return "[%s]" % ",".join(_cv_str(v) for v in values)


def _cv_times(values):
    return "[%s]" % ",".join("%06.3f" % float(v) for v in values)


def _cv_write(path, lines):
    """CRLF, UTF-8, ohne Umbruch am Ende - so wie das Spiel es schreibt."""
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(lines))
    return path


def write_cv_meta(path, caption="", image="", timestamps=(), characters=()):
    """Metadaten einer Sprechzeile schreiben."""
    lines = ["[data]", ""]
    if caption:
        lines.append("caption=%s" % _cv_str(caption))
    if image:
        lines.append("image=%s" % _cv_str(image))
    lines.append("dub_timestamps=%s" % _cv_times(timestamps or []))
    if characters:
        lines.append("dub_characters=%s" % _cv_list(characters))
    return _cv_write(path, lines)


def write_pack_info(path, title="", icon="", authors=(), readme="",
                    characters=()):
    """_pack_info.ini fuer den Pack schreiben."""
    lines = ["[data]", ""]
    if title:
        lines.append("title=%s" % _cv_str(title))
    if icon:
        lines.append("icon=%s" % _cv_str(icon))
    if authors:
        lines.append("authors=%s" % _cv_list(authors))
    if readme:
        lines.append("readme=%s" % _cv_str(readme))
    if characters:
        lines.append("preselected_dub_characters=%s" % _cv_list(characters))
    return _cv_write(path, lines)


def cv_numbering(clips):
    """
    Nummeriert je Figur durch, nicht ueber die ganze Szene.

    In echten Packs ist 06_woody spaeter als 06_buzz - die Nummer ordnet
    innerhalb einer Figur, die Reihenfolge in der Szene steckt allein in
    den Zeitstempeln.
    """
    seen = {}
    out = []
    for c in clips:
        who = (c.get("character") or c.get("name") or "clip").strip()
        seen[who] = seen.get(who, 0) + 1
        out.append((seen[who], who))
    return out


# --------------------------------------------------------------------------
# Dateinamen / file names
# --------------------------------------------------------------------------

def safe_name(text, fallback="clip"):
    text = re.sub(r"[^\w\-. ]+", "", (text or "").strip(), flags=re.UNICODE)
    text = re.sub(r"\s+", "_", text)
    return text or fallback


CAPTION_FILE = "_captions.json"


def write_captions(folder, mapping):
    """
    Schreibt die Untertitel als _captions.json in den Pack.
    Schluessel ist der Dateiname des Clips.
    """
    data = {}
    for name, text in (mapping or {}).items():
        text = (text or "").strip()
        if text:
            data[name] = text
    path = os.path.join(folder, CAPTION_FILE)
    if not data:
        if os.path.exists(path):
            os.remove(path)
        return None
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def read_captions(folder):
    """Liest _captions.json; zusaetzlich .txt-Dateien neben den Clips."""
    out = {}
    path = os.path.join(folder, CAPTION_FILE)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if isinstance(v, str) and v.strip():
                        out[k] = v.strip()
        except Exception:
            pass
    try:
        for f in os.listdir(folder):
            if not f.lower().endswith(".txt") or f.startswith("_"):
                continue
            stem = os.path.splitext(f)[0]
            for ext in (".wav", ".mp3", ".ogg", ".flac"):
                clip = stem + ext
                if clip in out or not os.path.isfile(os.path.join(folder, clip)):
                    continue
                try:
                    with open(os.path.join(folder, f), "r", encoding="utf-8",
                              errors="replace") as fh:
                        text = fh.read().strip()
                    if text:
                        out[clip] = text
                except Exception:
                    pass
    except Exception:
        pass
    return out


def clip_filename(index, label, start=None, dub=False):
    """
    Voice-Pack:  01_MeinClip
    Dub-Pack:    01_MeinClip_44-048   (Guide-Konvention: Zeitstempel im Namen)
    """
    base = "%02d_%s" % (index, safe_name(label, "clip%02d" % index))
    if dub and start is not None:
        base += "_%s" % ("%.3f" % float(start)).replace(".", "-")
    return base + ".wav"


# --------------------------------------------------------------------------
# Pack kopieren / copy a pack
# --------------------------------------------------------------------------

def copy_pack(src_folder, target_dir, overwrite=True):
    """Kopiert einen fertigen Pack in einen beliebigen Zielordner."""
    if not os.path.isdir(target_dir):
        raise RuntimeError(M("no_target", target_dir))
    dest = os.path.join(target_dir, os.path.basename(src_folder))
    if os.path.exists(dest):
        if not overwrite:
            raise RuntimeError(M("pack_exists", dest))
        shutil.rmtree(dest)
    shutil.copytree(src_folder, dest)
    return dest
