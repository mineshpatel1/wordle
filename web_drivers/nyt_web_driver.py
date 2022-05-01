import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.remote.shadowroot import ShadowRoot
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from typing import Callable, Optional

from wordle import (
    filter_words_from_info,
    get_info_from_hints,
    get_best_move,
    load_words,
    load_answers,
    Hint,
    INITIAL_GUESSES,
    MAX_GUESSES,
    NUM_PROCESSES,
)
from utils import log

DELAY = 0.2
TIMEOUT = 5
URL: str = "https://www.nytimes.com/games/wordle/index.html"
GUESS_STATE = {
    "absent": Hint.WRONG,
    "present": Hint.MISPLACED,
    "correct": Hint.CORRECT,
}


class NYTWebDriver:
    def __init__(self):
        opts = webdriver.ChromeOptions()
        opts.add_argument("--incognito")
        self.driver: WebDriver = webdriver.Chrome(options=opts)
        self.num_processes: int = NUM_PROCESSES
        self.guesses: list[str] = []
        self.hints: list[str] = []

    def remove_element_by_selector(self, css_selector: str, timeout: int = TIMEOUT):
        WebDriverWait(self.driver, timeout).until(
            expected_conditions.element_to_be_clickable((By.CSS_SELECTOR, css_selector))
        )
        script = f"document.querySelector('{css_selector}').remove()"
        self.driver.execute_script(script)

    def click(self, element: WebElement, timeout: int = TIMEOUT):
        WebDriverWait(self.driver, timeout).until(
            expected_conditions.element_to_be_clickable(element)
        )
        element.click()

    def open_site(self):
        self.driver.get(URL)
        self.driver.maximize_window()
        self.close_popups()
        time.sleep(1)

    def get_game_app(self) -> ShadowRoot:
        return self.driver.find_element(By.TAG_NAME, 'game-app').shadow_root

    def get_game_row(self, word: str) -> ShadowRoot:
        return self.get_game_app().find_element(
            By.CSS_SELECTOR, f'game-row[letters="{word.lower()}"]'
        ).shadow_root

    def get_game_tiles(self, word: str) -> list[WebElement]:
        row = self.get_game_row(word)
        return row.find_elements(By.TAG_NAME, 'game-tile')

    def close_popups(self):
        reject_cookies = self.driver.find_element(By.ID, 'pz-gdpr-btn-reject')
        self.click(reject_cookies)

        game_modal = self.get_game_app().find_element(By.TAG_NAME, 'game-modal')
        overlay = game_modal.shadow_root.find_element(By.CLASS_NAME, 'close-icon')
        self.click(overlay)
        self.remove_element_by_selector('.pz-snackbar')

    def type_key(self, letter: str):
        keyboard = self.get_game_app().find_element(By.TAG_NAME, 'game-keyboard').shadow_root
        key = keyboard.find_element(By.CSS_SELECTOR, f'button[data-key="{letter.lower()}"]')
        self.click(key)

    def has_won(self) -> bool:
        elements = self.get_game_app().find_elements(By.CSS_SELECTOR, 'game-row[win]')
        return len(elements) > 0

    def get_guess(self, word: str) -> tuple[Optional[str], Optional[str]]:
        tiles = self.get_game_tiles(word)
        guess = ""
        hint = ""
        for i, tile in enumerate(tiles):
            letter_str = tile.get_attribute('letter')
            state = tile.get_attribute('evaluation')

            # If empty, it means the word isn't allowed by NYT
            # Should prompt a retry in this case.
            if not state:
                return None, None

            guess += letter_str.upper()
            hint += GUESS_STATE[state]
        return guess, hint

    def enter_word(self, word: str, delay: float = DELAY) -> bool:
        for letter in word:
            self.type_key(letter)
            time.sleep(delay)
        self.type_key("↵")
        guess, hint = self.get_guess(word)
        if not guess:
            return False
        self.guesses.append(guess)
        self.hints.append(hint)
        return True

    def clear_word(self, delay: float = DELAY):
        for i in range(5):
            self.type_key("←")
            time.sleep(delay)

    def _gen_word_evaluated_check(self, word: str) -> Callable:
        """
        Returns a function for Selenium to wait for a word to return
        its evaluated hint.
        """
        def _check_evaluated(_driver):
            tiles = self.get_game_tiles(word)
            for tile in tiles:
                if tile.get_attribute('reveal') is None:
                    return False
                sub_tile = tile.shadow_root.find_element(By.CLASS_NAME, 'tile')
                animation = sub_tile.get_attribute('data-animation')
                if animation != 'idle':
                    return False
            return True
        return _check_evaluated

    def wait_for_word_evaluation(self, word: str):
        WebDriverWait(self.driver, 20).until(self._gen_word_evaluated_check(word))
        time.sleep(0.2)

    def play(
        self,
        initial_guesses: Optional[list[str]] = None,
    ):
        log.info('Initialising...')
        initial_guesses = initial_guesses or INITIAL_GUESSES
        answer_list = load_answers()
        all_words = load_words()
        self.open_site()

        for guess in initial_guesses:
            self.enter_word(guess.lower())
            self.wait_for_word_evaluation(guess)

        while len(self.guesses) < MAX_GUESSES and not self.has_won():
            info = get_info_from_hints(self.guesses, self.hints)
            possible_answers = filter_words_from_info(answer_list, *info)

            word = get_best_move(
                possible_answers,
                all_words,
                answer_list,
            )
            log.info(f"Best move: {word}")
            allowed = self.enter_word(str(word).lower())

            # Initiate retry if the word is not allowed
            if not allowed:
                time.sleep(1)
                if word in possible_answers:
                    idx = possible_answers.index(word)
                    del possible_answers[idx]
                if word in all_words:
                    del all_words[all_words.index(word)]
                self.clear_word()
                time.sleep(1)
            else:
                self.wait_for_word_evaluation(word)

        log.info(f"Game Over: {'Won' if self.has_won() else 'Lost'}")
        time.sleep(3)
        self.driver.close()
