# Changelog

All notable changes to this project are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

Nothing yet.

## [1.3.1] - 2026-10-25

### Fixed

- **The first half second of a recording was missing.** Three delays added up:
  recording started 300 ms after "Go!" appeared, the microphone was only
  opened at that moment — and many devices, USB and especially Bluetooth
  headsets, deliver silence for a few hundred milliseconds after opening,
  while Bluetooth also switches profiles and briefly cuts the sound — and the
  driver's input latency was not accounted for. DubStage now opens the
  microphone when the countdown starts, so the device is warm by the time it
  matters, starts recording and video exactly on "Go!", and skips the samples
  still buffered in the driver so the take lines up with the picture.

## [1.3.0] - 2026-09-28

### Added

- **A real Windows installer.** `DubStage-Setup-<version>.exe` installs both
  tools per user (no admin rights), brings its own Python with every package,
  downloads ffmpeg with a progress bar, and offers Demucs and speech recognition
  as optional components. DubForge and DubStage appear in the Start menu (and
  optionally on the desktop) with their own icons, and uninstall from
  *Settings → Apps*, asking before packs and recordings are deleted.
  `installer/build.ps1` builds it; GitHub Actions builds it on every push and
  attaches it to every published release. `Setup.bat` stays for running from
  source.
- **App icons.** Both windows and their taskbar buttons show their own icon
  instead of Python's, and Windows no longer groups the two tools under
  "Python".

### Changed

- **DubForge has a new look** that matches DubStage: the three steps sit on
  numbered cards, the target format is a segmented switch in the header next to
  the logo, buttons, fields and sliders are flat and consistent, scrollbars are
  slim, the clip table has alternating rows, and the waveform lights up inside
  each clip, with drag handles on the edges and numbered badges.
- **DubStage's menu** shows the logo and a preview frame for every pack.
- **While recording, DubStage shows a small "● REC" badge** in the corner of
  the video instead of a large banner across it, so the mouth you are syncing
  to stays visible. The countdown sits on a solid badge in the middle.
- **Screenshots** in the READMEs show the new interface, rendered on Windows
  by `dev/screenshots.py` with footage from *Tears of Steel* (CC BY 3.0).
- German texts use real umlauts ("Clips prüfen", "Löschen") instead of
  "ue"/"oe".


### Fixed

- **A pack name of `..` deleted the program folder.** Building a pack first
  removes the old one of the same name; `..` resolved to the folder holding the
  tools themselves, `.` to all packs. Names are now stripped of leading and
  trailing dots, and Windows device names such as `CON` or `NUL` are escaped.
- **Installing a pack into its own folder deleted it.** Choosing `packs/` as the
  target removed the pack and then failed to copy it. That case is now a no-op,
  and a target inside the pack is refused.
- **A failed MP4 export in DubStage threw away every take.** The error sent you
  back to the menu, and starting again cleared all recordings. You now stay on
  the finale and can simply save again.
- **The finale could hang half-drawn** when the video has no audio track and the
  pack no backing track; DubStage now reports the problem and stays on stage.
- **"Update yt-dlp" showed a message with a literal `%s`** when nothing
  changed: two messages shared one key, and the app-update text won. The hint
  now also names the Python that actually needs updating.
- **Audio files with a time range could not be analysed** — cutting insisted on
  a video stream.
- **Demucs could fail to read audio** because ffmpeg in `tools/` was not on its
  PATH, which sent it down a torchaudio fallback that newer versions no longer
  support. `tools/` is now passed along, and `requirements-demucs.txt` keeps
  torch/torchaudio below 2.9 until Demucs supports it.
- **DubStage's menu ran ffprobe for every pack on every redraw**, e.g. while
  resizing the window; the duration is now read once. Redrawing also no longer
  resets a microphone you picked but have not tested yet.
- **DubForge opened with a delay of several seconds** while it checked ffmpeg
  and yt-dlp; that check now runs in the background.
- **After a self-update, the app restarted through `Start ….bat`**, which picks
  whichever Python is first on the PATH. It now restarts with the Python it was
  running on. As with every updater fix, this takes effect from the update
  *after* the one that installs it.

## [1.2.1] - 2026-08-20

### Fixed

- **Hovering turned controls white and swallowed their text.** Radio buttons,
  checkboxes and the column headers of the clip list all took their hover
  colours from a ttk state table that `configure()` cannot reach — the same trap
  the dropdowns fell into earlier. All of them are now set through `map()`,
  along with the slider, the spinbox, and read-only entry fields, which had the
  same problem when the URL field is switched off in file mode.
- The whole styling block now tolerates colour options an older Tk does not
  know: a rejected line falls back to the default instead of stopping the
  program from starting.

- **A console window appeared during an update and stayed.** The swap script was
  started with `DETACHED_PROCESS`, which leaves the process without a console —
  so `tasklist`, `find` and `ping` each opened one of their own. Now started
  with `CREATE_NO_WINDOW`, which hands it an invisible console that the child
  processes inherit.
