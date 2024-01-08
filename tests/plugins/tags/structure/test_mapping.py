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
from material.plugins.tags.structure.tag import Tag
from mkdocs.structure.nav import Link

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class TestMapping(unittest.TestCase):
    """
    Test cases for mapping.
    """

    def test_init(self):
        """
        Should initialize the mapping.
        """
        link = Link(title = "link",  url = "url")
        tags = [Tag("foo"), Tag("bar")]

        # Initialize mapping and perform assertions
        mapping = Mapping(link, tags = tags)
        self.assertEqual(mapping.item, link)
        self.assertEqual(mapping.tags, set(tags))

    def test_init_duplicate_tags(self):
        """
        Should initialize the mapping with duplicate tags.
        """
        link = Link(title = "link",  url = "url")
        tags = [Tag("foo"), Tag("bar"), Tag("bar")]

        # Initialize mapping and perform assertions
        mapping = Mapping(link, tags = tags)
        self.assertEqual(mapping.item, link)
        self.assertEqual(mapping.tags, set(tags))

    def test_repr(self):
        """
        Should return a printable representation of the mapping.
        """
        link = Link(title = "link",  url = "url")
        tags = [Tag("foo"), Tag("bar")]

        # Initialize mapping and perform assertions
        mapping = Mapping(link, tags = tags)
        self.assertIsInstance(repr(mapping), str)

    def test_and(self):
        """
        Should iterate over the tags featured in the mapping.
        """
        link = Link(title = "link",  url = "url")
        parent = Tag("parent")
        tag = Tag("tag", parent = parent)

        # Initialize mapping and perform assertions
        mapping = Mapping(link, tags = [parent, tag])
        self.assertEqual(set(mapping & set([parent])), set([parent, tag]))

    def test_and_expand(self):
        """
        Should iterate over the parent tags featured in the mapping.

        This test ensures that, albeit the tag is expanded and the parent tags
        of a tag are tested, it is always the tag itself that is returned.
        """
        link = Link(title = "link",  url = "url")
        parent = Tag("parent")
        tag = Tag("tag", parent = parent)

        # Initialize mapping and perform assertions
        mapping = Mapping(link, tags = [tag])
        self.assertEqual(set(mapping & set([parent])), set([tag]))
