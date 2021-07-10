# Copyright (c) 2016-2021 Martin Donath <martin.donath@squidfunk.com>

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

from mkdocs.config.config_options import Type
from mkdocs.plugins import BasePlugin
import os

from .card import Card

# -----------------------------------------------------------------------------
# Class
# -----------------------------------------------------------------------------

# Social plugin
class SocialPlugin(BasePlugin):

    # Configuration scheme
    config_scheme = (
        ("cards", Type(bool, default = True)),
        # TODO: rename cards whatever, because that's not the single thing we generate...
        ("cards_directory", Type(str, default = "assets/images/social")),
        ("cards_defaults", Type(dict, required = False)),
    )

    # Initialize plugin
    def __init__(self):
        [self.background, self.color] = colors.get("indigo")

    # Retrieve configuration for rendering
    def on_config(self, config):
        theme = config.get("theme")

        # Retrieve palette from theme configuration
        if "palette" in theme:
            palette = theme["palette"]
            if isinstance(palette, list):
                palette = palette[0]

            # Set colors according to palette
            if "primary" in palette and palette["primary"] in colors:
                [self.background, self.color] = colors.get(palette["primary"])

            # Set colors according to defaults
            defaults = self.config.get("cards_defaults", {}) or {} # TODO: hacky
            if "background" in defaults:
                self.background = defaults["background"]
            if "color" in defaults:
                self.color = defaults["color"]

    # Render social cards
    def on_page_content(self, html, page, config, files):

        # if self.config.get("cards"):
        directory = self.config.get("cards_directory")
        file = os.path.splitext(page.file.src_path)[0]

        url = "{}.png".format(os.path.join(config.get("site_url"), directory, file))
        target = "{}.png".format(os.path.join(config.get("site_dir"), directory, file))

        project = config.get("site_name")
        if "social" in page.meta:
            social = page.meta["social"]
            if "project" in social:
                project = social["project"]

        title = page.title
        if "title" in page.meta:
            title = page.meta["title"]

        description = config.get("site_description")
        if "description" in page.meta:
            description = page.meta["description"]

        card = Card(
            background = self.background,
            color = self.color,
            logo = "tmp/material.png", # TODO: modularize
            project = project,
            title = title,
            description = description
        )

        output_dir = os.path.dirname(target)
        os.makedirs(output_dir, exist_ok=True)

        image = card.render()
        image.save(target)

        # Twitter
        social = [
            { "name": "twitter:card", "content": "summary_large_image" },
            { "name": "twitter:site", "content": "@squidfunk" },
            { "name": "twitter:creator", "content": "@squidfunk" },
            { "name": "twitter:title", "content": title },
            { "name": "twitter:description", "content": description },
            { "name": "twitter:image", "content": url }
        ]

        # Open Graph
        properties = [
            { "property": "og:type", "content": "website" },
            { "property": "og:title", "content": title },
            { "property": "og:description", "content": description },
            { "property": "og:url", "content": page.canonical_url },
            { "property": "og:image", "content": url },
            { "property": "og:image:type", "content": "image/png" },
            { "property": "og:image:width", "content": "1200" },
            { "property": "og:image:height", "content": "630" }
        ]

        # TODO: just inject before the end of </head>?

        metatags1 = ["<meta name=\"{}\" content=\"{}\" />".format(
            tag["name"], tag["content"]
        ) for tag in social]

        metatags2 = ["<meta property=\"{}\" content=\"{}\" />".format(
            tag["property"], tag["content"]
        ) for tag in properties]

        return html + "\n" + "\n".join(metatags2) + "\n".join(metatags1)

# -----------------------------------------------------------------------------
# Data
# -----------------------------------------------------------------------------

# Default Material Design colors
colors = dict({
    "red":         ["#ef5552", "#ffffff"],
    "pink":        ["#e92063", "#ffffff"],
    "purple":      ["#ab47bd", "#ffffff"],
    "deep-purple": ["#7e56c2", "#ffffff"],
    "indigo":      ["#4051b5", "#ffffff"],
    "blue":        ["#2094f3", "#ffffff"],
    "light-blue":  ["#02a6f2", "#ffffff"],
    "cyan":        ["#00bdd6", "#ffffff"],
    "teal":        ["#009485", "#ffffff"],
    "green":       ["#4cae4f", "#ffffff"],
    "light-green": ["#8bc34b", "#ffffff"],
    "lime":        ["#cbdc38", "#000000"],
    "yellow":      ["#ffec3d", "#000000"],
    "amber":       ["#ffc105", "#000000"],
    "orange":      ["#ffa724", "#000000"],
    "deep-orange": ["#ff6e42", "#ffffff"],
    "brown":       ["#795649", "#ffffff"],
    "grey":        ["#757575", "#ffffff"],
    "blue-grey":   ["#546d78", "#ffffff"],
    "black":       ["#000000", "#ffffff"],
    "white":       ["#ffffff", "#000000"]
})