- **A failure while closing could block the update.** The swap script waits for
  the application to disappear before touching any files, and gives up after 60
  seconds. If saving the settings or cleaning the temporary folder raised on the
  way out, the window closed but the process stayed, and the update quietly did
  nothing. Both tools now treat every cleanup step as optional and always reach
  the actual shutdown.

Note that the fix only takes effect from the *next* update onwards: the script
that performs a swap always comes from the version being replaced, not from the
one being installed.

## [1.2.0] - 2026-08-20

### Added

- **Two export formats, selectable at the top of the window.** DubStage as
  before, or **The Choicer Voicer**. The choice changes what the interface
  offers: the CV profile adds a character per clip, an image per character and
  the pack description; the DubStage profile stays exactly as it was.
- **Choicer Voicer export**: one `.txt` per line beside its audio, plus
  `_pack_info.ini`, and the video as OGV — Godot reads nothing else, so a pack
  without `dub_video.ogv` does not load at all.
- **Character images straight from the scene.** Select a clip, type the
  character, press "Grab image": DubForge pulls a still frame from the video at
  that moment and assigns it to that character, with a thumbnail next to the
  field. The pack icon works the same way. Real packs use one image per speaker
  rather than one per line, and the export follows that.
- Numbering in the CV profile runs **per character**, not across the scene —
  `06_woody` may well sit later than `06_buzz`. The order within the scene comes
  from the timestamps alone, which is how the game reads it.

### Notes on the format

The `.txt` format is not documented anywhere; the official route is the editor
inside the game. This implementation was read out of a working pack and verified
against it: all twenty metadata files and the `_pack_info.ini` of that pack are
reproduced byte for byte. UTF-8, CRLF, no newline at the end of the file,
timestamps padded to two digits with three decimals, lists without a space after
the comma.

Captions never need escaping because real packs use typographic quotation marks
inside the straight ones. The export does the same: straight quotes in a subtitle
are converted, so the question of how the game escapes a `"` never arises.

## [1.1.0] - 2026-08-15

### Added

- **Update notice inside both tools.** On start they ask GitHub once whether a
  newer release exists — at most every six hours, and the answer is remembered
  so the banner also appears when no request is made. The banner names the new
  version, expands to show that release's changelog, and updates the tools on
  one click: the archive is downloaded, checked, the app closes, the files are
  replaced and the app starts again.
- `packs/`, `dubs/`, `tools/` and the settings files are never touched by an
  update. Only known project files are replaced, everything else in the archive
  is discarded before the swap, and the previous `.pyw`, `.py`, `.bat` and `.md`
  files are copied to a backup folder in `%TEMP%` first. A log of every step
  lands next to it.
- Guard rails on the way in: HTTPS only, GitHub hosts only, this repository
  only, a size limit on the download, no archive paths pointing outside the
  target folder, and every `.py`/`.pyw` from the archive is compiled before
  anything is replaced — a truncated download cannot leave a broken install.
- The check can be switched off by setting `"check_updates": false` in
  `dubforge_settings.json` or `dubstage_settings.json`. Nothing but the release
  information is ever requested, and nothing is sent.

### Fixed

- **YouTube downloads failed with HTTP 403 on newer ffmpeg builds.** With
  `--download-sections`, yt-dlp hands the video URL to ffmpeg and lets it fetch
  the data; that request does not carry what the URL was signed for, and Google
  refuses it. DubForge now falls back to downloading the whole video with
  yt-dlp's own downloader and cutting it locally with the existing trim path —
  slower, but it works regardless of the ffmpeg build. The fast section
  download is still tried first.

- **"Update yt-dlp" updated a different yt-dlp than the one that runs.** The
  button always went through `pip` for the interpreter running DubForge, while
  the version shown — and the binary actually used for downloads — comes from
  `shutil.which`, which finds any `yt-dlp.exe` in `PATH` first. With both
  present, pip reported success and nothing changed. The button now updates
  whatever `ytdlp()` resolves to: a standalone build updates itself with `-U`,
  a pip launcher falls back to pip from *its own* installation. The startup log
  and the yt-dlp line now name the file in use, and if the version is unchanged
  after an update the dialog says so and explains why instead of claiming
  success.

- **DubForge was unusable in a non-maximised window.** The three steps were
  packed straight into the window, so anything past the bottom edge — step 3,
  "Build pack", the progress bar and the log — was simply gone, with no way to
  reach it. The content now sits in a scrollable canvas. It is stretched to the
  window as long as there is room, so a maximised window looks exactly as
  before; below that it scrolls.
- The mouse wheel scrolls the page, except over widgets that scroll or count on
  their own: the waveform still zooms, the clip list and the log scroll
  themselves and hand the wheel back to the page once they hit their end, and
  the spinbox keeps counting.
- Minimum window size lowered from 980×740 to 900×480, and both tools now open
  no taller than the screen allows. At 1180×880 DubForge did not fit on a 1080p
  display once the taskbar and title bar were subtracted — which is how the
  problem arose in the first place.
