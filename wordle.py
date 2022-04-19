from __future__ import annotations

import re
import os
import json
import math
import random
import requests
import time
from random import randrange
from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebElement
from selenium.webdriver.chrome.webdriver import WebDriver
from enum import Enum
from utils import log, chunks, multi_process, batch
from typing import Dict, List, Optional, Set, Tuple, Union

GuessMap = Dict[str, float]
WordGuessMap = Dict[str, GuessMap]
GuessDb = Dict[str, WordGuessMap]
WordDb = Dict[str, Dict[str, float]]

WORD_SIZE = 5
NUM_GUESSES = 6
NUM_PROCESSES = 5
INITIAL_GUESSES = ["CRANE"]
BASE_DIR = os.path.dirname(__file__)
WORD_LIST_DIR = os.path.join(BASE_DIR, 'word_lists')
WORD_LIST = os.path.join(WORD_LIST_DIR, 'uk.txt')
ANSWER_LIST = os.path.join(WORD_LIST_DIR, 'answers.txt')
WORD_DB = os.path.join(WORD_LIST_DIR, 'uk_word_db.json')
SCORE_ANSWERS_DB = os.path.join(WORD_LIST_DIR, 'scores-answers.json')
SCORE_OVERALL_DB = os.path.join(WORD_LIST_DIR, 'scores-overall.json')


class WrongWordSize(ValueError):
    pass


class GuessState(Enum):
    WRONG = '🟥'
    POSITION = '🟨'
    CORRECT = '🟩'

    @staticmethod
    def from_basic(basic_id: str) -> GuessState:
        convert = {
            '.': GuessState.WRONG,
            'P': GuessState.POSITION,
            'C': GuessState.CORRECT,
        }
        return convert[basic_id]

    @staticmethod
    def from_web(web_id: str) -> GuessState:
        convert = {
            "absent": GuessState.WRONG,
            "present": GuessState.POSITION,
            "correct": GuessState.CORRECT,
        }
        return convert[web_id.lower()]


class Word:
    def __init__(
        self,
        word: str,
        entropy: float = 0,
        entropy_2: float = 0,
        ngram_prob: float = 0,
    ):
        self.word = word
        self.entropy = entropy
        self.entropy_2 = entropy_2
        self.ngram_prob = ngram_prob

    @property
    def word(self):
        return self._word.upper()

    @word.setter
    def word(self, word):
        self._word = word
        if len(word) != WORD_SIZE:
            raise WrongWordSize(f"Invalid word {word}: Only words of size {WORD_SIZE} allowed.")

    @property
    def has_unique_letters(self):
        return len(set(self.word)) == len(self.word)

    @property
    def letter_map(self) -> Dict[str, int]:
        out = {}
        for char in self.word:
            out[char] = out.get(char, 0)
            out[char] += 1
        return out

    @property
    def repeated_letters(self) -> List[str]:
        return [k for k, v in self.letter_map.items() if v > 1]

    @property
    def json(self) -> Dict[str, float]:
        out = {'H0': self.entropy}
        if self.entropy_2:
            out['H1'] = self.entropy_2
        if self.ngram_prob:
            out['p_n'] = self.ngram_prob
        return out

    def get_probability_map(
        self,
        possible_words: List[Word],
    ) -> Dict[str, float]:
        """
        Returns:
            dict of guess pattern keys and probability of occurrence in the word list.
        """

        prob_map = {}
        for answer in possible_words:
            guess_str = _guess_mask(self.word, answer.word)
            prob_map[guess_str] = prob_map.get(guess_str, 0)
            prob_map[guess_str] += 1

        return {guess: num / len(possible_words) for guess, num in prob_map.items()}

    def get_information_map(
        self,
        possible_words: List[Word],
    ) -> Dict[str, float]:
        """
        Returns:
            Dict of guess pattern keys and the information value for the first guess.
        """

        info_map = {}
        for answer in possible_words:
            guess_str = _guess_mask(self.word, answer.word)
            if guess_str not in info_map:
                game = Game(answer, word_list=possible_words)
                game.guess(self.word, skip_validation=True)
                try:
                    info_map[guess_str] = game.information_value
                except ValueError as err:
                    log.error(f"{self} {answer}")
                    raise err
        return info_map

    def __str__(self):
        return self.word

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        return self.word == other.word


