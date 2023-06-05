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

import functools
import html
import json
import logging
import os
import pickle
import posixpath
import re
import requests

from cairosvg import svg2png
from concurrent.futures import Future, ThreadPoolExecutor
from copy import copy
from fnmatch import fnmatch
from glob import glob
from hashlib import sha1
from io import BytesIO
from jinja2 import Environment, meta
from mkdocs.config.base import Config
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.exceptions import PluginError
from mkdocs.plugins import BasePlugin, event_priority
from mkdocs.structure.files import File
from mkdocs.structure.pages import Page
from mkdocs.utils import copy_file
from PIL import Image, ImageColor, ImageDraw, ImageFont
from PIL.Image import Image as _Image
from statistics import stdev
from tempfile import TemporaryFile, TemporaryDirectory
from threading import Lock
from zipfile import ZipFile

from material.plugins.social.config import SocialConfig
from material.plugins.social.layout import Layer, Layout, Line
from material.plugins.social.layout import get_size, get_offset

# -----------------------------------------------------------------------------
# Class
# -----------------------------------------------------------------------------

# Social plugin
class SocialPlugin(BasePlugin[SocialConfig]):
    supports_multiple_instances = True

    # Determine whether we're serving the site, and thus doing an incremental
    # build, and initialize thread pools for card generation. Card generation
    # is split into two stages: rendering of layers and composition. We use two
    # thread pools, one for each stage, as we need to make sure that all layers
    # of a card are rendered before we compose the card itself. At the same time
    # we want to off-load as much as possible onto worker threads, as card
    # generation is a problem that can be perfectly solved in parallel. Thus,
    # we leverage the file system to cache the generated images, so we don't
    # re-generate the exact same images again and again, making successive
    # builds of large sites much faster.
    def on_startup(self, *, command, dirty):
        self.is_serve = (command == "serve")

        # Initialize thread pool for cards
        self.card_pool = ThreadPoolExecutor(self.config.concurrency)
        self.card_jobs: dict[str, Future] = dict()

        # Initialize thread pool for card layers
        self.card_layer_pool = ThreadPoolExecutor(self.config.concurrency)
        self.card_layer_jobs: dict[str, Future] = dict()

    # Initialize plugin
    def on_config(self, config):
        if not self.config.enabled:
            return

        # Initialize lock for synchronizing downloading of fonts
        self.lock = Lock()

        # Initialize card layouts, variables and environment
        self.card_layouts: dict[str, Layout] = dict()
        self.card_variables: dict[str, list[list[str]]] = dict()
        self.card_env = Environment()

        # Initialize cache
        self.cache: dict[str, str] = dict()
        self.cache_file = os.path.join(self.config.cache_dir, "manifest.json")
        self.cache_file = os.path.normpath(self.cache_file)

        # Load cache map, if it exists and the cache should be used
        if os.path.isfile(self.cache_file) and self.config.cache:
            with open(self.cache_file) as f:
                self.cache = json.load(f)

        # Always print a warning when debug mode is active
        if self.config.debug:
            log.warning("Debug mode is enabled for \"social\" plugin.")

            # By default, debug mode is disabled when the documentation is
            # built, but not when it is served. This should nicely align with
            # the expected user experience when authoring documentation.
            if not self.is_serve and not self.config.debug_on_build:
                self.config.debug = False

        # Check if site URL is defined
        if not config.site_url:
            log.warning(
                "The \"site_url\" option is not set. The cards are generated, "
                "but not linked, so they won't be visible on social media."
            )

        # Remember last error, so we can disable the plugin if necessary. This
        # allows for a much better editing experience, as the user can fix the
        # issue and the plugin will pick up the changes, so there's no need to
        # restart the preview server.
        self.error = None

    # Generate card as soon as metadata is available (run latest) - run this
    # hook after all other plugins, so they can alter the card configuration
    @event_priority(-100)
    def on_page_markdown(self, markdown, *, page, config, files):
        if not self.config.enabled or self.error:
            return

        # Skip if cards should not be generated
        if not self.config.cards or self._is_excluded(page):
            return

        # Resolve card layout - currently, only a single layout per site is
        # supported, but this restriction will be lifted in the near future.
        # We also preload the layout here, so we're not triggering multiple
        # concurrent loads in the worker threads.
        name = self.config.cards_layout
        try:
            self._resolve_layout(name, config)

        # If an error occurs during layout resolution, we need to disable the
        # plugin, as we cannot generate cards without a valid layout
        except Exception as e:
            return self._error(e)

        # Spawn concurrent job to generate card for page and add future to
        # list of jobs, as it returns the file we need to copy later on
        self.card_jobs[page.file.src_uri] = self.card_pool.submit(
            self._generate, name, page, config
        )

    # Generate card metadata (run earlier) - don't run this hook too late, as
    # we want plugins like the minify plugin to pick up the HTML we inject
    @event_priority(50)
    def on_post_page(self, output, *, page, config):
        if not self.config.enabled or self.error:
            return

        # Skip if cards should not be generated
        if not self.config.cards or self._is_excluded(page):
            return

        # Reconcile concurrent jobs - we need to wait for the card job to finish
        # before we can copy the generated files to the output directory. If an
        # exception occurred in one of the jobs, we raise it here, so the build
        # fails and the user can fix the issue.
        future = self.card_jobs[page.file.src_uri]
        if future.exception():
            return self._error(future.exception())
        else:
            file: File = future.result()
            file.copy_file()

        # Resolve card layout - currently, only a single layout per site is
        # supported, but this restriction will be lifted in the near future
        name = self.config.cards_layout
        layout, _ = self._resolve_layout(name, config)

        # Stop if no tags are present or site URL is not set
        if not layout.tags or not config.site_url:
            return

        # Resolve image dimensions and curate image metadata
        width, height = get_size(layout)
        image = {
            "url": posixpath.join(config.site_url, file.url),
            "type": "image/png",
            "width": width,
            "height": height
        }

        # Find offset of closing head tag, so we can insert meta tags before
        # it. This is a bit hacky, but much faster that regular expressions.
        at = output.find("</head>")
        return "\n".join([
            output[:at],
            "\n".join([
                f"<meta property=\"{property}\" content=\"{content}\" />"
                    for property, content in _replace(
                        layout.tags, self.card_env, config,
                        page = page, image = image,
                        layout = self.config.cards_layout_options,
                    ).items() if content
            ]),
            output[at:]
        ])

    # Reconcile jobs (run latest) - all other plugins do not depend on the
    # generated cards, so we can run this hook after all of them
    @event_priority(-100)
    def on_post_build(self, *, config):
        if not self.config.enabled or self.error:
            return

        # Skip if cards should not be generated
        if not self.config.cards:
            return

        # Shutdown thread pools if we're not serving
        if not self.is_serve:
            for pool in [self.card_layer_pool, self.card_pool]:
                pool.shutdown()

    # Add custom layout directory to watched files, if it exists
    def on_serve(self, server, *, config, builder):
        path = os.path.abspath(self.config.cards_layout_dir)
        if os.path.exists(path):
            server.watch(path, recursive = True)

    # -------------------------------------------------------------------------

    # Check if the given page is excluded - giving the author the option to
    # include and exclude specific pages is important, as it allows control
    # which pages should generate social cards, and which don't. Different
    # cards can be built by using multiple instances of the plugin.
    def _is_excluded(self, page: Page):
        path = page.file.src_uri

        # Check if page matches one of the inclusion patterns
        if self.config.cards_include:
            for pattern in self.config.cards_include:
                if fnmatch(path, pattern):
                    return False

            # Page is not included
            log.debug(f"Excluding page: {path}")
            return True

        # Check if page matches one of the exclusion patterns
        for pattern in self.config.cards_exclude:
            if fnmatch(path, pattern):
                log.debug(f"Excluding page: {path}")
                return True

        # Page is not excluded
        return False

    # -------------------------------------------------------------------------

    # Generate card for the given page - generation of cards does not depend on
    # anything else than the page content (incl. metadata) and configuration,
    # which is why it is an embarrassingly parallel problem and can be solved
    # by delegating the generation of each card to a thread pool.
    def _generate(self, name: str, page: Page, config: MkDocsConfig):
        layout, variables = self._resolve_layout(name, config)

        # Each card can consist of multiple layers, many of which are likely
        # the same across cards (like background or logo layers). Some of the
        # input values to generate a card may be dependent on author-provided
        # data, e.g., the site description or card title that is sourced from
        # front matter. Additionally, layouts may allow to define arbitrary
        # text boxes with author-provided metadata like tags or categories.
        # Thus, we generate a hash for each card, which is based on the layers
        # and the values of all variables that are used to generate the card.
        layers: dict[str, Layer] = dict()
        for layer, templates in zip(layout.layers, variables):
            fingerprints = [self.config, layer]

            # Compute fingerprints for each layer
            for template in templates:
                template = _compile(template, self.card_env)
                fingerprints.append(template.render(
                    page = page, config = config,
                    layout = self.config.cards_layout_options
                ))

            # Compute digest of fingerprints
            layers[_digest(fingerprints)] = layer

        # Compute digest of all fingerprints - we use this value to check if
        # the exact same card was already generated and cached
        hash = _digest([layout, *list(layers.keys())])

        # Determine part of path we need to replace - this depends on whether
        # we're using directory URLs and if the page is an index page or not
        suffix = ".html"
        if config.use_directory_urls and not page.is_index:
            suffix = "/index.html"

        # Compute path to card, which is sourced from the cache directory, and
        # generate file to register it with MkDocs as soon as it was generated
        path = page.file.dest_uri.replace(suffix, ".png")
        file = self._generate_file(path, config)

        # Check if file hash changed, so we need to re-generate the card. If
        # the hash didn't change, we can return the existing file.
        prev = self.cache.get(file.url, "")
        if hash == prev and os.path.exists(file.abs_src_path):
            return file

        # Spawn jobs to render layers - we only need to render layers that we
        # haven't already dispatched, reducing work by deduplication
        for h, layer in layers.items():
            sentinel = Future()

            # We need to use a hack here to avoid locking the thread pool while
            # we check if the layer was already dispatched. If we don't do this,
            # layers might be dispatched multiple times. The track is to use a
            # sentinel value to check if the layer was already dispatched.
            if sentinel == self.card_layer_jobs.setdefault(h, sentinel):
                self.card_layer_jobs[h] = self.card_layer_pool.submit(
                    self._render, layer, page, config
                )

        # Reconcile concurrent jobs to render layers and compose card - since
        # layers are rendered in parallel, we can compose the card as soon as
        # all layers have been rendered. For this, we await each future to
        # resolve with the image of the rendered layer.
        image = Image.new(mode = "RGBA", size = get_size(layout))
        for h, layer in layers.items():
            image.alpha_composite(
                self.card_layer_jobs[h].result(),
                get_offset(layer, image)
            )

        # If debug mode is enabled, render overlay
        if self.config.debug:
            image = self._render_overlay(layout, image)

        # Save composed image to cache - the caller must copy the image from
        # the cache, so we don't need to worry about concurrent access
        os.makedirs(os.path.dirname(file.abs_src_path), exist_ok = True)
        image.save(file.abs_src_path)

        # Update cache map and write it immediately, so we keep intermediate
        # results when doing incremental builds
        self.cache[file.url] = hash
        with open(self.cache_file, "w") as f:
            f.write(json.dumps(self.cache, indent = 2))

        # Return file for generated card
        return file

    # Render layer - this is the core of the plugin, which renders a single
    # layer of a card. Order is: background, icon, and typography.
    def _render(self, layer: Layer, page: Page, config: MkDocsConfig):
        image = Image.new(mode = "RGBA", size = get_size(layer))
        layer = _replace(
            layer, self.card_env, config,
            page = page, layout = self.config.cards_layout_options
        )

        # Render background, icon, and typography
        image = self._render_background(layer, image)
        image = self._render_icon(layer, image, config)
        image = self._render_typography(layer, image)

        # Return image with layer
        return image

    # Render layer background
    def _render_background(self, layer: Layer, input: _Image):
        background = layer.background

        # If given, load background image and resize it proportionally to cover
        # the entire area while retaining the aspect ratio of the input image
        if background.image:
            with open(background.image, "br") as f:
                data = f.read()
                if background.image.endswith(".svg"):
                    data = svg2png(data, output_width = input.width)

            # Resize image to cover entire area
            image = Image.open(BytesIO(data)).convert("RGBA")
            input.alpha_composite(_resize_cover(image, input))

        # If given, fill background color - this is done after the image is
        # loaded to allow for transparent tints. How awesome is that?
        if background.color:
            color = background.color
            image = Image.new(mode = "RGBA", size = input.size, color = color)
            input.alpha_composite(image)

        # Return image with background
        return input

    # Render layer icon
    def _render_icon(self, layer: Layer, input: _Image, config: MkDocsConfig):
        icon = layer.icon
        if not icon.value:
            return input

        # Resolve icon by searching all configured theme directories and apply
        # the fill color before rendering, if given. Note that the fill color
        # must be converted to rgba() function syntax, or opacity will not work
        # correctly. This way, we don't need to use the fill-opacity property.
        data = self._resolve_icon(icon.value, config)
        if icon.color:
            (r, g, b, *a) = ImageColor.getrgb(icon.color)
            opacity = a[0] / 255 if a else 1

            # Compute and replace fill color
            fill = f"rgba({r}, {g}, {b}, {opacity})"
            data = data.replace("<svg", f"<svg fill=\"{fill}\"")

        # Rasterize vector image given by icon to match the size of the
        # input image, resize it and render it on top of the input image
        image = Image.open(BytesIO(svg2png(data, output_width = input.width)))
        input.alpha_composite(_resize_contain(image.convert("RGBA"), input))

        # Return image with icon
        return input

    # Render layer typography
    def _render_typography(self, layer: Layer, input: _Image):
        typography = layer.typography
        if not typography.content:
            return input

        # Retrieve font family and font style
        family = typography.font.family
        styles = set([typography.font.style])

        # Resolve and load font and compute metrics
        path = self._resolve_font(family, styles)
        current, spacing = _metrics(path, typography.line, input)
        font = ImageFont.truetype(path, current)

        # Create image and initialize drawing context
        image = Image.new(mode = "RGBA", size = input.size)
        context = ImageDraw.Draw(image)

        # Compute length of whitespace and ellipsis - in the next step, we will
        # distribute the words across the lines we have available, which means
        # we need to compute the length of each word and intersperse it with
        # whitespace. Note that lengths of words are perfectly additive, so we
        # can compute the length of a line by adding the lengths of all words
        # and the whitespace between them.
        space = context.textlength(" ", font = font)
        ellipsis = context.textlength("...", font = font)

        # Initialize lists to hold the lengths of words and indexes of lines.
        # Tracking line indexes allows us to improve splitting using heuristics.
        lengths: list[int] = []
        indexes, current = [0], 0

        # Split words at whitespace, and successively add words to the current
        # line. For every other than the first word, account for the whitespace
        # between words. If the next word would exceed the width of the input
        # image, and thus overflow the line, start a new one.
        words = re.split(r"\s+", typography["content"])
        for word in words:
            length = context.textlength(word, font = font)
            lengths.append(length)

            # Start new line if current line overflows
            whitespace = space if current else 0
            if current + whitespace + length > input.width:
                indexes.append(len(lengths) - 1)
                current = length

            # Add word to current line
            else:
                current += whitespace + length

        # Add terminating index, if not already present
        if len(lengths) != indexes[-1]:
            indexes.append(len(lengths))

        # If the number of lines exceeds the maximum amount we are able to
        # render, either shrink or truncate the text and add an ellipsis
        amount = typography.line.amount
        if amount < len(indexes) - 1:

            # If overflow mode is set to 'shrink', decrease the font size and
            # try to render the typography again to see if it fits
            overflow = typography.get("overflow")
            if overflow == "shrink":
                typography.line.amount += 1

                # Render layer with new typography metrics by calling this
                # function recursively and returning immediately from it
                return self._render_typography(layer, input)

            # Determine last and penultimate line indexes
            indexes = indexes[:amount + 1]
            p, q = indexes[-2:]

            # Compute the length of the last line, and check whether we can add
            # the ellipsis after the last word. If not, replace the last word.
            current = sum(lengths[p:q]) + (q - p) * space
            if current + ellipsis < input.width:
                q += 1

            # Update line indexes and replace word with ellipsis
            indexes[-1]  = q
            words[q - 1] = "..."

        # If there are exactly two lines, check if we can improve splitting by
        # moving the last word of the first line to the last line
        elif len(indexes) == 3:
            p, q, r = indexes[-3:]

            # Create two configurations of lines, one with the last word of the
            # first line moved to the last line, and one without the change
            a = [len(" ".join(l)) for l in [words[p:q],     words[q:r]]]
            b = [len(" ".join(l)) for l in [words[p:q - 1], words[q - 1:r]]]

            # Compute standard deviation of line lengths before and after the
            # change, and if the standard deviation decreases, move the word
            if stdev(b) < stdev(a):
                indexes[-2] -= 1

        # Compute anchor and deduce alignment, as well as offset. The anchor
        # is computed as a string of two characters, where the first character
        # denotes the horizontal alignment and the second character denotes
        # the vertical alignment.
        anchor = _anchor(typography.align)

        # Compute horizontal alignment
        if   anchor[0] == "l": align, x = "left",   0
        elif anchor[0] == "m": align, x = "center", input.width  >> 1
        elif anchor[0] == "r": align, x = "right",  input.width  >> 0

        # Compute vertical alignment
        if   anchor[1] == "a":        y =           0
        elif anchor[1] == "m":        y =           input.height >> 1
        elif anchor[1] == "d":        y =           input.height >> 0

        # Join words with whitespace and lines with line breaks
        text = "\n".join([
            " ".join(words[p:q])
                for p, q in zip(indexes, indexes[1:])
        ])

        # Draw text onto image
        context.text(
            (x, y), text,
            font = font,
            anchor = anchor,
            spacing = spacing,
            fill = typography.color,
            align = align
        )

        # Return image with typography
        input.alpha_composite(image)
        return input

    # Render overlay for debugging
    def _render_overlay(self, layout: Layout, input: _Image):
        path = self._resolve_font("Roboto", ["Regular"])
        typeface = ImageFont.truetype(path, 12)

        # Create image and initialize drawing context
        image = Image.new(mode = "RGBA", size = input.size)
        context = ImageDraw.Draw(image)

        # Draw overlay grid
        fill = self.config.debug_color
        if self.config.debug_grid:
            step = self.config.debug_grid_step
            for i in range(0, input.width, step):
                for j in range(0, input.height, step):
                    context.ellipse(
                        ((i - 1, j - 1), (i + 1, j + 1)),
                        fill = fill
                    )

        # Compute luminosity of debug color and use it to determine the color
        # of the text that will be drawn on top of the debug color
        (r, g, b, *_) = ImageColor.getrgb(fill)
        color = "black" if r * 0.299 + g * 0.587 + b * 0.114 > 150 else "white"

        # Draw overlay outline for each layer
        for i, layer in enumerate(layout.layers):
            x, y = get_offset(layer, image)
            w, h = get_size(layer)

            # Draw overlay outline
            context.rectangle(outline = fill, xy = (x, y,
                min(x + w, input.width  - 1),
                min(y + h, input.height - 1)
            ))

            # Assemble text and compute its width and height - we only use the
            # coordinates denoting the width and height of the text, as we need
            # to compute the coordinates of the text box manually in order to
            # have the rectangle align perfectly with the outline
            text = f"{i} – {x}, {y}"
            (_, _, x1, y1) = context.textbbox((x, y), text, font = typeface)

            # Draw text on a small rectangle in the top left corner of the
            # layer denoting the number of the layer and its offset
            context.rectangle(fill = fill, xy = (x, y, x1 + 8, y1 + 4))
            context.text((x + 4, y + 2), text, font = typeface, fill = color)

        # Return image with overlay
        input.alpha_composite(image)
        return input

    # -------------------------------------------------------------------------

    # Resolve layout - authors can specify a custom directory for layouts in
    # the configuration, which is checked prior to the layout directory shipped
    # with this plugin. If the layout cannot be resolved in any of the known
    # directories, the plugin must abort with an error.
    def _resolve_layout(self, name: str, config: MkDocsConfig):
        name, _ = os.path.splitext(name)
        if name in self.card_layouts:
            return self.card_layouts[name], self.card_variables[name]

        # If the user specified a custom directory, try to resolve the layout
        # from this directory first, otherwise fall back to the default.
        for base in [
            os.path.abspath(self.config.cards_layout_dir),
            os.path.join(os.path.dirname(__file__), "layouts")
        ]:
            path = os.path.join(base, f"{name}.yml")
            path = os.path.normpath(path)

            # Skip if layout does not exist and try next directory
            if not os.path.exists(path):
                continue

            # Open file and parse layout as YAML
            with open(path, encoding = "utf-8") as f:
                layout = Layout()
                layout.load_file(f)

                # Validate layout and abort if errors occurred
                errors, warnings = layout.validate()
                for key, w in warnings:
                    log.warning(w)
                for key, e in errors:
                    raise e

                # Store layout and variables
                self.card_layouts[name] = layout
                self.card_variables[name] = []

                # Extract variables for each layer from layout
                for layer in layout.layers:
                    variables = _extract(layer, self.card_env, config)
                    self.card_variables[name].append(variables)

                    # Set default values for for layer size, if not given
                    for key, value in layer.size.items():
                        if value == 0:
                            layer.size[key] = layout.size[key]

            # Abort, since we're done
            break

        # Abort, since the layout could not be resolved
        if name not in self.card_layouts:
            raise PluginError(f"Couldn't find layout '{name}'")

        # Return layout and variables
        return self.card_layouts[name], self.card_variables[name]

    # Resolve icon with given name - this function searches for the icon in all
    # known theme directories, including custom directories specified by the
    # author, which allows for using custom icons in cards. If the icon cannot
    # be resolved, the plugin must abort with an error.
    def _resolve_icon(self, name: str, config: MkDocsConfig, color: str = None):
        for base in config.theme.dirs:
            path = os.path.join(base, ".icons", f"{name}.svg")
            path = os.path.normpath(path)

            # Skip if icon does not exist and try next directory
            if not os.path.exists(path):
                continue

            # Load and convert icon to PNG
            with open(path) as f:
                return f.read()

        # Abort, since the icon could not be resolved
        raise PluginError(f"Couldn't find icon '{name}'")

    # Resolve font family with specific style - if we haven't already done it,
    # the font family is first downloaded from Google Fonts and the styles are
    # saved to the cache directory. If the font cannot be resolved, the plugin
    # must abort with an error.
    def _resolve_font(self, family: str, styles: "set[str]"):
        path = os.path.join(self.config.cache_dir, "fonts", family)
        path = os.path.normpath(path)

        # Fetch font family, if it hasn't been fetched yet - we use a lock to
        # synchronize access, so the font is not downloaded multiple times, but
        # all other threads wait for the font being available. This is also why
        # we need the double path check, which makes sure that we only use the
        # lock when we actually need to download a font that doesn't exist. If
        # we already downloaded it, we don't want to block at all.
        if not os.path.exists(path):
            with self.lock:
                if not os.path.exists(path):
                    self._fetch_font_from_google_fonts(family)

        # Check for availability of font style
        list = sorted(os.listdir(path))
        for file in list:
            name, _ = os.path.splitext(file)
            if name in styles:
                return os.path.join(path, file)

        # Print warning in debug mode, since the font could not be resolved
        if self.config.debug:
            styles = ", ".join(styles)
            log.warning(
                f"Couldn't find style '{styles}' for font family '{family}'. " +
                f"Styles available:\n\n" +
                f"\n".join([os.path.splitext(file)[0] for file in list]) +
                f"\n\n"
                f"Falling back to: Regular\n"
                f"\n"
            )

        # Fall back to regular font
        return self._resolve_font(family, { "Regular" })

    # -------------------------------------------------------------------------

    # Fetch font family from Google Fonts
    def _fetch_font_from_google_fonts(self, family: str):
        path = os.path.join(self.config.cache_dir, "fonts")
        path = os.path.normpath(path)

        # Download archive from Google Fonts to in-memory archive
        with TemporaryFile() as f:
            url = f"https://fonts.google.com/download?family={family}"
            res = requests.get(url, stream = True)
            for chunk in res.iter_content(chunk_size = 8192):
                f.write(chunk)

            # Ensure that the download succeeded
            if res.status_code != 200:
                raise PluginError(
                    f"Couldn't find font family '{family}' on Google Fonts "
                    f"({res.status_code}: {res.reason})"
                )

            # Extract fonts from archive
            with TemporaryDirectory() as temp:
                archive = ZipFile(f)
                archive.extractall(temp, [
                    file for file in archive.namelist()
                        if re.search(r"\.[ot]tf$", file)
                ])

                # Rename and move fonts to cache directory
                for file in glob(
                    os.path.join(temp, "**/*.[to]tf"),
                    recursive = True
                ):
                    typeface = ImageFont.truetype(file)

                    # Extract font family name and style
                    name, style = typeface.getname()
                    name = " ".join([name.replace(family, ""), style]).strip()

                    # Move fonts to cache directory
                    copy_file(file, os.path.join(path, family, f"{name}.ttf"))

    # -------------------------------------------------------------------------

    # Handle error - if we're serving, we just log the first error we encounter.
    # If we're building, we raise an exception, so the build fails.
    def _error(self, e: Exception):
        if not self.is_serve:
            raise PluginError(str(e))

        # Remember last error
        if not self.error:
            self.error = e

            # If we're serving, just log the error and emit a warning that
            # social cards are not being generated from that point on.
            log.error(e)
            log.warning(
                "Skipping generation of social cards for this build. "
                "Please fix the error to enable social cards again."
            )

    # Create a file for the given path
    def _generate_file(self, path: str, config: MkDocsConfig):
        return File(
            posixpath.join(self.config.cards_dir, path),
            os.path.abspath(self.config.cache_dir),
            config.site_dir,
            False
        )

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

