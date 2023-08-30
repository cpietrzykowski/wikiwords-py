import re
from datetime import datetime, timezone
from io import StringIO
from typing import Optional

from .element import Element


class TextSection():
    def __init__(self, text: str = ""):
        self.text = StringIO(text)

    def addText(self, text: str) -> None:
        self.text.write(text)


class CategorySection(TextSection):
    """ inflection, alternative forms, descendants, derived terms, etc. """

    def __init__(self, name: str, text: str = ""):
        super().__init__(text)
        self.name = name


class LanguageCategory(TextSection):
    """ represents a word class, ex: noun, verb, adjective, adverb, etc. """

    def __init__(self, name: str, text: str = "", sections: dict[str, CategorySection] = {}):
        super().__init__(text)
        self.name = name
        self.sections = sections

    def getSection(self, name: str) -> Optional[CategorySection]:
        if not name in self.sections:
            self.sections[name] = CategorySection(name)

        return self.sections.get(name)


class RevisionLanguage(TextSection):
    """ represents a word's language """

    def __init__(self, name: str, categories: dict[str, LanguageCategory] = {}, text: str = ""):
        super().__init__(text)
        self.name = name
        self.categories = categories

    def getCategory(self, name: str) -> Optional[LanguageCategory]:
        if not name in self.categories:
            self.categories[name] = LanguageCategory(name)

        return self.categories.get(name)


class WordRevision(TextSection):
    TEXT_MIME = "text/x-wiki"

    MARKUP_COMMENT = r"<!--.*-->$"
    DIRECTIVES: dict[str, list[str]] = {
        "embed": [r"\[\[(.+)\]\]"],

        "redirect": [r"#REDIRECT \[\[([^\]]+)\]\]"],

        # links to other pages {{also|some|other|word}}
        "reference": [
            r"{{(.+)}}",
            r"''See also:''.+"
        ],

        "toc": [r"^__TOC__"],
    }

    def __init__(
        self,
        timestamp: datetime,
        format: str,
        text: str,
        languages: list[RevisionLanguage] = [],
    ):
        super().__init__()
        self.timestamp = timestamp
        self.format = format
        self.text = StringIO(text)
        self.languages = languages

        # TODO: for markdown parser debugging
        self.unparentedCategories: list[LanguageCategory] = []
        self.unparentedSections: list[CategorySection] = []
        self.uncategorizedData: list[str] = []

    def addUnparentedCategories(self, c: list[LanguageCategory]) -> None:
        self.unparentedCategories = c

    def addUnparentedSections(self, m: list[CategorySection]) -> None:
        self.unparentedSections = m

    def addUncategorizedData(self, d: list[str]) -> None:
        self.uncategorizedData = d

    @staticmethod
    def parse(text: str) -> tuple[list[RevisionLanguage], list[LanguageCategory], list[CategorySection], list[str]]:
        """
        attempts to parse the "wiki markdown" for a page's word

        uncategorized text data is returned for later processing
        """

        # TODO: clean up state machine/parser using captured lambdas instead of
        # temporary variables
        languages: dict[str, RevisionLanguage] = {}
        uncategorized: list[str] = []
        unparentedCategories: list[LanguageCategory] = []
        unparentedSections: list[CategorySection] = []
        currentLanguage: Optional[RevisionLanguage] = None
        currentCategory: Optional[LanguageCategory] = None
        current: Optional[TextSection] = None

        for l in text.splitlines():
            headerMatch = re.match(r"^([=]+)\s*([^=]+)\s*\1$", l)
            if headerMatch is None:
                if current is not None:
                    # add text to current context object
                    current.addText(l)
                else:
                    # text without section
                    l_trimmed = l.strip()
                    if len(l_trimmed) > 0:
                        uncategorized.append(l_trimmed)
                continue

            h = headerMatch.group(2).lower()
            hlevel = len(headerMatch.group(1))

            if hlevel == 2:
                current = currentLanguage = languages[h] = languages.get(
                    h, RevisionLanguage(h)
                )
            elif hlevel == 3:
                if currentLanguage is None:
                    current = currentCategory = LanguageCategory(h)
                    unparentedCategories.append(currentCategory)
                    continue

                current = currentCategory = currentLanguage.getCategory(
                    h
                )
            elif hlevel == 4:
                if currentCategory is None:
                    current = s = CategorySection(h)
                    unparentedSections.append(s)
                    continue

                current = currentCategory.getSection(h)

        return (list(languages.values()), unparentedCategories, unparentedSections, uncategorized)

    @staticmethod
    def from_element(e: Element) -> Optional["WordRevision"]:
        # <timestamp>2023-07-04T08:08:52Z</timestamp>
        ts = e.getChild("timestamp")
        if ts is None:
            return None

        fmt = e.getChild("format")
        if fmt is None or fmt.text.getvalue() != WordRevision.TEXT_MIME:
            return None

        txt = e.getChild("text")
        if txt is None:
            return None

        (languages, uc, um, ud) = WordRevision.parse(txt.text.getvalue())

        # python 3.11 will support multiple iso formats
        # dt = datetime.fromisoformat(ts.text)

        # strptime doesn't include a timezone, and since the string is
        # specifically "zulu" it should be safe to just set it to utc.
        dt = datetime.strptime(ts.text.getvalue(), "%Y-%m-%dT%H:%M:%SZ",).replace(tzinfo=timezone.utc)
        rev = WordRevision(dt, fmt.text.getvalue(), txt.text.getvalue(), languages)

        # TODO: for debugging the markdown parser
        rev.addUnparentedCategories(uc)
        rev.addUnparentedSections(um)
        rev.addUncategorizedData(ud)
        return rev

    @staticmethod
    def from_elements(elements: list[Element]) -> list["WordRevision"]:
        revisions = [r for r in [
            WordRevision.from_element(e) for e in elements
        ] if r is not None]

        return sorted(revisions, key=lambda r: r.timestamp)


class WikiPage():
    # TODO: maybe support other kinds of pages, for other archives?
    def __init__(self, text: str):
        self.text = StringIO(text)


class WordPage(WikiPage):
    """
        represents a wiki word page

        > reference `ns 0` is a word page
    """

    def __init__(self, name: str, text: str, revisions: list[WordRevision] = []):
        super().__init__(text)
        self.name = name
        self.revisions = revisions

    def most_recent_revision(self) -> Optional[WordRevision]:
        rcount = len(self.revisions)
        if rcount > 0:
            return self.revisions[rcount - 1]

        return None

    @staticmethod
    def from_element(e: Element) -> Optional["WordPage"]:
        word = e.getChild("title")
        if word is None:
            return None

        return WordPage(
            word.text.getvalue(),
            e.text.getvalue(),
            WordRevision.from_elements(e.getChildren("revision"))
        )
