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

import re

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

    def _add_entry(self, title, text, loc):
        """
        A simple wrapper to add an entry, dropping bad characters.
        """

        # text = text.replace('\u00a0', ' ')
        # text = re.sub(r'[ \t\n\r\f\v]+', ' ', text.strip())
        text = re.sub(r'\n\n+', '\n\n', text).strip()

        self._entries.append({
            'title': title,
            'text': text,
            'location': loc
        })

    # Override to add additional fields for each page
    def add_entry_from_context(self, page):
        index = len(self._entries)
        # super().add_entry_from_context(page)

        ###

        # Create the content parser and feed in the HTML for the
        # full page. This handles all the parsing and prepares
        # us to iterate through it.
        parser = ContentParser()
        parser.feed(page.content)
        parser.close()

        #print(parser.stripped_html)

        # Get the absolute URL for the page, this is then
        # prepended to the urls of the sections
        url = page.url

        # Create an entry for the full page.
        text = parser.stripped_html.rstrip('\n') if self.config['indexing'] == 'full' else ''
        self._add_entry(
            title=page.title,
            text=text,
            loc=url
        )

        if self.config['indexing'] in ['full', 'sections']:
            for section in parser.data:
                self.create_entry_for_section(section, page.toc, url)
        ###

        entry = self._entries[index]

        # Add document tags
        if "tags" in page.meta:
            entry["tags"] = page.meta["tags"]

        # Add document boost for search
        search = page.meta.get("search", {})
        if "boost" in search:
            entry["boost"] = search["boost"]

    def create_entry_for_section(self, section, toc, abs_url):
        """
        Given a section on the page, the table of contents and
        the absolute url for the page create an entry in the
        index
        """

        toc_item = self._find_toc_by_id(toc, section.id)

        text = ''.join(section.text) if self.config['indexing'] == 'full' else ''
        if toc_item is not None:
            self._add_entry(
                title=toc_item.title,
                text=text,
                loc=abs_url + toc_item.url
            )

    # def _add_entry(self, title, text, loc):
    #     """
    #     A simple wrapper to add an entry, dropping bad characters.
    #     """
    #     text = text.replace('\u00a0', ' ')
    #     # text = re.sub(r'[ \t\n\r\f\v]+', ' ', text.strip())
    #     # print(text)
    #     self._entries.append({
    #         'title': title,
    #         'text': text,
    #         'location': loc
    #     })

class ContentSection:
    """
    Used by the ContentParser class to capture the information we
    need when it is parsing the HMTL.
    """

    def __init__(self, text=None, id_=None, title=None):
        self.text = text or []
        self.id = id_
        self.title = title

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

        self.data = []
        self.section = None

        self.is_header_tag = False
        self.is_pre_tag = None
        self.is_script_tag = False

        self._stripped_html = []

    def handle_starttag(self, tag, attrs):
        """Called at the start of every HTML tag."""

        # We only care about the opening tag for headings.
        if tag in ([f"h{x}" for x in range(1, 7)]):
            # We are dealing with a new header, create a new section
            # for it and assign the ID if it has one.
            self.is_header_tag = True
            self.section = ContentSection()
            self.data.append(self.section)

            for attr in attrs:
                if attr[0] == "id":
                    self.section.id = attr[1]

            return

        a = dict(attrs)
        if tag == "a" and a.get("class", None) == "headerlink":
            self.is_script_tag = True
            return

        # OVERRIDE
        # if tag == "div":
        #     self.is_pre_tag = "div"

        # if tag == "ul":
        #     self.is_pre_tag = "ul"

        # if tag == "ol":
        #     self.is_pre_tag = "ol"

        # if tag == "pre":
        #     self.is_pre_tag = "pre"

        # if tag == "code" and not self.is_pre_tag:
        #     self.is_pre_tag = "code"

        self.is_pre_tag = True

        if tag == "script" or tag == "img":
            self.is_script_tag = True
            return

        # if self.is_pre_tag and self.section:
        #     more = ["{}='{}'".format(k, v) for k, v in attrs]
        #     if tag == "pre":
        #         more.append("class=highlight")
        #     self.section.text.append("<{} {}>".format(tag, " ".join(more)))

        if self.section:
            more = ["{}='{}'".format(k, v) for k, v in attrs]
            if tag == "pre":
                more.append("class=highlight")
            self.section.text.append("<{} {}>".format(tag, " ".join(more)))


    def handle_endtag(self, tag):
        """Called at the end of every HTML tag."""

        # We only care about the opening tag for headings.
        if tag in ([f"h{x}" for x in range(1, 7)]):
            self.is_header_tag = False
            return

        if tag == "script" or tag == "img" or (tag == "a" and self.is_script_tag):
            self.is_script_tag = False
            return

        # OVERRIDE
        # if self.is_pre_tag and self.section:
        #     self.section.text.append("</{}>".format(tag))

        if self.section:
            self.section.text.append("</{}>".format(tag))

        # TODO: better use a stack
        if tag == self.is_pre_tag:
            self.is_pre_tag = None

    def handle_data(self, data):
        """
        Called for the text contents of each tag.
        """

        if self.is_script_tag:
            return

        # if self.is_pre_tag:
        #     self._stripped_html.append(escape(data))
        # else:
        #     self._stripped_html.append(data)#

        # TODO: MINIFY HTML!!!

        if self.section is None:
            # This means we have some content at the start of the
            # HTML before we reach a heading tag. We don't actually
            # care about that content as it will be added to the
            # overall page entry in the search. So just skip it.
            return

        # If this is a header, then the data is the title.
        # Otherwise it is content of something under that header
        # section.
        if self.is_header_tag:
            self.section.title = data
        elif self.is_pre_tag:
            self.section.text.append(escape(data))
        else:
            self.section.text.append(data)

    @property
    def stripped_html(self):
        return ''.join(self._stripped_html)
