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
import posixpath
import re
import yaml

from collections.abc import Iterable, Iterator
from material.plugins.tags.config import TagsConfig
from material.plugins.tags.renderer import Renderer
from material.plugins.tags.structure.listing import Listing, ListingConfig
from material.plugins.tags.structure.mapping import Mapping
from material.plugins.tags.structure.tag import Tag
from material.plugins.tags.structure.tag.reference import TagReference
from mkdocs.exceptions import PluginError
from mkdocs.structure.pages import Page
from mkdocs.structure.nav import Link
from re import Match

from .anchors import populate
from .helper import ListingHelper

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class ListingManager:
    """
    A listing manager.
    """

    def __init__(self, config: TagsConfig):
        """
        Initialize listing manager.

        Arguments:
            config: The configuration.
            renderer: The renderer.
        """
        self.config = config
        self.helper = ListingHelper(config)
        self.data = set()

    def __iter__(self) -> Iterator[Listing]:
        """
        Iterate over listings.

        Yields:
            The current listing.
        """
        return iter(self.data)

    # -------------------------------------------------------------------------

    config: TagsConfig
    """
    The configuration.
    """

    helper: ListingHelper
    """
    The listing helper.
    """

    data: set[Listing]
    """
    The listings.
    """

    # -------------------------------------------------------------------------

    def add(self, page: Page) -> str:
        """
        Add page.

        This method is called by the tags plugin to retrieve all listings of a
        page. It will parse the page's Markdown and add injections points into
        the page's Markdown, which will be replaced by the renderer with the
        actual listing later on.

        Note that this method is intended to be called with the page during the
        `on_page_markdown` event, as it will modify the page's Markdown.

        Arguments:
            page: The page.

        Returns:
            The page's Markdown with injection points.
        """
        assert isinstance(page.markdown, str)

        # Replace callback
        def replace(match: Match):
            config = self._resolve(page, match.group(2))

            # Compute listing identifier - as the author might include multiple
            # listings on a single page, we must make sure that the identifier
            # is unique, so we use the page source file path and the position
            # of the match within the page as an identifier.
            id = f"{page.file.src_uri}:{match.start()}-{match.end()}"
            self.data.add(Listing(page, id, config))

            # Replace tags marker with h6 headline
            return f"###### {id}/name {{ #{id}/slug }}"

        # Hack: replace tags markers with a h6 headline to mark the injection
        # point for the anchor links we will generate after parsing all pages.
        # By using a h6 headline, we can make sure that the injection point
        # will always be a child of the preceding headline.
        directive = self.config.listings_directive
        return re.sub(
            r"(<!--\s*?{directive}(.*?)\s*-->)".format(directive = directive),
            replace, page.markdown, flags = re.I | re.M | re.S
        )

    def populate(
        self, listing: Listing, mappings: Iterable[Mapping], renderer: Renderer
    ) -> None:
        """
        Populate listing with tags featured in the mappings.

        This method is called by the tags plugin to populate the given listing
        with the given mappings. It will also remove the injection points from
        the page's Markdown. Note that this method is intended to be called
        during the `on_env` event, after all pages have been rendered.

        Arguments:
            listing: The listing.
            mappings: The mappings.
            renderer: The renderer.
        """
        page = listing.page
        assert isinstance(page.content, str)

        # Add mappings to listing, respecting shadow tag configuration
        for mapping in mappings:
            listing.add(mapping, hidden = listing.config.shadow)

        # Sort listings and tags - we can only do this after all mappings have
        # been added to the listing, because the tags inside the mappings do
        # not have a proper order yet, and we need to order them by the settings
        # as specified in the configuration.
        listing.tags = self.helper.sort_listing_tags(listing.tags)

        # Render tags for listing headlines
        name = os.path.join(listing.config.layout, "tag.html")
        for tree in listing:
            tree.content = renderer.render(page, name, tag = tree.tag)

            # Sort the mappings and tags of a listing
            tree.mappings = self.helper.sort_listings(tree.mappings)
            tree.children = self.helper.sort_listing_tags(tree.children)

        # Replace callback
        def replace(match: Match):
            hx = match.group()

            # Populate listing with anchor links to tags
            anchors = populate(listing, self.helper.slugify)
            if not anchors:
                return

            # Get reference to first tag in listing
            head = next(iter(anchors.values()))

            # Replace h6 with actual level of listing and listing ids with
            # placeholders to create a format string for the headline
            hx = re.sub(r"<(/?)h6\b", r"<\g<1>h{}".format(head.level), hx)
            hx = re.sub(
                r"{id}\/(\w+)".format(id = listing.id),
                r"{\1}", hx, flags = re.I | re.M
            )

            # Render listing headlines - this is recursive
            for tree in listing:
                tree.content = hx.format(
                    slug = anchors[tree.tag].id,
                    name = tree.content
                )

            # Render listing
            name = os.path.join(listing.config.layout, "listing.html")
            return "\n".join([
                renderer.render(page, name, listing = tree)
                    for tree in listing.tags.values()
            ])

        # Hack: replace injection points (h6 headlines) we added when parsing
        # the page's Markdown with the actual listing content. Additionally,
        # replace anchor links in the table of contents with the hierarchy
        # generated from mapping over the listing.
        page.content = re.sub(
            r"<h6[^>]+{id}.*?</h6>".format(id = f"{listing.id}/slug"),
            replace, page.content, flags = re.I | re.M
        )

    def get(self, mapping: Mapping) -> list[Listing]:
        """
        Get listings for a mapping.

        Listings are sorted by closeness to the given page, i.e. the number of
        common path components. This is useful for hierarchical listings, where
        the tags of a page link to the closest listing featuring that tag, with
        the option to show all listings featuring that tag.

        Arguments:
            mapping: The mapping.

        Returns:
            The listings.
        """

        # Retrieve listings featuring tags of mapping
        listings: list[Listing] = []
        for listing in self.data:
            if any(listing & mapping):
                listings.append(listing)

        # Rank listings by closeness to mapping
        listings.sort(
            key = lambda listing: self._rank(mapping, listing),
            reverse = True
        )

        # Return listings
        return listings

    def get_references(self, mapping: Mapping) -> list[TagReference]:
        """
        Get tag references for a mapping.

        Arguments:
            mapping: The mapping.

        Returns:
            The tag references.
        """
        tags: dict[Tag, TagReference] = {}
        for listing in self.get(mapping):

            # @todo: find a better method to check tags
            for tag in listing & mapping:
                if tag not in tags:
                    tags[tag] = TagReference(tag)

                # @todo move link generation into extra function
                tags[tag].links.append(Link(
                    listing.page.title,
                    "#".join([
                        listing.page.url or ".",
                        self.helper.slugify(tag)
                    ])
                ))

        # Add missing tag references
        for tag in mapping.tags:
            if tag not in tags:
                tags[tag] = TagReference(tag)


        # Sort and return tags
        return self.helper.sort_tags(tags.values())

    # -------------------------------------------------------------------------

    def _resolve(self, page: Page, args: str) -> ListingConfig:
        """
        Resolve listing configuration.

        Arguments:
            page: The page the listing in embedded in.
            args: The arguments, as parsed from Markdown.

        Returns:
            The listing configuration.
        """
        data = yaml.safe_load(args)
        path = page.file.abs_src_path

        # Try to resolve available listing configuration
        if isinstance(data, str):
            config = self.config.listings_map.get(data, None)
            if not config:
                keys = ", ".join(self.config.listings_map.keys())
                raise PluginError(
                    f"Couldn't find listing configuration: {data}. Available "
                    f"configurations: {keys}"
                )

        # Otherwise, parse listing configuration
        else:
            config = ListingConfig(config_file_path = path)
            config.load_dict(data or {})

            # Validate listing configuration
            errors, warnings = config.validate()
            for _, w in warnings:
                path = os.path.relpath(path)
                log.warning(
                    f"Error reading listing configuration in '{path}':\n"
                    f"{w}"
                )
            for _, e in errors:
                path = os.path.relpath(path)
                raise PluginError(
                    f"Error reading listing configuration in '{path}':\n"
                    f"{e}"
                )

        # Inherit shadow configuration, if not set
        if not isinstance(config.shadow, bool):
            config.shadow = self.config.shadow

        # Inherit layout configuration, if not set
        if not isinstance(config.layout, str):
            config.layout = self.config.listings_layout

        # Return listing configuration
        return config

    def _rank(self, mapping: Mapping, listing: Listing) -> int:
        """
        Rank listing according to listing closeness.

        Arguments:
            mapping: The mapping.
            listing: The listing.

        Returns:
            The rank.
        """
        return len(posixpath.commonpath([
            mapping.item.url,
            listing.page.url
        ]))

# -----------------------------------------------------------------------------
# Data
# -----------------------------------------------------------------------------

# Set up logging
log = logging.getLogger("mkdocs.material.plugins.tags")
