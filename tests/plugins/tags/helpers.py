# Copyright (c) 2016-2023 Martin Donath <martin.donath@squidfunk.com>

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

from collections.abc import Iterable
from material.plugins.tags.config import TagsConfig
from mkdocs.structure.pages import Page

from tests.helpers import stub_page

# -----------------------------------------------------------------------------
# Functions
# -----------------------------------------------------------------------------

def stub_tags_config(**settings: dict) -> TagsConfig:
    """
    Create a tags configuration.

    Arguments:
        **settings: Configuration settings.

    Returns:
        The tags configuration.
    """
    config = TagsConfig()
    if settings:
        config.load_dict(settings)

    # Validate and return configuration
    result = config.validate()
    assert result == ([], []), result
    return config

# -----------------------------------------------------------------------------

def stub_page_with_tags(
    tags: Iterable[str], page: Page | None = None
) -> Page:
    """
    Create a page with the given tags.

    Arguments:
        tags: The tags.
        page: The page.

    Returns:
        The page.
    """
    page = page or stub_page()
    page.meta["tags"] = list(tags)
    return page
