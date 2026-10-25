"""Local speech recognition and pack-independent caption/subtitle helpers.

Importing this module does not import faster-whisper or download a model.
All times are seconds relative to the supplied (already trimmed) media.
"""

from dataclasses import dataclass
from datetime import datetime
import html
import json
import math
from pathlib import Path
import shutil
import tempfile


MODELS = ("large-v3", "turbo", "small")
# Editable UI suggestions; the backend accepts every Whisper language code.
LANGUAGES = ("fr", "en", "de", "es", "it", "pt", "he", "ar", "ja", "zh", "ko", "ru", "uk")


def _decode(media):
    """Mono float32 at 16 kHz, decoded with the app's own ffmpeg.

    faster-whisper's decode_audio goes through PyAV, whose API changes under
    it (PyAV 19 dropped an argument decode_audio still passes); ffmpeg is
    already required by both apps and stable here.
    """
    import numpy as np
    import dubforge_core as pc
    data, _sr = pc.load_mono(str(media), sr=16000)
    return np.asarray(data, dtype=np.float32)


def prepare_audio(media):
    """Decode once at Whisper's sample rate; gently boost quiet inputs for VAD.

    Gain is capped at 20 dB and does not change timing or the source file.
    Exact silence is left alone.
    """
    import numpy as np
    audio = _decode(media)
    if len(audio):
        peak = float(np.max(np.abs(audio)))
        if 0 < peak < 0.95:
            audio = audio * min(10.0, 0.95 / peak)
    return audio


@dataclass(frozen=True)
class Word:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str
    words: tuple = ()


@dataclass(frozen=True)
class Transcript:
    language: str
    segments: tuple


def transcribe(media, language, model="large-v3", device="cpu", progress=None):
    """Return a completed transcript, or raise without mutating caller state."""
    language = language.strip().lower()
    if not language:
        raise ValueError("Select a spoken language code (for example fr for French).")
    if model not in MODELS or device not in ("cpu", "cuda"):
        raise ValueError("Unsupported model or device.")
    try:
        from faster_whisper import WhisperModel
        from faster_whisper.tokenizer import _LANGUAGE_CODES
    except ImportError as exc:
        raise RuntimeError("Speech recognition requires faster-whisper. Run the setup "
                           "again (Setup.exe or Setup.bat) and choose speech "
                           "recognition, or install with: "
                           "py -m pip install -r requirements-transcription.txt") from exc
    if language not in _LANGUAGE_CODES:
        raise ValueError("Unsupported spoken language code: %s" % language)
    report = progress or (lambda message, percent: None)
    report("Loading %s on %s; first use downloads the model. Audio stays local."
           % (model, device), 0)
    try:
        audio = prepare_audio(media)
        recognizer = WhisperModel(model, device=device,
                                  compute_type="int8" if device == "cpu" else "float16")
        raw, info = recognizer.transcribe(
            audio, language=language, task="transcribe", beam_size=5,
            word_timestamps=True, vad_filter=True)
        segments = []
        for segment in raw:
            words = tuple(Word(w.start, w.end, w.word) for w in (segment.words or ()))
            segments.append(Segment(segment.start, segment.end, segment.text.strip(), words))
            report("Transcribed %.1f / %.1f seconds" % (segment.end, info.duration),
                   min(99, 100 * segment.end / max(info.duration, 0.001)))
        report("Transcription complete: %d segments" % len(segments), 100)
        return Transcript(language, tuple(segments))
    except Exception as exc:
        raise RuntimeError("Transcription failed: %s. Check the model download/network, "
                           "available memory, and CUDA libraries if using GPU. "
                           "Existing captions have not been changed." % exc) from exc