# Compute a stable hash from a dictionary - since we're doing compositing, we
# can leverage caching to omit re-generating layers when their parameters stay
# the same. Additionally, we can identify identical layers between images,
# e.g., background, logos, or avatars, but also unchanged text.
def _digest(data: object):
    flat = pickle.dumps(data)
    return sha1(flat).hexdigest()

# -----------------------------------------------------------------------------

# Extract all variables recursively
def _extract(data: any, env: Environment, config: MkDocsConfig):

    # Traverse configuration or dictionary
    if isinstance(data, (Config, dict)):
        return [
            variable for value in data.values()
                for variable in _extract(value, env, config)
        ]

    # Traverse list
    elif isinstance(data, list):
        return [
            variable for value in data
                for variable in _extract(value, env, config)
        ]

    # Retrieve variables from string
    elif isinstance(data, str):
        if meta.find_undeclared_variables(env.parse(data)):
            return [data]

    # Return nothing
    return []

# Replace all variables recursively and return a copy of the given data
def _replace(data: any, env: Environment, config: MkDocsConfig, **kwargs):

    # Traverse configuration or dictionary
    if isinstance(data, (Config, dict)):
        data = copy(data)
        for key, value in data.items():
            data[key] = _replace(value, env, config, **kwargs)

    # Traverse list
    elif isinstance(data, list):
        return [
            _replace(value, env, config, **kwargs)
                for value in data
        ]

    # Retrieve variables from string
    elif isinstance(data, str):
        return _compile(data, env).render(
            config = config, **kwargs
        ) or None

    # Return data
    return data

