import unittest
from wordle import Game, GuessState, Letter, Word, WrongWordSize, WORD_SIZE


class Words(unittest.TestCase):
    def test_word_size(self):
        word = Word('renew')
        self.assertEqual(len(word.word), WORD_SIZE)
        self.assertRaises(WrongWordSize, Word, 'renew_1')

    def test_letter_uniqueness(self):
        word = Word('renew')
        self.assertFalse(word.has_unique_letters)
        word = Word('crane')
        self.assertTrue(word.has_unique_letters)

    def test_letter_counts(self):
        word = Word('ghost')
        self.assertEqual(word.letter_map, {'G': 1, 'H': 1, 'O': 1, 'S': 1, 'T': 1})
        self.assertEqual(word.repeated_letters, [])

        word = Word('renew')
        self.assertEqual(word.letter_map, {'R': 1, 'E': 2, 'N': 1, 'W': 1})
        self.assertEqual(word.repeated_letters, ['E'])

    def test_guesses(self):
        game = Game('ghost')
        game.guess('pious')
        self.assertEqual(str(game.last_guess), '🟥🟥🟩🟥🟨')
        game.guess('slosh')
        self.assertEqual(str(game.last_guess), '🟥🟥🟩🟩🟨')
        game.guess('ghost')
        self.assertEqual(str(game.last_guess), '🟩🟩🟩🟩🟩')

    def test_repeated_letters(self):
        game = Game('where')
        game.guess('there')
        self.assertEqual(str(game.last_guess), '🟥🟩🟩🟩🟩')
        game.guess('keeps')
        self.assertEqual(str(game.last_guess), '🟥🟨🟩🟥🟥')
        game.guess('apple')
        self.assertEqual(str(game.last_guess), '🟥🟥🟥🟥🟩')
        game.guess('abbey')
        self.assertEqual(str(game.last_guess), '🟥🟥🟥🟨🟥')

        game = Game('abbey')
        game.guess('keeps')
        self.assertEqual(str(game.last_guess), '🟥🟨🟥🟥🟥')

        game = Game('koran')
        game.guess('aaron')
        self.assertEqual(str(game.last_guess), '🟨🟥🟩🟨🟩')

    def test_guess_filter(self):
        game = Game('chest')
        game.guess('crane')
        self.assertEqual(
            game.information,
            (
                {Letter('C', 0, GuessState.CORRECT)},
                {Letter('E', 4, GuessState.POSITION)},
                {'A', 'R', 'N'},
                {},
            )
        )
        self.assertEqual(len(game.possible_answers), 46)
        game.guess('pious')
        self.assertEqual(len(game.possible_answers), 1)
        self.assertEqual(game.possible_answers[0].word, 'CHEST')

        correct = set()
        in_word = {
            Letter('E', 4, GuessState.POSITION),
            Letter('P', 0, GuessState.POSITION),
            Letter('O', 2, GuessState.POSITION),
        }
        not_in_word = {'C', 'R', 'I', 'U', 'S'}
        possible = Game('chest').filter_words_from_info(correct, in_word, not_in_word, {})
        self.assertEqual(
            [w.word for w in possible],
            ['BEBOP', 'DEPOT', 'DOPED', 'DOPEY', 'HOPED', 'LOPED', 'MOPED', 'OPTED', 'TEMPO', 'TOPED'],
        )

        game = Game('abbot')
        game.guess('aaron')
        self.assertEqual(len(game.possible_answers), 15)

        game = Game('beach')
        game.guess('aaron')
        self.assertEqual(len(game.possible_answers), 809)

        game = Game('koran')
        game.guess('aaron')
        self.assertEqual(len(game.possible_answers), 2)

        game = Game('watch')
        game.guess('hatch')
        self.assertEqual(len(game.possible_answers), 6)

        game = Game('borer')
        game.guess('rorer')
        self.assertEqual(len(game.possible_answers), 3)

    def test_probability(self):
        game = Game('chest')
        game.guess('rates')

        word = Word('chest')
        p_map = word.get_probability_map(game.possible_answers)
        total = 0
        for guess, prob in p_map.items():
            total += prob
        self.assertEqual(round(total, 2), 1.0)


if __name__ == '__main__':
    unittest.main()
