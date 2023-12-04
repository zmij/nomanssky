import logging


class Loggable:
    def __init__(self, logger: logging.Logger = None) -> None:
        self.set_logger(logger or logging.getLogger(self.__class__.__name__))

    def set_logger(self, logger: logging.Logger) -> None:
        self._logger = logger
        self.log_debug = self._logger.debug
        self.log_info = self._logger.info
        self.log_warning = self._logger.warning
        self.log_error = self._logger.error

    def log_none(self, *args) -> None:
        ...

    @classmethod
    def get_class_logger(cls) -> logging.Logger:
        logging.getLogger(cls.__name__)
