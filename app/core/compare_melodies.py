import io
import logging
from math import floor
from typing import List, Optional, Tuple

import librosa
import numpy as np


class AudioConfig:
    N_MELS = 64
    FREQ_BANDS = slice(4, 9)
    TIME_FACTOR = 4
    TRIM_DB = 14
    LOUDNESS_THRESHOLD = 0.25
    RHYTHM_THRESHOLD = 0.25


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def compare_melodies(
    file1: bytes, file2: bytes
) -> Optional[Tuple[float, List[int], List[int], List[int], List[float]]]:
    """Сравнивает две мелодии и возвращает их характеристики."""
    logging.info("Начало сравнения мелодий")
    try:
        if not isinstance(file1, bytes) or not isinstance(file2, bytes):
            raise TypeError("Входные файлы должны быть в формате bytes")
        if not file1 or not file2:
            raise ValueError("Входные файлы не могут быть пустыми")

        teacher_melody, min_per_t = extract_melody_from_audio(file1)
        if teacher_melody is None:
            raise ValueError("Не удалось извлечь мелодию учителя")

        children_melody, min_per_c = extract_melody_from_audio(file2)
        if children_melody is None:
            raise ValueError("Не удалось извлечь мелодию ребенка")

        all_t, all_c, freq_t, freq_c, t_m, c_m = synchronize_melodies(
            teacher_melody, children_melody, min_per_t, min_per_c
        )

        teacher_melody, children_melody, freq_t, freq_c, t_m, c_m = (
            compare_melody_sequences(
                all_t, all_c, freq_t, freq_c, t_m, c_m, teacher_melody, children_melody
            )
        )

        result = compare(t_m, c_m, freq_t, freq_c, teacher_melody, children_melody, 2)
        logging.info("Сравнение мелодий завершено")
        return result

    except TypeError as te:
        logging.error("Ошибка типа данных: %s", str(te))
        return None
    except ValueError as ve:
        logging.error("Ошибка ввода: %s", str(ve))
        return None
    except librosa.LibrosaError as le:
        logging.error("Ошибка обработки аудио: %s", str(le))
        return None
    except Exception as e:
        logging.error("Непредвиденная ошибка в %s: %s", __name__, str(e))
        return None


def extract_melody_from_audio(
    file_bytes: bytes,
) -> Tuple[Optional[List[float]], Optional[float]]:
    """Извлекает мелодию из аудиофайла."""
    logging.info("Начало извлечения мелодии из аудиофайла")
    try:
        if not file_bytes:
            raise ValueError("Пустой файл")

        tm, srt = librosa.load(io.BytesIO(file_bytes), sr=None)
        logging.debug("Аудиофайл загружен: длина %d, частота %d", len(tm), srt)

        tmt, _ = librosa.effects.trim(tm, top_db=AudioConfig.TRIM_DB)
        tmt_mel = librosa.feature.melspectrogram(
            y=tmt, sr=srt, n_mels=AudioConfig.N_MELS
        )
        tmt_db_mel = librosa.amplitude_to_db(tmt_mel)[AudioConfig.FREQ_BANDS]
        tmt_db_mel_transposed = np.transpose(tmt_db_mel)

        time_t = librosa.get_duration(y=tmt, sr=srt)
        min_per_t = round(len(tmt_db_mel_transposed)) / (
            time_t * AudioConfig.TIME_FACTOR
        )

        mask = np.all(tmt_db_mel_transposed < 0, axis=1)
        max_indices = np.argmax(tmt_db_mel_transposed[~mask], axis=1)
        max_values = np.max(tmt_db_mel_transposed[~mask], axis=1)

        result = np.zeros(len(tmt_db_mel_transposed))
        nonzero_indices = np.where(~mask)[0]
        result[nonzero_indices] = max_indices + (np.round(max_values) / 100)

        logging.info(
            "Извлечение мелодии завершено, найдено %d нот", len(nonzero_indices)
        )
        return result.tolist(), min_per_t

    except ValueError as ve:
        logging.error("Ошибка ввода: %s", str(ve))
        return None, None
    except librosa.LibrosaError as le:
        logging.error("Ошибка librosa: %s", str(le))
        return None, None
    except Exception as e:
        logging.error("Ошибка в extract_melody_from_audio: %s", str(e))
        return None, None


