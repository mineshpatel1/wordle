import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions

from multi_wordle import get_best_move_multi
from wordle import (
    filter_words_from_info,
    get_info_from_hints,
    load_words,
    load_answers,
    Hint,
    INITIAL_GUESSES,
    NUM_PROCESSES,
)
from utils import log

URL = "https://www.quordle.com/#/"
MAX_GUESSES = 9
DELAY = 0.2
TIMEOUT = 5


class QuordleWebDriver:
    def __init__(self):
        opts = webdriver.ChromeOptions()
        opts.add_argument("--incognito")
        self.driver: WebDriver = webdriver.Chrome(options=opts)
        self.num_processes: int = NUM_PROCESSES
        self.guesses: list[str] = []
        self.hints: list[list[str]] = [[] for _ in range(4)]
        self.boards_won = [False for _ in range(4)]

    @property
    def last_guess(self) -> str:
        return self.guesses[-1]

    @property
    def last_guess_index(self) -> int:
        return len(self.guesses) - 1

    def open_site(self):
        self.driver.get(URL)
        self.driver.maximize_window()
        time.sleep(1)

    def click(self, element: WebElement, timeout: int = TIMEOUT):
        WebDriverWait(self.driver, timeout).until(
            expected_conditions.element_to_be_clickable(element)
        )
        element.click()

    def get_keyboard(self) -> WebElement:
        return self.driver.find_element(By.CSS_SELECTOR, 'div[aria-label="Keyboard"]')

    def get_key(self, key: str) -> WebElement:
        return self.get_keyboard().find_element(By.CSS_SELECTOR, f'button[aria-label^="\'{key.upper()}\' key."]')

    def press_key(self, key: str):
        key = self.get_key(key)
        self.click(key)

    def get_game_board(self, index: int) -> WebElement:
        assert 0 <= index <= 3
        game_boards = self.driver.find_element(By.CSS_SELECTOR, 'div[aria-label="Game Boards"]')
        return game_boards.find_element(By.CSS_SELECTOR, f'div[aria-label="Game Board {index + 1}"]')

    def get_guess_row(self, board_num: int, guess_num: int) -> WebElement:
        game_board = self.get_game_board(board_num)
        return game_board.find_element(By.CSS_SELECTOR, f'div[aria-label*="Row {guess_num + 1}."]')

    def get_hint(self, board_num: int, guess_num: int):
        row = self.get_guess_row(board_num, guess_num)
        boxes = row.find_elements(By.CLASS_NAME, 'quordle-box')
        hint, guess = '', ''
        for box in boxes:
            class_prop = box.get_attribute('class')
            if 'bg-box-diff' in class_prop:
                hint += Hint.MISPLACED
            elif 'bg-box-correct' in class_prop:
                hint += Hint.CORRECT
            else:
                hint += Hint.WRONG

        self.hints[board_num].append(hint)

        if all(h == Hint.CORRECT for h in hint):
            self.boards_won[board_num] = True

    def press_enter_key(self):
        keyboard = self.get_keyboard()
        enter_key = keyboard.find_element(By.CSS_SELECTOR, 'button[aria-label="Enter Key"]')
        self.click(enter_key)

    def enter_word(self, word: str, delay: float = DELAY) -> bool:
        word = word.upper()
        for letter in word:
            self.press_key(letter)
            time.sleep(delay)
        self.press_enter_key()
        self.guesses.append(word)
        time.sleep(delay)
        return True

    def has_won(self) -> bool:
        banner = self.driver.find_elements(By.CSS_SELECTOR, 'div[aria-label="Game complete banner"]')
        return len(banner) > 0

    def play(self):
        log.info('Initialising...')
        initial_guesses = INITIAL_GUESSES
        answer_list = load_answers()
        all_words = load_words()
        self.open_site()

        for guess in initial_guesses:
            self.enter_word(guess)

        while len(self.guesses) < MAX_GUESSES and not self.has_won():
            possible_answer_list = []
            for board_num in range(4):
                self.get_hint(board_num, self.last_guess_index)
                info = get_info_from_hints(self.guesses, self.hints[board_num])
                possible_answers = filter_words_from_info(answer_list, *info)
                if not self.boards_won[board_num]:
                    possible_answer_list.append(possible_answers)

            best_move = get_best_move_multi(
                possible_answer_list,
                all_words,
                answer_list,
                parallelise=len(self.guesses) == 1,
            )
            self.enter_word(best_move)

        time.sleep(3)
        self.driver.close()

