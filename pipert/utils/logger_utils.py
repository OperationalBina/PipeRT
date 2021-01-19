import logging
import os
from logging.handlers import SocketHandler, TimedRotatingFileHandler


def create_parent_logger(name):
    logger_type = os.environ.get('LOGGER', 'file').lower()
    return getattr(LoggerGenerator, f"_create_{logger_type}_logger")(name)


class LoggerGenerator:
    def __init__(self):
        pass

    @staticmethod
    def _create_cutelog_logger(name):
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        socket_handler = SocketHandler('127.0.0.1', 19996)
        socket_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
        logger.addHandler(socket_handler)
        return logger

    @staticmethod
    def _create_file_logger(name):
        class FileLogger(logging.Logger):
            def __init__(self, name, level=logging.NOTSET):
                super().__init__(name=name, level=level)

            def getChild(self, suffix: str) -> logging.Logger:
                return self.create_file_logger('-'.join((self.name, suffix)))

            @staticmethod
            def create_file_logger(name):
                logger = FileLogger(name)
                logger.setLevel(logging.DEBUG)
                logger.propagate = False
                log_file = os.environ.get("LOGS_FOLDER_PATH",
                                          "pipert/utils/log_files") + "/" + name + ".log"
                file_handler = TimedRotatingFileHandler(log_file, when='midnight')
                file_handler.setFormatter(logging.Formatter(
                    "%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
                logger.addHandler(file_handler)
                return logger

        return FileLogger.create_file_logger(name)