class Letter:
    def __init__(
        self,
        letter: str,
        position: int,
        state: GuessState,
    ):
        assert len(letter) == 1, "Input guess and answer must be single letters."
        assert position < WORD_SIZE, f"Input position ({position}) must be less than {WORD_SIZE}"
        self.guess = letter.upper()
        self.position = position
        self.state = state

    def __eq__(self, other) -> bool:
        return self.guess == other.guess and self.position == other.position

    def __hash__(self) -> int:
        return hash(self.guess + str(self.position))

    def __str__(self) -> str:
        return self.guess.upper()

    def __repr__(self) -> str:
        return str(self)


class Guess(list):
    def __init__(self, *args, **kwargs):
        super(Guess, self).__init__(*args, **kwargs)

    @property
    def basic_str(self) -> str:
        return str(self)\
            .replace('🟥', '.') \
            .replace('🟨', 'P') \
            .replace('🟩', 'C')

    def __str__(self) -> str:
        return ''.join(letter.state.value for letter in self)


class Game:
    def __init__(
        self,
        answer: Union[str, Word],
        word_list: Optional[List[Word]] = None
    ):
        self.answer: Word = Word(answer) if isinstance(answer, str) else answer
        self.num_guesses: int = NUM_GUESSES
        self.turn: int = 0
        self.guesses: List[Guess] = []
        self.word_list: List[Word] = word_list or load_words()
        self._best_move: Optional[Word] = None

    @property
    def is_over(self) -> bool:
        if len(self.guesses) >= self.num_guesses:
            return True

        return self.is_won

    @property
    def is_won(self) -> bool:
        if len(self.guesses) == 0:
            return False
        return all(g.state == GuessState.CORRECT for g in self.last_guess)

    @property
    def score(self) -> int:
        return len(self.guesses)

    @property
    def last_guess(self) -> Guess:
        return self.guesses[-1]

    @property
    def possible_answers(self) -> List[Word]:
        return self.filter_words_from_info(*self.information)

    @property
    def information_value(self) -> float:
        """
        Returns:
            Information value, in bits, currently known in the game. Each bit
            represents a halving of the number of remaining possibilities.
        """
        return _get_information_value(len(self.possible_answers), len(self.word_list))

    @property
    def information(self) -> Tuple[Set[Letter], Set[Letter], Set[str], Dict[str, int]]:
        """
        Produces the summary of information from all the current guesses in the game.

        Returns:
            Tuple of correct letters, wrong position letters and letters not in the word.
        """

        return _get_information_from_guesses(self.guesses)

    def filter_words_from_info(
        self,
        correct: Set[Letter],
        wrong_position: Set[Letter],
        not_in_word: Set[str],
        max_occurrences: Optional[Dict[str, int]],
    ) -> List[Word]:
        return filter_words_from_info(
            correct,
            wrong_position,
            not_in_word,
            max_occurrences,
            self.word_list,
        )

    def guess(self, _guess: Union[str, Word], skip_validation: bool = False) -> bool:
        if self.is_over:
            return False  # No more guesses remaining

        try:
            guess = Word(str(_guess))
        except WrongWordSize:
            raise ValueError(f"{_guess} is not {WORD_SIZE} letters, please try again.")

        if guess not in self.word_list and not skip_validation:
            raise ValueError(f"{guess} is not in the available word list, please try again.")

        if not re.match(r'[a-zA-Z]+$', guess.word):
            raise ValueError(f"{guess} is not a valid word, please try again.")

        guess_states = Guess()
        guess_str = _guess_mask(guess.word, self.answer.word)

        for i, basic_guess in enumerate(guess_str):
            guess_states.append(
                Letter(
                    guess.word[i],
                    i,
                    GuessState.from_basic(basic_guess),
                )
            )

        self.guesses.append(guess_states)
        return True

    def __str__(self):
        out = '\n'
        for guess in self.guesses:
            out += ''.join(str(letter) for letter in guess)
            out += '\n'
            out += str(guess)
            out += '\n'
        return out


