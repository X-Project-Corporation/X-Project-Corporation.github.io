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

import re

from PIL.Image import Image as _Image
from typing import Dict, List, Optional, TypedDict, Union

# -----------------------------------------------------------------------------
# Typings
# -----------------------------------------------------------------------------

# Size
class Size(TypedDict):
    width: int
    height: int

# Offset
class Offset(TypedDict):
    x: int
    y: int

# -----------------------------------------------------------------------------

# Background
class Background(TypedDict):
    color: Optional[str]
    image: Optional[str]

# -----------------------------------------------------------------------------

# Icon
class Icon(TypedDict):
    value: Optional[str]
    color: Optional[str]

# -----------------------------------------------------------------------------

# Line
class Line(TypedDict):
    amount: Optional[int]
    height: Optional[int]

# Font
class Font(TypedDict):
    name: Optional[str]
    weight: Optional[str]

# Typography
class Typography(TypedDict):
    content: Optional[str]
    alignment: Optional[str]
    overflow: Optional[str]
    color: Optional[str]
    line: Optional[Line]
    font: Optional[Font]

# -----------------------------------------------------------------------------

# Layer
class Layer(TypedDict):
    size: Optional[Size]
    offset: Optional[Offset]
    background: Optional[Background]
    icon: Optional[Icon]
    typography: Optional[Typography]

# -----------------------------------------------------------------------------

# Layout
class Layout(TypedDict):
    tags: Dict[str, str]
    size: Size
    layers: List[Layer]

# -----------------------------------------------------------------------------
# Functions
# -----------------------------------------------------------------------------

# Get layer or layout size as tuple
def get_size(layer: Union[Layer, Layout]):
    size = layer["size"]
    return (
        size["width"],
        size["height"]
    )

# Get layer offset as tuple
def get_offset(layer: Layer, image: _Image):
    offset = layer["offset"]

    # Get layer offset
    x = offset.get("x", 0)
    y = offset.get("y", 0)

    # Compute offset from origin - if an origin is given, compute the offset
    # relative to the image and layer size to allow for flexible positioning
    if "origin" in layer:
        origin = re.split(r"\s+", layer.get("origin", "start"))

        # Get layer size
        w, h = get_size(layer)

        # Compute origin on x-axis
        if   "start"  in origin: pass
        elif "end"    in origin: x = (image.width  - w)      - x
        elif "center" in origin: x = (image.width  - w) >> 1 + x

        # Compute origin on y-axis
        if   "top"    in origin: pass
        elif "bottom" in origin: y = (image.height - h)      - y
        elif "center" in origin: y = (image.height - h) >> 1 + y

    # Return offset
    return x, y
