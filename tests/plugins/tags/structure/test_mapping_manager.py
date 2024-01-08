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

from material.plugins.tags.structure.mapping.manager import MappingManager
from material.plugins.tags.structure.tag import Tag
from mkdocs.config.base import ValidationError

from tests.helpers import stub_page
from tests.plugins.tags.helpers import (
  stub_page_with_tags,
  stub_tags_config
)

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class TestMappingManager(unittest.TestCase):
    """
    Test cases for mapping manager.
    """

    def test_init(self):
        """
        Should initialize the mapping manager.
        """
        config = stub_tags_config()
        manager = MappingManager(config)
        self.assertEqual(manager.config, config)

    def test_repr(self):
        """
        Should return a printable representation of the mapping manager.
        """
        manager = MappingManager(stub_tags_config())
        manager.add(stub_page_with_tags(["foo", "bar"]))
        self.assertIsInstance(repr(manager), str)

    def test_iter(self):
        """
        Should iterate over mappings.
        """
        manager = MappingManager(stub_tags_config())
        mapping_1 = manager.add(stub_page_with_tags(["foo"]))
        mapping_2 = manager.add(stub_page_with_tags(["bar"]))
        self.assertEqual(list(manager), [mapping_1, mapping_2])

    # -------------------------------------------------------------------------

    def test_add(self):
        """
        Should add page.
        """
        manager = MappingManager(stub_tags_config())
        page = stub_page_with_tags(["foo", "bar"])

        # Add page and perform assertions
        mapping = manager.add(page)
        self.assertEqual(manager.data[page.url], mapping)
        self.assertEqual(mapping.item, page)
        self.assertEqual(mapping.tags, set([Tag("foo"), Tag("bar")]))

    def test_add_duplicate_tags(self):
        """
        Should add page with deduplicated tags.

        This test ensures that if the author automatically adds tags by using
        the meta plugin or other plugins, tags are always deduplicated.
        """
        manager = MappingManager(stub_tags_config())

        # Add page and perform assertions
        mapping = manager.add(stub_page_with_tags(["foo", "bar", "bar"]))
        self.assertEqual(mapping.tags, set([Tag("foo"), Tag("bar")]))

    def test_add_zero_tags(self):
        """
        Should not add page with zero tags.

        This test ensures that pages that define `tags` in their front matter
        but leave them empty are not added to the mapping.
        """
        manager = MappingManager(stub_tags_config())

        # Add page and perform assertions
        self.assertIsNone(manager.add(stub_page_with_tags([])))

    def test_add_no_tags(self):
        """
        Should not add page with no tags.
        """
        manager = MappingManager(stub_tags_config())

        # Add page and perform assertions
        page = stub_page()
        self.assertIsNone(manager.add(page))

    def test_add_hierarchical_tags(self):
        """
        Should add page with hierarchical tags.

        This test adds a seemingly hierarchical tag, but hierachical tags are
        not enabled. The mapping manager must therefore keep them as-is.
        """
        manager = MappingManager(stub_tags_config())

        # Add page and perform assertions
        mapping = manager.add(stub_page_with_tags(["foo", "foo/bar"]))
        self.assertEqual(mapping.tags, set([Tag("foo"), Tag("foo/bar")]))
        for tag in mapping.tags:
            self.assertIsNone(tag.parent)

    def test_add_shadow_tags(self):
        """
        Should add page with shadow tags.
        """
        manager = MappingManager(stub_tags_config(shadow_tags = ["foo"]))

        # Add page and perform assertions
        mapping = manager.add(stub_page_with_tags(["foo", "foo/bar"]))
        self.assertEqual(mapping.tags, set([Tag("foo"), Tag("foo/bar")]))
        for tag in mapping.tags:
            self.assertEqual(tag.hidden, tag == Tag("foo"))

    def test_add_shadow_tags_prefix(self):
        """
        Should add page with shadow tags by prefix.
        """
        manager = MappingManager(stub_tags_config(shadow_tags_prefix = "foo"))

        # Add page and perform assertions
        mapping = manager.add(stub_page_with_tags(["foo", "foo/bar"]))
        self.assertEqual(mapping.tags, set([Tag("foo"), Tag("foo/bar")]))
        for tag in mapping.tags:
            self.assertTrue(tag.hidden)

    def test_add_shadow_tags_suffix(self):
        """
        Should add page with shadow tags by suffix.
        """
        manager = MappingManager(stub_tags_config(shadow_tags_suffix = "foo"))

        # Add page and perform assertions
        mapping = manager.add(stub_page_with_tags(["foo", "foo/bar"]))
        self.assertEqual(mapping.tags, set([Tag("foo"), Tag("foo/bar")]))
        for tag in mapping.tags:
            self.assertEqual(tag.hidden, tag == Tag("foo"))

    def test_add_throw_if_not_allowed(self):
        """
        Should throw if page features tags that are not allowed.
        """
        manager = MappingManager(stub_tags_config(tags_allowed = ["foo"]))
        with self.assertRaises(ValidationError):
            manager.add(stub_page_with_tags(["foo", "bar"]))

    # -------------------------------------------------------------------------

    def test_get(self):
        """
        Should get mapping for page.
        """
        manager = MappingManager(stub_tags_config())
        page = stub_page_with_tags(["foo", "bar"])

        # Add page and perform assertions
        mapping = manager.add(page)
        self.assertEqual(manager.get(page), mapping)

    def test_get_none(self):
        """
        Should get nothing if page does not have a mapping.
        """
        manager = MappingManager(stub_tags_config())

        # Add page and perform assertions
        page = stub_page_with_tags(["foo", "bar"])
        self.assertIsNone(manager.get(page))

