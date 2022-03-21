import re
from random import randrange
from enum import Enum
from utils import log
from typing import List, Optional


WORD_SIZE = 5
NUM_GUESSES = 6
WORD_LIST = 'word_list.txt'


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

    def __str__(self):
        return self.word

    def __eq__(self, other):
        return self.word == other.word


class Letter:
    def __init__(
        self,
        guess: str,
        position: int,
        answer: Word,
    ):
        assert len(guess) == 1, "guess and answer must be single letters."
        self.guess = guess.upper()
        self.position = position
        self.answer = answer

    @property
    def state(self) -> GuessState:
        if self.guess == self.answer.word[self.position]:
            return GuessState.CORRECT
        elif self.guess in self.answer.word:
            return GuessState.POSITION
        else:
            return GuessState.WRONG


class Game:
    def __init__(
        self,
        answer: Word,
        word_list: Optional[List[Word]] = None
    ):
        self.answer: Word = answer
        self.num_guesses: int = NUM_GUESSES
        self.turn: int = 0
        self.guesses: List[List[Letter]] = []
        self.word_list: List[Word] = word_list or load_words()

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

    def make_guess(self, _guess: str) -> bool:
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

        guess_states = []
        for i, letter in enumerate(guess.word):
            guess_states.append(Letter(letter, i, self.answer))

        self.guesses.append(guess_states)
        return True

    def __str__(self):
        out = '\n'
        for guess in self.guesses:
            out += ''.join(letter.guess for letter in guess)
            out += '\n'
            out += ''.join(letter.state.value for letter in guess)
            out += '\n'
        return out


def load_words() -> List[Word]:
    word_list = []
    with open(WORD_LIST, 'r') as f:
        for line in f.readlines():
            word_list.append(Word(line.strip()))
    return word_list


def play_game():
    word_list = load_words()
    game = Game(
        answer=word_list[randrange(len(word_list))],  # Pick a word at random
        word_list=word_list,
    )

    while not game.is_over:
        print(f'Guess {len(game.guesses) + 1}:')
        guess = input()
        if game.make_guess(guess):
            print(game)
    print()
    print(f"Answer: {game.answer}")



def main():
    pass


if __name__ == '__main__':
    main()
