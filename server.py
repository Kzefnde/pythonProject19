import zmq
import cv2
import time
import pickle

from threading import Thread

def send_frames(socket, video_path, annotations, speed_factor):
    cap = cv2.VideoCapture(video_path)
    frame_rate = cap.get(cv2.CAP_PROP_FPS)
    annotation_index = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if ret:
            timestamp = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            if annotation_index < len(annotations) and timestamp >= float(annotations[annotation_index]):
                annotation_index += 1

            time.sleep((1 / frame_rate) / speed_factor)

            # Отправляем данные в виде байтов
            data = {"frame": frame, "timestamp": timestamp, "annotation_index": annotation_index}
            socket.send(pickle.dumps(data))
        else:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

def main():
    try:
        context = zmq.Context()
        socket = context.socket(zmq.PUSH)
        socket.bind("tcp://*:8000")

        annotations_list = []
        for i in range(1, 5):
            annotations = open(f'{i}.txt').read().splitlines()
            annotations_list.append(annotations)

        speed_factor = 1.0  # Фактор скорости по умолчанию

        threads = []
        for i, video_path in enumerate(['1.mp4', '2.mp4', '3.mp4', '4.mp4']):
            thread = Thread(target=send_frames, args=(socket, video_path, annotations_list[i], speed_factor))
            threads.append(thread)

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

    except Exception as e:
        print(f'Error: {e}')
    finally:
        socket.close()

if __name__ == '__main__':
    main()