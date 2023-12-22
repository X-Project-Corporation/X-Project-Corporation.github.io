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

from collections.abc import Iterable
from material.plugins.tags.config import TagsConfig
from material.plugins.tags.structure.listing.tree import ListingTree
from material.plugins.tags.structure.mapping import Mapping
from material.plugins.tags.structure.tag import Tag

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class ListingHelper:
    """
    A listing helper.
    """

    def __init__(self, config: TagsConfig):
        """
        Initialize listing helper.

        Arguments:
            config: The configuration.
        """
        self.config = config

    # -------------------------------------------------------------------------

    config: TagsConfig
    """
    The configuration.
    """

    # -------------------------------------------------------------------------

    def sort_listings(
        self, mappings: Iterable[Mapping]
    ) -> list[Mapping]:
        """
        Sort listings.

        Arguments:
            mappings: The mappings.

        Returns:
            The listing, sorted.
        """
        return sorted(
            mappings,
            key = self.config.listings_sort_by,
            reverse = self.config.listings_sort_reverse
        )

    def sort_listing_tags(
        self, tags: dict[Tag, ListingTree]
    ) -> dict[Tag, ListingTree]:
        """
        Sort listing tags.

        Arguments:
            tags: The listing trees, each of which associated with a tag.

        Returns:
            The listing trees, sorted.
        """
        return dict(sorted(
            tags.items(),
            key = lambda item: self.config.listings_tags_sort_by(*item),
            reverse = self.config.listings_tags_sort_reverse
        ))

    def sort_tags(
        self, tags: Iterable[Tag]
    ) -> list[Tag]:
        """
        Sort tags.

        Arguments:
            tags: The listing trees, each of which associated with a tag.

        Returns:
            The listing trees, sorted.
        """
        return sorted(
            tags,
            key = self.config.tags_sort_by,
            reverse = self.config.tags_sort_reverse
        )

    def slugify(self, tag: Tag) -> str:
        return self.config.tags_slugify_format.format(
            slug = self.config.tags_slugify(
                tag.name.replace(
                    self.config.tags_hierarchy_separator,
                    self.config.tags_slugify_separator
                ),
                self.config.tags_slugify_separator
            )
        )
