"""
This module defines several custom exception classes used in the project.

Classes:
- WrongResponseCode: raised when the API returns an unexpected response code.
- NotForSend: raised when an exception is not meant to be sent to Telegram.
- EmptyResponseFromAPI: a subclass of NotForSend, raised when the API returns
                        an empty response.
- TelegramError: a subclass of NotForSend, raised when an error occurs while
                 sending a message to Telegram.
"""


class WrongResponseCode(Exception):
    """Неверный ответ API."""


class NotForSend(Exception):
    """Исключение не для пересылки в telegram."""


class EmptyResponseFromAPI(NotForSend):
    """Пустой ответ API."""


class TelegramError(NotForSend):
    """Ошибка отправки сообщения в telegram."""
