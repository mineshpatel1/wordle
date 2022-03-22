import unittest
from wordle import Game, Word, WrongWordSize, WORD_SIZE


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
        self.assertEqual(str(game.last_guess), '⬛⬛🟩⬛🟨')
        game.guess('slosh')
        self.assertEqual(str(game.last_guess), '⬛⬛🟩🟩⬛')
        game.guess('ghost')
        self.assertEqual(str(game.last_guess), '🟩🟩🟩🟩🟩')

    def test_repeated_letters(self):
        game = Game('where')
        game.guess('there')
        self.assertEqual(str(game.last_guess), '⬛🟩🟩🟩🟩')
        game.guess('keeps')
        self.assertEqual(str(game.last_guess), '⬛🟨🟩⬛⬛')
        game.guess('apple')
        self.assertEqual(str(game.last_guess), '⬛⬛⬛⬛🟩')
        game.guess('abbey')
        self.assertEqual(str(game.last_guess), '⬛⬛⬛🟨⬛')

        game = Game('abbey')
        game.guess('keeps')
        self.assertEqual(str(game.last_guess), '⬛🟨⬛⬛⬛')


if __name__ == '__main__':
    unittest.main()