def synchronize_melodies(
    teacher_melody: List[float],
    children_melody: List[float],
    min_per_t: float,
    min_per_c: float,
) -> Tuple[List[float], List[float], List[int], List[int], List[int], List[int]]:
    """Синхронизирует две мелодии."""
    logging.info("Начало синхронизации мелодий")
    try:
        all_t, freq_t, t_m = extract_notes(teacher_melody, min_per_t)
        all_c, freq_c, c_m = extract_notes(children_melody, min_per_c)
        return all_t, all_c, freq_t, freq_c, t_m, c_m
    except Exception as e:
        logging.error("Ошибка в synchronize_melodies: %s", str(e))
        return [], [], [], [], [], []


def extract_notes(
    melody: List[float], min_per: float
) -> Tuple[List[float], List[int], List[int]]:
    """Извлекает ноты из мелодии."""
    logging.debug("Начало извлечения нот")
    counter = 0
    all_notes = []
    freq = []
    lengths = []

    try:
        for i in range(len(melody) - 1):
            if floor(melody[i]) == floor(melody[i + 1]):
                counter += 1
            elif counter >= min_per:
                all_notes.append(floor(melody[i]) + counter / 100)
                freq.append(floor(melody[i]))
                lengths.append(counter)
                counter = 0

        logging.debug("Извлечение нот завершено, найдено %d нот", len(all_notes))
        return all_notes, freq, lengths
    except Exception as e:
        logging.error("Ошибка в extract_notes: %s", str(e))
        return [], [], []


def compare_melody_sequences(
    all_t: List[float],
    all_c: List[float],
    freq_t: List[int],
    freq_c: List[int],
    t_m: List[int],
    c_m: List[int],
    teacher_melody: List[float],
    children_melody: List[float],
) -> Tuple[List[float], List[float], List[int], List[int], List[int], List[int]]:
    """Сравнивает последовательности нот."""
    logging.info("Начало проверки последовательностей нот")
    exec_t, exec_c = [], []

    try:
        if len(all_t) != len(all_c):
            for i in range(min(len(all_t), len(all_c)) - 3):
                if all_c[i] != all_t[i] and all_c[i + 1 : i + 3] == all_t[i : i + 2]:
                    exec_c.append(i + all_c[i] % 1)
                elif all_c[i] != all_t[i] and all_c[i : i + 2] == all_t[i + 1 : i + 3]:
                    exec_t.append(i + all_t[i] % 1)

        for idx in exec_c:
            idx = floor(idx)
            t_m.insert(idx, 1)
            freq_t.insert(idx, 6)

        for idx in exec_t:
            idx = floor(idx)
            c_m.insert(idx, 1)
            freq_c.insert(idx, 6)

        teacher_melody, children_melody = extend_to_max_length(
            teacher_melody, children_melody, 0.0
        )
        freq_t, freq_c = extend_to_max_length(freq_t, freq_c, 0)
        t_m, c_m = extend_to_max_length(t_m, c_m, 1)

        return teacher_melody, children_melody, freq_t, freq_c, t_m, c_m
    except Exception as e:
        logging.error("Ошибка в compare_melody_sequences: %s", str(e))
        return teacher_melody, children_melody, freq_t, freq_c, t_m, c_m


def extend_to_max_length(
    list1: List, list2: List, fill_value: float
) -> Tuple[List, List]:
    """Расширяет списки до одинаковой максимальной длины."""
    max_length = max(len(list1), len(list2))
    list1.extend([fill_value] * (max_length - len(list1)))
    list2.extend([fill_value] * (max_length - len(list2)))
    return list1, list2


def normalize_melody(melody: List[float]) -> List[int]:
    """Нормализует мелодию в целые числа."""
    return [round((y % 1) * 100) for y in melody]


