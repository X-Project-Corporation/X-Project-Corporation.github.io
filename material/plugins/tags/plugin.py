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

from __future__ import annotations

import logging
import os
import re

from material.utilities.filter import PageFilter
from mkdocs.exceptions import PluginError
from mkdocs.plugins import BasePlugin, event_priority
from mkdocs.structure.pages import Page

from .config import TagsConfig
from .renderer import Renderer
from .structure.listing.manager import ListingManager
from .structure.mapping.manager import MappingManager

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

# Tags plugin
class TagsPlugin(BasePlugin[TagsConfig]):
    """
    Tags plugin.
    """

    supports_multiple_instances = True
    """
    This plugin supports multiple instances.

    @docs explain how multiple instances can be used
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialize incremental builds
        self.is_serve = False

        #
        self.mappings = None
        self.listings = None

    # -------------------------------------------------------------------------

    mappings: MappingManager
    """
    Mapping manager.
    """

    listings: ListingManager
    """
    Listing manager.
    """

    filter: PageFilter
    """
    Page filter.
    """

    # -------------------------------------------------------------------------

    def on_startup(self, *, command, dirty):
        self.is_serve = command == "serve"

    def on_config(self, config):
        """
        Initialize tags plugin.
        """
        self.mappings = MappingManager(self.config) # clean up on build error
        self.listings = ListingManager(self.config)

        #
        self.filter = PageFilter(self.config.filters)

        # only if tags or listings are enabled...
        if self.is_serve and self.config.shadow_on_serve:
            self.config.shadow = True

    # Identify tags - run later, so other plugins ot hooks can add tags to
    # metadata automatically @docs
    @event_priority(-50)
    def on_page_markdown(self, markdown, *, page, config, files):
        if not self.config.enabled:
            return

        # Skip if page should not be considered
        if not self.filter(page):
            return

        # Skip if tags should not be built
        if not self.config.tags:
            return

        # @todo: move into function?
        if page.file.src_uri == self.config.tags_file:

            #
            if "[TAGS]" in page.markdown:
                page.markdown = page.markdown.replace(
                    "[TAGS]", "<!-- @tags -->"
                )

            #
            if not re.search(r"<!--\s+@tags", page.markdown):
                page.markdown += "\n<!-- @tags -->"

        if page.file.src_uri in self.config.tags_extra_files:
            tags = self.config.tags_extra_files[page.file.src_uri]
            placeholder = f"<!-- @tags {{ include: [{', '.join(tags)}] }} -->"
            #
            if "[TAGS]" in page.markdown:
                page.markdown = page.markdown.replace(
                    "[TAGS]", placeholder
                )

            if not re.search(r"<!--\s+@tags", page.markdown):
                page.markdown += "\n" + placeholder

        #
        try:
            self.mappings.add(page)

        # Raise exception if tags cannot be read
        except Exception as e:
            docs = os.path.relpath(config.docs_dir)
            path = os.path.relpath(page.file.abs_src_path, docs)
            raise PluginError(
                    f"Error reading tags of page '{path}' in '{docs}':\n"
                    f"{e}"
                )

        # Must register in renderer
        return self.listings.add(page)

    @event_priority(100)
    def on_env(self, env, *, config, files):
        if not self.config.enabled:
            return

        #
        renderer = Renderer(env, config)
        for listing in self.listings:
            self.listings.populate(listing, self.mappings, renderer)

    def on_page_context(self, context, *, page, config, nav):
        if not self.config.enabled:
            return

        # Skip if page should not be considered
        if not self.filter(page):
            return

        # Skip if tags should not be built
        if not self.config.tags:
            return

        # Retrieve tags to render on page with URLs
        mapping = self.mappings.get(page)
        if mapping:
            tags = self.config.tags_name_variable
            context[tags] = self.listings.get_references(mapping)

# -----------------------------------------------------------------------------
# Data
# -----------------------------------------------------------------------------

# Set up logging
log = logging.getLogger("mkdocs.material.plugins.tags")
