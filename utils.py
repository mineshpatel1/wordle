import types
import logging
from typing import Optional


class ShellColor(object):
    """
    Usage: print(ShellColor.RED + '...' + ShellColor.RESET)
    See the colors at https://en.wikipedia.org/wiki/ANSI_escape_code#3.2F4_bit
    """
    RESET = '\033[0m'
    UNDERLINE = '\033[4m'
    BOLD = '\033[1m'
    FRAMED = '\033[51m'

    BLACK = '\033[30m'  # Black
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    BRIGHT_GRAY = '\033[37m'  # Dark White

    DARK_GRAY = '\033[1;30m'  # Bright Black
    BRIGHT_RED = '\033[1;31m'
    BRIGHT_GREEN = '\033[1;32m'
    BRIGHT_YELLOW = '\033[1;33m'
    BRIGHT_BLUE = '\033[1;34m'
    BRIGHT_MAGENTA = '\033[1;35m'
    BRIGHT_CYAN = '\033[1;36m'
    WHITE = '\033[1;37m'  # Bright White

    BACKGROUND_BLACK = '\033[40m'  # Black
    BACKGROUND_RED = '\033[41m'
    BACKGROUND_GREEN = '\033[42m'
    BACKGROUND_YELLOW = '\033[43m'
    BACKGROUND_BLUE = '\033[44m'
    BACKGROUND_MAGENTA = '\033[45m'
    BACKGROUND_CYAN = '\033[46m'
    BACKGROUND_BRIGHT_GRAY = '\033[47m'  # Dark White

    BACKGROUND_DARK_GRAY = '\033[100m'  # Bright Black
    BACKGROUND_BRIGHT_RED = '\033[101m'
    BACKGROUND_BRIGHT_GREEN = '\033[102m'
    BACKGROUND_BRIGHT_YELLOW = '\033[103m'
    BACKGROUND_BRIGHT_BLUE = '\033[104m'
    BACKGROUND_BRIGHT_MAGENTA = '\033[105m'
    BACKGROUND_BRIGHT_CYAN = '\033[106m'
    BACKGROUND_WHITE = '\033[107m'  # Bright White


def create_logger(name: str, log_file: Optional[str] = None):
    class ColouredFormatter(logging.Formatter):
        def __init__(self, msg, datefmt='%Y-%m-%d %H:%M:%S'):
            logging.Formatter.__init__(self, msg)
            self.datefmt = datefmt
            self.colours = {
                'DEBUG': ShellColor.FRAMED,
                'INFO': ShellColor.BRIGHT_GRAY,
                'WARNING': ShellColor.YELLOW,
                'CRITICAL': ShellColor.RED,
                'ERROR': ShellColor.RED,
            }

        def format(self, record):
            levelname = record.levelname
            if levelname in self.colours:
                levelname_color = self.colours[levelname] + levelname + ShellColor.RESET
                record.levelname = levelname_color
            return logging.Formatter.format(self, record)

    class FileFormatter(logging.Formatter):
        def __init__(self, msg, datefmt='%Y-%m-%d %H:%M:%S'):
            logging.Formatter.__init__(self, msg)
            self.datefmt = datefmt

        def format(self, record):
            return logging.Formatter.format(self, record)

    def log_newline(self, lines=1):
        # Switch handler, output a blank line
        if hasattr(self, 'file_handler'):
            self.removeHandler(self.file_handler)
            self.addHandler(self.blank_file_handler)

        self.removeHandler(self.console_handler)
        self.addHandler(self.blank_handler)

        for _ in range(lines):
            self.info('')

        # Switch back
        if hasattr(self, 'file_handler'):
            self.removeHandler(self.blank_file_handler)
            self.addHandler(self.file_handler)

        self.removeHandler(self.blank_handler)
        self.addHandler(self.console_handler)

    logger = logging.getLogger(name)
    if len(logger.handlers) == 0:
        logger.setLevel(logging.INFO)
        _format = '%(levelname)-17s [%(asctime)s]    %(message)s'
        _datefmt = '%Y-%m-%d %H:%M:%S'

        # Need to declare file handler before colour formatter
        if log_file is not None:
            file_handler = logging.FileHandler(log_file)
            file_format = FileFormatter(_format, _datefmt)
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)
            logger.file_handler = file_handler

            blank_file_handler = logging.FileHandler(log_file)
            blank_file_handler.setLevel(logging.DEBUG)
            blank_file_handler.setFormatter(logging.Formatter(fmt=''))
            logger.blank_file_handler = blank_file_handler

        console_handler = logging.StreamHandler()
        colour_formatter = ColouredFormatter(_format, _datefmt)
        console_handler.setFormatter(colour_formatter)
        logger.addHandler(console_handler)
        logger.console_handler = console_handler

        blank_handler = logging.StreamHandler()
        blank_handler.setLevel(logging.DEBUG)
        blank_handler.setFormatter(logging.Formatter(fmt=''))
        logger.blank_handler = blank_handler

        logger.newline = types.MethodType(log_newline, logger)

    return logger


log = create_logger('Wordle')