def calculate_loudness(
    t_m: List[int],
    c_m: List[int],
    teacher_melody: List[int],
    children_melody: List[int],
) -> List[int]:
    """Вычисляет метрику громкости."""
    res_loud = []
    counter_t, counter_c = 0, 0
    for i in range(len(t_m)):
        t_sum = sum(teacher_melody[counter_t : counter_t + t_m[i]])
        c_sum = sum(children_melody[counter_c : counter_c + c_m[i]])
        if (
            t_sum != 0
            and abs(1 - (c_sum / c_m[i]) / (t_sum / t_m[i]))
            <= AudioConfig.LOUDNESS_THRESHOLD
        ):
            res_loud.extend([0] * c_m[i])
        else:
            res_loud.extend([1] * c_m[i])
        counter_t += t_m[i]
        counter_c += c_m[i]
    return res_loud


def calculate_rhythm(t_m: List[int], c_m: List[int]) -> List[int]:
    """Вычисляет метрику ритма."""
    res_rhythm = []
    for i in range(len(t_m)):
        if abs((t_m[i] - c_m[i]) / t_m[i]) <= AudioConfig.RHYTHM_THRESHOLD:
            res_rhythm += [0] * c_m[i]
        else:
            res_rhythm += [0] * min(t_m[i], c_m[i]) + [1] * abs(c_m[i] - t_m[i])
    return res_rhythm


def calculate_frequency(
    freq_t: List[int], freq_c: List[int], c_m: List[int]
) -> List[int]:
    """Вычисляет метрику частоты."""
    res_frequency = []
    for i in range(len(freq_t)):
        res_frequency += [0] * c_m[i] if freq_t[i] == freq_c[i] else [1] * c_m[i]
    return res_frequency


def calculate_average_volume(children_melody: List[int]) -> List[float]:
    """Вычисляет среднюю громкость."""
    max_c = max(children_melody) if children_melody else 1
    return [round(m / max_c, 2) if max_c != 0 else round(m, 2) for m in children_melody]


def calculate_integral_indicator(total_errors: List[int]) -> float:
    """Вычисляет интегральный показатель."""
    integral_indicator = 1
    if total_errors:
        integral_indicator -= round(sum(total_errors) / len(total_errors), 2)
    return integral_indicator


def compare(
    t_m: List[int],
    c_m: List[int],
    freq_t: List[int],
    freq_c: List[int],
    teacher_melody: List[float],
    children_melody: List[float],
    time_c: float,
) -> Tuple[float, List[int], List[int], List[int], List[float]]:
    """Сравнивает мелодии и возвращает метрики."""
    logging.info("Начало финального сравнения мелодий")
    try:
        teacher_melody = normalize_melody(teacher_melody)
        children_melody = normalize_melody(children_melody)

        res_loud = calculate_loudness(t_m, c_m, teacher_melody, children_melody)
        res_rhythm = calculate_rhythm(t_m, c_m)
        res_frequency = calculate_frequency(freq_t, freq_c, c_m)
        res_average = calculate_average_volume(children_melody)

        total_errors = res_rhythm + res_frequency
        integral_indicator = calculate_integral_indicator(total_errors)

        rhythm = process_characteristics(res_rhythm, time_c)
        height = process_characteristics(res_frequency, time_c)
        volume1 = process_characteristics(res_loud, time_c)

        logging.info("Финальное сравнение завершено")
        return integral_indicator, rhythm, height, volume1, res_average
    except Exception as e:
        logging.error("Ошибка в compare: %s", str(e))
        return 0.0, [], [], [], []


def process_characteristics(x: List[int], time: float) -> List[int]:
    """Обрабатывает характеристики во временные интервалы."""
    logging.debug("Начало обработки характеристик")
    y = []
    time = round(time, 2)
    count_of_values = round(time * AudioConfig.TIME_FACTOR)

    try:
        if count_of_values == 0:
            logging.warning("Время равно нулю, возвращаем пустой список")
            return y

        while len(x) >= count_of_values:
            c = sum(x[:count_of_values]) / count_of_values
            y.append(1 if c > 0.5 else 0)
            x = x[count_of_values:]

        if x:
            c = sum(x) / len(x)
            y.append(1 if c > 0.5 else 0)

        logging.debug(
            "Обработка характеристик завершена, результат: %d значений", len(y)
        )
        return y
    except Exception as e:
        logging.error("Ошибка в process_characteristics: %s", str(e))
        return []
