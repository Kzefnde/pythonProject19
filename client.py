from multiprocessing import Value
import datetime
import zmq
import cv2
import pickle
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget, QSlider, QHBoxLayout
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtCore import QMutex
from PyQt5.QtCore import QMutexLocker

class VideoThread(QThread):
    frame_received = pyqtSignal(dict)

    def __init__(self, socket, annotations, speed_factor, shared_timestamp, mutex, parent=None):
        super(VideoThread, self).__init__(parent)
        self.socket = socket
        self.annotations = annotations
        self.speed_factor = speed_factor
        self.shared_timestamp = shared_timestamp
        self.mutex = mutex

    def run(self):
        while True:
            with QMutexLocker(self.mutex):
                data_bytes = self.socket.recv()
                data = pickle.loads(data_bytes)
                self.frame_received.emit(data)

            # Задержка между кадрами внутри потока
            self.msleep(int(1000 / self.speed_factor))

    def update_frame(self):
        with QMutexLocker(self.mutex):
            data_bytes = self.socket.recv()
            data = pickle.loads(data_bytes)
            self.frame_received.emit(data)

            # Запустить таймер для следующего кадра
            self.timer.singleShot(int(1000 / self.speed_factor), self.update_frame)

class VideoPlayer(QWidget):
    def __init__(self, socket, video_index, annotations, speed_factor, shared_timestamp, mutex, parent=None):
        super(VideoPlayer, self).__init__(parent)
        self.video_index = video_index
        self.annotations = annotations
        self.speed_factor = speed_factor
        self.shared_timestamp = shared_timestamp
        self.mutex = mutex
        self.setup_ui()

        self.video_thread = VideoThread(socket, self.annotations, self.speed_factor, self.shared_timestamp, self.mutex,
                                        self)
        self.video_thread.frame_received.connect(self.display_frame)
        self.video_thread.finished.connect(self.thread_finished)
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
        shared_timestamp = data["shared_timestamp"] * 1000  # Получаем общее время

        while annotation_index < len(self.annotations) and timestamp > float(self.annotations[annotation_index]):
            annotation_index += 1

        # Сравниваем timestamp с shared_timestamp
        if abs(timestamp - shared_timestamp) > 0.1:  # Задайте подходящий порог
            return

        if annotation_index < len(self.annotations):
            current_annotation = float(self.annotations[annotation_index])

            # Проверяем, достигнута ли аннотация
            epsilon = 0.1
            if abs(timestamp - current_annotation) < epsilon:
                print(f"Video {self.video_index + 1}, Timestamp: {timestamp}, Current Annotation: {current_annotation}")
                self.setStyleSheet("background-color: green;")
            else:
                # Добавляем метку о старом кадре, если timestamp < current_annotation
                if timestamp < current_annotation:
                    text = "Old Frame"
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.5
                    font_thickness = 1
                    color = (0, 0, 255)  # Красный цвет в формате BGR
                    org = (10, 30)  # Координаты начала текста

                    cv2.putText(frame, text, org, font, font_scale, color, font_thickness, cv2.LINE_AA)

                self.label.setPixmap(self.frame_to_pixmap(frame))
        else:
            self.setStyleSheet("background-color: green;")

    def thread_finished(self):
        print(f"Thread for Video {self.video_index + 1} finished.")

def main():
    app = QApplication([])
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect("tcp://localhost:8000")
    socket.setsockopt_string(zmq.SUBSCRIBE, '')

    annotations_list = []
    for i in range(1, 5):
        annotations = open(f'{i}.txt').read().splitlines()
        annotations_list.append(annotations)

    speed_factor = 1.0
    shared_timestamp = Value('d', 0.0)  # Общая переменная для хранения метки времени
    mutex = QMutex()

    players = [VideoPlayer(socket, i, annotations_list[i], speed_factor, shared_timestamp, mutex) for i in range(4)]
    layout = QHBoxLayout()
    for player in players:
        layout.addWidget(player)

    main_widget = QWidget()
    main_widget.setLayout(layout)
    main_widget.show()

    app.exec_()


if __name__ == '__main__':
    main()
