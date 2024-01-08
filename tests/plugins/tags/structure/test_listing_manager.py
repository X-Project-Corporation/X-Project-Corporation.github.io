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

from material.plugins.tags.structure.listing.manager import ListingManager

from tests.plugins.tags.helpers import (
  stub_page_with_listing,
  stub_tags_config
)

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class TestListingManager(unittest.TestCase):
    """
    Test cases for listing manager.
    """

    def test_init(self):
        """
        Should initialize the listing manager.
        """
        config = stub_tags_config()
        manager = ListingManager(config)
        self.assertEqual(manager.config, config)

    def test_repr(self):
        """
        Should return a printable representation of the listing manager.
        """
        manager = ListingManager(stub_tags_config())
        manager.add(stub_page_with_listing(include = ["foo"]))
        self.assertIsInstance(repr(manager), str)

    # @todo: add missing test cases
