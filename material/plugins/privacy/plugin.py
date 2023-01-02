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
import posixpath
import re
import requests

from fnmatch import fnmatch
from lxml import html
from mkdocs import utils
from mkdocs.commands.build import DuplicateFilter
from mkdocs.config import config_options as opt
from mkdocs.config.base import Config
from mkdocs.plugins import BasePlugin, event_priority
from mkdocs.structure.files import File
from urllib.parse import urlparse

# -----------------------------------------------------------------------------
# Class
# -----------------------------------------------------------------------------

# Privacy plugin configuration scheme
class PrivacyPluginConfig(Config):
    enabled = opt.Type(bool, default = True)

    # Options for caching
    cache = opt.Type(bool, default = True)
    cache_dir = opt.Type(str, default = ".cache/plugin/privacy")

    # Options for external assets and links
    external_assets = opt.Choice(("bundle", "report"), default = "bundle")
    external_assets_dir = opt.Type(str, default = "assets/external")
    external_assets_exclude = opt.Type(list, default = [])
    external_links = opt.Type(bool, default = True),
    external_links_attr_map = opt.Type(dict, default = dict())
    external_links_noopener = opt.Type(bool, default = True)

    # Deprecated options
    download = opt.Deprecated(moved_to = "enabled")
    download_directory = opt.Deprecated(moved_to = "external_assets_dir")
    externals = opt.Deprecated(moved_to = "external_assets")
    externals_dir = opt.Deprecated(moved_to = "external_assets_dir")
    externals_directory = opt.Deprecated(moved_to = "external_assets_dir")
    externals_exclude = opt.Deprecated(moved_to = "external_assets_exclude")

# -----------------------------------------------------------------------------

