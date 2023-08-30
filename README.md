# WIKIWORDS

_wikitionary -> rdbms_ (only sqlite supported at this time)

> Note: most of this document is copied directly from my .js project that does
> something similar.

## About

This is a .py project (poc of my own earlier attempt with [.js](https://github.com/cpietrzykowski/wikiwords)) that will take a wiktionary archive dump and parse/normalize it into a relational database.


## Why

I wanted a word list (for many reasons), that was; current, expansive, descriptive. I found it frustrating that this data was not anywhere else. Hacker lists, frequency lists, etc. are missing class information and are usually truncated/limited to n-percentile usage.

Wiktionary as a source is huge, and probably as good as any other authority on my native language (english), and maybe any other language. It is constantly updated, a living authority.

If Webster et. al. had a nice manner in which to grep their data I might've gone with one of them.

Now you can make your own lists.

## Caveats

> I am **not** a linguist (I just play one on TV).

- This was only tested with english input, however there should be no reason other input languages would work.
- xml parsing in python is excruciatingly slow (_but_ a huge thanks to `lxml` for making it bearable)

### lxml

[lxml](https://lxml.de/) is an amazing project. Before stumbling on "lxml" I thought I was doing something incomprehensibly wrong with xml parsing in Python. It was excruciatingly slow. For the size of the file it was completely unacceptable, but after some forum and so scouring I was able to find posters with the same concern. Ultimately leading to the "lxml" project.

## Developing

1. setup env
    > python -m venv /path/to/new/virtual/environment
2. activate env
    > source .venv/bin/activate
3. install requirements
    > python -m pip -r requirements.txt install

### Testing

* Run all tests:
    > python -m unittest


https://mypy.readthedocs.io/en/stable/config_file.html#confval-mypy_path

## Usage

1. Go and [download](https://dumps.wikimedia.org/) *pages-meta-current.xml for your language. Note: the dumps contain words for all languages, just the page data is localised. Example:

    > wget --directory-prefix=./out https://dumps.wikimedia.org/enwiktionary/20230801/enwiktionary-20230801-pages-meta-current.xml.bz2

2. Help
    > python src/clip.py --help

3. process all english entries
    > python src/cli.py --language english --sqlite out/words.db mediawiki_archive.xml

### Sample Queries

Dump all words in database:
```
SELECT word.word
FROM word
JOIN revision ON revision.wordid = word.id
JOIN revisions_languages ON revisions_languages.revisionid = revision.id
JOIN language ON language.id = revisions_languages.languageid
JOIN revisions_languages_categories ON revisions_languages_categories.revlangid = revisions_languages.id
JOIN category ON category.id = revisions_languages_categories.categoryid
GROUP BY word.word
ORDER BY word.word ASC
```

## Known Limitations

* parsing of wikitext is _poor_
* there is no frequency data
* storage accuracy of encoded character data has not been exhaustively verified

## TODO

should do, might do, won't do, etc.

* full wiki markdown processing
    * markdown directive processing
* front end and/or api

## Contributing

Feel free to open issues or submit a pull request.