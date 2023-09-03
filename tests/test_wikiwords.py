import io
import unittest
from datetime import datetime, timezone

from wikiwords.wiki_page import WordPage
from wikiwords.wikiwords import ParseWordPages

from tests.fixtures.multi_page import MULTI_PAGE_FIXTURE
from tests.fixtures.single_page import SINGLE_PAGE_FIXTURE


class TestWikiwords(unittest.TestCase):
    def test_empty_root(self) -> None:
        words: list[str] = []
        ParseWordPages(io.StringIO("""<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.10/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.mediawiki.org/xml/export-0.10/ http://www.mediawiki.org/xml/export-0.10.xsd" version="0.10" xml:lang="en">
</mediawiki>
"""), lambda n: words.append(n.name))

        self.assertEqual(len(words), 0)

    def test_single_page(self) -> None:
        words: list[WordPage] = []
        ParseWordPages(
            io.StringIO(SINGLE_PAGE_FIXTURE),
            lambda p: words.append(p)
        )

        self.assertEqual([w.name for w in words], ["raven"])

    def test_file_stream(self) -> None:
        # TODO: should probably be moved into an integration test
        words: list[str] = []
        with open("./tests/fixtures/mediawiki.xml", encoding='utf-8') as f:
            ParseWordPages(
                f,
                lambda p: words.append(p.name)
            )

        self.assertEqual(len(words), 189)

    def test_text_parsing(self) -> None:
        words: list[WordPage] = []
        ParseWordPages(
            io.StringIO(MULTI_PAGE_FIXTURE),
            lambda p: words.append(p)
        )

        self.assertEqual([
            [w.name, [l.name for l in w.revision.languages]] for w in words
        ], [
            ['dictionary', ["english"]],
            ['raven', [
                "english", "dutch", "german", "middle dutch", "slovene", "swedish"
            ]]
        ])

        self.assertEqual([
            r.timestamp for r in [w.revision for w in words]
        ], [
            datetime(2023, 7,23, 21, 30, 27, tzinfo=timezone.utc),
            datetime(2023, 7, 21, 13, 32, 9, tzinfo=timezone.utc),
        ])

        self.assertEqual([
            r.timestamp for r in [w.revision for w in words]
        ], [
            datetime(2023, 7, 23, 21, 30, 27, tzinfo=timezone.utc),
            datetime(2023, 7, 21, 13, 32, 9, tzinfo=timezone.utc)
        ], "order inconsistency")


if __name__ == '__main__':
    unittest.main()
