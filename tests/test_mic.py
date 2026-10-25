"""Aufnahme ohne echtes Audiogeraet: ein nachgebauter sounddevice-Stream."""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dubstage_core as ds


class FakeStream(object):
    latency = 0.05                       # Sekunden im Treiberpuffer

    def __init__(self, callback=None, **kwargs):
        self.callback = callback
        self.started = False
        FakeSD.streams.append(self)

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        pass

    def feed(self, samples):
        self.callback(np.asarray(samples, dtype=np.float32)[:, None],
                      len(samples), None, None)


class FakeSD(object):
    streams = []
    played = []

    InputStream = FakeStream

    @classmethod
    def play(cls, data, sr):
        cls.played.append(len(data))

    @classmethod
    def stop(cls):
        pass


class MicTests(unittest.TestCase):
    def setUp(self):
        FakeSD.streams, FakeSD.played = [], []
        self.mic = ds.Mic(sr=1000)
        self.mic.sd = FakeSD

    def test_warmup_before_begin_is_not_part_of_the_take(self):
        self.mic.arm()
        stream = FakeSD.streams[-1]
        stream.feed(np.zeros(500))       # Anlauf des Geraets: Stille
        self.assertEqual(self.mic.envelope()[0], [])
        self.mic.begin(playback=np.ones(10))
        # 50 ms Latenz = 50 Samples, die noch vor der Marke aufgenommen wurden
        stream.feed(np.full(50, 0.1))
        stream.feed(np.full(300, 0.5))
        take = self.mic.stop()
        self.assertEqual(len(take), 300)
        self.assertTrue(np.allclose(take, 0.5))
        self.assertEqual(FakeSD.played, [10])
        self.assertFalse(self.mic.armed)

    def test_envelope_starts_at_the_mark(self):
        self.mic.arm()
        stream = FakeSD.streams[-1]
        stream.feed(np.full(200, 0.9))   # vor dem Start: darf nicht erscheinen
        self.mic.begin()
        stream.feed(np.full(50, 0.9))    # Latenz
        stream.feed(np.full(100, 0.25))
        env, step = self.mic.envelope()
        self.assertEqual(step, 0.02)
        self.assertEqual(len(env), 5)    # 100 Samples / 20er-Fenster
        self.assertTrue(all(abs(v - 0.25) < 1e-6 for v in env))

    def test_start_still_works_for_the_mic_test(self):
        self.mic.start()
        stream = FakeSD.streams[-1]
        stream.feed(np.full(150, 0.3))
        self.assertEqual(len(self.mic.stop()), 100)

    def test_stop_without_begin_returns_nothing(self):
        self.mic.arm()
        FakeSD.streams[-1].feed(np.ones(100))
        self.assertEqual(len(self.mic.stop()), 0)
        self.assertFalse(self.mic.armed)

    def test_rearm_closes_the_previous_stream(self):
        self.mic.arm()
        first = FakeSD.streams[-1]
        self.mic.arm()
        self.assertFalse(first.started)
        self.assertEqual(len(FakeSD.streams), 2)


if __name__ == "__main__":
    unittest.main()
