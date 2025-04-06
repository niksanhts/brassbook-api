import logging
import os
import tempfile
import unittest

import numpy as np
import soundfile as sf

from app.core.compare_melodies import (calculate_average_volume,
                                       calculate_frequency,
                                       calculate_integral_indicator,
                                       calculate_loudness, calculate_rhythm,
                                       compare_melodies,
                                       compare_melody_sequences,
                                       extend_to_max_length, normalize_melody,
                                       process_characteristics,
                                       synchronize_melodies)

logging.basicConfig(level=logging.DEBUG)


class TestMelodyComparison(unittest.TestCase):

    def setUp(self):
        self.sample_rate = 22050
        self.duration = 1.0
        self.silence = np.zeros(int(self.sample_rate * self.duration))
        self.sine_wave = 0.5 * np.sin(
            2
            * np.pi
            * 440
            * np.linspace(0, self.duration, int(self.sample_rate * self.duration))
        )

        self.silence_bytes = self._audio_to_bytes(self.silence, self.sample_rate)
        self.sine_bytes = self._audio_to_bytes(self.sine_wave, self.sample_rate)

    def _audio_to_bytes(self, audio: np.ndarray, sr: int) -> bytes:
        """Конвертирует numpy массив в bytes для тестов."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            sf.write(tmp.name, audio, sr, format="WAV", subtype="PCM_16")
            with open(tmp.name, "rb") as f:
                data = f.read()
        os.remove(tmp.name)
        print("Размер записанных байтов:", len(data))
        return data

    def test_compare_melodies_invalid_input(self):
        result = compare_melodies(None, self.sine_bytes)
        self.assertIsNone(result)

        result = compare_melodies(b"", self.sine_bytes)
        self.assertIsNone(result)

    def test_synchronize_melodies(self):
        teacher_melody = [1.0, 1.0, 2.0, 3.0]
        children_melody = [1.0, 1.0, 2.0, 3.0]
        all_t, all_c, freq_t, freq_c, t_m, c_m = synchronize_melodies(
            teacher_melody, children_melody, 1, 1
        )
        self.assertEqual(len(all_t), len(all_c))
        self.assertEqual(len(freq_t), len(freq_c))
        self.assertEqual(len(t_m), len(c_m))

    def test_compare_melody_sequences(self):
        all_t = [1.0, 2.0, 3.0]
        all_c = [1.0, 2.0, 3.0]
        freq_t = [1, 2, 3]
        freq_c = [1, 2, 3]
        t_m = [1, 1, 1]
        c_m = [1, 1, 1]
        teacher_m = [1.0, 2.0, 3.0]
        children_m = [1.0, 2.0, 3.0]
        result = compare_melody_sequences(
            all_t, all_c, freq_t, freq_c, t_m, c_m, teacher_m, children_m
        )
        self.assertEqual(len(result), 6)
        t_mel, c_mel, f_t, f_c, t_m_new, c_m_new = result
        self.assertEqual(len(t_mel), len(c_mel))
        self.assertEqual(len(f_t), len(f_c))
        self.assertEqual(len(t_m_new), len(c_m_new))

    def test_normalize_melody(self):
        melody = [1.25, 2.75, 3.1]
        normalized = normalize_melody(melody)
        self.assertEqual(normalized, [25, 75, 10])

    def test_calculate_loudness(self):
        t_m = [2, 2]
        c_m = [2, 2]
        teacher_m = [50, 50, 60, 60]
        children_m = [50, 50, 60, 60]
        res_loud = calculate_loudness(t_m, c_m, teacher_m, children_m)
        self.assertEqual(res_loud, [0, 0, 0, 0])

    def test_calculate_rhythm(self):
        t_m = [2, 2]
        c_m = [2, 2]
        res_rhythm = calculate_rhythm(t_m, c_m)
        self.assertEqual(res_rhythm, [0, 0, 0, 0])

    def test_calculate_frequency(self):
        freq_t = [1, 2]
        freq_c = [1, 2]
        c_m = [2, 2]
        res_freq = calculate_frequency(freq_t, freq_c, c_m)
        self.assertEqual(res_freq, [0, 0, 0, 0])

    def test_calculate_average_volume(self):
        melody = [50, 100, 25]
        avg_volume = calculate_average_volume(melody)
        self.assertEqual(avg_volume, [0.5, 1.0, 0.25])

    def test_calculate_integral_indicator(self):
        errors = [0, 1, 0, 1]
        integral = calculate_integral_indicator(errors)
        self.assertAlmostEqual(integral, 0.5, places=2)

    def test_process_characteristics(self):
        characteristics = [1, 0, 1, 0, 1]
        time = 1.0
        result = process_characteristics(characteristics, time)
        self.assertEqual(result, [0, 1])

    def test_extend_to_max_length(self):
        list1 = [1, 2]
        list2 = [1, 2, 3, 4]
        extended1, extended2 = extend_to_max_length(list1, list2, 0)
        self.assertEqual(extended1, [1, 2, 0, 0])
        self.assertEqual(extended2, [1, 2, 3, 4])
