import json
from pathlib import Path
import runpy
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

import caption_pack
import dubstage_core as ds
import transcription as tr


def transcript():
    return tr.Transcript("fr", (
        tr.Segment(0.25, 2, "Bonjour, été !", (
            tr.Word(.25, .75, " Bonjour,"), tr.Word(1, 2, " été !"))),
        tr.Segment(5, 6, "Hors clip.", (tr.Word(5, 6, " Hors clip."),)),
    ))


class CaptionTests(unittest.TestCase):
    def test_mapping_keeps_gaps_and_uses_relative_time(self):
        clips = [{"start": 0, "end": 1}, {"start": 1, "end": 2},
                 {"start": 10, "end": 11}]
        self.assertEqual(tr.map_captions(transcript(), clips), ["Bonjour,", "été !", ""])
        self.assertIn("Hors clip.", tr.subtitle_text(transcript()))
        self.assertIn("00:00:00,250", tr.subtitle_text(transcript()))

    def test_maximum_overlap_and_earliest_tie(self):
        text = tr.Transcript("fr", (tr.Segment(1, 3, "un", (tr.Word(1, 3, " un"),)),))
        self.assertEqual(tr.map_captions(text, [{"start": 2, "end": 4},
                                              {"start": 0, "end": 2}]), ["", "un"])
        self.assertEqual(tr.map_captions(text, [{"start": 0, "end": 2},
                                              {"start": 1, "end": 4}]), ["", "un"])

    def test_silent_and_invalid_words_do_not_invent_text(self):
        text = tr.Transcript("fr", (tr.Segment(0, 1, "noise", (
            tr.Word(0, 0, "zero"), tr.Word(float("nan"), 1, "bad"))),))
        self.assertEqual(tr.map_captions(text, [{"start": 0, "end": 1}]), [""])
        self.assertEqual(tr.map_captions(text, []), [])

    def test_corrections_and_intentional_empty_caption_survive_remap(self):
        clips = [{"caption": "corrigé"}, {"caption": "auto", "_generated_caption": "auto"},
                 {"caption": "", "_manual_caption": True}, {"caption": ""}]
        tr.apply_captions(clips, ["a", "b", "c", "d"], remap=True)
        self.assertEqual([c["caption"] for c in clips], ["corrigé", "b", "", "d"])
        tr.apply_captions(clips, ["a", "b", "c", "d"], overwrite=True)
        self.assertEqual([c["caption"] for c in clips], ["a", "b", "c", "d"])

    def test_existing_generated_text_preserved_unless_remap_or_overwrite(self):
        clips = [{"caption": "ancien", "_generated_caption": "ancien"}]
        tr.apply_captions(clips, ["nouveau"])
        self.assertEqual(clips[0]["caption"], "ancien")

    def test_subtitle_formats_rounding_escaping_and_invalid_cues(self):
        text = tr.Transcript("fr", (
            tr.Segment(3599.9996, 3601, "é <b> &\n\nbonjour"),
            tr.Segment(1, 1, "zero"), tr.Segment(2, 3, " "),
            tr.Segment(float("nan"), 5, "bad"),
            tr.Segment(-1, .1, "début")))
        srt, vtt = tr.subtitle_text(text), tr.subtitle_text(text, True)
        self.assertIn("01:00:00,000 --> 01:00:01,000", srt)
        self.assertIn("é &lt;b&gt; &amp; bonjour", srt)
        self.assertIn("00:00:00,000 --> 00:00:00,100", srt)
        self.assertTrue(vtt.startswith("WEBVTT\n\n"))
        self.assertIn("01:00:00.000", vtt)
        self.assertNotIn("zero", srt)
        self.assertNotIn("bad", srt)
        self.assertEqual(tr.subtitle_text(tr.Transcript("fr", ()), True), "WEBVTT\n\n")

    def test_backup_and_json_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "_captions.json"
            path.write_text('{"line.wav": "été"}', encoding="utf-8")
            backup = tr.write_outputs(folder, {"_captions.json": "{}"}, backup=True)
            self.assertEqual(json.loads((backup / path.name).read_text(encoding="utf-8")),
                             {"line.wav": "été"})
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValueError):
                tr.read_existing_captions(folder)
            path.write_text("invalid", encoding="utf-8")
            with self.assertRaises(ValueError):
                tr.read_existing_captions(folder)

    def test_failed_commit_rolls_back_all_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            first = Path(folder) / "a.txt"
            first.write_text("original", encoding="utf-8")
            original_replace = Path.replace

            def fail_second(path, target):
                if Path(target).name == "b.txt":
                    raise OSError("disk failure")
                return original_replace(path, target)

            with patch.object(Path, "replace", fail_second):
                with self.assertRaises(OSError):
                    tr.write_outputs(folder, {"a.txt": "changed", "b.txt": "new"}, backup=True)
            self.assertEqual(first.read_text(), "original")
            self.assertFalse((Path(folder) / "b.txt").exists())

    def test_rejects_output_traversal(self):
        with self.assertRaises(ValueError):
            tr.write_outputs(".", {"../outside.txt": "bad"})


