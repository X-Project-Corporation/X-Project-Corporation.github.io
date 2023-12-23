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

from collections.abc import Iterator
from material.plugins.tags.structure.mapping import Mapping
from material.plugins.tags.structure.tag import Tag

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class ListingTree:
    """
    A listing tree.

    Listing trees are a tree structure that represent the hierarchy of tags
    and mappings. Each tree node is a tag, and each tag can have multiple
    mappings. Additionally, each tree can have subtrees, which are typically
    called nested tags.

    This is an internal data structure that is used to render listings. It is
    also the immediate structure that is passed to the template.
    """

    def __init__(self, tag: Tag):
        """
        Initialize listing tree.

        Arguments:
            tag: The tag.
        """
        self.tag = tag
        self.content = None
        self.mappings = []
        self.children = {}

    def __repr__(self) -> str:
        """
        Return a string representation of the listing tree for debugging.

        Returns:
            String representation.
        """
        return _print(self)

    def __iter__(self) -> Iterator[ListingTree]:
        """
        Iterate over subtrees of the listing tree.

        Yields:
            The current subtree.
        """
        return iter(self.children.values())

    # -------------------------------------------------------------------------

    tag: Tag
    """
    The tag.
    """

    content: str | None
    """
    The rendered content of the listing tree.

    This attribute holds the result of rendering the `tag.html` template, which
    is the rendered tag as displayed in the listing. It is essential that this
    is done for all tags (and nested tags) before rendering the tree, as the
    rendering process of the listing tree relies on this attribute.
    """

    mappings: list[Mapping]
    """
    The mappings associated with the tag.
    """

    children: dict[Tag, ListingTree]
    """
    The subtrees of the listing tree.
    """

# -----------------------------------------------------------------------------
# Functions
# -----------------------------------------------------------------------------

def _print(tree: ListingTree, indent: int = 0) -> str:
    """
    Return a string representation of a listing tree for debugging.

    Arguments:
        tree: The listing tree.
        indent: The indentation level.

    Returns:
        String representation.
    """
    lines: list[str] = []
    lines.append(" " * indent + f"ListingTree({repr(tree.tag)})")

    # Print mappings
    for mapping in tree.mappings:
        lines.append(" " * (indent + 2) + repr(mapping))

    # Print subtrees
    for child in tree.children.values():
        lines.append(_print(child, indent + 2))

    # Concatenate everything
    return "\n".join(lines)
