# Copyright (c) 2016-2023 Martin Donath <martin.donath@squidfunk.com>

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

from copy import copy
from markdown import Markdown
from mkdocs.config import config_options as opt
from mkdocs.config.base import Config
from mkdocs.plugins import BasePlugin

# -----------------------------------------------------------------------------
# Class
# -----------------------------------------------------------------------------

# Typeset plugin configuration scheme
class TypesetPluginConfig(Config):
    enabled = opt.Type(bool, default = True)

# -----------------------------------------------------------------------------

# Typeset plugin
class TypesetPlugin(BasePlugin[TypesetPluginConfig]):

    # Initialize plugin
    def on_config(self, config):
        if not self.config.enabled:
            return

        # Initialize titles
        self.title_map = dict()

        # Copy configuration and enable 'toc' extension
        mdx_configs        = copy(config.mdx_configs)
        mdx_configs["toc"] = copy(mdx_configs.get("toc", {}))

        # Ensure that headlines do not contain any links
        mdx_configs["toc"]["anchorlink"] = False
        mdx_configs["toc"]["permalink"]  = False

        # Create Markdown renderer and convert headlines
        self.markdown = Markdown(
            extensions = config.markdown_extensions,
            extension_configs = mdx_configs
        )

    # Extract source of page title before it's lost
    def on_pre_page(self, page, *, config, files):
        if not self.config.enabled:
            return

        # Check if page title was set in configuration
        if page.title:
            path = page.file.src_uri
            self.title_map[path] = "config"

    # Extract typeset content for headlines
    def on_page_content(self, html, *, page, config, files):
        if not self.config.enabled:
            return

        # Ensure to re-render headlines only
        html = self.markdown.convert("\n".join([
            line for line in page.markdown.split("\n")
                if line.startswith("#")
        ]))

        # Find id, typeset content and level for each headline
        expr = re.compile(
            r"id=\"([^\"]+).*?>(.*?)<\/h(\d)",
            re.IGNORECASE | re.MULTILINE
        )

        # Check if page title was set in metadata
        path = page.file.src_uri
        if path not in self.title_map:
            if "title" in page.meta:
                self.title_map[path] = "meta"

        # Flatten anchors and map to headlines
        anchors = _flatten(page.toc.items)
        for (id, title, level) in expr.findall(html):
            if id not in anchors:
                continue

            # Assign headline content to anchor
            anchors[id].typeset = { "title": title }
            if path not in self.title_map:

                # Assign first top-level headline to page
                if not hasattr(page, "typeset") and int(level) == 1:
                    page.typeset = anchors[id].typeset
                    page.title = re.sub(r"<[^>]+>", "", title)

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

# Flatten a tree of anchors
def _flatten(items):
    anchors = dict()
    for item in items:
        anchors[item.id] = item

        # Recursively expand children
        if item.children:
            anchors.update(_flatten(item.children))

    # Return anchors
    return anchors