class WordleWebDriver:
    URL: str = "https://www.nytimes.com/games/wordle/index.html"
    GUESS_STATE = {
        "absent": GuessState.WRONG,
        "present": GuessState.POSITION,
        "correct": GuessState.CORRECT,
    }

    def __init__(self):
        opts = webdriver.ChromeOptions()
        opts.add_argument("--incognito")
        self.driver: WebDriver = webdriver.Chrome(options=opts)
        self.num_processes = NUM_PROCESSES
        self.guesses = []

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

    def get_guess(self, word: str) -> Optional[Guess]:
        get_word_tiles = f"""
        return document
            .querySelector('game-app').shadowRoot
            .querySelector('game-row[letters="{word}"]').shadowRoot
            .querySelectorAll('game-tile')
        """
        tiles = self.driver.execute_script(get_word_tiles)
        guess = Guess()
        for i, tile in enumerate(tiles):
            letter_str = tile.get_attribute('letter')
            state = tile.get_attribute('evaluation')

            # If empty, it means the word isn't allowed by NYT
            # Should prompt a retry in this case.
            if not state:
                return None

            letter = Letter(letter_str, i, GuessState.from_web(state))
            guess.append(letter)
        return guess

    def enter_word(self, word: str, delay: float = 0.3) -> bool:
        for letter in word:
            self.type_key(letter)
            time.sleep(delay)
        self.type_key("↵")
        guess = self.get_guess(word)
        if not guess:
            return False
        self.guesses.append(guess)

        return True

    def clear_word(self, word: str, delay: float = 0.3):
        for i in range(5):
            self.type_key("←")
            time.sleep(delay)

    def play(
        self,
        filter_answers: bool = True,
        initial_guesses: Optional[List[str]] = None,
    ):
        log.info('Initialising...')
        filter_answers = filter_answers
        possible_words = load_words(ANSWER_LIST) if filter_answers else load_words()
        all_words = load_words()
        total_num_words = len(possible_words)
        initial_guesses = initial_guesses or INITIAL_GUESSES
        self.open_site()
        time.sleep(2)

        for guess in initial_guesses:
            self.enter_word(guess.lower())
            time.sleep(2)

        while len(self.guesses) < NUM_GUESSES and not self.has_won():
            info = _get_information_from_guesses(self.guesses)
            possible_words = filter_words_from_info(*info, possible_words)  # noqa
            info_value = _get_information_value(len(possible_words), total_num_words)
            word = get_best_move(
                possible_words,
                all_words=all_words,
                explore=(2 <= len(self.guesses) <= 4 and info_value < 6),
                num_processes=self.num_processes,
                must_answer=len(self.guesses) == NUM_GUESSES - 1,  # Last Go
            )
            log.info(f"Best move: {word}")
            allowed = self.enter_word(str(word).lower())

            # Initiate retry
            if not allowed:
                time.sleep(1)
                if word in possible_words:
                    idx = possible_words.index(word)
                    del possible_words[idx]
                del all_words[all_words.index(word)]
                self.clear_word(str(word))
                time.sleep(1)
            else:
                time.sleep(3)

        log.info(f"Game Over: {'Won' if self.has_won() else 'Lost'}")
        time.sleep(3)
        self.driver.close()


def _get_information_value(num_possible: int, num_total: int) -> float:
    return -1 * math.log(num_possible / num_total)


def _get_information_from_guesses(
    guesses: List[Guess]
) -> Tuple[Set[Letter], Set[Letter], Set[str], Dict[str, int]]:
    correct = set()
    wrong_position = set()
    not_in_word = set()
    max_occurrences = {}

    # Aggregate guess information
    for guess in guesses:
        include, exclude = {}, {}
        for letter in guess:
            include[str(letter)] = include.get(str(letter), 0)
            if letter.state == GuessState.CORRECT:
                correct.add(letter)
                include[str(letter)] += 1
            elif letter.state == GuessState.POSITION:
                wrong_position.add(letter)
                include[str(letter)] += 1
            elif letter.state == GuessState.WRONG:
                not_in_word.add(letter.guess)
                exclude[str(letter)] = True

        for letter in include:
            if include[letter] > 0 and letter in exclude:
                max_occurrences[letter] = include[letter]
    return correct, wrong_position, not_in_word, max_occurrences


def _guess_mask(word: str, answer: str):
    """Fast implementation of guessing logic with basic types."""
    guess = ''
    l_count = {}
    for i, letter in enumerate(word):
        l_count[letter] = l_count.get(letter, 0)
        l_count[letter] += 1

        if answer[i] == letter:
            guess += 'C'
        elif letter in answer:
            guess += 'P'
        else:
            guess += '.'

    repeated_letters = {k for k, v in l_count.items() if v > 1}

    if repeated_letters:
        answer_l_count = {}
        for letter in answer:
            answer_l_count[letter] = answer_l_count.get(letter, 0)
            answer_l_count[letter] += 1

        for repeated_letter in repeated_letters:
            if repeated_letter not in answer:
                continue

            # Get the total occurrences of the letter in the answer
            num_in_answer = answer_l_count[repeated_letter]
            num_matched = 0

            # Count all the exact matches first
            for i, letter in enumerate(guess):
                if letter == 'C' and word[i] == repeated_letter:
                    num_matched += 1

            # For remaining occurrences, ensure only the number of occurrences in the answer are indicated.
            for i, letter in enumerate(guess):
                if (
                    letter == 'P' and
                    word[i] == repeated_letter
                ):
                    num_matched += 1
                    if num_matched > num_in_answer:
                        guess = guess[:i] + '.' + guess[i + 1:]
    return guess


