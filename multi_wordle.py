import random
from utils import log, multi_process
from wordle import (
    Game,
    load_words,
    load_answers,
    get_optimal_entropies,
    sort_by_entropy,
    INITIAL_GUESSES,
    MAX_GUESSES,
    NUM_PROCESSES,
)
from typing import Optional

DEFAULT_NUM_GAMES = 2


class MultiGame:
    def __init__(
        self,
        num_games: int = DEFAULT_NUM_GAMES,
        max_guesses: int = MAX_GUESSES,
        answers: Optional[list[str]] = None,
    ):
        self.word_list = load_words()
        self.answer_list = load_answers()
        self.answers = []
        self.games: list[Game] = []
        self.guesses: list[str] = []
        self.max_guesses = max_guesses

        if not answers:
            for i in range(num_games):
                answer = None
                while answer not in self.answers:
                    answer = random.choice(self.answer_list)
                    self.answers.append(answer)
                self.games.append(
                    Game(self.answers[i], self.word_list, max_guesses=self.max_guesses)
                )
        else:
            for answer in answers:
                self.answers.append(answer)
                self.games.append(
                    Game(answer, self.word_list, max_guesses=self.max_guesses)
                )

    @property
    def is_over(self) -> bool:
        return all(g.is_over for g in self.games)

    @property
    def is_won(self) -> bool:
        return all(g.is_won for g in self.games)

    @property
    def score(self) -> int:
        return len(self.guesses)

    @property
    def last_guess(self) -> str:
        return self.guesses[-1]

    def make_guess(self, guess: str):
        self.guesses.append(guess)
        for game in self.games:
            game.make_guess(guess)

    def make_best_guess(self):
        best_guess = self.get_best_guess()
        for game in self.games:
            game.make_guess(best_guess)

    def get_best_guess(self) -> str:
        return get_best_move_multi(
            [game.possible_answers for game in self.games if not game.is_over],
            self.word_list,
            self.answer_list,
        )

    def __str__(self) -> str:
        def _convert_hint_str(hint: str) -> str:
            return hint.replace('⬛', 'x ').replace('🟩', '● ').replace('🟨', '○ ')

        output = "\n"
        for i in range(self.max_guesses):
            for game in self.games:
                if len(game.guesses) > i:
                    output += game.guesses[i] + (' ' * 7)
                else:
                    output += (' ' * 12)
            output += '\n'
            for game in self.games:
                if len(game.guesses) > i:
                    output += _convert_hint_str(game.hints[i]) + (' ' * 2)
                else:
                    output += (' ' * 12)
            output += '\n'
        return output


def aggregate_entropies(entropy_maps: list[dict[str, float]]) -> dict[str, float]:
    agg_entropy = {}
    for e_map in entropy_maps:
        for word, entropy in e_map.items():
            agg_entropy[word] = agg_entropy.get(word, 0) + entropy
    return agg_entropy


def get_best_move_multi(
    possible_answer_list: list[list[str]],
    word_list: list[str],
    answer_list: list[str],
) -> str:

    e_maps = multi_process(
        [(p, word_list, answer_list) for p in possible_answer_list],
        get_optimal_entropies,
        num_processes=min([NUM_PROCESSES, len(possible_answer_list)]),
        verbose=False,
    )

    agg_entropy = aggregate_entropies(e_maps)
    best_moves = sort_by_entropy(agg_entropy)
    return best_moves[0]


def bot_play_multi(
    num_games: int = DEFAULT_NUM_GAMES,
    max_guesses: int = MAX_GUESSES,
    answers: Optional[list[str]] = None,
    initial_guesses: list[str] = None,
):
    multi_game = MultiGame(num_games, max_guesses, answers)
    initial_guesses = initial_guesses or INITIAL_GUESSES

    for guess in initial_guesses:
        multi_game.make_guess(guess)

    while not multi_game.is_over:
        guess = multi_game.get_best_guess()
        log.info(f'Guessing {guess}...')
        multi_game.make_guess(guess)

    log.info(str(multi_game))
    return multi_game.score
