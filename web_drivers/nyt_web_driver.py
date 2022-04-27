import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.remote.shadowroot import ShadowRoot
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from typing import Optional

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

    def click(self, element: WebElement, timeout: int = TIMEOUT):
        WebDriverWait(self.driver, timeout).until(
            expected_conditions.element_to_be_clickable(element)
        )
        element.click()

    def open_site(self):
        self.driver.get(URL)
        self.driver.maximize_window()
        self.close_popups()

    def get_game_app(self) -> ShadowRoot:
        return self.driver.find_element(By.TAG_NAME, 'game-app').shadow_root

    def close_popups(self):
        reject_cookies = self.driver.find_element(By.ID, 'pz-gdpr-btn-reject')
        self.click(reject_cookies)

        game_modal = self.get_game_app().find_element(By.TAG_NAME, 'game-modal')
        overlay = game_modal.shadow_root.find_element(By.CLASS_NAME, 'close-icon')
        self.click(overlay)

    def type_key(self, letter: str):
        keyboard = self.get_game_app().find_element(By.TAG_NAME, 'game-keyboard').shadow_root
        key = keyboard.find_element(By.CSS_SELECTOR, f'button[data-key="{letter.lower()}"]')
        self.click(key)

    def has_won(self) -> bool:
        elements = self.get_game_app().find_elements(By.CSS_SELECTOR, 'game-row[win]')
        return len(elements) > 0

    def get_guess(self, word: str) -> tuple[Optional[str], Optional[str]]:
        row = self.get_game_app().find_element(By.CSS_SELECTOR, f'game-row[letters="{word.lower()}"]').shadow_root
        tiles = row.find_elements(By.TAG_NAME, 'game-tile')
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

    def play(
        self,
        initial_guesses: Optional[list[str]] = None,
    ):
        log.info('Initialising...')
        initial_guesses = initial_guesses or INITIAL_GUESSES
        answer_list = load_answers()
        all_words = load_words()
        self.open_site()
        time.sleep(2)

        for guess in initial_guesses:
            self.enter_word(guess.lower())
            time.sleep(2)

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

            # Initiate retry
            if not allowed:
                time.sleep(1)
                if word in possible_answers:
                    idx = possible_answers.index(word)
                    del possible_answers[idx]
                del all_words[all_words.index(word)]
                self.clear_word()
                time.sleep(1)
            else:
                time.sleep(3)

        log.info(f"Game Over: {'Won' if self.has_won() else 'Lost'}")
        time.sleep(3)
        self.driver.close()
