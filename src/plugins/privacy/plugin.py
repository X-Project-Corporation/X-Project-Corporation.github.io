# Copyright (c) 2016-2022 Martin Donath <martin.donath@squidfunk.com>

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
import re
import requests

from lxml import html
from mkdocs import utils
from mkdocs.config.config_options import Type
from mkdocs.plugins import BasePlugin
from shutil import copyfile
from urllib.parse import urlparse

# -----------------------------------------------------------------------------
# Class
# -----------------------------------------------------------------------------

# Privacy plugin
class PrivacyPlugin(BasePlugin):

    # Configuration scheme
    config_scheme = (
        ("download", Type(bool, default = True)),
        ("download_directory", Type(str, default = "assets/externals"))
    )

    # Determine base and initialize resource mappings
    def on_config(self, config):
        self.base_url = urlparse(config.get("site_url"))
        self.base_dir = config.get("site_dir")
        self.resource = dict()

    # Parse, fetch and store external assets
    def on_post_page(self, output, page, config):
        if not self.config.get("download"):
            return

        # Find all external scripts and style sheets
        expr = re.compile(
            r'<(?:link[^>]+href?|script[^>]+src)=[\'"]?http[^>]+>',
            re.IGNORECASE | re.MULTILINE
        )

        # Parse occurrences and replace in reverse
        for match in reversed(list(expr.finditer(output))):
            value = match.group()

            # Compute offsets for replacements
            l = match.start()
            r = l + len(value)

            # Handle preconnect hints and style sheets
            el = html.fragment_fromstring(value)
            if el.tag == "link":
                raw = el.get("href", "")

                # Check if resource is external
                url = urlparse(raw)
                if not self.__is_external(url):
                    continue

                # Replace external preconnect hint in output
                rel = el.get("rel")
                if rel == "preconnect":
                    output = output[0:l] + output[r:]

                # Replace external style sheet in output
                if rel == "stylesheet":
                    output = "".join([
                        output[:l],
                        value.replace(raw, self.__fetch(url, page)),
                        output[r:]
                    ])

            # Handle external scripts
            if el.tag == "script":
                raw = el.get("src", "")

                # Check if resource is external
                url = urlparse(raw)
                if not self.__is_external(url):
                    continue

                # Replace external script in output
                output = "".join([
                    output[:l],
                    value.replace(raw, self.__fetch(url, page)),
                    output[r:]
                ])

        # Return output with replaced occurrences
        return output

    # -------------------------------------------------------------------------

    # Check if the given URL must be considered external
    def __is_external(self, url):
        return url.hostname != self.base_url.hostname

    # Fetch external resource included in given page
    def __fetch(self, url, page):
        if not url in self.resource:
            res = requests.get(url.geturl(), headers = {

                # Set user agent explicitly, so Google Fonts gives us *.woff2
                # files, which according to caniuse.com is the only format we
                # need to download as it covers the entire range of browsers
                # we're officially supporting
                "User-Agent": " ".join([
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "AppleWebKit/537.36 (KHTML, like Gecko)",
                    "Chrome/98.0.4758.102 Safari/537.36"
                ])
            })

            # Compute path name after cleaning up URL
            data = url._replace(scheme = "", query = "", fragment = "")
            file = os.path.join(
                self.config.get("download_directory"),
                data.geturl()[2:]
            )

            # Compute and ensure presence of file extension
            name = re.findall(r'^[^;]+', res.headers["content-type"])[0]
            extension = extensions[name]
            if not file.endswith(extension):
                file += extension

            # Compute and post-process content
            content = res.content
            if extension == ".css":
                content = self.__fetch_css_urls(res.text, file)

            # Write content to file
            utils.write_file(content, os.path.join(
                self.base_dir,
                file
            ))

            # Update resource mappings
            self.resource[url] = file

        # Return URL relative to current page
        return utils.get_relative_url(
            utils.normalize_url(self.resource[url]),
            page.url
        )

    # Fetch external assets from style sheet
    def __fetch_css_urls(self, output, base):
        expr = re.compile(
            r'url\((\s*http?[^)]+)\)',
            re.IGNORECASE | re.MULTILINE
        )

        # Parse occurrences and replace in reverse
        for match in reversed(list(expr.finditer(output))):
            value = match.group(0)
            raw   = match.group(1)

            # Compute offsets for replacements
            l = match.start()
            r = l + len(value)

            # Check if resource is external
            url = urlparse(raw)
            if not self.__is_external(url):
                continue

            # Download file if it's not contained in the cache
            data = url._replace(scheme = "", query = "", fragment = "")
            file = os.path.join(".cache", data.geturl()[2:])
            if not os.path.isfile(file):
                res = requests.get(raw)
                utils.write_file(res.content, file)

            # Compute final path relative to output directory
            path = os.path.join(
                self.config.get("download_directory"),
                data.geturl()[2:]
            )

            # Replace external resource in output
            output = "".join([
                output[:l],
                value.replace(raw, utils.get_relative_url(path, base)),
                output[r:]
            ])

            # Ensure presence of directory
            path = os.path.join(self.base_dir, path)
            directory = os.path.dirname(path)
            if not os.path.isdir(directory):
                os.makedirs(directory)

            # Copy file from cache
            copyfile(file, path)

        # Return output with replaced occurrences
        return bytes(output, encoding = "utf8")

# -----------------------------------------------------------------------------
# Data
# -----------------------------------------------------------------------------

# Expected file extensions
extensions = dict({
    "application/javascript": ".js",
    "text/javascript": ".js",
    "text/css": ".css"
})
