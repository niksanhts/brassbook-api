import os
from pymongo import MongoClient
import gridfs

# Настройки подключения к MongoDB
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "audio_db"

# Подключение к MongoDB
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
fs = gridfs.GridFS(db)

def save_audio_file(file_path):
    """Сохраняет аудиофайл в GridFS."""
    if os.path.exists(file_path):
        with open(file_path, 'rb') as audio_file:
            file_id = fs.put(audio_file, filename=os.path.basename(file_path))
            print(f"Файл '{file_path}' успешно сохранен с ID: {file_id}")
            return file_id
    else:
        print("Файл не найден.")
        return None

def retrieve_audio_file(file_id, output_path):
    """Извлекает аудиофайл из GridFS по ID и сохраняет его на диск."""
    try:
        audio_data = fs.get(file_id).read()
        with open(output_path, 'wb') as output_file:
            output_file.write(audio_data)
            print(f"Файл успешно извлечен и сохранен как '{output_path}'")
    except Exception as e:
        print(f"Ошибка при извлечении файла: {e}")

if __name__ == "__main__":
    # Пример использования
    audio_file_path = "path/to/your/audiofile.mp3"  # Укажите путь к вашему аудиофайлу
    file_id = save_audio_file(audio_file_path)

    # Извлечение файла
    if file_id:
        retrieve_audio_file(file_id, "output_audio.mp3")  # Укажите путь для сохранения извлеченного файла
