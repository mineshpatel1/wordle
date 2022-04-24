import functools
import os
import random
from utils import log, multi_process, batch
from typing import Any, Optional, Union

MAX_GUESSES = 6
BASE_DIR = os.path.dirname(__file__)
WORD_LIST_DIR = os.path.join(BASE_DIR, 'word_lists')
WORD_LIST = os.path.join(WORD_LIST_DIR, 'uk.txt')
ANSWER_LIST = os.path.join(WORD_LIST_DIR, 'answers.txt')


class Hint:
    CORRECT = '🟩'
    MISPLACED = '🟨'
    WRONG = '⬛'


class Game:
    def __init__(
        self,
        answer: str,
        word_list: Optional[list[str]] = None,
    ):
        self.answer = answer.upper()
        self.word_list = word_list or load_words()
        self.guesses: list[str] = []
        self.hints: list[str] = []

    @property
    def is_over(self) -> bool:
        if len(self.guesses) >= MAX_GUESSES:
            return True
        return self.is_won

    @property
    def is_won(self) -> bool:
        if len(self.guesses) == 0:
            return False
        return all(c == Hint.CORRECT for c in self.last_hint)

    @property
    def last_hint(self) -> str:
        return self.hints[-1]

    @property
    def possible_words(self) -> list[str]:
        return filter_words_from_info(
            self.word_list,
            *get_info_from_hints(self.guesses, self.hints)
        )

    def make_guess(self, guess: str) -> Optional[str]:
        guess = guess.upper()

        if self.is_over:
            return None  # No more guesses remaining

        assert len(guess) == 5, "Word must be 5 letters long."
        assert guess in self.word_list, "Word must be a valid UK English word."
        hint = get_hint_from_guess(guess, self.answer)
        self.guesses.append(guess)
        self.hints.append(hint)
        return hint


def get_hint_from_guess(guess: str, answer: str) -> str:
    guess = guess.upper()
    answer = answer.upper()
    hint = ''
    for i, letter in enumerate(guess):
        if answer[i] == letter:
            hint += Hint.CORRECT  # Correct letter and position
        elif letter in answer:
            hint += Hint.MISPLACED  # Correct letter, wrong position
        else:
            hint += Hint.WRONG  # Incorrect letter

    def _count_letters(state: dict[str, int], l: str):
        state[l] = state.get(l, 0) + 1
        return state

    letter_count = functools.reduce(_count_letters, guess, {})
    repeated_letters = {k for k, v in letter_count.items() if v > 1}

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
            for i, letter in enumerate(hint):
                if letter == Hint.CORRECT and guess[i] == repeated_letter:
                    num_matched += 1

            # For remaining occurrences, ensure only the number of occurrences in the answer are indicated.
            for i, letter in enumerate(hint):
                if (
                    letter == Hint.MISPLACED and
                    guess[i] == repeated_letter
                ):
                    num_matched += 1
                    if num_matched > num_in_answer:
                        hint = hint[:i] + Hint.WRONG + hint[i + 1:]
    return hint


def get_info_from_hints(
    guesses: list[str],
    hints: list[str],
) -> tuple[dict[int, str], set[(str, int)], set[str], dict[str, int]]:
    """Aggregates the information from guesses and hints."""
    correct = {}
    wrong_position = set()
    not_in_word = set()
    max_occurrences = {}

    for i, hint in enumerate(hints):
        include, exclude = {}, {}
        for j, state in enumerate(hint):
            letter = guesses[i][j]
            include[letter] = include.get(letter, 0)
            match state:
                case Hint.CORRECT:
                    correct[j] = letter
                    include[letter] += 1
                case Hint.MISPLACED:
                    wrong_position.add((letter, j))
                    include[letter] += 1
                case Hint.WRONG:
                    not_in_word.add(letter)
                    exclude[letter] = True

        for letter in include:
            if include[letter] > 0 and letter in exclude:
                max_occurrences[letter] = include[letter]
    return correct, wrong_position, not_in_word, max_occurrences


def get_probability_map(
    guess: str,
    possible_words: list[str],
) -> dict[str, float]:
    """
    Returns:
        dict of guess pattern keys and probability of occurrence in the word list.
    """

    prob_map = {}
    # Loop over possible words
    for answer in possible_words:
        hint = get_hint_from_guess(guess, answer)   # Get the hint for the given guess on that answer
        prob_map[hint] = prob_map.get(hint, 0) + 1  # Count how many times that hint occurs across the set of words

    # Divide the frequency by the total for the probability of each hint occurring
    return {hint: num / len(possible_words) for hint, num in prob_map.items()}


def filter_words_from_info(
    word_list: list[str],
    correct: dict[int, str],
    wrong_position: set[(str, int)],
    not_in_word: set[str],
    max_occurrences: dict[str, int],
) -> list[str]:
    """Filters list down based on known information."""
    possible_words = []
    answer_has_letter = {c for c in correct.values()}.union({l for l, _ in wrong_position})
    for word in word_list:
        exceeded_max = False
        for letter in max_occurrences:
            if word.count(letter) > max_occurrences[letter]:
                exceeded_max = True

        if (
            all(word[pos] == letter for pos, letter in correct.items()) and
            all(letter in word for letter, _ in wrong_position) and
            all(word[pos] != letter for letter, pos in wrong_position) and
            (all(letter not in word for letter in not_in_word if
                 letter not in answer_has_letter) and not exceeded_max) and
            True
        ):
            possible_words.append(word)
    return possible_words


def _load_str(file_path: str) -> list[str]:
    word_list = []
    with open(file_path, 'r') as f:
        for line in f.readlines():
            word_list.append(line.strip().upper())
    return word_list


def load_words():
    return _load_str(WORD_LIST)


def load_answers():
    return _load_str(ANSWER_LIST)


def bot_play(word: str, word_list: Optional[list[str]] = None) -> int:
    game = Game(word, word_list)
    while not game.is_over:
        guess = random.choice(game.possible_words)
        game.make_guess(guess)
    if not game.is_won:
        return -1
    return len(game.guesses)


def test_bot():
    answers = load_answers()
    words = load_words()
    scores = multi_process(
        [(a, words) for a in answers],
        bot_play,
        num_processes=5,
    )

    total = 0
    failures = 0
    for score in scores:
        if score == -1:
            failures += 1
            continue
        total += score
    log.info(round(total / (len(answers) - failures), 2))
    log.info(f"Failures {failures}")


if __name__ == '__main__':

    all_words = load_answers()
    p_map = get_probability_map('table', all_words)
