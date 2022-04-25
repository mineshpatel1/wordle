import time
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
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


class NYTWebDriver:
    URL: str = "https://www.nytimes.com/games/wordle/index.html"
    GUESS_STATE = {
        "absent": Hint.WRONG,
        "present": Hint.MISPLACED,
        "correct": Hint.CORRECT,
    }

    def __init__(self):
        opts = webdriver.ChromeOptions()
        opts.add_argument("--incognito")
        self.driver: WebDriver = webdriver.Chrome(options=opts)
        self.num_processes: int = NUM_PROCESSES
        self.guesses: list[str] = []
        self.hints: list[str] = []

    def open_site(self):
        self.driver.get(self.URL)
        self.driver.maximize_window()
        self.close_popups()

    def close_popups(self):
        reject_cookies = self.driver.find_element_by_id('pz-gdpr-btn-reject')
        reject_cookies.click()

        close_modal = """
                document
                    .querySelector('game-app')
                    .shadowRoot.querySelector('game-modal')
                    .shadowRoot.querySelector('.overlay').click()
                """
        self.driver.execute_script(close_modal)

    def type_key(self, letter: str):
        hit_key = f"""
        return document
            .querySelector('game-app').shadowRoot
            .querySelector('#game game-keyboard').shadowRoot
            .querySelector('button[data-key="{letter}"]').click()
        """
        self.driver.execute_script(hit_key)

    def has_won(self) -> bool:
        has_won = """
        return document
            .querySelector('game-app').shadowRoot
            .querySelectorAll('game-row[win]')
        """
        elements = self.driver.execute_script(has_won)
        return len(elements) > 0

    def get_guess(self, word: str) -> tuple[Optional[str], Optional[str]]:
        get_word_tiles = f"""
        return document
            .querySelector('game-app').shadowRoot
            .querySelector('game-row[letters="{word}"]').shadowRoot
            .querySelectorAll('game-tile')
        """
        tiles = self.driver.execute_script(get_word_tiles)
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
            hint += self.GUESS_STATE[state]
        return guess, hint

    def enter_word(self, word: str, delay: float = 0.3) -> bool:
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

    def clear_word(self, delay: float = 0.3):
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
