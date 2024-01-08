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

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.structure.files import File
from mkdocs.structure.pages import Page
from uuid import uuid4

# -----------------------------------------------------------------------------
# Functions
# -----------------------------------------------------------------------------

def stub_config(**settings: dict) -> MkDocsConfig:
    """
    Stub an MkDocs configuration.

    Arguments:
        **settings: Configuration settings.

    Returns:
        The MkDocs configuration.
    """
    config = MkDocsConfig()
    config.load_dict(dict(site_name = "Example"))
    if settings:
        config.load_dict(settings)

    # Validate and return configuration
    result = config.validate()
    assert result == ([], []), result
    return config

# -----------------------------------------------------------------------------

def stub_file(
    *, path: str | None = None,
    config: MkDocsConfig | None = None
) -> File:
    """
    Stub a file.

    Arguments:
        path: The file path.
        config: The MkDocs configuration.

    Returns:
        The file.
    """
    config = config or stub_config()
    return File(
        path or f"{uuid4()}.md",
        config.docs_dir,
        config.site_dir,
        config.use_directory_urls
    )

def stub_page(
    *, title: str = "Page", path: str | None = None,
    config: MkDocsConfig | None = None
) -> Page:
    """
    Stub a page.

    Arguments:
        title: The page title.
        path: The file path.
        config: The MkDocs configuration.

    Returns:
        The page.
    """
    config = config or stub_config()
    file = stub_file(path = path, config = config)

    # Create page
    page = Page(title, file, config)
    page.markdown = ""
    return page
