import telebot
from loguru import logger
import os
import time
from telebot.types import InputFile, BotCommand
from img_proc import Img
import requests

class Bot:

    def __init__(self, token, telegram_chat_url):
        # create a new instance of the TeleBot class.
        # all communication with Telegram servers are done using self.telegram_bot_client
        self.telegram_bot_client = telebot.TeleBot(token)
        self.user_state = {}  # Dictionary to track what each user is doing
        # remove any existing webhooks configured in Telegram servers
        self.telegram_bot_client.remove_webhook()
        time.sleep(0.5)

        # set the webhook URL
        self.telegram_bot_client.set_webhook(url=f'{telegram_chat_url}/{token}/', timeout=60)


        logger.info(f'Telegram Bot information\n\n{self.telegram_bot_client.get_me()}')



    def send_text(self, chat_id, text):
        self.telegram_bot_client.send_message(chat_id, text)

    def send_text_with_quote(self, chat_id, text, quoted_msg_id):
        self.telegram_bot_client.send_message(chat_id, text, reply_to_message_id=quoted_msg_id)

    def is_current_msg_photo(self, msg):
        return 'photo' in msg

    def is_current_msg_text(self, msg):
        return 'text' in msg


    def download_user_photo(self, msg):
        """
        Downloads the photos that sent to the Bot to `photos` directory (should be existed)
        :return:
        """
        if not self.is_current_msg_photo(msg):
            raise RuntimeError(f'Message content of type \'photo\' expected')

        file_info = self.telegram_bot_client.get_file(msg['photo'][-1]['file_id'])
        data = self.telegram_bot_client.download_file(file_info.file_path)
        folder_name = file_info.file_path.split('/')[0]

        if not os.path.exists(folder_name):
            os.makedirs(folder_name)

        with open(file_info.file_path, 'wb') as photo:
            photo.write(data)

        return file_info.file_path

    def send_photo(self, chat_id, img_path):
        if not os.path.exists(img_path):
            raise RuntimeError("Image path doesn't exist")

        self.telegram_bot_client.send_photo(
            chat_id,
            InputFile(img_path)
        )

    def handle_message(self, msg):
        """Bot Main message handler"""
        logger.info(f'Incoming message: {msg}')
        self.send_text(msg['chat']['id'], f'Your original message: {msg["text"]}')


class QuoteBot(Bot):
    def handle_message(self, msg):
        logger.info(f'Incoming message: {msg}')

        if msg["text"] != 'Please don\'t quote me':
            self.send_text_with_quote(msg['chat']['id'], msg["text"], quoted_msg_id=msg["message_id"])