def map_captions(transcript, clips):
    """Assign each word once by greatest overlap; ties use earliest clip."""
    text = [[] for _ in clips]
    order = sorted(range(len(clips)), key=lambda i: (clips[i]["start"], i))
    for segment in transcript.segments:
        for word in segment.words:
            if not all(math.isfinite(v) for v in (word.start, word.end)):
                continue
            best, overlap = None, 0
            for i in order:
                amount = min(word.end, clips[i]["end"]) - max(word.start, clips[i]["start"])
                if amount > overlap:
                    best, overlap = i, amount
            if best is not None:
                text[best].append(word.text)
    # Whisper word strings include their original spacing, including punctuation
    # and languages that do not separate words with spaces.
    return ["".join(words).strip() for words in text]


def apply_captions(clips, captions, overwrite=False, remap=False):
    """Mark generated text so later timing edits can preserve manual corrections."""
    for clip, caption in zip(clips, captions):
        generated = ("_generated_caption" in clip and
                     clip.get("caption", "") == clip["_generated_caption"])
        if overwrite or (remap and generated) or (
                not clip.get("caption", "") and not clip.get("_manual_caption", False)):
            clip["caption"] = caption
            clip["_generated_caption"] = caption
            clip.pop("_manual_caption", None)


def _timestamp(milliseconds, vtt=False):
    seconds, ms = divmod(milliseconds, 1000)
    minutes, sec = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    return "%02d:%02d:%02d%s%03d" % (hours, minute, sec, "." if vtt else ",", ms)


def subtitle_text(transcript, vtt=False):
    cues = []
    for segment in sorted(transcript.segments, key=lambda s: s.start):
        if not all(math.isfinite(v) for v in (segment.start, segment.end)):
            continue
        start, end = round(max(0, segment.start) * 1000), round(segment.end * 1000)
        text = " ".join(segment.text.split())
        if not text or end <= start:
            continue
        text = html.escape(text, quote=False)
        cues.append("%d\n%s --> %s\n%s" % (
            len(cues) + 1, _timestamp(start, vtt), _timestamp(end, vtt), text))
    prefix = "WEBVTT\n\n" if vtt else ""
    return prefix + ("\n\n".join(cues) + "\n\n" if cues else "")


def subtitle_outputs(transcript):
    return {"dub_video.srt": subtitle_text(transcript),
            "dub_video.vtt": subtitle_text(transcript, vtt=True)}


def read_existing_captions(folder):
    """Unlike the playback reader, reject corrupt metadata before a write."""
    path = Path(folder) / "_captions.json"
    if path.exists():
        with path.open(encoding="utf-8") as stream:
            data = json.load(stream)
        if not isinstance(data, dict) or any(
                not isinstance(k, str) or not isinstance(v, str) for k, v in data.items()):
            raise ValueError("_captions.json must be a filename-to-text object.")
    import dubforge_core as pc
    return pc.read_captions(str(folder))


def write_outputs(folder, outputs, backup=False):
    """Stage every output; back up replacements and roll back a failed commit.

    Only the explicitly named output files are touched. Backup directories are
    retained after success and on failure for recovery.
    """
    folder = Path(folder)
    if any(Path(name).name != name for name in outputs):
        raise ValueError("Output names must be plain filenames.")
    backup_dir = None
    with tempfile.TemporaryDirectory(prefix=".captions-stage-", dir=folder) as temp:
        staging = Path(temp)
        originals = {}
        for name, text in outputs.items():
            (staging / name).write_text(text, encoding="utf-8")
            dest = folder / name
            originals[name] = dest.read_bytes() if dest.exists() else None
        if backup and any(value is not None for value in originals.values()):
            backup_dir = Path(tempfile.mkdtemp(
                prefix="_caption_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S_"),
                dir=folder))
            for name, value in originals.items():
                if value is not None:
                    shutil.copy2(folder / name, backup_dir / name)
        committed = []
        try:
            for name in outputs:
                (staging / name).replace(folder / name)
                committed.append(name)
        except Exception:
            for name in reversed(committed):
                if originals[name] is None:
                    (folder / name).unlink()
                else:
                    (staging / name).write_bytes(originals[name])
                    (staging / name).replace(folder / name)
            raise
    return backup_dir
