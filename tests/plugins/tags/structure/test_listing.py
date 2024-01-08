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

from material.plugins.tags.structure.listing import Listing
from material.plugins.tags.structure.mapping import Mapping
from material.plugins.tags.structure.mapping.manager import MappingManager
from material.plugins.tags.structure.tag import Tag

from tests.helpers import stub_page
from tests.plugins.tags.helpers import (
  stub_listing_config,
  stub_page_with_tags,
  stub_tags_config
)

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class TestListing(unittest.TestCase):
    """
    Test cases for listing.
    """

    def test_init(self):
        """
        Should initialize the listing.
        """
        page = stub_page()
        config = stub_listing_config()

        # Initialize listing and perform assertions
        listing = Listing(page, "foo", config)
        self.assertEqual(listing.page, page)
        self.assertEqual(listing.id, "foo")
        self.assertEqual(listing.config, config)
        self.assertEqual(listing.tags, {})

    def test_repr(self):
        """
        Should return a printable representation of the listing.
        """
        page = stub_page()
        config = stub_listing_config()

        # Initialize listing and perform assertions
        listing = Listing(page, "id", config)
        self.assertIsInstance(repr(listing), str)

    def test_hash(self):
        """
        Should return the hash of the listing.
        """
        page = stub_page()
        config = stub_listing_config()

        # Initialize listing and perform assertions
        listing = Listing(page, "id", config)
        self.assertEqual(hash(listing), hash("id"))

    def test_iter(self):
        """
        Should iterate over the listing in pre-order.
        """
        listing = Listing(
            stub_page(), "id",
            stub_listing_config()
        )

        # Initialize mapping manager and add mappings to listing
        manager = MappingManager(stub_tags_config(tags_hierarchy = True))
        manager.add(stub_page_with_tags(tags = ["foo"]))
        manager.add(stub_page_with_tags(tags = ["foo/bar"]))
        manager.add(stub_page_with_tags(tags = ["qux"]))
        manager.add(stub_page_with_tags(tags = ["foo/baz/qux"]))
        manager.add(stub_page_with_tags(tags = ["foo/baz"]))
        for mapping in manager:
            listing.add(mapping)

        # Iterate over listing and perform assertions
        self.assertEquals(
            list(str(listing.tag) for listing in listing),
            ["foo", "foo/bar", "foo/baz", "foo/baz/qux", "qux"]
        )

    def test_and(self):
        """
        Should iterate over the tags of a mapping featured in the listing.
        """
        listing = Listing(
            stub_page(), "id",
            stub_listing_config()
        )

        # Initialize mapping and perform assertions
        tags = set([Tag("foo"), Tag("bar")])
        mapping = Mapping(stub_page(), tags = tags)
        self.assertEqual(set(listing & mapping), tags)

    def test_and_in_scope(self):
        """
        Should yield if mapping is in scope.
        """
        listing = Listing(
            stub_page(path = "foo.md"), "id",
            stub_listing_config(scope = True)
        )

        # Initialize mapping and perform assertions
        tags = set([Tag("foo"), Tag("bar")])
        mapping = Mapping(stub_page(path = "foo/bar.md"), tags = tags)
        self.assertEqual(set(listing & mapping), tags)

    def test_and_excluded(self):
        """
        Should not yield if mapping features excluded tags.
        """
        listing = Listing(
            stub_page(), "id",
            stub_listing_config(exclude = ["foo"])
        )

        # Initialize mapping and perform assertions
        tags = set([Tag("foo"), Tag("bar")])
        mapping = Mapping(stub_page(), tags = tags)
        self.assertEqual(set(listing & mapping), set())

    def test_and_included(self):
        """
        Should yield if mapping features included tags.
        """
        listing = Listing(
            stub_page(), "id",
            stub_listing_config(include = ["foo"])
        )

        # Initialize mapping and perform assertions
        tags = set([Tag("foo"), Tag("bar")])
        mapping = Mapping(stub_page(), tags = tags)
        self.assertEqual(set(listing & mapping), set([Tag("foo")]))

    def test_and_same_page(self):
        """
        Should not yield if listing and mapping are on the same page.
        """
        listing = Listing(
            stub_page(path = "foo.md"), "id",
            stub_listing_config(scope = True)
        )

        # Initialize mapping and perform assertions
        tags = set([Tag("foo"), Tag("bar")])
        mapping = Mapping(stub_page(path = "foo.md"), tags = tags)
        self.assertEqual(set(listing & mapping), set())

    def test_and_not_in_scope(self):
        """
        Should not yield if mapping is not in scope.
        """
        listing = Listing(
            stub_page(path = "foo.md"), "id",
            stub_listing_config(scope = True)
        )

        # Initialize mapping and perform assertions
        tags = set([Tag("foo"), Tag("bar")])
        mapping = Mapping(stub_page(path = "bar.md"), tags = tags)
        self.assertEqual(set(listing & mapping), set())

    def test_and_not_excluded(self):
        """
        Should yield if mapping doesn't feature excluded tags.
        """
        listing = Listing(
            stub_page(), "id",
            stub_listing_config(exclude = ["qux"])
        )

        # Initialize mapping and perform assertions
        tags = set([Tag("foo"), Tag("bar")])
        mapping = Mapping(stub_page(), tags = tags)
        self.assertEqual(set(listing & mapping), tags)

    def test_and_not_included(self):
        """
        Should not yield if mapping doesn't feature included tags.
        """
        listing = Listing(
            stub_page(), "id",
            stub_listing_config(include = ["qux"])
        )

        # Initialize mapping and perform assertions
        tags = set([Tag("foo"), Tag("bar")])
        mapping = Mapping(stub_page(), tags = tags)
        self.assertEqual(set(listing & mapping), set())

    # -------------------------------------------------------------------------

    def test_add(self):
        """
        Should add mapping to listing.
        """
        listing = Listing(
            stub_page(), "id",
            stub_listing_config()
        )

        # Initialize mapping and perform assertions
        tags = set([Tag("foo"), Tag("bar", hidden = True)])
        mapping = Mapping(stub_page(), tags = tags)
        listing.add(mapping)
        for tag in tags:
            self.assertTrue(tag in listing.tags)

    def test_add_hidden(self):
        """
        Should add mapping with hidden tags to listing.
        """
        listing = Listing(
            stub_page(), "id",
            stub_listing_config()
        )

        # Initialize mapping and perform assertions
        tags = set([Tag("foo"), Tag("bar", hidden = True)])
        mapping = Mapping(stub_page(), tags = tags)
        listing.add(mapping, hidden = False)
        for tag in tags:
            self.assertEquals(tag.hidden, tag not in listing.tags)
