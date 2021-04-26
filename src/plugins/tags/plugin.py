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

from collections import defaultdict
from mkdocs.structure.files import File
from mkdocs.plugins import BasePlugin
from mkdocs.config.config_options import Type

# -----------------------------------------------------------------------------
# Class
# -----------------------------------------------------------------------------

# Tags plugin
class TagsPlugin(BasePlugin):

    # Configuration scheme
    config_scheme = (
        ("index", Type(str, required = False)),
    )

    # Initialize plugin
    def __init__(self):
        self.tags = defaultdict(list)
        self.tags_file = None

    # Hack: second pass for index page
    def on_files(self, files, config, **kwargs):
        if self.config.get("index"):
            self.tags_file = files.get_file_from_path(self.config.get("index"))
            files.append(self.tags_file)

    # Build inverted index and render index page
    def on_page_markdown(self, markdown, page, **kwargs):
        if "tags" in page.meta:
            for tag in page.meta["tags"]:
                self.tags[tag].append(page)

        # Render tags index page
        if page.file == self.tags_file:
            return self._render(markdown)

    # Render tags inside given Markdown source
    def _render(self, markdown):
        if not markdown.find("[TAGS]"):
            markdown += "\n[TAGS]"

        # Render tags and inject into placeholder in Markdown source
        tags = [self._render_tag(*args) for args in self.tags.items()]
        return markdown.replace("[TAGS]", "\n".join(tags))

    # Render the given tag and links to all pages with occurrences
    def _render_tag(self, tag, pages):
        content = ["## <span class=\"md-tag\">{}</span>".format(tag), ""]
        for page in pages:
            url = page.file.url_relative_to(self.tags_file)
            content.append("- [{}]({})".format(page.title, url))

        # Return Markdown source
        return "\n".join(content)
