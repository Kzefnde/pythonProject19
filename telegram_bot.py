import os
import tempfile
import time

import cv2
import zmq
import telepot
from telepot.loop import MessageLoop
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton

send_video_to_bot = True


def send_video(chat_id, socket, video_index, bot=None):
    if send_video_to_bot:
        bot.sendMessage(chat_id, f"Sending video {video_index + 1} to bot...")
    else:
        print(f"Sending video {video_index + 1} to server...")

    video_paths = ['1.mp4', '2.mp4', '3.mp4', '4.mp4']
    selected_video_path = video_paths[video_index]

    cap = cv2.VideoCapture(selected_video_path)
    frame_rate = cap.get(cv2.CAP_PROP_FPS)

    try:
        temp_file, temp_file_path = tempfile.mkstemp(suffix='.mp4')
        temp_file = os.fdopen(temp_file, 'wb')

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_file_path, fourcc, frame_rate, (int(cap.get(3)), int(cap.get(4))))

        while cap.isOpened():
            ret, frame = cap.read()
            if ret:
                out.write(frame)
                time.sleep(1 / frame_rate)
            else:
                break

        out.release()
        temp_file.close()

        if send_video_to_bot:
            bot.sendVideo(chat_id, open(temp_file_path, 'rb'))
        else:
            with open(temp_file_path, 'rb') as video_file:
                socket.send_multipart([b"server", b"", video_file.read()])

    except Exception as e:
        print(f'Error: {e}')
    finally:
        cap.release()
        os.remove(temp_file_path)

def handle_message(msg, bot):
    content_type, chat_type, chat_id = telepot.glance(msg)
    if content_type == 'text':
        command = msg['text']
        if command == '/get_video':
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='Video 1', callback_data='0')],
                [InlineKeyboardButton(text='Video 2', callback_data='1')],
                [InlineKeyboardButton(text='Video 3', callback_data='2')],
                [InlineKeyboardButton(text='Video 4', callback_data='3')],
            ])

            if bot:
                bot.sendMessage(chat_id, 'Select a video:', reply_markup=keyboard)
        elif command.startswith('/video_'):
            video_index = int(command.split('_')[1])
            if 0 <= video_index < 4:
                if bot:
                    send_video(chat_id, None, video_index, bot)
                else:
                    context = zmq.Context()
                    socket = context.socket(zmq.DEALER)
                    socket.connect("tcp://localhost:8000")
                    send_video(chat_id, socket, video_index, bot)
                    socket.close()


def on_callback_query(msg):
    query_id, from_id, query_data = telepot.glance(msg, flavor='callback_query')
    video_index = int(query_data)
    bot = telepot.Bot('6850904035:AAH8R7vVlU_OV-rOUR5fbBwRmkf5gVtq06A')
    if 0 <= video_index < 4:
        if bot:  # Проверим, что объект bot определен
            send_video(from_id, None, video_index, bot)
        else:
            context = zmq.Context()
            socket = context.socket(zmq.DEALER)
            socket.connect("tcp://localhost:8000")
            send_video(from_id, socket, video_index, bot)
            socket.close()


def run_telegram_bot():
    context = zmq.Context()
    socket = context.socket(zmq.DEALER)
    socket.connect("tcp://localhost:8000")  # адрес и порт клиента

    bot = telepot.Bot('6850904035:AAH8R7vVlU_OV-rOUR5fbBwRmkf5gVtq06A')
    MessageLoop(bot, {'chat': lambda msg: handle_message(msg, bot), 'callback_query': on_callback_query}).run_as_thread()

    while True:
        time.sleep(10)

# Внесем изменения в условие __name__
if __name__ == '__main__':
    run_telegram_bot()