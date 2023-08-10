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

import logging
import os

from glob import glob
from mergedeep import Strategy, merge
from mkdocs.exceptions import PluginError
from mkdocs.plugins import BasePlugin, event_priority
from yaml import SafeLoader, load

from material.plugins.meta.config import MetaConfig

# -----------------------------------------------------------------------------
# Class
# -----------------------------------------------------------------------------

# Meta plugin
class MetaPlugin(BasePlugin[MetaConfig]):

    # Construct metadata mapping
    def on_pre_build(self, *, config):
        if not self.config.enabled:
            return

        # Initialize metadata mapping
        self.meta = dict()

        # Resolve and load meta files in docs directory
        path = os.path.relpath(config.docs_dir)
        for file in sorted(glob(
            os.path.join(path, self.config.meta_file),
            recursive = True
        )):
            with open(file, encoding = "utf-8") as f:
                file = os.path.relpath(file, path)
                try:
                    self.meta[file] = load(f, SafeLoader)

                # The meta file could not be loaded because of a syntax error,
                # which we display to the user with a nice error message
                except Exception as e:
                    raise PluginError(
                        f"Error reading meta file '{file}' in '{path}':"
                        f"\n\n"
                        f"{e}"
                    )

    # Set metadata for page, if applicable (run earlier)
    @event_priority(50)
    def on_page_markdown(self, markdown, *, page, config, files):
        if not self.config.enabled:
            return

        # Merge matching meta files in level-order
        for file, defaults in self.meta.items():
            if not page.file.src_path.startswith(os.path.dirname(file)):
                continue

            # Try to merge metadata
            strategy = Strategy.TYPESAFE_ADDITIVE
            try:
                merge(page.meta, defaults, strategy = strategy)

            # Merging the metadata with the given strategy resulted in an error,
            # which we display to the user with a nice error message
            except Exception as e:
                path = os.path.relpath(config.docs_dir)
                file = os.path.relpath(file, path)
                raise PluginError(
                    f"Error merging meta file '{file}' in '{path}':"
                    f"\n\n"
                    f"{e}"
                )

# -----------------------------------------------------------------------------
# Data
# -----------------------------------------------------------------------------

# Set up logging
log = logging.getLogger("mkdocs.material.meta")
