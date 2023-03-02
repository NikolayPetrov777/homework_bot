import json
import logging
import os
import sys
import time
from logging import Formatter, StreamHandler

import requests
import telegram
from dotenv import load_dotenv
from requests.exceptions import RequestException

from exceptions import EndpointStatusError, NotCriticalError

load_dotenv()


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
formatter = Formatter('%(asctime)s, %(levelname)s, %(message)s')
handler.setFormatter(formatter)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True


def send_message(bot, message):
    """Отправляет информационные сообщения в Telegram."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f'Бот отправил сообщение: {message}')
        return True
    except telegram.error.TelegramError as error:
        message = f'Не удалось отправить сообщение - {error}'
        logger.error(message)
        return False


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except RequestException as error:
        raise EndpointStatusError(error)
    if response.status_code != 200:
        raise EndpointStatusError('Ошибка в коде ответа')
    try:
        return response.json()
    except json.JSONDecodeError:
        message = 'Сервер вернул невалидный ответ'
        logger.error(message)
        raise EndpointStatusError('Ошибка в коде ответа')


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Неверный тип данных API')
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ homeworks')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Неверный тип данных домашки')
    if 'current_date' not in response:
        message = 'Отсутствует ключ current_date'
        logger.error(message)
        raise KeyError('Отсутствует ключ current_date')
    return response['homeworks'][0]


def parse_status(homework):
    """Извлекает статус проверки домашнего задания."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует необходимый ключ homework_name')
    if 'status' not in homework:
        raise KeyError('Отсутствует необходимый ключ status')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError('Отсутствует вердикт для данного статуса')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}": {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствует обязательная переменная окружения')
        sys.exit('Отсутствует одна или несколько обязательных переменных')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    error_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            timestamp = response.get('current_date', timestamp)
            if not homework:
                raise NotCriticalError('Статус домашней работы не обновлен')
            else:
                status = parse_status(homework)
                send_message(bot, status)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message not in error_message:
                send_message(bot, message)
                if send_message(bot, message) is True:
                    error_message = message
                    logger.error(error_message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
