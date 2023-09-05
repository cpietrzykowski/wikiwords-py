import json
from sqlite3 import Connection, Cursor, IntegrityError
from typing import Callable, Optional

from .wiki_page import (CategorySection, LanguageCategory, RevisionLanguage,
                        WordPage)


def insert_or_select_id(
        cursor: Cursor,
        insert_op: Callable[[Cursor], Optional[Cursor]],
        select_id_op: Callable[[Cursor], Cursor]
    ) -> Optional[int]:
        """ guarded insert and retrieve id """
        # NOTE: `insert_op` accepts optional return type, but is never used
        # (for supporting lambdas)

        try:
            insert_op(cursor)
        except IntegrityError:
            res = select_id_op(cursor)
            fetched = res.fetchone()
            last_id = fetched[0]
            assert(isinstance(last_id, int))
            return last_id
        
        return cursor.lastrowid

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


class WordTable(DatabaseTable):
    def __init__(self) -> None:
        super().__init__("word")
        self.setFields({
            "id": TableField("INTEGER", "NOT NULL"),
            "word": TableField("TEXT", "NOT NULL UNIQUE"),

            # most recent revision fields
            "time": TableField("TEXT"),
            "uncategorized": TableField("TEXT"),
            "unparented_categories": TableField("TEXT"),
        })

        self.addPrimaryKey("id")

    @staticmethod
    def dumpSections(sections: list[CategorySection]) -> str:
        def _dump_section(section: CategorySection) -> str:
            return json.dumps({
                "name": section.name,
                "body": section.getText()
            })

        return json.dumps([_dump_section(x) for x in sections])
    

    @staticmethod
    def dumpCategories(categories: list[LanguageCategory]) -> str:
        def _dump_category(category: LanguageCategory) -> str:
            return json.dumps({
                "name": category.name,
                "sections": WordTable.dumpSections(list(category.getSections()))
            })
        
        return json.dumps([_dump_category(x) for x in categories])

    @staticmethod
    def save(cursor: Cursor, word: WordPage, languages: list[str] = []) -> bool:
        filtered_languages = word.revision.getLanguages(*languages)
        if not len(filtered_languages) > 0:
            return False

        word_id = insert_or_select_id(
            cursor,
            lambda c: c.execute('''INSERT INTO
word (word, time, uncategorized, unparented_categories)
VALUES (?, ?, ?, ?)
''',
                (
                    word.name,
                    word.revision.timestamp.isoformat(),
                    json.dumps(word.revision.uncategorizedData),
                    WordTable.dumpCategories(word.revision.unparentedCategories)
                )),
            lambda c: c.execute('SELECT id FROM word WHERE word = ?', (word.name,))
        )

        assert(word_id is not None)
        for l in filtered_languages:
            WordLanguagesTable.save(cursor, word_id, l)

        return True

class LanguageTable(DatabaseTable):
    def __init__(self) -> None:
        super().__init__("language")
        self.setFields({
            "id": TableField("INTEGER", "NOT NULL"),
            "language": TableField("TEXT", "NOT NULL UNIQUE")
        })

        self.addPrimaryKey("id")

    @staticmethod
    def save(cursor: Cursor, language: RevisionLanguage) -> Optional[int]:
        return insert_or_select_id(
            cursor,
            lambda c: c.execute('INSERT INTO language (language) VALUES (?)', (language.name,)),
            lambda c: c.execute('SELECT id FROM language WHERE language = ?', (language.name,))
        )


class WordLanguagesTable(DatabaseTable):
    """ join table for relating a word to a language """
    def __init__(self) -> None:
        super().__init__("word_languages")
        self.setFields({
            "id": TableField("INTEGER", "NOT NULL"),
            "wordid": TableField("INTEGER", "NOT NULL"),
            "languageid": TableField("INTEGER", "NOT NULL"),
        })

        self.addPrimaryKey("id")
        self.addForeignKey(["wordid"], "word", ["id"])
        self.addForeignKey(["languageid"], "language", ["id"])

    @staticmethod
    def save(cursor: Cursor, word_id: int, language: RevisionLanguage) -> None:
        language_id = LanguageTable.save(cursor, language)
        assert(language_id is not None)

        cursor.execute(
            'INSERT INTO word_languages (wordid, languageid) VALUES (?, ?)',
            (word_id, language_id)
        )

        word_lang_id = cursor.lastrowid
        assert(word_lang_id is not None)


        for v in language.getCategories():
            WordLanguagesCategoriesTable.save(cursor, word_lang_id, v)


class CategoryTable(DatabaseTable):
    def __init__(self) -> None:
        super().__init__("category")
        self.setFields({
            "id": TableField("INTEGER", "NOT NULL"),
            "category": TableField("TEXT", "NOT NULL UNIQUE"),
        })

        self.addPrimaryKey("id")

    @staticmethod
    def save(cursor: Cursor, category: str) -> Optional[int]:
        return insert_or_select_id(
            cursor,
            lambda c: c.execute('INSERT INTO category (category) VALUES (?)', (category,)),
            lambda c: c.execute('SELECT id FROM category WHERE category = ?', (category,))
        )


class WordLanguagesCategoriesTable(DatabaseTable):
    """ join table for relating a category to a language """
    def __init__(self) -> None:
        super().__init__("languages_categories")
        self.setFields({
            "id": TableField("INTEGER", "NOT NULL"),
            "wordlangid": TableField("INTEGER", "NOT NULL"),
            "categoryid": TableField("INTEGER", "NOT NULL"),
        })

        self.addPrimaryKey("id")
        self.addForeignKey(["wordlangid"], "word_languages", ["id"])
        self.addForeignKey(["categoryid"], "category", ["id"])

    @staticmethod
    def save(cursor: Cursor, word_language_id: int, category: LanguageCategory) -> None:
        category_id = CategoryTable.save(cursor, category.name)
        cursor.execute('''INSERT INTO languages_categories
(wordlangid, categoryid) VALUES (?, ?)
''',
            (word_language_id, category_id)
        )

        word_language_category_id = cursor.lastrowid
        assert(word_language_category_id is not None)
        for v in category.getSections():
            LanguagesCategorySectionTable.save(
                cursor,
                word_language_category_id,
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
        return insert_or_select_id(
            cursor,
            lambda c: c.execute('INSERT INTO category_section(section) VALUES (?)', (section.name,)),
            lambda c: c.execute('SELECT id FROM category_section WHERE section = ?', (section.name,))
        )


class LanguagesCategorySectionTable(DatabaseTable):
    def __init__(self) -> None:
        super().__init__("languages_category_section")
        self.setFields({
            "id": TableField("INTEGER", "NOT NULL"),
            "wordlangcatid": TableField("INTEGER", "NOT NULL"),
            "sectionid": TableField("INTEGER", "NOT NULL"),
            "data": TableField("TEXT")
        })

        self.addPrimaryKey("id")
        self.addForeignKey(["wordlangcatid"], "word_languages_categories", ["id"])
        self.addForeignKey(["sectionid"], "category_section", ["id"])

    @staticmethod
    def save(cursor: Cursor, word_language_category_id: int, section: CategorySection) -> None:
        section_id = CategorySectionTable.save(cursor, section)
        cursor.execute('''INSERT INTO languages_category_section
(wordlangcatid, sectionid) VALUES (?, ?)
''',
            (word_language_category_id, section_id)
        )

def models() -> list[DatabaseTable]:
    return [
        WordTable(),
        LanguageTable(),
        CategoryTable(),
        CategorySectionTable(),
        WordLanguagesTable(),
        WordLanguagesCategoriesTable(),
        LanguagesCategorySectionTable(),
    ]
