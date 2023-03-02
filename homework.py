"""
This module defines functions and classes for logging in Python.

It provides a flexible logging infrastructure that allows you to customize
the log message format, the destination for log messages, and the level of
messages that are logged.
"""
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (EmptyResponseFromAPI,
                        NotForSend,
                        TelegramError,
                        WrongResponseCode)

load_dotenv()

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


def check_tokens() -> bool:
    """
    Check if all necessary tokens are present.

    This function checks if all necessary tokens, including PRACTICUM_TOKEN,
    TELEGRAM_TOKEN and TELEGRAM_CHAT_ID, are present in the environment or
    configuration file.

    Returns:
        bool: True if all tokens are present, False otherwise.
    """
    logging.info('Проверка наличия всех токенов.')
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def get_api_answer(current_timestamp: int) -> dict:
    """
    Get API answer for a given timestamp.

    Args:
        current_timestamp (int, optional): Timestamp to use for the request.
        Defaults to the current timestamp if not provided.

    Raises:
        WrongResponseCode: If the response status code is not 200, or an
        exception occurs during the request or response handling.
        The exception message contains details about the error.

    Returns:
        dict: A dictionary containing the JSON data returned by the API
        endpoint.
    """
    timestamp = current_timestamp or int(time.time())

    params_request = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp},
    }

    message = ('Начало запроса к API. '
               'Запрос: {url}, {headers}, {params}.'
               ).format(**params_request)

    logging.info(message)

    try:
        response = requests.get(**params_request)
        if response.status_code != HTTPStatus.OK:
            message = ('API не возвращает 200. '
                       f'Код ответа {response.status_code}. '
                       'Запрос: {url}, {headers}, {params}.'
                       ).format(**params_request)
            raise WrongResponseCode(message)
        return response.json()
    except requests.exceptions.RequestException as error:
        message = ('Произошла ошибка при запросе к API. '
                   'API не возвращает 200. '
                   'Запрос: {url}, {headers}, {params}.'
                   ).format(**params_request)
        logging.exception(message, error)
        raise WrongResponseCode(message, error)


def check_response(response: dict) -> list:
    """
    Check the API response for correctness.

    Args:
        response (dict): A dictionary containing the API response.

    Raises:
        TypeError: If the input response is not a dictionary.
        EmptyResponseFromAPI: If the 'homeworks' or 'current_date' keys are
        missing in the response.
        KeyError: If the 'homeworks' key is not a list.

    Returns:
        list: A list of homeworks obtained from the response.
    """
    logging.info('Проверка ответа API на корректность.')

    if not isinstance(response, dict):
        raise TypeError('Ответ API не является dict.')

    if 'homeworks' not in response or 'current_date' not in response:
        raise EmptyResponseFromAPI('Отсутствует один из ключей, homeworks или '
                                   'current_date, в ответе API.')

    homeworks = response.get('homeworks')

    if not isinstance(homeworks, list):
        raise TypeError('homeworks не является list.')

    return homeworks


def parse_status(homework):
    """
    Extract and check homework status from API response.

    Args:
        homework (dict): A dictionary containing information about a homework.

    Raises:
        KeyError: If the 'homework_name' key is not present in the homework
                  dictionary.
        ValueError: If the status of the homework is not recognized.

    Returns:
        str: A string containing the status of the homework and its name.
    """
    logging.info('Проводим проверки и извлекаем статус работы.')

    if 'homework_name' not in homework:
        raise KeyError('Нет ключа homework_name в ответе API.')

    homework_name = homework.get('homework_name')

    homework_status = homework.get('status')

    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус работы - {homework_status}.')

    return ('Изменился статус проверки работы "{homework_name}". {verdict}'
            ).format(homework_name=homework_name,
                     verdict=HOMEWORK_VERDICTS[homework_status]
                     )


def send_message(bot: telegram.bot.Bot, message: str) -> None:
    """
    Send a message to a specified Telegram chat using a Telegram bot.

    Args:
        bot (telegram.bot.Bot): A Telegram bot instance.
        message (str): The message to be sent to the Telegram chat.

    Raises:
        TelegramError: If there was an error sending the message to the
        Telegram chat.

    Returns:
        None
    """
    try:
        logging.debug('Начало отправки статуса в telegram.')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError as error:
        logging.error('Ошибка отправки статуса в telegram.')
        raise TelegramError(f'Ошибка отправки статуса в telegram: {error}.')
    else:
        logging.info('Статус отправлен в telegram.')


def main():
    """
    Run main logic of the bot.

    The function checks if the TELEGRAM_TOKEN is present. If the token is
    missing, it logs a critical error message and exits the program.
    It creates a telegram.Bot object using the TELEGRAM_TOKEN and sends a start
    message.
    The function then enters an infinite loop where it periodically checks an
    API for new homeworks. If there are new homeworks, it sends a message to
    the user via the bot with the details of the homework. If there are no new
    homeworks, it logs an info message. If there is an exception raised, it
    logs an error message and sends a message to the user via the bot with the
    exception details.

    Args:
        None

    Returns:
        None
    """
    if not check_tokens():
        message = 'Отсутствует токен. Бот остановлен!'
        logging.critical(message)
        sys.exit(message)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    current_timestamp = int(time.time())

    start_message = 'Бот начал работу.'

    send_message(bot, start_message)

    logging.info(start_message)

    prev_msg = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get(
                'current_date', int(time.time())
            )
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
            else:
                message = 'Нет новых статусов'
            if message != prev_msg:
                send_message(bot, message)
                prev_msg = message
            else:
                logging.info(message)
        except NotForSend as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message, exc_info=True)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message, exc_info=True)
            if message != prev_msg:
                send_message(bot, message)
                prev_msg = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    # logging setup
    logging.basicConfig(
        level=logging.INFO,  # set logging level
        handlers=[  # add handlers for logging
            logging.FileHandler(
                # add a handler to write to a file
                os.path.abspath('main.log'), mode='a', encoding='UTF-8'),
            # add a handler for output to the console
            logging.StreamHandler(stream=sys.stdout)
        ],
        # set the log message format
        format=(
            '%(asctime)s, '
            '%(levelname)s, '
            '%(name)s, '
            '%(funcName)s, '
            '%(lineno)s, '
            '%(message)s'
        )
    )
    main()  # start the main function of the application
