import zmq
import cv2
import pickle
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget, QSlider, QHBoxLayout
from PyQt5.QtCore import Qt, QThread, pyqtSignal

class VideoThread(QThread):
    frame_received = pyqtSignal(dict)

    def __init__(self, socket, annotations, speed_factor, parent=None):
        super(VideoThread, self).__init__(parent)
        self.socket = socket
        self.annotations = annotations
        self.speed_factor = speed_factor

    def run(self):
        while True:
            data_bytes = self.socket.recv()
            data = pickle.loads(data_bytes)
            self.frame_received.emit(data)
            self.msleep(int(1000 / self.speed_factor))

class VideoPlayer(QWidget):
    def __init__(self, socket, video_index, annotations, speed_factor, parent=None):
        super(VideoPlayer, self).__init__(parent)
        self.video_index = video_index
        self.annotations = annotations
        self.speed_factor = speed_factor
        self.setup_ui()

        self.video_thread = VideoThread(socket, self.annotations, self.speed_factor, self)
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


    def display_frame(self, data, annotation=None):
        frame = data["frame"]
        timestamp = data["timestamp"] * 1000  # Преобразование обратно в миллисекунды
        annotation_index = data["annotation_index"]

        # Найти ближайшую аннотацию
        while annotation_index < len(self.annotations) and timestamp > float(self.annotations[annotation_index]):
            annotation_index += 1

        # Синхронизация по временным меткам и обработка аннотаций
        if annotation_index < len(self.annotations):
            current_annotation = float(self.annotations[annotation_index])
            print(f"Video {self.video_index + 1}, Timestamp: {timestamp}, Current Annotation: {current_annotation}")


            if annotation == timestamp:
                print("Достигнута аннотация.")

            else:
                self.setStyleSheet("background-color: green;")

        # Отображение кадра
        self.label.setPixmap(self.frame_to_pixmap(frame))

    def thread_finished(self):
        print(f"Thread for Video {self.video_index + 1} finished.")

def main():
    app = QApplication([])
    socket = zmq.Context().socket(zmq.PULL)
    socket.connect("tcp://localhost:8000")

    annotations_list = []
    for i in range(1, 5):
        annotations = open(f'{i}.txt').read().splitlines()
        annotations_list.append(annotations)

    speed_factor = 1.0  # Фактор скорости по умолчанию

    players = [VideoPlayer(socket, i, annotations_list[i], speed_factor) for i in range(4)]
    layout = QHBoxLayout()
    for player in players:
        layout.addWidget(player)

    main_widget = QWidget()
    main_widget.setLayout(layout)
    main_widget.show()

    app.exec_()

if __name__ == '__main__':
    main()