import json
from sqlite3 import Connection, Cursor
from typing import Callable, Optional

from .wiki_page import (CategorySection, LanguageCategory, RevisionLanguage,
                        WordPage, WordRevision)


class TableField():
    def __init__(self, fieldType: str, options: Optional[str] = None):
        self.fieldType = fieldType
        self.options = options

    def toStatement(self) -> str:
        stmt = f'{self.fieldType}'
        if self.options is not None:
            stmt = f'{stmt} {self.options}'
        return stmt


class DatabaseTable():
    def __init__(self, name: str):
        self.name = name
        self.fields: dict[str, TableField] = {}
        self._primary_key: Optional[str] = None
        self._foreign_keys: dict[str, str] = {}

    def addField(self, name: str, field: TableField) -> None:
        self.fields[name] = field

    def setFields(self, fields: dict[str, TableField]) -> None:
        for k in fields:
            self.addField(k, fields[k])

    def addPrimaryKey(self, *args: str) -> None:
        self._primary_key = ','.join([f'"{x}"' for x in args])

    def addForeignKey(self, names: list[str], ref_table: str, ref_fields: list[str]) -> None:
        key_str = [f'"{x}"' for x in names]
        ref_str = [f'"{x}"' for x in ref_fields]
        self._foreign_keys[f'FOREIGN KEY ({",".join(key_str)})'] = f'REFERENCES "{ref_table}" ({",".join(ref_str)})'


    def migrate(self, conn: Connection) -> None:
        stmt = self.toStatement()
        conn.execute(stmt)

    def toStatement(self) -> str:
        lines: list[str] = []

        for k, v in self.fields.items():
            lines.append(f'"{k}" {v.toStatement()}')

        if self._primary_key is not None:
            lines.append(f'PRIMARY KEY ({self._primary_key})')

        # TODO: current mypy has issues with variables with the same name used
        # earlier in the same block (despite them being assigned for the `for`)
        for fkk, fkv in self._foreign_keys.items():
            lines.append(f'{fkk} {fkv}')

        joined_lines = ',\n'.join(lines)
        return f'CREATE TABLE IF NOT EXISTS "{self.name}" ({joined_lines});'

    @staticmethod
    def last_insert_id(cursor: Cursor, fallback_query: Optional[Callable[[Cursor], Cursor]]) -> int:
        """ convenience for `last_insert_id` of `cursor` with a fallback query """

        # last_id = cursor.lastrowid
        # if last_id is not None and last_id > 0:
        #     return last_id

        if fallback_query is not None:
            res = fallback_query(cursor)
            fetched = res.fetchone()
            last_id = fetched[0]
            assert(isinstance(last_id, int))
            return last_id

        raise ValueError("unable to retrieve `lastrowid`")


class WordTable(DatabaseTable):
    def __init__(self) -> None:
        super().__init__("word")
        self.setFields({
            "id": TableField("INTEGER", "NOT NULL"),
            "word": TableField("TEXT", "NOT NULL UNIQUE")
        })

        self.addPrimaryKey("id")

    @staticmethod
    def save(cursor: Cursor, word: WordPage) -> None:
        cursor.execute(
            'INSERT OR IGNORE INTO word (word) VALUES (?)',
            (word.name,)
        )

        word_id =  DatabaseTable.last_insert_id(
            cursor,
            lambda c: c.execute(
                'SELECT id FROM word WHERE word = ?',
                (word.name,)
        ))

        for r in word.revisions:
            RevisionTable.save(cursor, r, word_id)


class RevisionTable(DatabaseTable):
    def __init__(self) -> None:
        super().__init__("revision")
        self.setFields({
            "id": TableField("INTEGER", "NOT NULL"),
            "wordid": TableField("INTEGER", "NOT NULL"),
            "time": TableField("TEXT"),
            "format": TableField("TEXT"),
            "text": TableField("TEXT"),
            "uncategorized": TableField("TEXT"),
            "unparented_categories": TableField("TEXT"),
            "unparented_meta": TableField("TEXT"),
        })

        self.addPrimaryKey("id")
        self.addForeignKey(["wordid"], "word", ["id"])

    @staticmethod
    def dumpSections(sections: list[CategorySection]) -> str:
        def _dump_section(section: CategorySection) -> str:
            return json.dumps({
                "name": section.name,
                "body": section.text
            })

        return json.dumps([_dump_section(x) for x in sections])
    
    @staticmethod
    def dumpCategories(categories: list[LanguageCategory]) -> str:
        def _dump_category(category: LanguageCategory) -> str:
            return json.dumps({
                "name": category.name,
                "sections": RevisionTable.dumpSections(list(category.sections.values()))
            })
        
        return json.dumps([_dump_category(x) for x in categories])

    @staticmethod
    def save(cursor: Cursor, revision: WordRevision, word_id: int) -> None:
        cursor.execute('''INSERT INTO revision (
    wordid, time, format, uncategorized, unparented_categories, unparented_meta
)
VALUES (?, ?, ?, ?, ?, ?)
''', (
                word_id,
                revision.timestamp.isoformat(),
                revision.format,
                json.dumps(revision.uncategorizedData),
                RevisionTable.dumpCategories(revision.unparentedCategories),
                RevisionTable.dumpSections(revision.unparentedSections)
        ))

        revision_id = cursor.lastrowid
        assert(revision_id is not None)

        for l in revision.languages:
            RevisionsLanguagesTable.save(cursor, revision_id, l)


