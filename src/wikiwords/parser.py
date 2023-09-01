from typing import Callable, Dict, Optional, Union

from lxml import etree

from .element import Element
from .wiki_page import WordPage

WordPageCallback = Callable[[WordPage], None]

lxmlStr = Union[str, bytes]

def _narrow_str_bytes(v: lxmlStr) -> str:
    if isinstance(v, str):
        return v
    
    return v.decode()

def _narrow_target_dict(d: dict[lxmlStr, lxmlStr]) -> dict[str, str]:
    return dict([(_narrow_str_bytes(k), _narrow_str_bytes(v)) for k, v in d.items()])

class MediaWikiPageTarget():
    ELEMENT_PATH = "/mediawiki/page"

    def __init__(self, callback: WordPageCallback) -> None:
        super().__init__()
        self._callback = callback
        self._context: list[str] = ['']
        self._current: Optional[Element] = None

    def _context_path(self) -> str:
        return '/'.join(self._context)

    def start(self, tag: lxmlStr, attrib: Dict[lxmlStr, lxmlStr]) -> None:
        tag_name = etree.QName(tag).localname
        self._context.append(tag_name)

        if self._current is None:
            if self._context_path() == MediaWikiPageTarget.ELEMENT_PATH:
                cur_element = Element(tag_name, _narrow_target_dict(attrib), self._current)
                self._current = cur_element
        else:
            cur_element = Element(tag_name, _narrow_target_dict(attrib), self._current)
            self._current.addChild(cur_element)
            self._current = cur_element

    def data(self, data: lxmlStr) -> None:
        if self._current is None:
            return
        
        self._current.addText(_narrow_str_bytes(data))

    def end(self, tag: lxmlStr) -> None:
        if self._current is not None:
            if self._context_path() == MediaWikiPageTarget.ELEMENT_PATH:
                # element's with '0' namespace are "word" pages
                # TODO: reference namespace source
                if "0" in [ns.getText() for ns in self._current.getChildren("ns")]:
                    page = WordPage.from_element(self._current)
                    if page is not None:
                        self._callback(page)
                self._current = None
            else:
                self._current = self._current.parent

        self._context.pop()

    def comment(self, _text: lxmlStr) -> None:
        pass

    def close(self) -> None:
        pass
