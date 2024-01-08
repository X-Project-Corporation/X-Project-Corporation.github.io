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

from material.plugins.tags.structure.tag import Tag
from material.plugins.tags.structure.tag.reference import TagReference
from mkdocs.structure.nav import Link

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class TestTagReference(unittest.TestCase):
    """
    Test cases for tag reference.
    """

    def test_init(self):
        """
        Should initialize the tag reference.
        """
        link_1 = Link(title = "Link 1", url = "url/1")
        link_2 = Link(title = "Link 2", url = "url/2")

        # Initialize tag reference and perform assertions
        ref = TagReference(Tag("tag"), [link_1, link_2])
        self.assertEqual(ref.name, "tag")
        self.assertEqual(ref.links, [link_1, link_2])

    def test_repr(self):
        """
        Should return a printable representation.
        """
        ref = TagReference(Tag("tag"))
        self.assertIsInstance(repr(ref), str)

    # -------------------------------------------------------------------------

    def test_url(self):
        """
        Should return the URL of the tag reference.
        """
        link_1 = Link(title = "Link 1", url = "url/1")
        link_2 = Link(title = "Link 2", url = "url/2")

        # Initialize tag reference and perform assertions
        ref = TagReference(Tag("tag"), [link_1, link_2])
        self.assertEqual(ref.url, "url/1")

    def test_url_none(self):
        """
        Should return nothing if the tag reference has no associated links.
        """
        ref = TagReference(Tag("tag"))
        self.assertIsNone(ref.url)

    # -------------------------------------------------------------------------

    def test_issubclass(self):
        """
        Should be a subclass of tag.
        """
        self.assertTrue(issubclass(TagReference, Tag))
