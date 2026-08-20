# -*- coding: utf-8 -*-
"""
updater.py - Update-Pruefung und Selbstaktualisierung.
updater.py - update check and self update.

Gemeinsam von DubForge und DubStage benutzt. Ohne zusaetzliche Pakete:
alles aus der Standardbibliothek (urllib, zipfile).

Ablauf / flow:
  check_latest()   fragt die GitHub-API nach dem neuesten Release
  download_zip()   laedt das Quellarchiv zu diesem Tag
  stage()          entpackt es und prueft, ob es wirklich das Projekt ist
  apply()          schreibt ein Tauschskript, startet es, App beendet sich

Sicherheitsgrenzen:
  - nur HTTPS, nur Adressen bei GitHub, nur dieses eine Repository
  - Groessenlimit fuer den Download
  - keine Pfade mit ".." oder absoluten Angaben aus dem Archiv
  - jede .py/.pyw aus dem Archiv wird vor dem Tausch compiliert
  - packs/, dubs/, tools/ und die Einstellungen werden nie angefasst
"""

import io
import os
import re
import ssl
import sys
import json
import time
import zipfile
import tempfile
import subprocess

from urllib.parse import urlparse
from urllib.request import Request, urlopen

# ------------------------------------------------------------------ Eckdaten
VERSION = "1.2.1"
REPO = "xmrius/dubstage"

API_LATEST = "https://api.github.com/repos/%s/releases/latest" % REPO
RELEASES_PAGE = "https://github.com/%s/releases" % REPO
UA = "DubStage-Updater/%s (+https://github.com/%s)" % (VERSION, REPO)

TIMEOUT = 12                       # Sekunden pro Anfrage
MAX_ZIP = 80 * 1024 * 1024         # 80 MB - das Projekt liegt weit darunter
CHECK_EVERY = 6 * 3600             # hoechstens alle 6 Stunden nachfragen

# Nur diese Hosts liefern bei GitHub Releases aus.
ALLOWED_HOSTS = ("api.github.com", "github.com", "codeload.github.com",
                 "objects.githubusercontent.com",
                 "release-assets.githubusercontent.com")

# Was beim Tausch ueberschrieben werden darf.
OK_EXT = (".pyw", ".py", ".bat", ".cmd", ".md", ".png", ".txt")
OK_NAMES = ("LICENSE",)
SKIP_DIRS = ("packs", "dubs", "tools", ".git", ".github", "__pycache__",
             ".venv", "venv")
SKIP_FILES = ("dubforge_settings.json", "dubstage_settings.json",
              "push_log.txt", "RELEASE_NOTES.md", "Push to GitHub.bat")

# Ohne diese Dateien ist es nicht dieses Projekt - dann kein Tausch.
REQUIRED = ("DubForge.pyw", "DubStage.pyw",
            "dubforge_core.py", "dubstage_core.py")


class UpdateError(Exception):
    """Fehler, dessen Text dem Benutzer gezeigt werden darf."""


# ==========================================================================
#  Versionen
# ==========================================================================

def parse_version(text):
    """'v1.2.3' -> (1, 2, 3). Unbekanntes wird zu (0,)."""
    s = str(text or "").strip().lstrip("vV")
    out = []
    for chunk in re.split(r"[.\-+_]", s):
        m = re.match(r"^(\d+)", chunk)
        if not m:
            break
        out.append(int(m.group(1)))
    return tuple(out) if out else (0,)


def is_newer(remote, local=VERSION):
    """Ist remote echt neuer als local?"""
    a, b = parse_version(remote), parse_version(local)
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return a > b


# ==========================================================================
#  Netz
# ==========================================================================

def _trusted(url):
    p = urlparse(url or "")
    if p.scheme != "https" or p.hostname not in ALLOWED_HOSTS:
        return False
    # Archive muessen aus genau diesem Repository stammen.
    if "zipball" in p.path or "legacy.zip" in p.path:
        return REPO.lower() in p.path.lower()
    return True


def _open(url, extra=None):
    if not _trusted(url):
        raise UpdateError("Nicht vertrauenswuerdige Adresse: %s" % url)
    head = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if extra:
        head.update(extra)
    ctx = ssl.create_default_context()      # Zertifikate werden geprueft
    return urlopen(Request(url, headers=head), timeout=TIMEOUT, context=ctx)


def check_latest():
    """Neuestes Release abfragen. Gibt ein dict zurueck."""
    try:
        with _open(API_LATEST) as r:
            raw = r.read(1024 * 1024)
    except UpdateError:
        raise
    except Exception as e:
        raise UpdateError("%s" % e)

    try:
        d = json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        raise UpdateError("Antwort von GitHub war nicht lesbar.")

    tag = (d.get("tag_name") or "").strip()
    if not tag:
        raise UpdateError("Kein Release gefunden.")

    zip_url = d.get("zipball_url") or ""
    return {
        "tag": tag,
        "version": tag.lstrip("vV"),
        "title": (d.get("name") or tag).strip(),
        "notes": (d.get("body") or "").strip(),
        "page": d.get("html_url") or RELEASES_PAGE,
        "zip": zip_url if _trusted(zip_url) else "",
        "published": (d.get("published_at") or "")[:10],
        "newer": is_newer(tag),
    }


