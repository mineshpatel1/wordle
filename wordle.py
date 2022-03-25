import re
import os
from random import randrange
from enum import Enum
from utils import log
from typing import Optional, Union


WORD_SIZE = 5
NUM_GUESSES = 6
BASE_DIR = os.path.dirname(__file__)
WORD_LIST = os.path.join(BASE_DIR, 'word_list_uk.txt')
ANSWER_LIST = os.path.join(BASE_DIR, )


class WrongWordSize(ValueError):
    pass


class GuessState(Enum):
    WRONG = '⬛'
    POSITION = '🟨'
    CORRECT = '🟩'


class Word:
    def __init__(self, word: str):
        self.word: str = word

    @property
    def word(self):
        return self._word.upper()

    @word.setter
    def word(self, word):
        self._word = word
        if len(word) != WORD_SIZE:
            raise WrongWordSize(f"Only words of size {WORD_SIZE} allowed.")

    @property
    def has_unique_letters(self):
        return len(set(self.word)) == len(self.word)

    @property
    def letter_map(self) -> dict[str, int]:
        out = {}
        for char in self.word:
            out[char] = out.get(char, 0)
            out[char] += 1
        return out

    @property
    def repeated_letters(self) -> list[str]:
        return [k for k, v in self.letter_map.items() if v > 1]

    def __str__(self):
        return self.word

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        return self.word == other.word


class Letter:
    def __init__(
        self,
        guess: str,
        position: int,
        answer: Optional[Word] = None,
        override: Optional[GuessState] = None,
    ):
        assert len(guess) == 1, "guess and answer must be single letters."
        self.guess = guess.upper()
        self.position = position
        self.answer = answer
        self.override = override

    @property
    def state(self) -> GuessState:
        if self.override:
            return self.override

        if self.guess == self.answer.word[self.position]:
            return GuessState.CORRECT
        elif self.guess in self.answer.word:
            return GuessState.POSITION
        else:
            return GuessState.WRONG

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

    def __str__(self) -> str:
        return ''.join(letter.state.value for letter in self)


class Game:
    def __init__(
        self,
        answer: Union[str, Word],
        word_list: Optional[list[Word]] = None
    ):
        self.answer: Word = Word(answer) if isinstance(answer, str) else answer
        self.num_guesses: int = NUM_GUESSES
        self.turn: int = 0
        self.guesses: list[Guess] = []
        self.word_list: list[Word] = word_list or load_words()

    @property
    def is_over(self) -> bool:
        if len(self.guesses) >= self.num_guesses:
            return True

        if len(self.guesses) == 0:
            return False

        guess_states = self.guesses[-1]
        return all(g.state == GuessState.CORRECT for g in guess_states)

    @property
    def score(self) -> int:
        return len(self.guesses)

    @property
    def last_guess(self) -> Guess:
        return self.guesses[-1]

    @property
    def possible_answers(self) -> list[Word]:
        return self.filter_words_from_info(*self.information)

    @property
    def information_value(self) -> float:
        return 1 / len(self.possible_answers)

    @property
    def information(self) -> tuple[set[Letter], set[Letter], set[str]]:
        """
        Produces the summary of information from all the current guesses in the game.

        Returns:
            Tuple of correct letters, wrong position letters and letters not in the word.
        """
        correct = set()
        wrong_position = set()
        not_in_word = set()

        # Aggregate guess information
        for guess in self.guesses:
            for letter in guess:
                match letter.state:
                    case GuessState.CORRECT:
                        correct.add(letter)
                    case GuessState.POSITION:
                        wrong_position.add(letter)
                    case GuessState.WRONG:
                        not_in_word.add(letter.guess)
        return correct, wrong_position, not_in_word

    def filter_words_from_info(
        self,
        correct:
        set[Letter],
        wrong_position: set[Letter],
        not_in_word: set[str],
    ) -> list[Word]:
        possible_words = []
        for word in self.word_list:
            if (
                    all(c.guess == word.word[c.position] for c in correct) and
                    all(p.guess in word.word for p in wrong_position) and
                    all(p.guess != word.word[p.position] for p in wrong_position) and
                    all(n not in word.word for n in not_in_word)
            ):
                possible_words.append(word)
        return possible_words

    def guess(self, _guess: str) -> bool:
        if self.is_over:
            return False  # No more guesses remaining

        try:
            guess = Word(_guess)
        except WrongWordSize:
            log.warning(f"{_guess} is not {WORD_SIZE} letters, please try again.")
            return False  # Not a valid word, guess again

        if guess not in self.word_list or not re.match(r'[a-zA-Z]+$', guess.word):
            log.warning(f"{guess} is not a valid word, please try again.")
            return False  # Not a valid word, guess again

        guess_states = Guess()
        for i, letter in enumerate(guess.word):
            guess_states.append(Letter(letter, i, self.answer))

        # Handle repeated letter behaviour:
        # https://nerdschalk.com/wordle-same-letter-twice-rules-explained-how-does-it-work/
        if guess.repeated_letters:
            for repeated_letter in guess.repeated_letters:
                if repeated_letter not in self.answer.word:
                    continue

                # Get the total occurrences of the letter in the answer
                num_in_answer = self.answer.letter_map[repeated_letter]
                num_matched = 0

                # Count all the exact matches first
                for letter in guess_states:
                    if letter.state == GuessState.CORRECT:
                        num_matched += 1

                # For remaining occurrences, ensure only the number of occurrences in the answer are indicated.
                for letter in guess_states:
                    if letter.state == GuessState.POSITION:
                        num_matched += 1
                        if num_matched > num_in_answer:
                            letter.override = GuessState.WRONG

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


def load_words(file_path: str = WORD_LIST) -> list[Word]:
    word_list = []
    with open(file_path, 'r') as f:
        for line in f.readlines():
            word_list.append(Word(line.strip()))
    return word_list


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


def main():
    play_game()



if __name__ == '__main__':
    main()