- Scrollbars were unstyled and showed up pale grey against the dark interface.

## [1.0.1] - 2026-08-11

### Added

- **yt-dlp maintenance.** DubForge reports the installed yt-dlp version and its
  age at startup, warns beyond 60 days, and offers a one-click update. The
  updater detects how yt-dlp was installed: a standalone binary in `tools/`
  updates itself with `-U`, a pip installation goes through pip. If a download
  fails and the version is older than 30 days, the log points at it as the
  likely cause — YouTube changes its delivery constantly and a stale yt-dlp is
  by far the most common reason for failures.
- **Logo** in light and dark variants (`docs/logo.png`, `docs/logo-dark.png`),
  switched automatically via `<picture>` and `prefers-color-scheme`. The dark
  variant lifts the wordmark to a light tone and the wave from `#4b24ed` to
  `#7c5cff`; on GitHub's dark background the original values reach only 1.10
  and 2.50 contrast, below the 3.0 minimum for graphics.
- **Screenshots** in the README.
- **`.gitattributes`** — LF inside the repository, CRLF on checkout for `.bat`
  and `.cmd`. Keeps `LICENSE` from showing up as fully rewritten whenever line
  endings differ between systems.

### Fixed

- **Read-only dropdowns were unreadable.** Their colours come from a ttk state
  table that `configure()` does not reach, so the light default background
  survived. Now set through `map()` with an explicit `readonly` entry, in both
  tools. The popup list is a plain Tk widget that ttk does not style at all and
  is now coloured via `option_add` — it would have stayed white.
- **Batch files had LF-only line endings.** cmd.exe handles those unreliably,
  particularly around labels and `goto`. All `.bat` files converted to CRLF and
  pinned via `.gitattributes`.
- Status text announced "converting to OGV" although MP4 has been written since
  the format switch; two dialogs still spoke of copying "into the game".

### Removed

- `Push to GitHub.bat` is no longer part of the repository. It is a maintenance
  helper, not part of the project. The push script now untracks anything that
  matches `.gitignore` but is still tracked, so the file stays on disk while
  disappearing from GitHub.

## [1.0.0] - 2026-08-10

First public release. Two Windows desktop tools, German and English interface,
switchable at runtime.

### DubForge — building packs

- Source from a YouTube link or a local file, limited to a chosen time span.
  The stream-copy cut is verified against the expected duration and re-encoded
  when it lands off target, because keyframe seeking is frequently inaccurate.
- Optional vocal separation with Demucs; falls back to the original audio when
  it is unavailable, losing only the backing track.
- Automatic clip detection from the loudness envelope, with adjustable
  sensitivity and maximum clip length. Long segments are split at their
  quietest point.
- Waveform editor: drag edges to trim, drag empty space for a new clip, split,
  rename, delete, listen. Mouse wheel zooms.
- Subtitles per clip. Enter saves and moves to the next clip, so a whole pack
  can be captioned without touching the mouse.
- Clips exported at −1 dBFS peak so that loudness does not distort the
  comparison later.
- Video written as MP4/H.264. Roughly four times faster to encode than the
  previous Theora path and about 40 % smaller.

### DubStage — recording

- Line-by-line workflow: hear the original, record over it, play your own take
  back, as often as you like. Any line can be left empty and keeps the original
  voice.
- **Comparison strip** — the original as a silhouette with your take drawn over
  it on a shared time axis, live while recording. Both curves are normalised to
  their own peak, so what you judge is timing and rhythm rather than level.
- Subtitles shown below the video, and running along as real subtitles during
  the final playback.
- Finale plays the whole scene with your recordings mixed over the backing
  track; export as MP4.
- Microphone test with level readout and playback.
- Video is split into JPEG frames once and cached instead of being decoded
  during playback, at 25 fps and 960 px. Playback timing derives each frame
  deadline from the start time rather than adding a fixed delay, which is the
  difference between a nominal 25 fps and 19 effective.

### Packs

- A pack is a plain folder. Each clip carries its start time in the file name
  (`07_MyLine_44-048.wav` = 44.048 s), subtitles live in `_captions.json`.
  No database and no binary index, so packs stay readable and hand-editable.

### Robustness

- Recording can never leave the interface stuck: button states are set before
  any drawing happens, the frame loop tolerates drawing errors, a watchdog ends
  the recording even if the loop stalls, and every phase carries a deadline
  after which the interface is released.
- Array lengths are aligned before mixing a take with the backing track.
  `int(len(x) / sr * sr)` does not reliably return `len(x)`; for roughly 8 % of
  clip lengths it lands one sample short, which previously raised mid-playback
  and froze the interface.

[Unreleased]: https://github.com/xmrius/dubstage/compare/v1.3.1...HEAD
[1.3.1]: https://github.com/xmrius/dubstage/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/xmrius/dubstage/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/xmrius/dubstage/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/xmrius/dubstage/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/xmrius/dubstage/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/xmrius/dubstage/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/xmrius/dubstage/releases/tag/v1.0.0
