import threading
from multiprocessing import Value
import zmq
import cv2
import time
import pickle
from threading import Thread, Lock

def send_frames(socket, video_path, annotations, speed_factor, shared_timestamp, mutex, sync_mutex, stop_event):
    cap = cv2.VideoCapture(video_path)
    frame_rate = cap.get(cv2.CAP_PROP_FPS)
    annotation_index = 0

    while cap.isOpened() and not stop_event.is_set():
        ret, frame = cap.read()
        if ret:
            timestamp = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            if annotation_index < len(annotations) and timestamp >= float(annotations[annotation_index]):
                annotation_index += 1

            time.sleep((1 / frame_rate) / speed_factor)

            data = {"frame": frame, "timestamp": timestamp, "annotation_index": annotation_index}

            # Отправка данных с блокировкой
            with sync_mutex:
                data["shared_timestamp"] = shared_timestamp.value  # Добавляем shared_timestamp в словарь
                socket.send(pickle.dumps(data))

            # Обновление общей метки времени
            with mutex:
                shared_timestamp.value = timestamp
        else:
            break

    cap.release()


def main():
    try:
        context = zmq.Context()
        socket = context.socket(zmq.PAIR)
        socket.bind("tcp://*:8000")

        annotations_list = []
        for i in range(1, 5):
            annotations = open(f'{i}.txt').read().splitlines()
            annotations_list.append(list(map(float, annotations)))  # Преобразуем строки в числа и сохраняем в виде списка

        speed_factor = 1.0
        shared_timestamp = Value('d', 0.0)  # Общая переменная для хранения метки времени
        mutex = Lock()
        sync_mutex = Lock()
        stop_event = threading.Event()

        threads = []
        for i, video_path in enumerate(['1.mp4', '2.mp4', '3.mp4', '4.mp4']):
            thread = Thread(target=send_frames, args=(socket, video_path, annotations_list[i], speed_factor, shared_timestamp, mutex, sync_mutex, stop_event))
            threads.append(thread)

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

    except Exception as e:
        print(f'Error: {e}')
    finally:
        stop_event.set()
        socket.close()

if __name__ == '__main__':
    main()