class LanguageTable(DatabaseTable):
    def __init__(self) -> None:
        super().__init__("language")
        self.setFields({
            "id": TableField("INTEGER", "NOT NULL"),
            "language": TableField("TEXT", "NOT NULL UNIQUE")
        })

        self.addPrimaryKey("id")

    @staticmethod
    def save(cursor: Cursor, language: RevisionLanguage) -> int:
        cursor.execute(
            'INSERT OR IGNORE INTO language (language) VALUES (?)',
            (language.name,)
        )

        return DatabaseTable.last_insert_id(
            cursor,
            lambda c: c.execute(
                'SELECT id FROM language WHERE language = ?',
                (language.name,)
        ))


class RevisionsLanguagesTable(DatabaseTable):
    """ join table for relating a revision to a language """
    def __init__(self) -> None:
        super().__init__("revisions_languages")
        self.setFields({
            "id": TableField("INTEGER", "NOT NULL"),
            "revisionid": TableField("INTEGER", "NOT NULL"),
            "languageid": TableField("INTEGER", "NOT NULL"),
            "text": TableField("TEXT")
        })

        self.addPrimaryKey("id")
        self.addForeignKey(["revisionid"], "revision", ["id"])
        self.addForeignKey(["languageid"], "language", ["id"])

    @staticmethod
    def save(cursor: Cursor, revision_id: int, language: RevisionLanguage) -> None:
        language_id = LanguageTable.save(cursor, language)
        cursor.execute(
            'INSERT INTO revisions_languages (revisionid, languageid) VALUES (?, ?)',
            (revision_id, language_id)
        )

        rev_lang_id = cursor.lastrowid
        assert(rev_lang_id is not None)

        for v in language.categories.values():
            RevisionsLanguagesCategoriesTable.save(cursor, rev_lang_id, v)


class CategoryTable(DatabaseTable):
    def __init__(self) -> None:
        super().__init__("category")
        self.setFields({
            "id": TableField("INTEGER", "NOT NULL"),
            "category": TableField("TEXT", "NOT NULL UNIQUE"),
        })

        self.addPrimaryKey("id")

    @staticmethod
    def save(cursor: Cursor, category: str) -> int:
        """ create a category entry """
        cursor.execute('''INSERT OR IGNORE INTO category
(category) VALUES (?)
''',
            (category,)
        )
    
        return DatabaseTable.last_insert_id(
            cursor,
            lambda c: c.execute(
                'SELECT id FROM category WHERE category = ?',
                (category,)
        ))


class RevisionsLanguagesCategoriesTable(DatabaseTable):
    """ join table for relating a category to a revision language """
    def __init__(self) -> None:
        super().__init__("revisions_languages_categories")
        self.setFields({
            "id": TableField("INTEGER", "NOT NULL"),
            "revlangid": TableField("INTEGER", "NOT NULL"),
            "categoryid": TableField("INTEGER", "NOT NULL"),
            "data": TableField("TEXT")
        })

        self.addPrimaryKey("id")
        self.addForeignKey(["revlangid"], "revisions_languages", ["id"])
        self.addForeignKey(["categoryid"], "category", ["id"])

    @staticmethod
    def save(cursor: Cursor, revision_language_id: int, category: LanguageCategory) -> None:
        category_id = CategoryTable.save(cursor, category.name)
        cursor.execute('''INSERT INTO revisions_languages_categories
(revlangid, categoryid) VALUES (?, ?)
''',
            (revision_language_id, category_id)
        )

        revision_language_category_id = cursor.lastrowid
        assert(revision_language_category_id is not None)
        for v in category.sections.values():
            RevisionsLanguagesCategorySectionTable.save(
                cursor,
                revision_language_category_id,
                v
            )

class CategorySectionTable(DatabaseTable):
    def __init__(self) -> None:
        super().__init__("category_section")
        self.setFields({
            "id": TableField("INTEGER", "NOT NULL"),
            "section": TableField("TEXT", "NOT NULL UNIQUE"),
        })

        self.addPrimaryKey("id")

    @staticmethod
    def save(cursor: Cursor, section: CategorySection) -> Optional[int]:
        cursor.execute('''INSERT OR IGNORE INTO category_section
(section) VALUES (?)
''',
            (section.name,)
        )

        return DatabaseTable.last_insert_id(
            cursor,
            lambda c: c.execute(
                'SELECT id FROM category_section WHERE section = ?',
                (section.name,)
            )
        )


class RevisionsLanguagesCategorySectionTable(DatabaseTable):
    def __init__(self) -> None:
        super().__init__("revisions_languages_category_section")
        self.setFields({
            "id": TableField("INTEGER", "NOT NULL"),
            "revlangcatid": TableField("INTEGER", "NOT NULL"),
            "sectionid": TableField("INTEGER", "NOT NULL"),
            "data": TableField("TEXT")
        })

        self.addPrimaryKey("id")
        self.addForeignKey(["revlangcatid"], "revisions_languages_categories", ["id"])
        self.addForeignKey(["sectionid"], "category_section", ["id"])

    @staticmethod
    def save(cursor: Cursor, revision_language_category_id: int, section: CategorySection) -> None:
        section_id = CategorySectionTable.save(cursor, section)
        cursor.execute('''INSERT INTO revisions_languages_category_section
(revlangcatid, sectionid) VALUES (?, ?)
''',
            (revision_language_category_id, section_id)
        )

def models() -> list[DatabaseTable]:
    return [
        WordTable(),
        RevisionTable(),
        LanguageTable(),
        CategoryTable(),
        CategorySectionTable(),
        RevisionsLanguagesTable(),
        RevisionsLanguagesCategoriesTable(),
        RevisionsLanguagesCategorySectionTable(),
    ]