# -----------------------------------------------------------------------------

class TestMappingManagerWithTagHierarchies(unittest.TestCase):
    """
    Test cases for mapping manager with tag hierarchies enabled.
    """

    def test_add_hierarchical_tags(self):
        """
        Should add page with hierarchical tags.

        This test ensures that the mapping manager creates the tag hierarchy,
        e.g., `foo/bar` is expanded into `foo` and `foo/bar`.
        """
        manager = MappingManager(stub_tags_config(tags_hierarchy = True))

        # Add page and perform assertions
        mapping = manager.add(stub_page_with_tags(["foo", "foo/bar"]))
        self.assertEqual(mapping.tags, set([Tag("foo"), Tag("foo/bar")]))
        for tag in mapping.tags:
            if tag == Tag("foo"):
                self.assertIsNone(tag.parent)
            else:
                self.assertEqual(tag.parent, Tag("foo"))

    def test_add_hierarchical_tags_separator(self):
        """
        Should add page with hierarchical tags and configured separator.

        This test ensures that the mapping manager creates the tag hierarchy,
        e.g., `foo|bar` is expanded into `foo` and `foo|bar`.
        """
        manager = MappingManager(stub_tags_config(
            tags_hierarchy = True,
            tags_hierarchy_separator = "|"
        ))

        # Add page and perform assertions
        mapping = manager.add(stub_page_with_tags(["foo", "foo|bar"]))
        self.assertEqual(mapping.tags, set([Tag("foo"), Tag("foo|bar")]))
        for tag in mapping.tags:
            if tag == Tag("foo"):
                self.assertIsNone(tag.parent)
            else:
                self.assertEqual(tag.parent, Tag("foo"))

    def test_add_shadow_tags(self):
        """
        Should add page with shadow tags.

        This test ensures that explicitly listed shadow tags are not expanded,
        e.g., `foo/bar` is not hidden if `foo` is a shadow tag.
        """
        manager = MappingManager(stub_tags_config(
            tags_hierarchy = True,
            shadow_tags = ["foo"]
        ))

        # Add page and perform assertions
        mapping = manager.add(stub_page_with_tags(["foo", "foo/bar"]))
        self.assertEqual(mapping.tags, set([Tag("foo"), Tag("foo/bar")]))
        for tag in mapping.tags:
            self.assertTrue(tag.hidden, tag == Tag("foo"))

    def test_add_shadow_tags_prefix(self):
        """
        Should add page with shadow tags by prefix.

        This test ensures that all tags that have a parent tag that matches the
        shadows tags prefix are marked as hidden, e.g., `foo/bar` for `bar`.
        """
        manager = MappingManager(stub_tags_config(
            tags_hierarchy = True,
            shadow_tags_prefix = "bar"
        ))

        # Add page and perform assertions
        mapping = manager.add(stub_page_with_tags(["foo", "foo/bar"]))
        self.assertEqual(mapping.tags, set([Tag("foo"), Tag("foo/bar")]))
        for tag in mapping.tags:
            self.assertEqual(tag.hidden, tag == Tag("foo/bar"))

    def test_add_shadow_tags_suffix(self):
        """
        Should add page with shadow tags by suffix.

        This test ensures that all tags that have a parent tag that matches the
        shadows tags suffix are marked as hidden, e.g., `foo/bar` for `foo`.
        """
        manager = MappingManager(stub_tags_config(
            tags_hierarchy = True,
            shadow_tags_suffix = "foo"
        ))

        # Add page and perform assertions
        mapping = manager.add(stub_page_with_tags(["foo", "foo/bar"]))
        self.assertEqual(mapping.tags, set([Tag("foo"), Tag("foo/bar")]))
        for tag in mapping.tags:
            self.assertTrue(tag.hidden)
