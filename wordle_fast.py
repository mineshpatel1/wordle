import functools
import os
import math
import random
from utils import log, multi_process
from typing import Optional

MAX_GUESSES = 6
NUM_PROCESSES = 5
INITIAL_GUESSES = ['CRANE']
IV_THRESHOLD = 9.0
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

    @property
    def information_value(self) -> float:
        return -1 * math.log(len(self.possible_words) / len(self.word_list), 2)

    @property
    def score(self) -> int:
        if self.is_won:
            return len(self.guesses)
        else:
            return -1

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

    def __str__(self) -> str:
        str_rep = "\n"
        for i, guess in enumerate(self.guesses):
            str_rep += f"{guess}\n"
            str_rep += f"{self.hints[i]}\n"
        return str_rep


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
) -> tuple[dict[int, str], set[tuple[str, int]], set[str], dict[str, int]]:
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


def get_prob_and_iv(
    guess: str,
    possible_words: list[str],
) -> dict[str, dict[str, float]]:
    """
    Returns:
        dict of guess pattern keys and probability of occurrence in the word list.
    """

    freq_map = {}
    # Loop over possible words
    for answer in possible_words:
        hint = get_hint_from_guess(guess, answer)   # Get the hint for the given guess on that answer
        freq_map[hint] = freq_map.get(hint, 0) + 1  # Count how many times that hint occurs across the set of words

    iv_map = {}
    for hint, freq in freq_map.items():
        iv_map[hint] = {}
        # Divide the frequency by the total for the probability of each hint occurring
        iv_map[hint]['p'] = freq / len(possible_words)
        # Compute the information value based on the probability
        iv_map[hint]['I'] = get_information_value(iv_map[hint]['p'])
    return iv_map


def get_information_value(prob: float) -> float:
    """Returns the information value from a reduction in possibilities."""
    return math.log(1 / prob, 2)


def compute_entropy(
    guess: str,
    possible_words: list[str],
) -> float:
    """Sums probability x information value for possible words from the given guess."""
    iv_map = get_prob_and_iv(guess, possible_words)
    entropy = 0
    for item in iv_map.values():
        entropy += item['p'] * item['I']
    return entropy


def sort_by_entropy(entropy_map: dict[str, float]) -> list[str]:
    e_sorted = sorted([(word, H) for word, H in entropy_map.items()], key=lambda x: x[1], reverse=True)
    return [word for word, H in e_sorted]


def compute_many_entropies(
    guesses: list[str],
    possible_words: list[str],
) -> list[str]:
    e_map = {}
    for guess in guesses:
        e_map[guess] = compute_entropy(guess, possible_words)
    return sort_by_entropy(e_map)


def filter_words_from_info(
    word_list: list[str],
    correct: dict[int, str],
    wrong_position: set[tuple[str, int]],
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


def get_best_move(
    possible_answers: list[str],
    word_list: Optional[list[str]] = None,
    answer_list: Optional[list[str]] = None,
    iv_threshold: float = IV_THRESHOLD,
) -> str:
    word_list = word_list or load_words()
    answer_list = answer_list or load_answers()
    possible_answers = [w for w in possible_answers if w in answer_list]

    # If there's still a lot of uncertainty, don't pick a possible answer, just maximise entropy
    iv = get_information_value(len(possible_answers) / len(answer_list))
    if iv < iv_threshold:
        best_moves = compute_many_entropies(word_list, possible_answers)
    else:
        best_moves = compute_many_entropies(possible_answers, possible_answers)
    return best_moves[0]


def bot_play_random(
    word: str,
    word_list: Optional[list[str]] = None,
    filter_by_list: Optional[list[str]] = None,
):
    game = Game(word, word_list)
    while not game.is_over:
        possible_answers = game.possible_words
        if filter_by_list:
            possible_answers = [w for w in possible_answers if w in filter_by_list]

        guess = random.choice(possible_answers)
        game.make_guess(guess)
    return game.score


def bot_play(
    word: str,
    word_list: Optional[list[str]] = None,
    answer_list: Optional[list[str]] = None,
    verbose: bool = True,
    initial_guesses: list[str] = None,
) -> int:
    initial_guesses = initial_guesses or INITIAL_GUESSES
    word_list = word_list or load_words()
    answer_list = answer_list or load_answers()
    game = Game(word, word_list)

    for guess in initial_guesses:
        game.make_guess(guess)

    while not game.is_over:
        guess = get_best_move(game.possible_words, word_list, answer_list)
        game.make_guess(guess)  # Make a guess

    if verbose:
        log.info(str(game))

    return game.score


def test_bot_random():
    answers = load_answers()
    words = load_words()

    total = 0
    failures = 0
    scores = multi_process(
        [(w, words, answers) for w in answers],
        bot_play_random,
        num_processes=NUM_PROCESSES,
    )

    for score in scores:
        if score == -1:
            failures += 1
            continue
        total += score
    print('')
    log.info(f"Avg Score: {round(total / (len(answers) - failures), 2)}")
    log.info(f"Failures {failures}")


def test_bot():
    answers = load_answers()
    words = load_words()

    total = 0
    failures = 0

    scores = multi_process(
        [(w, words, answers, False) for w in answers],
        bot_play,
        num_processes=NUM_PROCESSES,
    )

    for score in scores:
        if score == -1:
            failures += 1
            continue
        total += score
    print('')
    log.info(f"Avg Score: {round(total / (len(answers) - failures), 2)}")
    log.info(f"Failures {failures}")


if __name__ == '__main__':
    test_bot()
