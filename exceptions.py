class NotCriticalError(Exception):
    """Класс ошибки, о которой не нужно сообщать в Телеграм."""

    pass


class EndpointStatusError(Exception):
    """Класс для обработки ошибки cтатуса ответа сервера."""

    pass