class EngineTests(unittest.TestCase):
    def test_missing_dependency_is_actionable(self):
        with patch.dict(sys.modules, {"faster_whisper": None}):
            with self.assertRaisesRegex(RuntimeError, "Setup.bat"):
                tr.transcribe("audio.wav", "fr")

    def test_explicit_french_and_cpu_settings_and_lazy_generator(self):
        raw = types.SimpleNamespace(start=.25, end=2, text=" Bonjour ", words=[
            types.SimpleNamespace(start=.25, end=2, word=" Bonjour")])
        model = Mock()
        model.transcribe.return_value = (iter([raw]), types.SimpleNamespace(duration=10))
        factory = Mock(return_value=model)
        modules = {"faster_whisper": types.SimpleNamespace(WhisperModel=factory),
                   "faster_whisper.tokenizer": types.SimpleNamespace(_LANGUAGE_CODES=("fr",))}
        with patch.dict(sys.modules, modules), patch.object(tr, "prepare_audio", return_value="decoded audio"):
            result = tr.transcribe("trimmed.wav", "FR")
            factory.assert_called_once_with("large-v3", device="cpu", compute_type="int8")
            model.transcribe.assert_called_once_with("decoded audio", language="fr",
                task="transcribe", beam_size=5, word_timestamps=True, vad_filter=True)
            self.assertEqual(result.segments[0].start, .25)
            with self.assertRaisesRegex(ValueError, "Unsupported spoken"):
                tr.transcribe("trimmed.wav", "invalid")

    def test_quiet_audio_gain_is_bounded_and_preserves_sample_positions(self):
        import numpy as np
        decode = Mock(return_value=np.array([0., .01, -.01, 0.], dtype=np.float32))
        with patch.object(tr, "_decode", decode):
            boosted = tr.prepare_audio("quiet.wav")
            np.testing.assert_allclose(boosted, [0, .1, -.1, 0])
            decode.assert_called_once_with("quiet.wav")
            decode.return_value = np.zeros(4, dtype=np.float32)
            np.testing.assert_array_equal(tr.prepare_audio("silent.wav"), np.zeros(4))

    def test_apps_import_without_optional_dependency(self):
        with patch.dict(sys.modules, {"faster_whisper": None}):
            for path, entry in (("DubForge.pyw", "App"), ("DubStage.pyw", "Game")):
                namespace = runpy.run_path(path, run_name="import_test")
                self.assertTrue(callable(namespace[entry]))


class PackTests(unittest.TestCase):
    def make_pack(self, folder):
        for name in ("dub_video.mp4", "01_a_0-000.wav", "02_b_1-000.wav"):
            (Path(folder) / name).write_bytes(b"unchanged media")

    def test_existing_pack_round_trip_and_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            self.make_pack(folder)
            path = Path(folder) / "_captions.json"
            path.write_text(json.dumps({"01_a_0-000.wav": "manuel"}), encoding="utf-8")
            with patch.object(tr, "transcribe", return_value=transcript()), \
                    patch.object(caption_pack.pc, "probe_duration", return_value=1):
                caption_pack.caption_pack(folder, "fr")
                pack = ds.load_pack(folder)
                self.assertEqual([line.caption for line in pack.lines], ["manuel", "été !"])
                caption_pack.caption_pack(folder, "fr", overwrite=True)
                self.assertEqual(ds.load_pack(folder).lines[0].caption, "Bonjour,")
            self.assertIn("Hors clip.", (Path(folder) / "dub_video.srt").read_text(encoding="utf-8"))
            self.assertEqual((Path(folder) / "dub_video.mp4").read_bytes(), b"unchanged media")

    def test_failure_and_corrupt_metadata_do_not_write(self):
        with tempfile.TemporaryDirectory() as folder:
            self.make_pack(folder)
            path = Path(folder) / "_captions.json"
            path.write_text("{}", encoding="utf-8")
            with patch.object(tr, "transcribe", side_effect=RuntimeError("model failed")), \
                    patch.object(caption_pack.pc, "probe_duration", return_value=1):
                with self.assertRaises(RuntimeError):
                    caption_pack.caption_pack(folder, "fr")
            self.assertEqual(path.read_text(), "{}")
            self.assertFalse((Path(folder) / "dub_video.srt").exists())
            path.write_text("broken", encoding="utf-8")
            with patch.object(tr, "transcribe") as recognize:
                with self.assertRaises(ValueError):
                    caption_pack.caption_pack(folder, "fr")
                recognize.assert_not_called()

    def test_overwrite_silence_clears_legacy_sidecar_and_keeps_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            self.make_pack(folder)
            sidecar = Path(folder) / "01_a_0-000.txt"
            sidecar.write_text("ancien", encoding="utf-8")
            with patch.object(tr, "transcribe", return_value=tr.Transcript("fr", ())), \
                    patch.object(caption_pack.pc, "probe_duration", return_value=1):
                result = caption_pack.caption_pack(folder, "fr", overwrite=True)
            self.assertEqual(ds.load_pack(folder).lines[0].caption, "")
            self.assertEqual((result["backup"] / sidecar.name).read_text(), "ancien")


if __name__ == "__main__":
    unittest.main()
