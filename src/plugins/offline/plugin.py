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

import os

from mkdocs.plugins import BasePlugin, event_priority
from mkdocs.utils import write_file

from .config import OfflineConfig

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

# Offline plugin
class OfflinePlugin(BasePlugin[OfflineConfig]):

    # Set configuration for offline build
    def on_config(self, config):
        if not self.config.enabled:
            return

        # Ensure correct resolution of links when viewing the site from the
        # file system by disabling directory URLs
        config.use_directory_urls = False

    # Add support for offline search (run latest) - the search index is copied
    # and inlined into a script, so that it can be used without a server
    @event_priority(-100)
    def on_post_build(self, *, config):
        if not self.config.enabled:
            return

        # Check for existence of search index
        path = os.path.join(config.site_dir, "search", "search_index.json")
        if not os.path.isfile(path):
            return

        # Create script with inlined search index
        with open(path, encoding = "utf-8") as f:
            write_file(
                f"var __index = {f.read()}".encode("utf-8"),
                path.replace(".json", ".js"),
            )
