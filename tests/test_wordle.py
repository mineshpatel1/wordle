import unittest
from wordle import Word, WrongWordSize, WORD_SIZE


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


if __name__ == '__main__':
    unittest.main()
