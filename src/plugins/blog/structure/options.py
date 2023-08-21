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

from collections import UserDict
from datetime import date, datetime, time
from mkdocs.config.base import BaseConfigOption, Config, ValidationError
from mkdocs.structure.files import Files
from mkdocs.structure.nav import (
    Navigation, _add_parent_links, _data_to_navigation
)

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

# Date dictionary
class DateDict(UserDict[str, datetime]):

    # Initialize date dictionary
    def __init__(self, data: dict):
        super().__init__(data)

        # Initialize date of creation
        if "created" in data:
            self.created: datetime = data["created"]

    def __getattr__(self, name: str):
        if name in self.data:
            return self.data[name]

# -----------------------------------------------------------------------------

# Post date option
class PostDate(BaseConfigOption[DateDict]):

    # Initialize post dates
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    # Normalize the supported types for post dates to datetime
    def pre_validation(self, config: Config, key_name: str):

        # If the date points to a scalar value, convert it to a dictionary,
        # since we want to allow the user to specify custom and arbitrary date
        # values for posts. Currently, only the `created` date is mandatory,
        # because it's needed to sort posts for views.
        if not isinstance(config[key_name], dict):
            config[key_name] = { "created": config[key_name] }

        # Convert all date values to datetime
        for key, value in config[key_name].items():
            if isinstance(value, date):
                config[key_name][key] = datetime.combine(value, time())

        # Initialize date dictionary
        config[key_name] = DateDict(config[key_name])

    # Ensure each date value is of type datetime
    def run_validation(self, value: DateDict):
        for key in value:
            if not isinstance(value[key], datetime):
                raise ValidationError(
                    f"Expected type: {date} or {datetime} "
                    f"but received: {type(value[key])}"
                )

        # Ensure presence of `date.created`
        if not value.created:
            raise ValidationError(
                "Expected 'created' date when using dictionary syntax"
            )

        # Return date dictionary
        return value

# -----------------------------------------------------------------------------

# Post links option
class PostLinks(BaseConfigOption[Navigation]):

    # Create navigation from structured items - we don't need to provide a
    # configuration object to the function, because it will not be used
    def run_validation(self, value: object):
        items = _data_to_navigation(value, Files([]), None)
        _add_parent_links(items)

        # Return navigation
        return Navigation(items, [])
