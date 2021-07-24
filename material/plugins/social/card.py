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

from PIL import Image, ImageDraw, ImageFont

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

# Image width
WIDTH = 1200

# Image height
HEIGHT = 630

# Image border offset
OFFSET = 48

# Header height
HEIGHT_HEADER = 72

# # Font for regular text
# FONT_REGULAR = "Roboto-Regular.ttf" # TODO: this is now determine dynamically...

# # Font for bold text
# FONT_BOLD = "Roboto-Bold.ttf" # TODO: this is now determine dynamically...

# -----------------------------------------------------------------------------
# Class
# -----------------------------------------------------------------------------

# Social card generator
class Card:

    # Initialize social card
    def __init__(self, background, color, logo, project, title, description):

        self.font = FontLoader("Roboto")

        # Set back- and foreground color
        self.background  = background
        self.color       = color

        # Set data to render on card
        self.logo        = logo
        self.project     = project
        self.title       = title
        self.description = description

    # Render social card
    def render(self):

        # Render image layers
        header      = self._render_header()
        title       = self._render_title(self.title)
        description = self._render_description(self.description)

        # Create image and render layers
        image = self._render_background()
        image.alpha_composite(header, (OFFSET, OFFSET))
        image.alpha_composite(title, (
            OFFSET,
            HEIGHT - title.height - 160 - OFFSET
        ))
        image.alpha_composite(description, (
            OFFSET,
            HEIGHT - description.height - OFFSET
        ))

        # Return image
        return image

    # Render background
    def _render_background(self):
        return Image.new(
            mode = "RGBA",
            size = (WIDTH, HEIGHT),
            color = self.background
        )

    # Render header
    def _render_header(self):
        font = ImageFont.truetype(self.font.regular, size = int(HEIGHT_HEADER / 2))

        # Create image
        image = Image.new(
            mode = "RGBA",
            size = (WIDTH - 2 * OFFSET, HEIGHT_HEADER)
        )

        # Create drawing context and compute bounding box
        context = ImageDraw.Draw(image)
        textbox = context.textbbox((0, 0), self.project, font = font)

        # Compute vertical offset and render text
        offset = (HEIGHT_HEADER - (textbox[1] + textbox[3])) / 2
        context.text(
            (HEIGHT_HEADER + OFFSET, offset), self.project,
            font = font, fill = self.color
        )

        # Load and resize logo
        logo = self.logo # Image.open(self.logo)
        logo = logo.resize((HEIGHT_HEADER, int(
            HEIGHT_HEADER * logo.height / logo.width
        )))

        # Render logo and return image
        image.alpha_composite(logo, (0, 0))
        return image

    # Render title
    def _render_title(self, text):
        font = ImageFont.truetype(self.font.bold, 96)
        return self._render_text(text, font, 16)

    # Render description
    def _render_description(self, text):
        font = ImageFont.truetype(self.font.regular, 32)
        return self._render_text(text, font, 24)

    # Render a text box
    def _render_text(self, text, font, spacing):
        lines = []
        words = []

        # Create temporary image
        image = Image.new(
            mode = "RGBA",
            size = (WIDTH - 2 * OFFSET, HEIGHT_HEADER)
        )

        # Create drawing context and split text into lines
        context = ImageDraw.Draw(image)
        for word in text.split(" "):
            combine = " ".join(words + [word])
            textbox = context.textbbox((0, 0), combine, font = font)
            if textbox[2] <= WIDTH - 2 * OFFSET:
                words.append(word)
            else:
                lines.append(words)
                words = [word]

        # TODO: partition the list into even parts. median?

        # Add last line and limit lines to 2
        lines.append(words)
        if len(lines) > 2:
            lines = lines[0:2]
            lines[-1][-1] = "..."

        # Join words for each line
        lines = [" ".join(line) for line in lines]

        # Compute bounding box and create actual image
        textbox = context.textbbox(
            (0, 0), "\n".join(lines),
            font = font, spacing = spacing
        )
        image = Image.new(
            mode = "RGBA",
            size = (WIDTH - 2 * OFFSET, textbox[3] + textbox[1]),
        )

        # Create drawing context and split text into lines
        context = ImageDraw.Draw(image)
        context.text(
            (0, 0), "\n".join(lines),
            font = font, fill = self.color, spacing = spacing
        )

        # Return image
        return image





from cssutils import parseString

import requests
import re
import os

# just return a dict and good?

class FontLoader:

    # Initialize font loader
    def __init__(self, name, base = ".cache"):
        self.name = name
        self.base = base

        # Create cache directory
        if not os.path.isdir(self.base):
            os.makedirs(self.base)

        # Check if files exist
        if not all(os.path.isfile(
            os.path.join(
                self.base,
                "{}.{}.ttf".format(self.name, weight)
            )
        ) for weight in ["400", "700"]):
            self._load()

        # Set names - TODO: just put this in a function
        self.regular = os.path.join(self.base, "{}.400.ttf".format(name))
        self.bold    = os.path.join(self.base, "{}.700.ttf".format(name))

    def _load(self):
        url = "https://fonts.googleapis.com/css?family={}:400,700"
        res = requests.get(url.format(self.name))

        # Parse stylesheet with font declarations
        sheet = parseString(res.text)
        fonts = dict((
            rule.style["font-weight"],
            rule.style["src"]
        ) for rule in sheet)

        # Fetch fonts
        for weight, url in fonts.items():
            url = re.search('url\((.+?)\)', url).group(1)
            res = requests.get(url)

            # Save font file
            f = open(os.path.join(self.base, "{}.{}.ttf".format(self.name, weight)), "wb")
            f.write(res.content)
            f.close()