# Compile template and cache it indefinitely
@functools.lru_cache(maxsize = None)
def _compile(data: str, env: Environment):
    return env.from_string(html.unescape(data))

# -----------------------------------------------------------------------------

# Resize image to match the size of the reference image and align it to the
# center of the reference image so that it is fully covered
def _resize_cover(image: _Image, ref: _Image):
    ratio = max(
        ref.width  / image.width,
        ref.height / image.height
    )

    # Compute aspect ratios of both images and choose the larger one, then
    # resize the image so that it covers the entire reference image
    image = image.resize((
        int(image.width  * ratio),
        int(image.height * ratio)
    ))

    # Align image to the center of the reference image - we also need to crop
    # the image if it's larger than the given reference image
    return image.crop((
        image.width  - ref.width  >> 1,
        image.height - ref.height >> 1,
        image.width  + ref.width  >> 1,
        image.height + ref.height >> 1
    ))

# Resize image to match the size of the reference image and align it to the
# center of the reference image so that it is fully contained
def _resize_contain(image: _Image, ref: _Image):
    ratio = min(
        ref.width  / image.width,
        ref.height / image.height
    )

    # Resize image according to minimum ratio
    image = image.resize((
        int(image.width  * ratio),
        int(image.height * ratio)
    ))

    # Create a blank image and paste the resized image into it
    blank = Image.new(mode = "RGBA", size = ref.size)
    blank.paste(image, (
        ref.width  - image.width  >> 1,
        ref.height - image.height >> 1
    ))

    # Return resized image
    return blank

