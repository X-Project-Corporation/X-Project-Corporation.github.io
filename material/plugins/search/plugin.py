# Copyright (c) 2016-2021 Martin Donath <martin.donath@squidfunk.com>

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

from html import escape
from html.parser import HTMLParser
from mkdocs.contrib.search import SearchPlugin as BasePlugin
from mkdocs.contrib.search.search_index import SearchIndex as BaseIndex

# -----------------------------------------------------------------------------
# Class
# -----------------------------------------------------------------------------

# Search plugin with custom search index
class SearchPlugin(BasePlugin):

    # Override to use a custom search index
    def on_pre_build(self, config):
        super().on_pre_build(config)
        self.search_index = SearchIndex(**self.config)

# -----------------------------------------------------------------------------

# Search index with support for additional fields
class SearchIndex(BaseIndex):

    # A simple wrapper to add an entry, dropping bad characters
    def _add_entry(self, title, text, loc):
        self._entries.append({
            'title': title,
            'text': text,
            'location': loc
        })

    # Override to add additional fields for each page
    def add_entry_from_context(self, page):
        """
        Create a set of entries in the index for a page. One for
        the page itself and then one for each of its' heading
        tags.
        """

        # Create the content parser and feed in the HTML for the
        # full page. This handles all the parsing and prepares
        # us to iterate through it.
        parser = ContentParser()
        parser.feed(page.content)
        parser.close()

        # Get the absolute URL for the page, this is then
        # prepended to the urls of the sections
        url = page.url
        if self.config['indexing'] in ['full', 'sections']:
            for section in parser.data:
                self.create_entry_for_section(section, page.toc, url, page)

    def create_entry_for_section(self, section, toc, abs_url, page):
        """
        Given a section on the page, the table of contents and
        the absolute url for the page create an entry in the
        index
        """

        toc_item = self._find_toc_by_id(toc, section.id)

        # TODO: always use full indexing...
        text = ''.join(section.text).strip()
        # TODO: when literal h1, h2 etc are used, this won't work
        if toc_item is not None and section.tag != "h1":
            self._add_entry(
                title="".join(section.title),
                text=text,
                loc=abs_url + toc_item.url
            )
        else:
            # this is a whole page entry!
            self._add_entry(
                title=page.title,
                text=text,
                loc=abs_url
            )

        # Add document tags
        entry = self._entries[len(self._entries) - 1] # TODO: too hacky
        if "tags" in page.meta:
            entry["tags"] = page.meta["tags"]

        # Add document boost for search
        search = page.meta.get("search", {})
        if "boost" in search:
            entry["boost"] = search["boost"]

class ContentSection:
    """
    Used by the ContentParser class to capture the information we
    need when it is parsing the HMTL.
    """

    def __init__(self, tag, text=None, id_=None, title=None):
        self.text = text or []
        self.id = id_
        self.title = title or []
        self.tag = tag

    def __eq__(self, other):
        return (
            self.text == other.text and
            self.id == other.id and
            self.title == other.title
        )

class ContentParser(HTMLParser):
    """
    Given a block of HTML, group the content under the preceding
    heading tags which can then be used for creating an index
    for that section.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Tags to skip (i.e. to not include contents in index)
        self.skip = set([
            "img",
            "object",
            "script",
            "style"
        ])

        # Tags to keep
        self.keep = set([
            "code",
            "li",
            "ol",
            "p",
            "pre",
            "ul",
            # "table",
            # "td",
            # "th",
            # "tr"
        ])

        self.context = []
        self.section = None

        self.data = []

    # Called at the start of every HTML tag
    def handle_starttag(self, tag, attrs):
        self.context.append(tag)

        # Handle headings
        if tag in ([f"h{x}" for x in range(1, 7)]):
            self.section = ContentSection(tag)
            self.data.append(self.section)

            # Set identifier on section for TOC resolution
            for attr in attrs:
                if attr[0] == "id":
                    self.section.id = attr[1]
                    break

        # Handle preface to headings - ensure top-level section
        if not self.section:
            self.section = ContentSection("h1")
            self.data.append(self.section)

        # Render opening tag if kept
        if tag in self.keep:
            text = self.section.text
            if self.section.tag in self.context:
                text = self.section.title

            # Append to section title or text
            text.append("<{}>".format(tag))

    # Called at the end of every HTML tag
    def handle_endtag(self, tag):
        if self.context[-1] == tag:
            self.context.pop()

        # Render closing tag if kept
        if tag in self.keep:
            text = self.section.text
            if self.section.tag in self.context:
                text = self.section.title

            # Append to section title or text
            text.append("</{}>".format(tag))

    # Called for the text contents of each tag.
    def handle_data(self, data):
        if self.skip.intersection(self.context):
            return

        # Collapse whitespace in non-pre contexts
        if not "pre" in self.context:
            if not data.isspace():
                data = data.replace("\n", " ")
            else:
                data = " "

        # Ignore section headline
        if self.section.tag in self.context:
            if not "a" in self.context:
                self.section.title.append(escape(data, quote = False))

        # Handle everything else
        else:
            self.section.text.append(escape(data, quote = False))