class ImageProcessingBot(Bot):
    def __init__(self, token, telegram_chat_url):
        super().__init__(token, telegram_chat_url)
        self.concat_first_image = {}  # Stores first image per user
        self.telegram_bot_client.set_my_commands([
            BotCommand("start", "Start the fun"),
            BotCommand("segment", "Segment an image"),
            BotCommand("concat", "Concatenates two images"),
            BotCommand("salt_n_pepper", "Adds salt and pepper to the image"),
            BotCommand("rotate", "Rotates an image clockwise"),
            BotCommand("contour", "Contours an image"),
            BotCommand("detect", "Detect objects with YOLO")

        ])

        self.handlers = {
            '/start': self.handle_start,
            '/segment': self.handle_segment,
            '/salt_n_pepper': self.handle_salt_n_pepper,
            '/rotate': self.handle_rotate,
            '/concat': self.handle_concat,
            '/contour': self.handle_contour,
            '/detect': self.handle_detect,

        }

        self.status_handlers = {"waiting_for_segmenting_photo": self.handle_segment_photo,
                                'waiting_for_salt_n_pepper_photo': self.handle_salt_n_pepper_photo,
                                'waiting_for_rotate_photo': self.handle_rotate_photo,
                                'waiting_for_contour_photo': self.handle_contour_photo,
                                'waiting_for_concat_photo_1': self.handle_concat_photo_1,
                                'waiting_for_concat_photo_2': self.handle_concat_photo_2,
                                'waiting_for_detection_photo': self.handle_detection_photo,
                                }

    def handle_message(self, msg):
        if self.is_current_msg_photo(msg):
            if 'caption' in msg and msg['caption'] in self.handlers:
                self.handlers[msg['caption']](msg)
            self.photo_handler(msg)
        elif self.is_current_msg_text(msg) and msg['text'] in self.handlers:
            self.handlers[msg['text']](msg)
        elif self.is_current_msg_text(msg) and self.user_state is not None:
            self.send_text(msg['chat']['id'], "Still waiting for you to send the right thing!")
        else:
            self.send_text(msg['chat']['id'], "Bro if you want me to be useful use a command!")



    def photo_handler(self,msg):
        chat_id = msg['chat']['id']
        if chat_id not in self.user_state or self.user_state[chat_id] is None:
            self.send_text(chat_id, "Bro are you kidding? you have to use a command first!")
        else:
            self.status_handlers[self.user_state[chat_id]](msg)
            if self.user_state[chat_id] != 'waiting_for_concat_photo_2':
                self.user_state[chat_id] = None

    def handle_detect(self, msg):
        chat_id = msg['chat']['id']
        self.user_state[chat_id] = 'waiting_for_detection_photo'
        self.send_text(chat_id, "Send an image to detect objects using YOLO.")


    def handle_start(self,msg):
        chat_id = msg['chat']['id']
        self.send_text(chat_id, "Send any any command from the list and let the fun begin!")

    def handle_segment(self,msg):
        chat_id = msg['chat']['id']
        self.user_state[chat_id] = 'waiting_for_segmenting_photo'
        self.send_text(chat_id, "Please send the image you want to segment.")

    def handle_salt_n_pepper(self, msg):
        chat_id = msg['chat']['id']
        self.user_state[chat_id] = 'waiting_for_salt_n_pepper_photo'
        self.send_text(chat_id, "Please send the image to add salt & pepper noise.")

    def handle_rotate(self, msg):
        chat_id = msg['chat']['id']
        self.user_state[chat_id] = 'waiting_for_rotate_photo'
        self.send_text(chat_id, "Please send the image to rotate.")

    def handle_concat(self, msg):
        chat_id = msg['chat']['id']
        self.user_state[chat_id] = 'waiting_for_concat_photo_1'
        self.send_text(chat_id, "Please send the first image to concatenate.")

    def handle_contour(self, msg):
        chat_id = msg['chat']['id']
        self.user_state[chat_id] = 'waiting_for_contour_photo'
        self.send_text(chat_id, "Please send the image to contour.")


    def handle_segment_photo(self, msg):
        self.process_image(msg, lambda img: img.segment())

    def handle_salt_n_pepper_photo(self, msg):
        self.process_image(msg, lambda img: img.salt_n_pepper())

    def handle_rotate_photo(self, msg):
        self.process_image(msg, lambda img: img.rotate())

    def handle_contour_photo(self, msg):
        self.process_image(msg, lambda img: img.contour())

    def handle_concat_photo_1(self, msg):
        chat_id = msg['chat']['id']
        try:
            img_path = self.download_user_photo(msg)
            self.concat_first_image[chat_id] = img_path
            self.user_state[chat_id] = 'waiting_for_concat_photo_2'
            self.send_text(chat_id, "Great. Now send the second image.")
        except Exception as e:
            self.send_text(msg['chat']['id'],
                           f"Something went wrong while processing the image. Please try again later.")


    def handle_concat_photo_2(self, msg):
        chat_id = msg['chat']['id']
        img1_path = self.concat_first_image.get(chat_id)
        if not img1_path:
            self.send_text(chat_id, "Oops! Something went wrong. Start over with /concat.")
            return

        img2_path = self.download_user_photo(msg)

        img1 = Img(img1_path)
        img2 = Img(img2_path)

        try:
            img1.concat(img2)
            new_img_path = img1.save_img()
            self.send_photo(chat_id, new_img_path)
        except ValueError as e:
            self.send_text(chat_id, f"Error: {e}")

        # Clean up state
        self.concat_first_image.pop(chat_id, None)
        self.user_state[chat_id] = None

    def handle_detection_photo(self, msg):
        chat_id = msg['chat']['id']
        try:
            image_path = self.download_user_photo(msg)
            result = self.send_to_yolo(image_path)

            labels = result.get("labels", [])
            count = result.get("detection_count", 0)
            prediction_image_url = result.get("predicted_image_url")

            caption = f"Detected {count} object(s): {', '.join(labels)}"
            if prediction_image_url:
                self.send_photo(chat_id, prediction_image_url)
            else:
                self.send_text(chat_id, caption)
        except Exception as e:
            self.send_text(chat_id, f"Error during detection: {e}")
        finally:
            self.user_state[chat_id] = None

    def send_to_yolo(self, image_path):
        yolo_url = "http://10.0.1.26:8080/predict"  # update to your IP or ngrok domain
        with open(image_path, "rb") as f:
            files = {"file": f}
            response = requests.post(yolo_url, files=files)
        return response.json()

    def process_image(self, msg, processing_fn):
        try:
            img_path = self.download_user_photo(msg)
            my_img = Img(img_path)
            processing_fn(my_img)
            new_img_path = my_img.save_img()
            self.send_photo(msg['chat']['id'], new_img_path)
        except Exception as e:
            self.send_text(msg['chat']['id'], f"Something went wrong while processing the image. Please try again later.")



