import unittest

from wikiwords.format import formatDuration


class TestFormat(unittest.TestCase):
    def test_format_duration(self) -> None:
        self.assertEqual(formatDuration(0), "0ms")
        self.assertEqual(formatDuration(0.0208), "21ms")
        self.assertEqual(formatDuration(1.0008), "1.001")
        self.assertEqual(formatDuration(59.005), "59.005")
        self.assertEqual(formatDuration(123.005), "2:03.005")
        self.assertEqual(formatDuration(1234.005), "20:34.005")
        self.assertEqual(formatDuration(12345.005), "3:25:45.005")


if __name__ == '__main__':
    unittest.main()