def get_best_move(
    word_list: List[Word],
    num_processes: int = NUM_PROCESSES,
    explore: bool = False,
    must_answer: bool = False,
    all_words: Optional[List[Word]] = None,
) -> Word:
    if explore:
        all_words = all_words or load_words()
        e_map = compute_entropy(word_list, all_words)  # Use all available words
        best_words = sort_by_entropy(e_map)
    else:
        e_map = compute_entropy(word_list, num_processes=num_processes)
        best_words = sort_by_entropy(e_map)

        # When the answers are similar in quality, look for other words (that may not be an answer)
        # Use must_answer to a force a possible guess, e.g. on the last go
        unique_entropies = set(w.entropy for w in best_words[:5])
        if len(unique_entropies) < 3 < len(word_list) and not must_answer:
            all_words = all_words or load_words()
            e_map = compute_entropy(word_list, all_words)  # Use all available words
            best_words = sort_by_entropy(e_map)

    return best_words[0]


def filter_words_from_info(
    correct: Set[Letter],
    wrong_position: Set[Letter],
    not_in_word: Set[str],
    max_occurrences: Dict[str, int],
    word_list: Optional[List[Word]] = None,
) -> List[Word]:
    word_list = word_list or load_words()
    possible_words = []
    answer_has_letter = {str(c) for c in correct}.union({str(c) for c in wrong_position})
    for word in word_list:
        exceeded_max = False
        for letter in max_occurrences:
            if word.word.count(letter) > max_occurrences[letter]:
                exceeded_max = True
        if (
            all(c.guess == word.word[c.position] for c in correct) and
            all(p.guess in word.word for p in wrong_position) and
            all(p.guess != word.word[p.position] for p in wrong_position) and
            # For incorrect letters, need to make sure multiple occurrences are catered for
            all(n not in word.word for n in not_in_word if n not in answer_has_letter) and
            not exceeded_max
        ):
            possible_words.append(word)
    return possible_words


def load_words(file_path: str = WORD_LIST) -> List[Word]:
    word_list = []
    with open(file_path, 'r') as f:
        for line in f.readlines():
            word_list.append(Word(line.strip()))
    return word_list


def load_word_db(file_path: str = WORD_DB) -> Dict[str, Word]:
    with open(file_path, 'r') as f:
        word_db = json.load(f)
    return {
        w: Word(w, data.get('H0', 0), data.get('H1', 0), data.get('p_n', 0))
        for w, data in word_db.items()
    }


def save_word_db(
    word_db: Union[WordDb, List[Word]],
    file_path: str = WORD_DB,
):
    if isinstance(word_db, list):
        word_db = {w.word: w.json for w in word_db}

    with open(file_path, 'w') as f:
        json.dump(word_db, f, indent=4)


def sanitise_word_list(file_path: str = WORD_LIST):
    word_list = load_words(file_path)
    flat_words = [w.word for w in word_list]
    flat_words = sorted(flat_words)
    with open(file_path, 'w') as f:
        f.write('\n'.join(flat_words))


def play_game():
    word_list = load_words()
    game = Game(
        answer=word_list[randrange(len(word_list))],  # Pick a word at random
        word_list=word_list,
    )

    while not game.is_over:
        print(f'Guess {len(game.guesses) + 1}:')
        guess = input()
        if game.guess(guess):
            print(game)
    print()
    print(f"Answer: {game.answer}")


def merge_guess_maps(
    prob_map: WordGuessMap,
    info_map: WordGuessMap,
) -> GuessDb:
    db = {}
    for word in info_map:
        if word in prob_map:
            db[word] = {}
            for guess in info_map[word]:
                if guess in prob_map[word]:
                    db[word][guess] = {
                        "p": prob_map[word][guess],
                        "I": info_map[word][guess],
                    }
    return db


