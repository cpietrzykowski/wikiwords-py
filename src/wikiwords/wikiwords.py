from typing import Callable, TextIO

from lxml import etree

from .parser import MediaWikiPageTarget as ParserTarget
from .wiki_page import WordPage

WordPageCallback = Callable[[WordPage], None]


def ParseWordPages(stream: TextIO, on_page: WordPageCallback) -> None:
    """ main page parser for word pages """

    target = ParserTarget(on_page)
    parser = etree.XMLParser(
        # encoding='utf-8',
        target=target,
        attribute_defaults=False,
        load_dtd=False,
        dtd_validation=False,
        # recover=True,
        # ns_clean=True,
        huge_tree=True,
        resolve_entities=False,
        remove_comments=True,
        remove_blank_text=True
    )

    etree.parse(stream, parser)
    target.close()
