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

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class TestTag(unittest.TestCase):
    """
    Test cases for tag.
    """

    def test_init(self):
        """
        Should initialize the tag.
        """
        tag = Tag("tag")
        self.assertEqual(tag.name, "tag")
        self.assertEqual(tag.parent, None)
        self.assertEqual(tag.hidden, False)

    def test_repr(self):
        """
        Should return a printable representation of the tag.
        """
        tag = Tag("tag")
        self.assertIsInstance(repr(tag), str)

    def test_str(self):
        """
        Should return a string representation of the tag.
        """
        tag = Tag("tag")
        self.assertEqual(str(tag), "tag")

    def test_hash(self):
        """
        Should return the hash of the tag.
        """
        tag = Tag("tag")
        self.assertEqual(hash(tag), hash("tag"))

    def test_iter(self):
        """
        Should iterate over the tag and its parent tags.
        """
        parent = Tag("parent")
        tag = Tag("tag", parent = parent)
        self.assertEqual(list(tag), [tag, parent])

    def test_contains(self):
        """
        Should check if the tag contains another tag.
        """
        parent = Tag("parent")
        tag = Tag("tag", parent = parent)
        self.assertTrue(tag not in parent)
        self.assertTrue(parent in tag)

    def test_eq(self):
        """
        Should check if the tag is equal to another tag.
        """
        parent = Tag("parent")
        tag = Tag("tag", parent = parent)
        self.assertTrue(parent == Tag("parent"))
        self.assertTrue(parent != tag)

    def test_lt(self):
        """
        Should check if the tag is less than another tag.
        """
        parent = Tag("parent")
        tag = Tag("tag", parent = parent)
        self.assertTrue(parent < tag)
        self.assertTrue(tag >= parent)
