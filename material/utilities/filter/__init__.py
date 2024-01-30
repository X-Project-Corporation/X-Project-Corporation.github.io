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

from __future__ import annotations

import logging

from fnmatch import fnmatch
from mkdocs.structure.files import File

from .config import FilterConfig

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class Filter:
    """
    A filter.
    """

    config: FilterConfig
    """
    The filter configuration.
    """

    def __init__(self, config: FilterConfig):
        """
        Initialize the filter.

        Arguments:
            config: The filter configuration.
        """
        self.config = config

    def __call__(self, value: str, ref: str | None = None) -> bool:
        """
        Filter a value.

        Arguments:
            value: The value to filter.
            ref: The value used for logging.

        Returns:
            Whether the value should be included.
        """
        ref = ref or value

        # Check if value matches one of the inclusion patterns
        if self.config.include:
            for pattern in self.config.include:
                if fnmatch(value, pattern):
                    return True

            # Value is not included
            log.debug(f"Excluding '{ref}' due to inclusion patterns")
            return False

        # Check if value matches one of the exclusion patterns
        for pattern in self.config.exclude:
            if fnmatch(value, pattern):
                log.debug(f"Excluding '{ref}' due to exclusion patterns")
                return False

        # Value is not excluded
        return True

# -----------------------------------------------------------------------------

class FileFilter(Filter):
    """
    A file filter.
    """

    def __call__(self, file: File) -> bool:
        """
        Filter a file by its source path.

        Arguments:
            file: The file to filter.

        Returns:
            Whether the file should be included.
        """
        if file.inclusion.is_excluded():
            return False

        # Filter file by source path
        return super().__call__(
            file.src_uri,
            file.src_path
        )

# -----------------------------------------------------------------------------
# Data
# -----------------------------------------------------------------------------

# Set up logging
log = logging.getLogger("mkdocs.material.utilities")
