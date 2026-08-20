<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/logo-dark.png">
    <img src="docs/logo.png" alt="DubStage" width="420">
  </picture>
</p>

<p align="center">
  Dub scenes from video yourself — two Windows desktop tools, Python and ffmpeg, no accounts and no cloud.
</p>

---

**DubForge** cuts a video into speakable clips, **DubStage** records your voice line by line and plays the whole scene back with it.

---

## Screenshots

**DubForge** — clip detection, waveform editor, subtitles

<img src="docs/dubforge.png" alt="DubForge: waveform editor with detected clips and subtitle field" width="900">

**DubStage** — recording a line, your take drawn live over the original

<img src="docs/dubstage-record.png" alt="DubStage: video, subtitle and the comparison strip while recording" width="900">

**DubStage** — the finished scene in your own voice

<img src="docs/dubstage-finale.png" alt="DubStage: finale playing the whole scene back" width="900">

## What it does

**DubForge** takes a YouTube link or a local video file, trims it to the span you want, separates the voices from music and noise, and finds the spoken segments on its own. You review the clips in a waveform editor, add subtitles, and build a pack.

**DubStage** plays a pack line by line. You hear the original, record over it as often as you like, and see your take drawn live on top of the original waveform — so you can tell whether your timing lands. At the end the whole scene plays back in your voice, and you can export it as MP4.

## Install

1. Download the files into one folder
2. Run `Setup.bat` — installs the Python packages and fetches ffmpeg into `tools/`
3. `Start DubForge.bat` to build a pack, `Start DubStage.bat` to record

Requires Windows and Python 3.9+. The setup offers [Demucs](https://github.com/adefossez/demucs) for vocal separation; it pulls in PyTorch (several hundred MB up to ~2 GB) and is optional — without it you simply get no backing track.

## Quick start

```
DubForge   →  paste a link, set "From" and "To", "Load and analyse"
           →  check the clips, type subtitles, "Build pack"
DubStage   →  pick the pack, record line by line, "Done"
```

Packs land in `packs/` next to the tools, which is exactly where DubStage looks.

## Export formats

At the top of DubForge you choose what the pack is for:

- **DubStage** — start time in the file name, subtitles in `_captions.json`,
  video as MP4.
- **The Choicer Voicer** — one `.txt` per line next to its audio, one image per
  character, `_pack_info.ini`, video as OGV. The interface then also asks for a
  character per clip and can pull that character's image straight out of the
  scene.

## What a pack looks like

```
packs/MyScene/
  01_Hello_0-920.wav        clip, with its start time in the file name
  02_Goodbye_4-120.wav
  dub_video.mp4             the scene
  _backing_track.wav        music and noise without voices
  _captions.json            subtitles
  _TIMESTAMPS.txt           overview
```

The start time sits in the file name (`44-048` = 44.048 s), so a pack stays readable and editable without any database. DubStage also accepts `dub_video` as `.ogv`, `.mkv`, `.webm`, `.mov` or `.avi`.

## How it works

Video is never decoded during playback. Each pack is split into JPEG frames once (25 fps at 960 px, cached in `%TEMP%`), which keeps playback smooth and independent of codecs. Audio runs through `sounddevice`; recording and the backing track play simultaneously, and the microphone writes a running envelope so the comparison strip can be drawn live.

Clips are loudness-normalised to −1 dBFS peak. The comparison normalises both curves to their own level, so what you judge is rhythm rather than volume.

## Updates

Both tools check GitHub on start — at most once every six hours — for a newer
release. If there is one, a banner appears that names the version, expands to
show that release's changelog, and can install it: the archive is downloaded and
checked, the app closes, the files are replaced and it starts again. Your
`packs/`, `dubs/`, `tools/` and settings are never touched, and the previous
files are backed up to `%TEMP%` first.

This is the only network access apart from downloading a video you asked for.
Nothing is sent, no account is involved. To switch it off, set
`"check_updates": false` in `dubforge_settings.json` or `dubstage_settings.json`.

## Languages

The interface is available in German and English, switchable at runtime in the top right of either tool.

## Documentation

- [`README_EN.md`](README_EN.md) — full manual in English
- [`LIESMICH.md`](LIESMICH.md) — deutsche Anleitung
- [`CHANGELOG.md`](CHANGELOG.md) — what changed, and why

## Licence

GPL-3.0 — see [LICENSE](LICENSE).

You are responsible for only using material you are entitled to use.
