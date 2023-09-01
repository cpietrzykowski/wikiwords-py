import argparse
import logging
import os
import sqlite3 as sqlite
import sys
from datetime import datetime
from typing import Callable, Optional

from wikiwords._version import __version__
from wikiwords.db import create_and_connect
from wikiwords.models import WordTable
from wikiwords.wiki_page import WordPage, WordRevision
from wikiwords.wikiwords import ParseWordPages

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", logging.INFO))

def page_handler(
    conn: sqlite.Connection,
    cursor: sqlite.Cursor,
    languages: list[str],
    batch_size: int
) -> tuple[Callable[[WordPage], None], Callable[[], int]]:
    c: int = 0
    c_split: int = 0
    t_last = datetime.now()

    def _filter_language(p: WordPage, languages: list[str]) -> Optional[WordPage]:
        """ create a `WordPage` that only contains values of language in `languages` """

        if not len(languages) > 0:
            # empty list allows all
            return p

        revisions: list[WordRevision] = []
        for r in p.revisions:
            langs = [x for x in r.languages if x.name in languages]
            if len(langs) > 0:
                revisions.append(WordRevision(
                    r.timestamp,
                    r.format,
                    r.text.getvalue(),
                    langs
                ))

        if len(revisions) > 0:
            return WordPage(p.name, p.text.getvalue(), revisions)
        
        return None


    def _handler(p: WordPage) -> None:
        nonlocal c
        nonlocal c_split
        nonlocal t_last
        c = c + 1

        new_p = _filter_language(p, languages)
        if new_p is None:
            return
    
        WordTable.save(cursor, new_p)
        if c % batch_size == 0:
            conn.execute('END TRANSACTION')
            t_now = datetime.now()
            logger.info(f"progress ({t_now}): {c} ({((c - c_split) / (t_now - t_last).total_seconds()):.02f} w/s)")
            c_split = c
            t_last = t_now
            conn.execute('BEGIN TRANSACTION')

    def _count() -> int:
        return c

    return (_handler, _count)


def main(name: str, argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog='wikiwords-py',
        description="""A tool to parse <mediawiki> archives."""
    )
    parser.add_argument('--verbose', '-v', action='count', default=0)
    parser.add_argument(
        '--version', action='version', version=f'%(prog)s {__version__}'
    )
    parser.add_argument('--language', help='comma delimited language list')
    parser.add_argument('--sqlite', metavar="DB", required=True)
    parser.add_argument('archive_file')
    args = parser.parse_args(argv)
    archive_file: str = args.archive_file
    db_file: str  = args.sqlite
    languages: list[str] = []
    if args.language is not None:
        languages = args.language.split(',')

    logger.info(f'reading from: {archive_file}')
    logger.info(f'writing to: {db_file}')

    conn = create_and_connect(db_file)

    conn.execute('BEGIN TRANSACTION')
    t_start = datetime.now()
    logger.info(f'start: {t_start}')
    cursor = conn.cursor()
    (handler, get_count) = page_handler(conn, cursor, languages, 10000)

    with open(archive_file, encoding="utf-8") as f:
        ParseWordPages(f, handler)

    cursor.close()
    t_end = datetime.now()
    word_count = get_count()
    logger.info(f"words: {word_count} ({(word_count / (t_end - t_start).total_seconds()):.02f} w/s)")
    logger.info(f'finished: {t_end}')
    conn.execute('END TRANSACTION')
    conn.close()


if __name__ == '__main__':
    main(sys.argv[0], sys.argv[1:])
