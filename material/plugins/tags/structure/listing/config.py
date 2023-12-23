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

from material.plugins.tags.structure.tag.options import TagSet
from mkdocs.config.base import Config
from mkdocs.config.config_options import Optional, Type

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class ListingConfig(Config):
    """
    A listing configuration.
    """

    scope = Type(bool, default = False)
    """
    Whether to only include pages in the current subsection.

    Enabling this setting will only include pages that are on the same level or
    on a lower level than the page the listing is on. This allows to create a
    listing of tags on a page that only includes pages that are in the same
    subsection of the documentation.
    """

    shadow = Optional(Type(bool))
    """
    Whether to include shadow tags.

    This setting allows to override the global setting for shadow tags. If this
    setting is not specified, the global `shadow` setting is used.
    """

    layout = Optional(Type(str))
    """
    The layout to use for rendering the listing.

    This setting allows to override the global setting for the layout. If this
    setting is not specified, the global `listings_layout` setting is used.
    """

    include = TagSet()
    """
    Tags to include in the listing.

    If this set is empty, the listing does not filter pages by tags. Otherwise,
    all pages that have at least one of the tags in this set will be included.
    """

    exclude = TagSet()
    """
    Tags to exclude from the listing.

    If this set is empty, the listing does not filter pages by tags. Otherwise,
    all pages that have at least one of the tags in this set will be excluded.
    """
