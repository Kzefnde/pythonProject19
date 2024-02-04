import threading
import time
from multiprocessing import Value
import zmq
import cv2
import pickle
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget, QSlider, QHBoxLayout
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QMutex, QMutexLocker
from bisect import bisect_left
class VideoThread(QThread):
    frame_received = pyqtSignal(dict)

    def __init__(self, socket, annotations, speed_factor, shared_timestamp, mutex, sync_mutex, stop_event, parent=None):
        super(VideoThread, self).__init__(parent)
        self.socket = socket
        self.annotations = annotations
        self.speed_factor = speed_factor
        self.shared_timestamp = shared_timestamp
        self.mutex = mutex
        self.sync_mutex = sync_mutex
        self.stop_event = stop_event

    def run(self):
        while not self.stop_event.is_set():
            # Блокировка мьютекса
            with QMutexLocker(self.sync_mutex):
                data_bytes = self.socket.recv()
                data = pickle.loads(data_bytes)
                self.frame_received.emit(data)

            # Задержка между кадрами внутри потока
            self.msleep(int(1000 / self.speed_factor))

            # небольшая задержка, чтобы учесть время передачи данных по сети
            time.sleep(0.01)

    def stop(self):
        self.stop_event.set()

class VideoPlayer(QWidget):
    def __init__(self, socket, video_index, annotations, speed_factor, shared_timestamp, mutex, sync_mutex, stop_event, parent=None):
        super(VideoPlayer, self).__init__(parent)
        self.video_index = video_index
        self.annotations = annotations
        self.speed_factor = speed_factor
        self.shared_timestamp = shared_timestamp
        self.mutex = mutex
        self.sync_mutex = sync_mutex
        self.stop_event = stop_event
        self.setup_ui()

        self.video_thread = VideoThread(socket, self.annotations, self.speed_factor, self.shared_timestamp, self.mutex,
                                        self.sync_mutex, self.stop_event, self)
        self.video_thread.frame_received.connect(self.display_frame)
        self.video_thread.start()

    def frame_to_pixmap(self, frame):
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
        return QPixmap.fromImage(q_image)

    def setup_ui(self):
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)

        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setMinimum(1)
        self.speed_slider.setMaximum(10)
        self.speed_slider.setValue(int(self.speed_factor * 10))
        self.speed_slider.valueChanged.connect(self.update_speed)

        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.speed_slider)
        self.setMinimumWidth(300)
        self.setMinimumHeight(300)

    def update_speed(self):
        self.speed_factor = self.speed_slider.value() / 10.0
        print(f"Video {self.video_index + 1}, Speed Factor: {self.speed_factor}")

    def display_frame(self, data):
        frame = data["frame"]
        timestamp = data["timestamp"] * 1000
        annotation_index = data["annotation_index"]

        # проверка на наличие 'shared_timestamp' в словаре
        shared_timestamp = data.get("shared_timestamp", None)
        if shared_timestamp is not None:
            shared_timestamp *= 1000
        else:
            # обработка, если 'shared_timestamp' отсутствует в словаре
            print("Warning: 'shared_timestamp' not found in the received data.")
            return

        with QMutexLocker(self.mutex):
            current_annotation = float(self.annotations[annotation_index]) if annotation_index < len(
                self.annotations) else float('inf')

        # бинарный поиск для поиска ближайшей временной метки
        closest_annotation_index = bisect_left(self.annotations, timestamp)
        if closest_annotation_index > 0:
            closest_annotation_index -= 1

        closest_annotation = self.annotations[closest_annotation_index]

        if abs(timestamp - shared_timestamp) > 0.1:
            # метка, что кадр старый
            text = "Old Frame"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            font_thickness = 1
            color = (0, 0, 255)
            org = (10, 30)

            cv2.putText(frame, text, org, font, font_scale, color, font_thickness, cv2.LINE_AA)
            self.label.setPixmap(self.frame_to_pixmap(frame))
            return

        if annotation_index < len(self.annotations):
            current_annotation = float(self.annotations[annotation_index])

            epsilon = 0.1
            if abs(timestamp - closest_annotation) < epsilon:  # Используем ближайшую метку
                print(f"Video {self.video_index + 1}, Timestamp: {timestamp}, Current Annotation: {current_annotation}")
                self.setStyleSheet("background-color: red;")
            else:
                if timestamp < closest_annotation:
                    text = "Old Frame"
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.5
                    font_thickness = 1
                    color = (0, 0, 255)
                    org = (10, 30)

                    cv2.putText(frame, text, org, font, font_scale, color, font_thickness, cv2.LINE_AA)

                self.label.setPixmap(self.frame_to_pixmap(frame))
        else:
            self.setStyleSheet("background-color: red;")

def main():
    app = QApplication([])
    context = zmq.Context()
    socket = context.socket(zmq.PAIR)
    socket.connect("tcp://localhost:8000")

    annotations_list = []
    for i in range(1, 5):
        annotations = open(f'{i}.txt').read().splitlines()
        annotations_list.append(list(map(float, annotations)))  # Преобразование строки в числа и сохраняем в виде списка

    speed_factor = 1.0
    shared_timestamp = Value('d', 0.0)
    mutex = QMutex()
    sync_mutex = QMutex()
    stop_event = threading.Event()

    # общий виджет
    main_widget = QWidget()
    layout = QHBoxLayout(main_widget)

    players = [VideoPlayer(socket, i, annotations_list[i], speed_factor, shared_timestamp, mutex, sync_mutex, stop_event) for i in range(4)]

    # видеоплееры в общем виджете
    for player in players:
        layout.addWidget(player)
        player.show()  # Показать видеоплееры в главном окне

    main_widget.show()
    app.exec_()

    stop_event.set()

if __name__ == '__main__':
    main()
