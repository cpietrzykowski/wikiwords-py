
from typing import Optional


class Element:
    """ simple transfer object for elements found via xml parsers """
    def __init__(self, name: str, attrs: dict[str, str], parent: Optional["Element"]):
        self.name = name
        self.attrs = attrs
        self.parent = parent
        self._text: list[str] = []
        self._children: list[Element] = []

    def addText(self, text: str) -> None:
        self._text.append(text)

    def getText(self) -> str:
        return ''.join(self._text)

    def addChild(self, child: "Element") -> None:
        self._children.append(child)

    def getChildren(self, name: Optional[str] = None) -> list["Element"]:
        """ return all children of this element, optionally only of `name` """

        if name is None:
            return list(self._children)

        return [c for c in self._children if c.name.lower() == name.lower()]

    def getChild(self, name: str, nth: int = 0) -> Optional["Element"]:
        """
            convenience for returning a single element (example: only a
            single child element is expected -- instead of a collection)
        """
        # TODO: add a predicate to determine "which" child should be prioritized
        children = self.getChildren(name)
        if len(children) > nth:
            return children[nth]

        return None