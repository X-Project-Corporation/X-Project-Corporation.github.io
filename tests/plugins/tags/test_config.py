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

from material.plugins.tags.config import TagsConfig

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class TestTagsConfig(unittest.TestCase):
    """
    Test cases for configuration.
    """

    def test_init(self):
        """
        Should initialize the configuration.

        This test ensures that the tags configuration defines sane defaults,
        so the author can initialize the configuration without any arguments.
        It is essentially only a safety net for us, so that we don't start
        requiring arguments for the configuration in the future.
        """
        config = TagsConfig()
        self.assertEqual(config.validate(), ([], []))
