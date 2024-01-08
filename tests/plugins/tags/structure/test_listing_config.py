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
import yaml

from material.plugins.tags.structure.listing.config import ListingConfig

from tests.plugins.tags.helpers import stub_listing_config

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class TestListingConfig(unittest.TestCase):
    """
    Test cases for listing configuration.
    """

    def test_init(self):
        """
        Should initialize the listing configuration.

        This test ensures that the listing configuration defines sane defaults,
        so the author can initialize the configuration without any arguments.
        It is essentially only a safety net for us, so that we don't start
        requiring arguments for the configuration in the future.
        """
        config = ListingConfig()
        self.assertEqual(config.validate(), ([], []))

    # -------------------------------------------------------------------------

    def test_representer(self):
        """
        Should serialize a listing configuration.
        """
        config = stub_listing_config()
        self.assertEqual(
            yaml.dump(config, default_flow_style = True),
            "{scope: false}\n"
        )

    def test_representer_include(self):
        """
        Should serialize a listing configuration with includes.
        """
        config = stub_listing_config(include = ["foo"])
        self.assertEqual(
            yaml.dump(config, default_flow_style = True),
            "{include: [foo], scope: false}\n"
        )

    def test_representer_exclude(self):
        """
        Should serialize a listing configuration with excludes.
        """
        config = stub_listing_config(exclude = ["foo"])
        self.assertEqual(
            yaml.dump(config, default_flow_style = True),
            "{exclude: [foo], scope: false}\n"
        )
