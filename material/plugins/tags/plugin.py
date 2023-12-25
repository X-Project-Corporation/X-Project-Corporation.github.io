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

from jinja2 import Environment
from material.utilities.filter import PageFilter
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.exceptions import PluginError
from mkdocs.plugins import BasePlugin, event_priority
from mkdocs.structure.pages import Page
from mkdocs.utils.templates import TemplateContext

from .config import TagsConfig
from .renderer import Renderer
from .structure.listing.manager import ListingManager
from .structure.mapping.manager import MappingManager
from .structure.mapping.serializer import MappingSerializer

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class TagsPlugin(BasePlugin[TagsConfig]):
    """
    A tags plugin.

    This plugin collects tags from the front matter of pages, and builds a tag
    structure from them. The tag structure can be used to render tag listings
    on pages, or to just create a site-wide tags index and export all tags and
    mappings to a JSON file for consumption in another project.
    """

    supports_multiple_instances = True
    """
    This plugin supports multiple instances.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the plugin.
        """
        super().__init__(*args, **kwargs)

        # Initialize incremental builds
        self.is_serve = False

        # Initialize mapping and listing managers
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

    def on_startup(self, *, command, **kwargs) -> None:
        """
        Determine whether we're serving the site.

        Arguments:
            command: The command that is being executed.
            dirty: Whether dirty builds are enabled.
        """
        self.is_serve = command == "serve"

    def on_config(self, *args) -> None:
        """
        Create mapping and listing managers.

        Arguments:
            config: The MkDocs configuration.
        """
        self.mappings = MappingManager(self.config)
        self.listings = ListingManager(self.config)

        # Initialize page filter - the page filter can be used to include or
        # exclude entire subsections of the documentation, allowing for using
        # multiple instances of the plugin alongside each other
        self.filter = PageFilter(self.config.filters)

        # If the author only wants to extract and export mappings, we allow to
        # disable the rendering of all tags and listings with a single setting
        if self.config.export_only:
            self.config.tags = False
            self.config.listings = False

        # By default, shadow tags are rendered when the documentation is served,
        # but not when it is built, for a better user experience
        if self.is_serve and self.config.shadow_on_serve:
            self.config.shadow = True

    @event_priority(-50)
    def on_page_markdown(
        self, markdown: str, *, page: Page, config: MkDocsConfig, **kwargs
    ) -> str:
        """
        Collect tags and listings from page.

        Priority: -50 (run later)

        Arguments:
            markdown: The page's Markdown.
            page: The page.
            config: The MkDocs configuration.

        Returns:
            The page's Markdown with injection points.
        """
        if not self.config.enabled:
            return

        # Skip if page should not be considered
        if not self.filter(page):
            return

        # Handle deprecation of `tags_file` setting
        if self.config.tags_file:
            self._handle_deprecated_tags_file(page)

        # Handle deprecation of `tags_extra_files` setting
        if self.config.tags_extra_files:
            self._handle_deprecated_tags_extra_files(page)

        # Collect tags from page
        try:
            self.mappings.add(page)

        # Raise exception if tags could not be read
        except Exception as e:
            docs = os.path.relpath(config.docs_dir)
            path = os.path.relpath(page.file.abs_src_path, docs)
            raise PluginError(
                    f"Error reading tags of page '{path}' in '{docs}':\n"
                    f"{e}"
                )

        # Collect listings from page
        return self.listings.add(page)

    @event_priority(100)
    def on_env(
        self, env: Environment, *, config: MkDocsConfig, **kwargs
    ) -> None:
        """
        Populate listings.

        Priority: 100 (run earliest)

        Arguments:
            env: The Jinja environment.
            config: The MkDocs configuration.
        """
        if not self.config.enabled:
            return

        # Populate and render all listings
        self.listings.populate_all(self.mappings, Renderer(env, config))

        # Export mappings to file, if enabled
        if self.config.export:
            path = os.path.join(config.site_dir, self.config.export_file)
            path = os.path.normpath(path)

            # Serialize mappings and save to file
            serializer = MappingSerializer(self.config)
            serializer.save(path, self.mappings)

    def on_page_context(
        self, context: TemplateContext, *, page: Page, **kwargs
    ) -> None:
        """
        Add tag references to page context.

        Arguments:
            context: The template context.
            page: The page.
        """
        if not self.config.enabled:
            return

        # Skip if page should not be considered
        if not self.filter(page):
            return

        # Skip if tags should not be built
        if not self.config.tags:
            return

        # Retrieve tags references for page
        mapping = self.mappings.get(page)
        if mapping:
            tags = self.config.tags_name_variable
            if tags not in context:
                context[tags] = list(self.listings & mapping)

    # -------------------------------------------------------------------------

    def _handle_deprecated_tags_file(self, page: Page) -> None:
        """
        Handle deprecation of `tags_file` setting.

        Arguments:
            page: The page.
        """
        directive = self.config.listings_directive
        if page.file.src_uri != self.config.tags_file:
            return

        # Try to find the legacy tags marker and replace with directive
        if "[TAGS]" in page.markdown:
            page.markdown = page.markdown.replace(
                "[TAGS]", f"<!-- {directive} -->"
            )

        # Try to find the directive and add it if not present
        pattern = r"<!--\s+{directive}".format(directive = directive)
        if not re.search(pattern, page.markdown):
            page.markdown += f"\n<!-- {directive} -->"

    def _handle_deprecated_tags_extra_files(self, page: Page) -> None:
        """
        Handle deprecation of `tags_extra_files` setting.

        Arguments:
            page: The page.
        """
        directive = self.config.listings_directive
        if page.file.src_uri not in self.config.tags_extra_files:
            return

        # Compute tags to render on page
        tags = self.config.tags_extra_files[page.file.src_uri]
        if tags:
            directive += f" {{ include: [{', '.join(tags)}] }}"

        # Try to find the legacy tags marker and replace with directive
        if "[TAGS]" in page.markdown:
            page.markdown = page.markdown.replace(
                "[TAGS]", f"<!-- {directive} -->"
            )

        # Try to find the directive and add it if not present
        pattern = r"<!--\s+{directive}".format(directive = directive)
        if not re.search(pattern, page.markdown):
            page.markdown += f"\n<!-- {directive} -->"

# -----------------------------------------------------------------------------
# Data
# -----------------------------------------------------------------------------

# Set up logging
log = logging.getLogger("mkdocs.material.plugins.tags")