def calculate_entropy(
    pi_map: Dict[str, Dict[str, Dict[str, float]]],
) -> Dict[str, Dict[str, float]]:
    entropy_map = {}
    for word in pi_map:
        entropy = 0
        for guess, pi in pi_map[word].items():
            entropy += pi['p'] * pi['I']
        entropy_map[str(word)] = {
            'H': entropy,
        }
    return entropy_map


def compute_entropy(
    possible_words: List[Word],
    input_list: Optional[List[Word]] = None,
    verbose: bool = False,
    num_processes: int = 2,
) -> Dict[str, Dict[str, float]]:
    def _get_many_probabilities(
        _possible_words: List[Word],
        _input_words: Optional[List[Word]] = None,
        _verbose: bool = False,
        _num_processes: int = 2,
    ) -> WordGuessMap:
        _input_words = _input_words or _possible_words
        _input_list = [(w, _possible_words) for w in _input_words]
        return multi_process(
            _input_list,
            Word.get_probability_map,
            zip_with=lambda word, _word_list: str(word),
            verbose=_verbose,
            num_processes=_num_processes,
        )

    def _get_many_info_values(
        _possible_words: List[Word],
        _input_words: Optional[List[Word]] = None,
        _verbose: bool = False,
        _num_processes: int = 2,
    ) -> WordGuessMap:
        _input_words = _input_words or _possible_words
        _input_list = [(w, _possible_words) for w in _input_words]
        return multi_process(
            _input_list,
            Word.get_information_map,
            zip_with=lambda word, _word_list: str(word),
            verbose=_verbose,
            num_processes=_num_processes,
        )

    input_list = input_list or possible_words
    probs = _get_many_probabilities(possible_words, input_list, verbose, num_processes)
    info = _get_many_info_values(possible_words, input_list, verbose, num_processes)

    pi_map = merge_guess_maps(probs, info)
    return calculate_entropy(pi_map)


def sort_by_entropy(
    entropy_map: WordDb,
) -> List[Word]:
    word_list = [Word(w, data['H']) for w, data in entropy_map.items()]
    return sorted(word_list, key=lambda w: -w.entropy)


def crude_opening_pairs():
    all_words = load_word_db().values()
    exclusive = {}
    i, total = 0, len(all_words) ** 2
    for x in all_words:
        for y in all_words:
            i += 1
            progress = i / total
            print(
                f'\rProcessing: [{round(100 * progress)}%]',
                end="",
            )

            a = set(char for char in str(x))
            b = set(char for char in str(y))
            if len(a.intersection(b)) == 0:
                key = '|'.join(sorted([str(x), str(y)]))
                exclusive[key] = (key, x.entropy + y.entropy)
    print()
    exclusive = sorted(exclusive.values(), key=lambda item: -item[1])

    for w in exclusive[:100]:
        log.info(w)


def bot_play(
    word: Union[str, Word],
    initial_guesses: Optional[List[str]] = None,
    filter_answers: Optional[List[Word]] = None,
    verbose: bool = True,
    num_processes: int = 2,
) -> int:
    game = Game(word)
    initial_guesses = initial_guesses or INITIAL_GUESSES
    for guess in initial_guesses:
        game.guess(guess)

    while not game.is_over:
        if filter_answers:
            possible = [w for w in game.possible_answers if w in filter_answers]
        else:
            possible = game.possible_answers

        word = get_best_move(
            possible,
            num_processes=num_processes,
            explore=(2 <= len(game.guesses) <= 4 and game.information_value < 6),
            must_answer=len(game.guesses) == game.num_guesses - 1,  # Last Go
        )
        game.guess(word)

    if verbose:
        log.info(f'Guessing {word}...')
        log.info(game)
    return game.score if game.is_won else -1


