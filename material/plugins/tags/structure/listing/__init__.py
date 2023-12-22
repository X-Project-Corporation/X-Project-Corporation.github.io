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

import posixpath

from collections.abc import Iterator
from material.plugins.tags.structure.mapping import Mapping
from material.plugins.tags.structure.tag import Tag
from mkdocs.structure.pages import Page

from .config import ListingConfig
from .tree import ListingTree

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class Listing:
    """
    A listing of tags.

    Listings can be included on any page by using the `<!-- @tags [args] -->`
    directive. The arguments are passed to a YAML parser, and are expected to
    either be a valid listing configuration, or an dentifier that points to a
    valid listing configuration in the `listings_map` setting in `mkdocs.yml`.
    """

    def __init__(self, page: Page, id: str, config: ListingConfig):
        """
        Initialize the listing.

        Arguments:
            page: The page the listing is embedded in.
            id: The listing identifier.
            config: The listing configuration.
        """
        self.page = page
        self.id = id
        self.config = config
        self.tags = {}

    def __repr__(self) -> str:
        """
        Return a string representation of the listing for debugging.

        Returns:
            String representation.
        """
        return f"Listing({repr(self.page)})"

    def __iter__(self) -> Iterator[ListingTree]:
        """
        Iterate over the listing in pre-order.

        Yields:
            The current listing tree.
        """
        stack = list(reversed(self.tags.values()))
        while stack:
            tree = stack.pop()
            yield tree

            # Visit subtrees in reverse, so pre-order is preserved
            stack += reversed([*tree])

    def __and__(self, mapping: Mapping) -> Iterator[Tag]:
        """
        Iterate over the tags of a mapping featured in the listing.

        When hierarchical tags are used, the set of tags is expanded to include
        all parent tags, but only for the inclusion check. The returned tags are
        always the actual tags of the mapping. This is done to avoid duplicate
        entries in the listing.

        If a mapping features one of the tags excluded from the listing, the
        entire mapping is excluded from the listing. Additionally, if a listing
        should only include tags within the current scope, the mapping is only
        included if the page is a child of the page the listing was found on.

        Arguments:
            mapping: The mapping.

        Yields:
            The current tag.
        """
        assert isinstance(mapping, Mapping)

        # If the listing should only include tags within the current scope, we
        # check if the page is a child of the page the listing is embedded in
        if self.config.scope:
            base = posixpath.dirname(self.page.url)
            if not mapping.item.url.startswith(base):
                return iter([])

            # If the mapping on the same page as the listing, we skip it, as
            # it makes no sense to link to the listing on the same page
            if mapping.item == self.page:
                return iter([])

        # If an exclusion list is given, expand each tag to check if the tag
        # itself or one of its parents is excluded from the listing
        if self.config.exclude:
            if any(mapping & self.config.exclude):
                return iter([])

        # If an inclusion list is given, expand each tag to check if the tag
        # itself or one of its parents is included in the listing
        if self.config.include:
            return mapping & self.config.include

        # Otherwise, we can just return an iterator over the set of tags of the
        # mapping as is, as no expansion is required
        return iter(mapping.tags)

    # -------------------------------------------------------------------------

    page: Page
    """
    The page the listing is embedded in.
    """

    id: str
    """
    The listing identifier.
    """

    config: ListingConfig
    """
    The listing configuration.
    """

    tags: dict[Tag, ListingTree]
    """
    The listing trees, each of which associated with a tag.
    """

    # -------------------------------------------------------------------------

    def add(self, mapping: Mapping, *, hidden = True) -> None:
        """
        Add mapping to listing.

        Mappings are only added to listings, if the listing features tags that
        are also featured in the mapping, and which are not explicitly hidden.

        Arguments:
            mapping: The mapping.
            hidden: Whether to add hidden tags.
        """
        for leaf in self & mapping:
            tree = self.tags

            # Skip if hidden tags should not be rendered
            if not hidden and leaf.hidden:
                continue

            # Iterate over expanded tags
            for tag in reversed([*leaf]):
                if tag not in tree:
                    tree[tag] = ListingTree(tag)

                # If the tag is the leaf, i.e., the actual tag we want to add,
                # we add the mapping to the listing tree's mappings
                if tag == leaf:
                    tree[tag].mappings.append(mapping)

                # Otherwise, we continue traversing the tree
                else:
                    tree = tree[tag].children