# Privacy plugin
class PrivacyPlugin(BasePlugin[PrivacyPluginConfig]):

    # Initialize plugin
    def on_config(self, config):
        self.site  = urlparse(config.site_url or "")
        self.queue = []

    # Determine files that might include external assets
    def on_files(self, files, *, config):
        if not self.config.enabled:
            return

        # Enqueue files for processing, but short-circuit Lunr.js
        for file in files:
            if file.url.endswith(".js") or file.url.endswith(".css"):
                if not "assets/javascripts/lunr" in file.url:
                    self.queue.append(file)

        # If site URL is not given, add Mermaid.js - see https://bit.ly/36tZXsA
        # This is a special case, as Material for MkDocs automatically loads
        # Mermaid.js when a Mermaid diagram is found in the page.
        if not config.site_url:
            if not any("mermaid" in url for url in config.extra_javascript):
                config.extra_javascript.append(
                    "https://unpkg.com/mermaid@9.1.7/dist/mermaid.min.js"
                )

    # Parse, fetch and store external assets and patch links (run later)
    @event_priority(-50)
    def on_post_page(self, output, *, page, config):
        if not self.config.enabled:
            return

        # Find all external assets and links
        expr = re.compile(
            r"<(?:(?:a|link)[^>]+href|(?:script|img)[^>]+src)=['\"]?http[^>]+>",
            re.IGNORECASE | re.MULTILINE
        )

        # Replacement callback
        def replacement(match):
            value = match.group()

            # Handle external links
            el = html.fragment_fromstring(value.encode("utf-8"))
            if self.config.external_links and el.tag == "a":
                for key, value in self.config.external_links_attr_map.items():
                    el.set(key, value)

                # Set rel="noopener" if link opens in a new window
                if self.config.external_links_noopener:
                    if el.get("target") == "_blank":
                        el.set("rel", "noopener")

                # Replace link opening tag (without closing tag)
                return html.tostring(el, encoding = "unicode")[:-4]

            # Handle external style sheet or preconnect hint
            if el.tag == "link":
                raw = el.get("href", "")

                # Only process external assets
                url = urlparse(raw)
                if not self._is_external(url):
                    return value

                # Replace external preconnect hint
                rel = el.get("rel")
                if rel == "preconnect":
                    return ""

                # Replace external style sheet or favicon
                if rel == "stylesheet" or rel == "icon":
                    return value.replace(
                        raw,
                        self._fetch(url, page.file, config)
                    )

            # Handle external script or image
            if el.tag == "script" or el.tag == "img":
                raw = el.get("src", "")

                # Only process external assets
                url = urlparse(raw)
                if not self._is_external(url):
                    return value

                # Replace external script or image
                return value.replace(raw, self._fetch(url, page.file, config))

        # Return output with replaced occurrences
        return expr.sub(replacement, output)

    # Parse, fetch and store external assets in style sheets and scripts
    def on_post_build(self, *, config):
        if not self.config.enabled:
            return

        # Process queued files
        for file in self.queue:
            if not os.path.isfile(file.abs_dest_path):
                continue

            # Open file and patch dependent assets
            with open(file.abs_dest_path, encoding = "utf-8") as f:
                utils.write_file(
                    self._fetch_dependents(f.read(), file, config),
                    file.abs_dest_path
                )

    # -------------------------------------------------------------------------

    # Check if the given URL is external
    def _is_external(self, url):
        return url.hostname != self.site.hostname

    # Check if the given URL is excluded
    def _is_excluded(self, url, base):
        url = re.sub(r"^https?:\/\/", "", url)
        for pattern in self.config.external_assets_exclude:
            if fnmatch(url, pattern):
                log.debug(f"Excluding external file in '{base}': {url}")
                return True

        # Report external assets if bundling is not enabled
        if self.config.external_assets == "report":
            log.warning(f"External file in '{base}': {url}")
            return True

    # Fetch external asset in the context of a page
    def _fetch(self, url, base, config):
        raw = url.geturl()

        # Skip excluded files
        if self._is_excluded(raw, base.dest_uri):
            return raw

        # Resolve file and check if it needs to be downloaded
        file = self._map_url_to_file(url, config)
        if not os.path.isfile(file.abs_src_path) or not self.config.cache:
            path = file.abs_src_path

            # Download external file
            log.debug(f"Downloading external file: {raw}")
            res = requests.get(raw, headers = {

                # Set user agent explicitly, so Google Fonts gives us *.woff2
                # files, which according to caniuse.com is the only format we
                # need to download as it covers the entire range of browsers
                # we're officially supporting.
                "User-Agent": " ".join([
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "AppleWebKit/537.36 (KHTML, like Gecko)",
                    "Chrome/98.0.4758.102 Safari/537.36"
                ])
            })

            # Compute and ensure presence of file extension
            mime = re.findall(r"^[^;]+", res.headers["content-type"])[0]
            extension = extensions.get(mime)
            if extension and not path.endswith(extension):
                path, _ = os.path.splitext(path)
                path += extension

            # Write contents and create symlink if no extension was present
            utils.write_file(res.content, path)
            if path != file.abs_src_path:

                # Creating symlinks might fail on Windows. Thus, we just print
                # a warning and continue - see https://bit.ly/3xYFzcZ
                try:
                    os.symlink(os.path.basename(path), file.abs_src_path)
                except OSError:
                    log.warning(
                        f"Couldn't create symbolic link '{file.src_uri}'"
                    )

                    # Fall back for when the symlink could not be created. This
                    # means that the plugin will download the original file on
                    # every build, as the content type cannot be resolved from
                    # the file extension.
                    file.abs_src_path = path

        # Resolve destination if file points to a symlink
        _, extension = os.path.splitext(file.abs_src_path)
        if os.path.isfile(file.abs_src_path):
            file.abs_src_path = os.path.realpath(file.abs_src_path)
            _, extension = os.path.splitext(file.abs_src_path)

            # If the symlink could not be created, we already set the correct
            # extension, so we need to check not to append it again.
            if not file.abs_dest_path.endswith(extension):

                # Compute destination file system path
                file.dest_uri += extension
                file.abs_dest_path += extension

                # Compute destination URL
                file.url += extension

        # Copy or open and patch file
        if not os.path.isfile(file.abs_dest_path):
            if not extension == ".css" and not extension == ".js":
                file.copy_file()

            # Open file and patch dependent assets
            else:
                with open(file.abs_src_path, encoding = "utf-8") as f:
                    utils.write_file(
                        self._fetch_dependents(f.read(), file, config),
                        file.abs_dest_path
                    )

        # Return URL relative to current page
        return file.url_relative_to(base)

    # Fetch dependent assets in external assets
    def _fetch_dependents(self, output, base, config):

        # Fetch external assets in style sheet
        if base.url.endswith(".css"):
            expr = re.compile(
                r"url\((\s*http?[^)]+)\)",
                re.IGNORECASE | re.MULTILINE
            )

        # Fetch external assets in script
        elif base.url.endswith(".js"):
            expr = re.compile(
                r"[\"'](http[^\"']+\.js)[\"']",
                re.IGNORECASE | re.MULTILINE
            )

        # Replacement callback
        def replacement(match):
            value = match.group(0)
            raw   = match.group(1)

            # Only process external files
            url = urlparse(raw)
            if not self._is_external(url):
                return value

            # Skip excluded files
            if self._is_excluded(raw, base.dest_uri):
                return value

            # Resolve file and check if it needs to be downloaded
            file = self._map_url_to_file(url, config)
            if not os.path.isfile(file.abs_src_path) or not self.config.cache:

                # Download external file
                log.debug(f"Downloading external file: {raw}")
                res = requests.get(raw)

                # Write contents
                utils.write_file(res.content, file.abs_src_path)

            # Create absolute URL for asset in script
            if base.url.endswith(".js"):
                url = posixpath.join(self.site.geturl(), file.url)

            # Create relative URL for everything else
            else:
                url = file.url_relative_to(base)

            # Copy file to target directory
            file.copy_file()

            # Replace external asset in output
            return value.replace(raw, url)

        # Return output with replaced occurrences
        return expr.sub(replacement, output).encode("utf8")

    # Resolve a file for a URL
    def _map_url_to_file(self, url, config):
        data = url._replace(scheme = "", query = "", fragment = "")
        base = self.config.external_assets_dir
        return File(
            posixpath.join(base, data.geturl()[2:]),
            self.config.cache_dir,
            config.site_dir,
            False
        )

# -----------------------------------------------------------------------------
# Data
# -----------------------------------------------------------------------------

# Set up logging
log = logging.getLogger("mkdocs")
log.addFilter(DuplicateFilter())

# Expected file extensions
extensions = dict({
    "application/javascript": ".js",
    "image/avif": ".avif",
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
    "text/javascript": ".js",
    "text/css": ".css"
})
