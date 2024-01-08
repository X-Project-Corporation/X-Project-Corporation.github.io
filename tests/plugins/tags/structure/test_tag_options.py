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
from material.plugins.tags.structure.tag.options import TagSet
from mkdocs.config.base import ValidationError

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class TestTagSet(unittest.TestCase):
    """
    Test cases for tag set setting.
    """

    def test_init(self):
        """
        Should initialize the setting.
        """
        setting = TagSet()
        self.assertEqual(setting.allowed, set())

    def test_init_allowed_tags(self):
        """
        Should initialize the setting with allowed tags.
        """
        allowed = set([Tag("foo")])
        setting = TagSet(allowed = allowed)
        self.assertEqual(setting.allowed, allowed)

    # -------------------------------------------------------------------------

    def test_validate(self):
        """
        Should return set of tags.
        """
        setting = TagSet()
        self.assertEqual(
            setting.validate(["foo", "bar"]),
            set([Tag("foo"), Tag("bar")])
        )

    def test_validate_empty(self):
        """
        Should return empty set of tags when nothing is given.
        """
        setting = TagSet()
        self.assertEqual(setting.validate(None), set())

    def test_validate_throw_if_invalid_type(self):
        """
        Should throw if value is not a supported type.
        """
        setting = TagSet()
        with self.assertRaises(ValidationError):
            setting.validate("foo")

    def test_validate_throw_if_invalid_item_type(self):
        """
        Should throw if value is not a supported item type.
        """
        setting = TagSet()
        with self.assertRaises(ValidationError):
            setting.validate([{}])

    def test_validate_throw_if_not_allowed(self):
        """
        Should throw if value is not in allowed tags.
        """
        setting = TagSet(allowed = set([Tag("foo")]))
        with self.assertRaises(ValidationError):
            setting.validate(["bar"])
