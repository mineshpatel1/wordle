import unittest
from wordle import (
    Game,
    load_words,
    get_prob_and_iv,
    filter_words_from_info,
    get_hint_from_guess,
)


class Words(unittest.TestCase):
    def test_hints(self):
        self.assertEqual(get_hint_from_guess('TABLE', 'LOBBY'), '⬛⬛🟩🟨⬛')
        self.assertEqual(get_hint_from_guess('KEEPS', 'ALGAE'), '⬛🟨⬛⬛⬛')
        self.assertEqual(get_hint_from_guess('SLOSH', 'GHOST'), '⬛⬛🟩🟩🟨')

    def test_guesses(self):
        game = Game('ghost')
        game.make_guess('pious')
        self.assertEqual(game.last_hint, '⬛⬛🟩⬛🟨')
        game.make_guess('slosh')
        self.assertEqual(game.last_hint, '⬛⬛🟩🟩🟨')
        game.make_guess('ghost')
        self.assertEqual(game.last_hint, '🟩🟩🟩🟩🟩')

    def test_repeated_letters(self):
        game = Game('where')
        game.make_guess('there')
        self.assertEqual(game.last_hint, '⬛🟩🟩🟩🟩')
        game.make_guess('keeps')
        self.assertEqual(game.last_hint, '⬛🟨🟩⬛⬛')
        game.make_guess('apple')
        self.assertEqual(game.last_hint, '⬛⬛⬛⬛🟩')
        game.make_guess('abbey')
        self.assertEqual(game.last_hint, '⬛⬛⬛🟨⬛')

        game = Game('abbey')
        game.make_guess('keeps')
        self.assertEqual(game.last_hint, '⬛🟨⬛⬛⬛')

        game = Game('koran')
        game.make_guess('aaron')
        self.assertEqual(game.last_hint, '🟨⬛🟩🟨🟩')

    def test_guess_filter(self):
        game = Game('chest')
        game.make_guess('crane')

        self.assertEqual(
            game.information,
            (
                {0: 'C'},
                {('E', 4)},
                {'A', 'R', 'N'},
                {},
            )
        )
        self.assertEqual(len(game.possible_answers), 46)
        game.make_guess('pious')
        self.assertEqual(len(game.possible_answers), 1)
        self.assertEqual(game.possible_answers[0], 'CHEST')

        correct = {}
        in_word = {
            ('E', 4),
            ('P', 0),
            ('O', 2),
        }
        not_in_word = {'C', 'R', 'I', 'U', 'S'}
        words = load_words()
        possible = filter_words_from_info(words, correct, in_word, not_in_word, {})
        self.assertEqual(
            [w for w in possible],
            ['BEBOP', 'DEPOT', 'DOPED', 'DOPEY', 'HOPED', 'LOPED', 'MOPED', 'OPTED', 'TEMPO', 'TOPED'],
        )

        game = Game('abbot')
        game.make_guess('aaron')
        self.assertEqual(len(game.possible_answers), 15)

        game = Game('beach')
        game.make_guess('aaron')
        self.assertEqual(len(game.possible_answers), 809)

        game = Game('koran')
        game.make_guess('aaron')
        self.assertEqual(len(game.possible_answers), 2)

        game = Game('watch')
        game.make_guess('hatch')
        self.assertEqual(len(game.possible_answers), 6)

        game = Game('borer')
        game.make_guess('rorer')
        self.assertEqual(len(game.possible_answers), 3)

    def test_probability(self):
        game = Game('chest')
        game.make_guess('rates')

        p_map = get_prob_and_iv('chest', game.possible_answers)
        total = 0
        for hint, item in p_map.items():
            total += item['p']
        self.assertEqual(round(total, 2), 1.0)


if __name__ == '__main__':
    unittest.main()