def download_zip(url, dest, progress=None):
    """Archiv laden. progress(geladen, gesamt_oder_None)."""
    if not _trusted(url):
        raise UpdateError("Nicht vertrauenswuerdige Adresse: %s" % url)
    done = 0
    with _open(url) as r:
        total = r.headers.get("Content-Length")
        total = int(total) if (total or "").isdigit() else None
        if total and total > MAX_ZIP:
            raise UpdateError("Archiv ist zu gross (%d MB)."
                              % (total // (1024 * 1024)))
        with open(dest, "wb") as f:
            while True:
                chunk = r.read(64 * 1024)
                if not chunk:
                    break
                done += len(chunk)
                if done > MAX_ZIP:
                    raise UpdateError("Archiv ist zu gross.")
                f.write(chunk)
                if progress:
                    progress(done, total)
    if done < 10 * 1024:
        raise UpdateError("Archiv ist unerwartet klein - Download unvollstaendig.")
    return dest


# ==========================================================================
#  Entpacken und pruefen
# ==========================================================================

def _safe_member(name):
    """Kein Ausbruch aus dem Zielordner."""
    if not name or name.startswith("/") or name.startswith("\\"):
        return False
    if ".." in name.replace("\\", "/").split("/"):
        return False
    if re.match(r"^[a-zA-Z]:", name):
        return False
    return True


def stage(zip_path, workdir):
    """Entpacken und pruefen. Gibt den Ordner mit dem Projekt zurueck."""
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        for n in names:
            if not _safe_member(n):
                raise UpdateError("Archiv enthaelt einen unzulaessigen Pfad: %s" % n)
        z.extractall(workdir)

    # GitHub packt alles in einen Ordner "user-repo-<sha>".
    root = workdir
    entries = [e for e in os.listdir(workdir)
               if not e.startswith(".")]
    if len(entries) == 1 and os.path.isdir(os.path.join(workdir, entries[0])):
        root = os.path.join(workdir, entries[0])

    missing = [f for f in REQUIRED if not os.path.isfile(os.path.join(root, f))]
    if missing:
        raise UpdateError("Archiv passt nicht zum Projekt, es fehlt: %s"
                          % ", ".join(missing))

    # Beschaedigten Download vor dem Tausch abfangen.
    for rel in collect(root):
        if rel.lower().endswith((".py", ".pyw")):
            p = os.path.join(root, rel)
            try:
                with io.open(p, "r", encoding="utf-8") as fh:
                    compile(fh.read(), rel, "exec")
            except SyntaxError as e:
                raise UpdateError("%s im Archiv ist fehlerhaft (Zeile %s)."
                                  % (rel, e.lineno))
            except Exception as e:
                raise UpdateError("%s im Archiv ist nicht lesbar: %s" % (rel, e))
    return root


def collect(root):
    """Relative Pfade, die getauscht werden duerfen."""
    out = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs
                   if d not in SKIP_DIRS and not d.startswith(".")]
        for f in files:
            if f.startswith(".") or f in SKIP_FILES:
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext not in OK_EXT and f not in OK_NAMES:
                continue
            rel = os.path.relpath(os.path.join(base, f), root)
            out.append(rel.replace("\\", "/"))
    return sorted(out)


# ==========================================================================
#  Tausch
# ==========================================================================

SWAP = r"""@echo off
setlocal
set "SRC=__SRC__"
set "DST=__DST__"
set "BAK=__BAK__"
set "LOG=__LOG__"

echo ---- Update __TAG__  %DATE% %TIME% > "%LOG%"
echo Quelle : %SRC% >> "%LOG%"
echo Ziel   : %DST% >> "%LOG%"

rem Warten, bis die App wirklich beendet ist (hoechstens 60 Sekunden).
rem ping statt timeout, weil timeout ohne Konsole aussteigt.
set /a N=0
:wait
tasklist /fi "PID eq __PID__" 2>nul | find "__PID__" >nul
if errorlevel 1 goto :sichern
set /a N+=1
if %N% GEQ 60 goto :laeuftnoch
ping -n 2 127.0.0.1 >nul
goto :wait

:laeuftnoch
echo App laeuft noch - Update abgebrochen. >> "%LOG%"
goto :ende

:sichern
mkdir "%BAK%" 2>nul
for %%E in (pyw py bat cmd md) do xcopy "%DST%\*.%%E" "%BAK%\" /y /q /i >> "%LOG%" 2>&1
echo Sicherung: %BAK% >> "%LOG%"

:kopieren
xcopy "%SRC%\*" "%DST%\" /e /y /q /i >> "%LOG%" 2>&1
if errorlevel 1 goto :fehler
echo Update eingespielt. >> "%LOG%"
goto :starten

:fehler
echo Kopieren fehlgeschlagen - Sicherung wird zurueckgeschrieben. >> "%LOG%"
xcopy "%BAK%\*" "%DST%\" /y /q /i >> "%LOG%" 2>&1
echo Alter Stand wiederhergestellt. >> "%LOG%"

:starten
start "" __RESTART__

:ende
endlocal
"""


def _restart_command(app_dir, which):
    """Wie die App nach dem Tausch wieder gestartet wird."""
    starter = os.path.join(app_dir, "Start %s.bat" % which)
    if os.path.isfile(starter):
        return '"%s"' % starter
    script = os.path.join(app_dir, "%s.pyw" % which)
    exe = sys.executable or "pythonw.exe"
    return '"%s" "%s"' % (exe, script)


def swap_text(staged_root, app_dir, bak, log, which, tag, pid):
    """Inhalt des Tauschskripts - getrennt, damit es pruefbar bleibt."""
    return (SWAP
            .replace("__SRC__", staged_root.rstrip("\\/"))
            .replace("__DST__", app_dir.rstrip("\\/"))
            .replace("__BAK__", bak)
            .replace("__LOG__", log)
            .replace("__TAG__", tag or "?")
            .replace("__PID__", str(pid))
            .replace("__RESTART__", _restart_command(app_dir, which)))


def prune(staged_root):
    """Alles aus dem Zwischenstand entfernen, was nicht getauscht werden darf."""
    keep = set(collect(staged_root))
    for base, dirs, files in os.walk(staged_root, topdown=False):
        for f in files:
            rel = os.path.relpath(os.path.join(base, f),
                                  staged_root).replace("\\", "/")
            if rel not in keep:
                try:
                    os.remove(os.path.join(base, f))
                except OSError:
                    pass
        for d in dirs:
            try:
                os.rmdir(os.path.join(base, d))      # nur wenn leer
            except OSError:
                pass
    return keep


def apply(staged_root, app_dir, which="DubForge", tag=""):
    """Tauschskript schreiben und starten. Die App muss sich danach beenden."""
    if os.name != "nt":
        raise UpdateError("Der automatische Tausch ist nur unter Windows "
                          "vorgesehen.")

    # Nur erlaubte Dateien stehen lassen, damit xcopy nichts Unerwartetes
    # ins Projekt kopiert.
    prune(staged_root)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    tmp = tempfile.gettempdir()
    bak = os.path.join(tmp, "dubstage_backup_%s" % stamp)
    log = os.path.join(tmp, "dubstage_update_%s.log" % stamp)
    bat = os.path.join(tmp, "dubstage_update_%s.bat" % stamp)

    text = swap_text(staged_root, app_dir, bak, log, which, tag, os.getpid())

    with io.open(bat, "w", encoding="cp1252", errors="replace",
                 newline="\r\n") as f:
        f.write(text)

    # CREATE_NO_WINDOW, nicht DETACHED_PROCESS: bei DETACHED hat der Prozess
    # gar keine Konsole, und tasklist/find machen sich dann jeweils eine
    # eigene auf - sichtbar. CREATE_NO_WINDOW gibt ihm eine unsichtbare,
    # die die Kindprozesse erben.
    flags = 0x08000000 | 0x00000200      # CREATE_NO_WINDOW | NEW_PROCESS_GROUP
    subprocess.Popen([os.environ.get("COMSPEC", "cmd.exe"), "/c", bat],
                     cwd=tmp, close_fds=True, creationflags=flags)
    return log


# ==========================================================================
#  Hilfen fuer die Oberflaeche
# ==========================================================================

def due(cfg):
    """Ist eine neue Abfrage faellig? cfg ist das Einstellungs-dict."""
    if not cfg.get("check_updates", True):
        return False
    try:
        last = float(cfg.get("upd_last") or 0)
    except (TypeError, ValueError):
        last = 0
    return (time.time() - last) > CHECK_EVERY


def note_checked(cfg):
    cfg["upd_last"] = time.time()


def plain_notes(md, width=None):
    """Markdown grob in lesbaren Text umsetzen - fuer die Anzeige im Banner."""
    out = []
    for line in (md or "").replace("\r\n", "\n").split("\n"):
        s = line.rstrip()
        s = re.sub(r"^#{1,6}\s*", "", s)               # Ueberschriften
        s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)  # Links
        s = s.replace("**", "").replace("`", "")
        s = re.sub(r"^(\s*)[-*]\s+", r"\1- ", s)
        out.append(s)
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text
