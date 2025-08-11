#!/usr/bin/env python3
import unittest

class TestSmoke(unittest.TestCase):
    def test_truth(self):
        self.assertTrue(True)

    def test_version_string_present(self):
        # Very simple placeholder: ensure README mentions Redboar
        with open('README.md', 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('Redboar', content)

if __name__ == '__main__':
    unittest.main()