def test_bot(
    initial_guesses: List[str],
    filter_answers: Optional[List[Word]],
    k: Optional[int] = None,
    verbose: bool = False,
    num_processes: int = 2,
):
    scores = []
    failed = []
    word_list = load_words(ANSWER_LIST)

    if k:
        word_list = random.choices(word_list, k=k)

    start = time.time()
    for i, word in enumerate(word_list):
        score = bot_play(
            word,
            initial_guesses=initial_guesses,
            verbose=verbose,
            num_processes=num_processes,
            filter_answers=filter_answers,
        )
        if not verbose:
            print(
                f'\rTesting bot: {i + 1}/{len(word_list)} [{round(100 * (i + 1) / len(word_list))}%]',
                end="",
            )
        if score == -1:
            failed.append(word)
        else:
            scores.append(score)

    print()
    if failed:
        log.newline()
        log.error("Failed to win the following games:")
        for failure in failed:
            log.error(f"    {failure}")
        log.error(
            f"Total failed: {len(failed)} ({round(100 * 1-(len(failed) / len(word_list)), 2)} success)"
        )
    log.newline()
    avg_score = round(sum(scores) / len(scores), 2)
    log.info(f"Time elapsed: {round(time.time() - start, 2)}s")
    log.info(f"Average score: {avg_score}")

    if not k:
        score_db = SCORE_ANSWERS_DB if filter_answers else SCORE_OVERALL_DB
        with open(score_db, 'r') as f:
            db = json.load(f)

        value = {
            ', '.join(initial_guesses): {
                "score": avg_score,
                "failed": [str(w) for w in failed],
            }
        }
        db.update(value)

        with open(score_db, 'w') as f:
            json.dump(db, f, indent=4)


def deep_probability_map(
    word: Word,
    possible_words: Optional[List[Word]] = None,
) -> Dict[str, float]:

    possible_words = possible_words or load_words()
    histogram = {}
    total = 0
    for i, answer in enumerate(possible_words):
        game = Game(answer)
        game.guess(word)
        first_guess = game.guesses[0].basic_str

        for second in game.possible_answers:
            if second != word:
                second_guess = _guess_mask(second.word, answer.word)
                key = f"{first_guess}|{second_guess}"
                histogram[key] = histogram.get(key, 0)
                histogram[key] += 1
                total += 1

    return {
        guess: num / total
        for guess, num in histogram.items()
    }


def deep_information_map(
    word: Word,
    possible_words: Optional[List[Word]] = None,
) -> Dict[str, float]:
    possible_words = possible_words or load_words()
    info_map = {}

    for i, answer in enumerate(possible_words):
        game = Game(answer)
        game.guess(word)
        first_guess = game.guesses[0].basic_str

        for second in game.possible_answers:
            if second != word:
                second_guess = _guess_mask(second.word, answer.word)
                key = f"{first_guess}|{second_guess}"

                if key not in info_map:
                    game.guess(second)
                    info_map[key] = game.information_value
    return info_map


def compute_deep_entropy(
    input_words: List[Word],
    possible_words: Optional[List[Word]] = None,
    num_processes: int = 2,
    verbose: bool = False,
) -> Dict[str, Dict[str, float]]:
    possible_words = possible_words or load_words()
    input_list = [(w, possible_words) for w in input_words]

    output = {}
    for key, function in [
        ('prob', deep_probability_map),
        ('info', deep_information_map),
    ]:
        output[key] = multi_process(
            input_list,
            function,
            zip_with=lambda word, _word_list: str(word),
            verbose=verbose,
            num_processes=num_processes,
        )

    pi_map = merge_guess_maps(output['prob'], output['info'])
    return calculate_entropy(pi_map)


def _two_guess_iv(word: Word, initial_guesses: List[Word]) -> float:
    game = Game(word)
    for guess in initial_guesses:
        game.guess(guess)
        if game.is_over:
            break
    return game.information_value


def compute_avg_iv(
    initial_guesses: List[str],
    num_processes: int = 2,
) -> float:
    all_words = load_words()
    output = multi_process(
        [(w, initial_guesses) for w in all_words],
        _two_guess_iv,
        num_processes=num_processes,
    )
    total_iv = sum(output)
    avg_iv = total_iv / len(all_words)
    log.info(f"Avg IV for {', '.join(initial_guesses)}: {round(avg_iv, 2)}")
    return avg_iv


def get_ngram_ratio(words: List[str]) -> Dict[str, float]:
    url = f'https://books.google.com/ngrams/json?content={",".join(words)}' \
          f'&year_start=1990&year_end=2019&corpus=26&smoothing=0'
    res = requests.get(url)
    out = {}
    for item in res.json():
        avg = sum(item['timeseries']) / len(item['timeseries'])
        out[item['ngram']] = avg
    return out


@batch
def batch_fetch_ngrams(words):
    ngram = get_ngram_ratio([str(w) for w in words])
    for w in words:
        w.ngram_prob = ngram[str(w)]
    return words


def main():
    driver = WordleWebDriver()
    driver.play()


if __name__ == '__main__':
    main()
