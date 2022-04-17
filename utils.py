import multiprocessing
import time
import types
import logging
import queue
import threading
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, Union

TAB = ' ' * 4


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


def _batch_wrap(
        function: Callable,
        input_list: List[Union[List[Any], Tuple[Any], Dict[str, Any]]],
        num_threads: int,
        zip_output: Optional[Callable],
        raise_exception: bool,
        class_ref: Optional[type] = None,
        track_progress: Optional[str] = None,
) -> Optional[Union[Dict[Any, Any], List[Any]]]:
    if len(input_list) == 0:  # Nothing to do
        return

    if num_threads > len(input_list):  # Don't need that many threads
        num_threads = len(input_list)

    def _print_progress(_output: Dict[int, Any]):
        # print('This is happening?', end="2")
        if track_progress:
            name = track_progress if isinstance(track_progress, str) else function.__name__
            print(
                f'{TAB}Processing: {name} '
                f'[{round(100 * (len(_output) / len(input_list)))}%]\r',
                end="",
            )
            print('')

    def _apply(_func: Callable, _item: Any):
        # If the argument is not iterable, put it in a tuple
        _item = _item if isinstance(_item, (list, tuple, dict)) else (_item,)

        if class_ref:  # Need to pass self as the first argument for methods
            if isinstance(_item, dict):
                return _func(class_ref, **_item)  # Kwargs
            else:
                return _func(class_ref, *_item)  # Args
        else:  # Pass args or kwargs
            if isinstance(_item, dict):
                return _func(**_item)  # Kwargs
            else:
                return _func(*_item)  # Args

    def _worker(_queue: queue.Queue, _output: Dict[int, Any]):
        while True:
            w_item, index = _queue.get()
            try:
                _output[index] = _apply(function, w_item)
            except Exception as err:
                log.error('Error: {}'.format(err))
                if raise_exception:
                    raise err
                _output[index] = None
            finally:
                _print_progress(_output)
                _queue.task_done()

    output = {}
    q = queue.Queue()

    for _i in range(num_threads):
        t = threading.Thread(target=_worker, args=(q, output))
        t.daemon = True
        t.start()

    _print_progress(output)

    for i, item in enumerate(input_list):
        q.put((item, i))

    q.join()  # Wait for all operations to complete

    output = [output[k] for k in sorted(output.keys())]  # Sort output by key

    if zip_output:
        output = dict(zip([_apply(zip_output, item) for item in input_list], output))
    return output


def batch(function: Callable):
    def batch_wrap(
            input_list: List[Union[List[Any], Tuple[Any], Dict[str, Any]]],
            num_threads: int = 25,
            zip_output: Optional[Callable] = None,
            raise_exception: bool = False,
            track_progress: Optional[str] = None,
    ):
        return _batch_wrap(
            function, input_list, num_threads, zip_output, raise_exception, None, track_progress,
        )

    return batch_wrap


def print_progress(
    name: str,
    progress: float,
):
    print(
        f'\rProcessing: {name} [{round(100 * progress)}%]',
        end="",
    )


def worker(
    worker_queue: multiprocessing.Queue,
    func: Callable,
    output: Dict[int, Any],
    num_jobs: int,
    verbose: bool = True,
):
    """
    Multiprocessing worker. Needs to be top level because it relies on being pickled.
    """
    while True:
        args, index = worker_queue.get(block=True)

        if index == -1:  # Signal for ending the process
            break

        try:
            output[index] = func(*args)
            if verbose:
                print_progress(func.__name__, len(output) / num_jobs)
        except Exception as err:
            log.error(str(err))
            raise err


def multi_process(
    input_list: List[Tuple[Any, ...]],
    func: Callable,
    num_processes: int = 2,
    zip_with: Optional[Callable] = None,
    verbose: bool = True,
) -> Union[List[Any], Dict[Any, Any]]:
    main_queue = multiprocessing.Queue()
    manager = multiprocessing.Manager()
    output = manager.dict()
    start = time.time()

    # Declare processes
    processes = []
    for i in range(num_processes):
        p = multiprocessing.Process(
            target=worker,
            args=(main_queue, func, output, len(input_list), verbose),
        )
        p.daemon = True
        p.start()
        processes.append(p)

    for i, input_args in enumerate(input_list):
        main_queue.put((input_args, i))

    # Send a kill signal for each process
    for i in range(num_processes):
        main_queue.put((None, -1))

    main_queue.close()
    main_queue.join_thread()

    if verbose:
        print_progress(func.__name__, 0)

    for p in processes:
        p.join()

    if verbose:
        print()
        log.info(f"Time elapsed: {round(time.time() - start, 2)}s")

    output = [output[k] for k in sorted(output.keys())]  # Sort output by key
    if zip_with:
        output = dict(zip(
            [zip_with(*x) for x in input_list],
            output,
        ))
    return output


def chunks(_list: List[Any], n: int) -> Generator[List[Any], None, None]:
    """Yield successive n-sized chunks from a list."""
    for i in range(0, len(_list), n):
        yield _list[i:i + n]


log = create_logger('Wordle')
