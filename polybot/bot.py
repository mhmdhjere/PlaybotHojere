import telebot
from loguru import logger
import os
import time
from telebot.types import InputFile, BotCommand
from polybot.img_proc import Img


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
        self.telegram_bot_client.set_my_commands([
            BotCommand("segment", "Segment an image"),
            BotCommand("concat", "Concatenates two images"),
            BotCommand("salt_n_pepper", "Adds salt and pepper to the image"),
            BotCommand("rotate", "Rotates an image clockwise")
        ])

        self.handlers = {'/segment': self.handle_segment,
                         '/salt_n_pepper': self.handle_salt_n_pepper
                         }

        self.status_handlers = {"waiting_for_segmenting_photo": self.handle_segment_photo,
                                'waiting_for_salt_n_pepper_photo': self.handle_salt_n_pepper_photo
                                }

    def handle_message(self, msg):
        if self.is_current_msg_photo(msg):
            self.photo_handler(msg)

        elif self.is_current_msg_text(msg) and msg['text'] in self.handlers:
            self.handlers[msg['text']](msg)


    def photo_handler(self,msg):
        chat_id = msg['chat']['id']
        if chat_id not in self.user_state:
            self.send_text(chat_id, "Bro are you kidding?")

        else:
            self.status_handlers[self.user_state[chat_id]](msg)
            self.user_state[chat_id] = None


    def handle_segment(self,msg):
        chat_id = msg['chat']['id']
        self.user_state[chat_id] = 'waiting_for_segmenting_photo'
        self.send_text(chat_id, "Please send the image you want to segment.")

    def handle_salt_n_pepper(self, msg):
        chat_id = msg['chat']['id']
        self.user_state[chat_id] = 'waiting_for_salt_n_pepper_photo'
        self.send_text(chat_id, "Please send the image to add salt & pepper noise.")

    def handle_segment_photo(self, msg):
        self.process_image(msg, lambda img: img.segment())

    def handle_salt_n_pepper_photo(self, msg):
        self.process_image(msg, lambda img: img.salt_n_pepper())

    def process_image(self, msg, processing_fn):
        img_path = self.download_user_photo(msg)
        my_img = Img(img_path)
        processing_fn(my_img)
        new_img_path = my_img.save_img()
        self.send_photo(msg['chat']['id'], new_img_path)



