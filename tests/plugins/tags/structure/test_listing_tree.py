# Copyright (c) 2016-2024 Martin Donath <martin.donath@squidfunk.com>

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

import unittest

from material.plugins.tags.structure.mapping import Mapping
from material.plugins.tags.structure.listing.tree import ListingTree
from material.plugins.tags.structure.tag import Tag

from tests.helpers import stub_page

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class TestListingTree(unittest.TestCase):
    """
    Test cases for listing tree.
    """

    def test_init(self):
        """
        Should initialize the listing tree.
        """
        tree = ListingTree(Tag("tag"))
        self.assertEqual(tree.tag, Tag("tag"))
        self.assertEqual(tree.content, None)
        self.assertEqual(tree.mappings, [])
        self.assertEqual(tree.children, {})

    def test_repr(self):
        """
        Should return a printable representation of the tag.
        """
        tree = ListingTree(Tag("foo"))
        tree.mappings.append(Mapping(stub_page()))
        tree.children.setdefault(Tag("bar"), ListingTree(Tag("bar")))
        self.assertIsInstance(repr(tree), str)

    def test_hash(self):
        """
        Should return the hash of the listing tree.
        """
        tree = ListingTree(Tag("tag"))
        self.assertEqual(hash(tree), hash("tag"))

    def test_iter(self):
        """
        Iterate over subtrees of the listing tree.
        """
        tree = ListingTree(Tag("tag"))
        for tag in [Tag("foo"), Tag("bar")]:
            tree.children[tag] = ListingTree(tag)

        # Iterate over subtrees and perform assertions
        self.assertEqual(list(tree), [
            ListingTree(Tag("foo")),
            ListingTree(Tag("bar")),
        ])

    def test_eq(self):
        """
        Should check if the listing tree is equal to another listing tree.
        """
        parent = ListingTree(Tag("parent"))
        tag = ListingTree(Tag("tag", parent = parent))
        self.assertTrue(parent == ListingTree(Tag("parent")))
        self.assertTrue(parent != tag)

    def test_lt(self):
        """
        Should check if the listing tree is less than another listing tree.
        """
        parent = ListingTree(Tag("parent"))
        tag = ListingTree(Tag("tag", parent = parent))
        self.assertTrue(parent < tag)
        self.assertTrue(tag >= parent)