# -----------------------------------------------------------------------------

# Resolve font metrics for given truetype font - this function computes the
# font size and spacing between lines based on the number of lines and height.
# In order to omit rounding errors, we compute the ascender and descender based
# on a font size of 1,000.
def _metrics(path: str, line: Line, ref: _Image):
    font = ImageFont.truetype(path, 1000)
    ascender, descender = font.getmetrics()

    # It would be too complex to let the author define the font size, since this
    # would involve a lot of fiddling to find the right value. Instead, we let
    # the author define the number of lines and the line height, and we compute
    # the font size from that. This is much more intuitive. As a basis, we use
    # the ascender as the actual line height and also add the descender to
    # account for the last line. It's no secret that correctly handling font
    # metrics is super tricky - see https://bit.ly/31u9bh6
    extent = line.amount * ascender + 1 * descender

    # Now, we still need to account for spacing between lines, which is why we
    # take the number of lines - 1, and multiply that with the line height we
    # computed from the ascender. We add this to the extent we computed before,
    # which we use as a basis for the final font size.
    extent += (line.amount - 1) * (line.height - 1) * ascender
    size = (1000 * ref.height) / extent

    # From this, we can compute the spacing between lines, and we're done. We
    # then return both, the font size and spacing between lines.
    spacing = (line.height - 1) * ascender * size / 1000
    return int(size), spacing

# Compute anchor, determining the alignment of text relative to the given
# coordinates, with the default being "top left" - see https://bit.ly/3NEfr07
def _anchor(data: str):
    axis = re.split(r"\s+", data)

    # Determine anchor on x-axis
    if   "start"  in axis: anchor  = "l"
    elif "end"    in axis: anchor  = "r"
    elif "center" in axis: anchor  = "m"
    else:                  anchor  = "l"

    # Determine anchor on y-axis
    if   "top"    in axis: anchor += "a"
    elif "bottom" in axis: anchor += "d"
    elif "center" in axis: anchor += "m"
    else:                  anchor += "a"

    # Return anchor
    return anchor

# -----------------------------------------------------------------------------
# Data
# -----------------------------------------------------------------------------

# Set up logging
log = logging.getLogger("mkdocs.material.social")
