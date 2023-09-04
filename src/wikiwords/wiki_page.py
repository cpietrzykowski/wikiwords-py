import re
from datetime import datetime, timezone
from io import StringIO
from typing import Optional

from .element import Element


class TextSection():
    def __init__(self, body: str = ""):
        self._body = StringIO(body)

    def addText(self, text: str) -> None:
        self._body.write(text)

    def getText(self) -> str:
        return self._body.getvalue()


class CategorySection(TextSection):
    """ inflection, alternative forms, descendants, derived terms, etc. """

    def __init__(self, name: str, body: str = ""):
        super().__init__(body)
        self.name = name


class LanguageCategory(TextSection):
    """ represents a word class, ex: noun, verb, adjective, adverb, etc. """

    def __init__(self, name: str, body: str = ""):
        super().__init__(body)
        self.name = name
        self._sections: Optional[list[CategorySection]] = None

    def _parse_body(self) -> None:
        self._sections = []
        currentSection: Optional[CategorySection] = None

        for l in self.getText().splitlines(True):
            headerMatch = re.match(r"^====\s*([^=]+)\s*====$", l)
            if headerMatch is None:
                if currentSection is None:
                    # TODO
                    pass
                else:
                    currentSection.addText(l.strip())
                continue

            currentSection = CategorySection(headerMatch.group(1).lower())
            self._sections.append(currentSection)

    def getSection(self, name: str) -> Optional[CategorySection]:
        sections = [s for s in self.getSections() if s.name.lower() == name.lower()]
        if len(sections) > 0:
            assert(len(sections) == 1)
            return sections[0]

        return None
    
    def getSections(self) -> list[CategorySection]:
        if self._sections is None:
            self._parse_body()

        return self._sections or []


class RevisionLanguage(TextSection):
    """ represents a word's language """

    def __init__(self, name: str, body: str = ""):
        super().__init__(body)
        self.name = name
        self._categories: Optional[list[LanguageCategory]] = None

    def getCategory(self, name: str) -> Optional[LanguageCategory]:
        if self._categories is None:
            return None

        # just find the first matching `category`
        for c in self._categories:
            if c.name.lower() == name.lower():
                return c

        return None

    def _parse_body(self) -> None:
        """ process language section body to categories """
        self._categories = []
        currentCategory: Optional[LanguageCategory] = None

        for l in self.getText().splitlines(True):
            headerMatch = re.match(r"^===\s*([^=]+)\s*===$", l)
            if headerMatch is None:
                if currentCategory is None:
                    # TODO
                    pass
                else:
                    currentCategory.addText(l)
                continue

            currentCategory = LanguageCategory(headerMatch.group(1).lower())
            self._categories.append(currentCategory)

    def getCategories(self) -> list[LanguageCategory]:
        if self._categories is None:
            self._parse_body()

        return self._categories or []

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

    def __init__(self, timestamp: datetime, body: str = ''):
        super().__init__(body)
        self.timestamp = timestamp
        self._languages: Optional[list[RevisionLanguage]] = None

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

    def _parse_body(self) -> None:
        """ rough first pass -- delay more complex parsing """
        self._languages = []
        currentLanguage: Optional[RevisionLanguage] = None

        for l in self.getText().splitlines(True):
            headerMatch = re.match(r"^==\s*([^=]+)\s*==$", l)
            if headerMatch is None:
                if currentLanguage is None:
                    self.uncategorizedData.append(l)
                else:
                    currentLanguage.addText(l)
                continue

            currentLanguage = RevisionLanguage(headerMatch.group(1).lower())
            self._languages.append(currentLanguage)

    def getLanguages(self, *predicate: str) -> list[RevisionLanguage]:
        if self._languages is None:
            self._parse_body()

        languages = self._languages or []
        if len(predicate) > 0:
            return [l for l in languages if l.name in predicate]
        
        return languages

    @staticmethod
    def from_element(e: Element) -> Optional["WordRevision"]:
        # <timestamp>2023-07-04T08:08:52Z</timestamp>
        ts = e.getChild("timestamp")
        if ts is None:
            return None

        fmt = e.getChild("format")
        if fmt is None or fmt.getText() != WordRevision.TEXT_MIME:
            return None

        txt = e.getChild("text")
        if txt is None:
            return None

        # python 3.11 will support multiple iso formats
        # dt = datetime.fromisoformat(ts.text)

        # strptime doesn't include a timezone, and since the string is
        # specifically "zulu" it should be safe to just set it to utc.
        dt = datetime.strptime(ts.getText(), "%Y-%m-%dT%H:%M:%SZ",).replace(tzinfo=timezone.utc)
        return WordRevision(dt, txt.getText())

    @staticmethod
    def from_elements(elements: list[Element]) -> list["WordRevision"]:
        revisions = [r for r in [
            WordRevision.from_element(e) for e in elements
        ] if r is not None]

        return sorted(revisions, key=lambda r: r.timestamp, reverse=True)


class WikiPage():
    # TODO: maybe support other kinds of pages, for other archives?
    pass


class WordPage(WikiPage):
    """
        represents a wiki word page

        > reference `ns 0` is a word page
    """

    def __init__(self, name: str, revision: WordRevision):
        self.name = name
        self.revision = revision

    @staticmethod
    def from_element(e: Element) -> Optional["WordPage"]:
        word = e.getChild("title")
        if word is None:
            return None

        revisions = WordRevision.from_elements(e.getChildren("revision"))
        if len(revisions) > 0:
            return WordPage(word.getText(), revisions[0])
        
        return None
