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

import copy
import logging
import os
import paginate
import posixpath
import re
import readtime
import sys

from babel.dates import format_date
from datetime import date
from functools import partial
from markdown.extensions.toc import slugify
from mkdocs import utils
from mkdocs.utils.meta import get_data
from mkdocs.commands.build import DuplicateFilter, _populate_page
from mkdocs.config import config_options as opt
from mkdocs.config.base import Config
from mkdocs.contrib.search import SearchIndex
from mkdocs.plugins import BasePlugin
from mkdocs.structure.files import File, Files
from mkdocs.structure.nav import Link, Section
from mkdocs.structure.pages import Page
from yaml import SafeLoader, load

# -----------------------------------------------------------------------------
# Class
# -----------------------------------------------------------------------------

# Blog plugin configuration scheme
class BlogPluginConfig(Config):
    enabled = opt.Type(bool, default = True)

    # Options for blog
    blog_dir = opt.Type(str, default = "blog")
    blog_custom_dir = opt.Optional(opt.Type(str)) # Do not use, internal option

    # Options for posts
    post_date_format = opt.Type(str, default = "long")
    post_url_date_format = opt.Type(str, default = "yyyy/MM/dd")
    post_url_format = opt.Type(str, default = "{date}/{slug}")
    post_slugify = opt.Type((type(slugify), partial), default = slugify)
    post_slugify_separator = opt.Type(str, default = "-")
    post_excerpt = opt.Choice(["optional", "required"], default = "optional")
    post_excerpt_max_authors = opt.Type(int, default = 1)
    post_excerpt_max_categories = opt.Type(int, default = 5)
    post_excerpt_separator = opt.Type(str, default = "<!-- more -->")
    post_readtime = opt.Type(bool, default = True)
    post_readtime_words_per_minute = opt.Type(int, default = 265)

    # Options for archive
    archive = opt.Type(bool, default = True)
    archive_name = opt.Type(str, default = "blog.archive")
    archive_date_format = opt.Type(str, default = "yyyy")
    archive_url_date_format = opt.Type(str, default = "yyyy")
    archive_url_format = opt.Type(str, default = "archive/{date}")

    # Options for categories
    categories = opt.Type(bool, default = True)
    categories_name = opt.Type(str, default = "blog.categories")
    categories_url_format = opt.Type(str, default = "category/{slug}")
    categories_slugify = opt.Type((type(slugify), partial), default = slugify)
    categories_slugify_separator = opt.Type(str, default = "-")
    categories_allowed = opt.Type(list, default = [])

    # Options for pagination
    pagination = opt.Type(bool, default = True)
    pagination_per_page = opt.Type(int, default = 10)
    pagination_url_format = opt.Type(str, default = "page/{page}")
    pagination_template = opt.Type(str, default = "~2~")
    pagination_keep_content = opt.Type(bool, default = False)

    # Options for authors
    authors = opt.Type(bool, default = True)
    authors_file = opt.Type(str, default = "{blog}/.authors.yml")

    # Options for drafts
    draft = opt.Type(bool, default = False)
    draft_on_serve = opt.Type(bool, default = True)
    draft_if_future_date = opt.Type(bool, default = False)

    # Deprecated options
    authors_in_excerpt = opt.Deprecated(moved_to = "post_excerpt_max_authors")

# -----------------------------------------------------------------------------

# Blog plugin
class BlogPlugin(BasePlugin[BlogPluginConfig]):

    # Determine whether we're running under dirty reload
    def on_startup(self, *, command, dirty):
        self.is_serve = (command == "serve")
        self.dirtyreload = False
        self.dirty = dirty

    # Initialize plugin
    def on_config(self, config):
        if not self.config.enabled:
            return

        # Resolve source directory for posts
        self.post_dir = self._resolve("posts")

        # Initialize posts
        self.post_map = dict()
        self.post_meta_map = dict()
        self.post_pages = []
        self.post_pager_pages = []
        self.post_excerpt_map = dict()

        # Initialize archive
        if self.config.archive:
            self.archive_map = dict()
            self.archive_post_map = dict()

        # Initialize categories
        if self.config.categories:
            self.category_map = dict()
            self.category_name_map = dict()
            self.category_post_map = dict()

        # Initialize authors
        if self.config.authors:
            self.authors_map = dict()

            # Resolve authors file
            path = os.path.normpath(os.path.join(
                config.docs_dir,
                self.config.authors_file.format(
                    blog = self.config.blog_dir
                )
            ))

            # Load authors map, if it exists
            if os.path.isfile(path):
                with open(path, encoding = "utf-8") as f:
                    self.authors_map = load(f, SafeLoader) or {}

        # Ensure that format strings have no trailing slashes
        for option in [
            "post_url_format",
            "archive_url_format",
            "categories_url_format",
            "pagination_url_format"
        ]:
            if self.config[option].endswith("/"):
                log.error(f"Option '{option}' must not contain trailing slash.")
                sys.exit(1)

        # If pagination should not be used, set to large value
        if not self.config.pagination:
            self.config.pagination_per_page = 1e7

        # By default, drafts are rendered when the documentation is served,
        # but not when it is built. This should nicely align with the expected
        # user experience when authoring documentation.
        if self.is_serve and self.config.draft_on_serve:
            self.config.draft = True

    # Adjust paths to assets in the posts directory and preprocess posts
    def on_files(self, files, *, config):
        if not self.config.enabled:
            return

        # Adjust destination paths for assets
        path = self._resolve("assets")
        for file in files.media_files():
            if self.post_dir not in file.src_uri:
                continue

            # Compute destination URL
            file.url = file.url.replace(self.post_dir, path)

            # Compute destination file system path
            file.dest_uri = file.dest_uri.replace(self.post_dir, path)
            file.abs_dest_path = os.path.join(config.site_dir, file.dest_path)

        # Hack: as post URLs are dynamically computed and can be configured by
        # the author, we need to compute them before we process the contents of
        # any other page or post. If we wouldn't do that, URLs would be invalid
        # and we would need to patch them afterwards. The only way to do this
        # correctly is to first extract the metadata of all posts. Additionally,
        # while we're at it, generate all archive and category pages as we have
        # the post metadata on our hands. This ensures that we can safely link
        # from anywhere to all pages that are generated as part of the blog.
        for file in files.documentation_pages():
            if self.post_dir not in file.src_uri:
                continue

            # Read and preprocess post
            with open(file.abs_src_path, encoding = "utf-8") as f:
                markdown, meta = get_data(f.read())

                # Ensure post has a date set
                if not meta.get("date"):
                    log.error(f"Blog post '{file.src_uri}' has no date set.")
                    sys.exit(1)

                # Compute slug from metadata, content or file name
                headline = utils.get_markdown_title(markdown)
                slug = meta.get("title", headline or file.name)

                # Front matter can be defind in YAML, guarded by two lines with
                # `---` markers, or MultiMarkdown, separated by an empty line.
                # If the author chooses to use MultiMarkdown syntax, date is
                # returned as a string, which is different from YAML behavior,
                # which returns a date. Thus, we must check for its type, and
                # parse the date for normalization purposes.
                if isinstance(meta["date"], str):
                    meta["date"] = date.fromisoformat(meta["date"])

                # Compute path from format string
                date_format = self.config.post_url_date_format
                path = self.config.post_url_format.format(
                    date = self._format_date(meta["date"], date_format, config),
                    slug = meta.get("slug", self.config.post_slugify(
                        slug, self.config.post_slugify_separator
                    ))
                )

                # Compute destination URL according to settings
                file.url = self._resolve(path)
                if not config.use_directory_urls:
                    file.url = ".html"
                else:
                    file.url += "/"

                # Compute destination file system path
                file.dest_uri = re.sub(r"(?<=\/)$", "index.html", file.url)
                file.abs_dest_path = os.path.join(
                    config.site_dir, file.dest_path
                )

                # Add post metadata
                self.post_meta_map[file.src_uri] = meta

        # Sort post metadata by date (descending)
        self.post_meta_map = dict(sorted(
            self.post_meta_map.items(),
            key = lambda item: item[1]["date"], reverse = True
        ))

        # Find and extract the section hosting the blog
        path = self._resolve("index.md")
        root = _host(config.nav, path)

        # Ensure blog root exists
        file = files.get_file_from_path(path)
        if not file:
            log.error(f"Blog root '{path}' does not exist.")
            sys.exit(1)

        # Generate and register files for archive
        if self.config.archive:
            name = self._translate(config, self.config.archive_name)
            data = self._generate_files_for_archive(config, files)
            if data:
                root.append({ name: data })

        # Generate and register files for categories
        if self.config.categories:
            name = self._translate(config, self.config.categories_name)
            data = self._generate_files_for_categories(config, files)
            if data:
                root.append({ name: data })

        # Hack: add posts temporarily, so MkDocs doesn't complain
        root.append({ "__posts": list(self.post_meta_map.keys()) })

    # Cleanup navigation before proceeding
    def on_nav(self, nav, *, config, files):
        if not self.config.enabled:
            return

        # Find and resolve index for cleanup
        path = self._resolve("index.md")
        file = files.get_file_from_path(path)

        # Determine blog root section
        self.main = file.page
        if self.main.parent:
            root = self.main.parent.children
        else:
            root = nav.items

        # Hack: remove temporarily added posts from the navigation
        for item in root:
            if not item.is_section or item.title != "__posts":
                continue

            # Detach previous and next links of posts
            if item.children:
                head = item.children[+0]
                tail = item.children[-1]

                # Link page prior to posts to page after posts
                if head.previous_page:
                    head.previous_page.next_page = tail.next_page

                # Link page after posts to page prior to posts
                if tail.next_page:
                    tail.next_page.previous_page = head.previous_page

                # Contain previous and next links inside posts
                head.previous_page = None
                tail.next_page     = None

            # Set blog as parent page
            for page in item.children:
                page.parent = self.main
                next = page.next_page

                # Switch previous and next links
                page.next_page = page.previous_page
                page.previous_page = next

            # Remove posts from navigation
            root.remove(item)
            break

    # Prepare post for rendering
    def on_page_markdown(self, markdown, *, page, config, files):
        if not self.config.enabled:
            return

        # Only process posts
        if self.post_dir not in page.file.src_uri:
            return

        # Skip processing of drafts
        if self._is_draft(page.file.src_uri):
            return

        # Ensure template is set or use default
        if "template" not in page.meta:
            page.meta["template"] = self._template("blog-post.html")

        # Ensure use of previously normalized value
        if isinstance(page.meta["date"], str):
            page.meta["date"] = self.post_meta_map[page.file.src_uri]["date"]

        # Ensure navigation is hidden
        page.meta["hide"] = page.meta.get("hide", [])
        if "navigation" not in page.meta["hide"]:
            page.meta["hide"].append("navigation")

        # Format date for rendering
        date_format = self.config.post_date_format
        page.meta["date_format"] = self._format_date(
            page.meta["date"], date_format, config
        )

        # Compute readtime if desired and not explicitly set
        if self.config.post_readtime:
            if "readtime" not in page.meta:
                rate = self.config.post_readtime_words_per_minute
                read = readtime.of_markdown(markdown, rate)
                page.meta["readtime"] = read.minutes

        # Compute post categories
        page.categories = []
        if self.config.categories:
            for name in page.meta.get("categories", []):
                file = files.get_file_from_path(self.category_name_map[name])
                page.categories.append(file.page)

        # Compute post authors
        page.authors = []
        if self.config.authors:
            for name in page.meta.get("authors", []):
                if name not in self.authors_map:
                    log.error(
                        f"Blog post '{page.file.src_uri}' author '{name}' "
                        f"unknown, not listed in .authors.yml"
                    )
                    sys.exit(1)

                # Add author to page
                page.authors.append(self.authors_map[name])

        # Fix stale link if previous post is a draft
        prev = page.previous_page
        while prev and self._is_draft(prev.file.src_uri):
            page.previous_page = prev.previous_page
            prev = prev.previous_page

        # Fix stale link if next post is a draft
        next = page.next_page
        while next and self._is_draft(next.file.src_uri):
            page.next_page = next.next_page
            next = next.next_page

    # Filter posts and generate excerpts for generated pages
    def on_env(self, env, *, config, files):
        if not self.config.enabled:
            return

        # Skip post excerpts on dirty reload to save time
        if self.dirtyreload:
            return

        # Remove 'toc' to disable permalinks for post excerpts
        config = copy.copy(config)
        config.markdown_extensions = [
            e for e in config.markdown_extensions if e != "toc"
        ]

        # Filter posts that should not be published
        for file in files.documentation_pages():
            if self.post_dir in file.src_uri:
                if self._is_draft(file.src_uri):
                    files.remove(file)

                # Compute navigation for post links
                file.page.links = _data_to_navigation(
                    file.page.meta.get("links", []),
                    config, files
                )

        # Ensure template is set
        if "template" not in self.main.meta:
            self.main.meta["template"] = self._template("blog.html")

        # Populate archive
        if self.config.archive:
            for path in self.archive_map:
                self.archive_post_map[path] = []

                # Generate post excerpts for archive
                base = files.get_file_from_path(path)
                for file in self.archive_map[path]:
                    self.archive_post_map[path].append(
                        self._generate_excerpt(file, base, config, files)
                    )

                # Ensure template is set
                page = base.page
                if "template" not in page.meta:
                    page.meta["template"] = self._template("blog-archive.html")

        # Populate categories
        if self.config.categories:
            for path in self.category_map:
                self.category_post_map[path] = []

                # Generate post excerpts for categories
                base = files.get_file_from_path(path)
                for file in self.category_map[path]:
                    self.category_post_map[path].append(
                        self._generate_excerpt(file, base, config, files)
                    )

                # Ensure template is set
                page = base.page
                if "template" not in page.meta:
                    page.meta["template"] = self._template("blog-category.html")

        # Resolve path of initial index
        curr = self._resolve("index.md")
        base = self.main.file

        # Initialize index
        self.post_map[curr] = []
        self.post_pager_pages.append(self.main)

        # Generate indexes by paginating through posts
        for path in self.post_meta_map.keys():
            file = files.get_file_from_path(path)
            if not self._is_draft(path):
                self.post_pages.append(file.page)
            else:
                continue

            # Generate new index when the current is full
            per_page = self.config.pagination_per_page
            if len(self.post_map[curr]) == per_page:
                offset = 1 + len(self.post_map)

                # Resolve path of new index
                curr = self.config.pagination_url_format.format(page = offset)
                curr = self._resolve(curr + ".md")

                # Generate file if it doesn't exist
                if not files.get_file_from_path(curr):
                    content = f"# {self.main.title}"
                    if self.config.pagination_keep_content:
                        content = self.main.content

                    # Generate file with content
                    self._generate_file(curr, content)

                # Register file and page
                base = self._register_file(curr, config, files)
                page = self._register_page(base, config, files)

                # Inherit page metadata, title and position
                page.meta          = self.main.meta
                page.title         = self.main.title
                page.parent        = self.main
                page.previous_page = self.main.previous_page
                page.next_page     = self.main.next_page

                # Initialize next index
                self.post_map[curr] = []
                self.post_pager_pages.append(page)

            # Assign post excerpt to current index
            self.post_map[curr].append(
                self._generate_excerpt(file, base, config, files)
            )

    # Populate generated pages
    def on_page_context(self, context, *, page, config, nav):
        if not self.config.enabled:
            return

        # Provide post excerpts for index
        path = page.file.src_uri
        if path in self.post_map:
            context["posts"] = self.post_map[path]

            # Create pagination
            pagination = paginate.Page(
                self.post_pages,
                page = list(self.post_map.keys()).index(path) + 1,
                items_per_page = self.config.pagination_per_page,
                url_maker = lambda n: utils.get_relative_url(
                    self.post_pager_pages[n - 1].url,
                    page.url
                )
            )

            # Create pagination pager
            context["pagination"] = lambda args: pagination.pager(
                format = self.config.pagination_template,
                show_if_single_page = False,
                **args
            )

        # Provide post excerpts for archive
        if self.config.archive:
            if path in self.archive_post_map:
                context["posts"] = self.archive_post_map[path]

        # Provide post excerpts for categories
        if self.config.categories:
            if path in self.category_post_map:
                context["posts"] = self.category_post_map[path]

    # Determine whether we're running under dirty reload
    def on_serve(self, server, *, config, builder):
        self.dirtyreload = self.dirty

    # -------------------------------------------------------------------------

    # Generate and register files for archive
    def _generate_files_for_archive(self, config, files):
        for path, meta in self.post_meta_map.items():
            file = files.get_file_from_path(path)
            if self._is_draft(path):
                continue

            # Compute name from format string
            date_format = self.config.archive_date_format
            name = self._format_date(meta["date"], date_format, config)

            # Compute path from format string
            date_format = self.config.archive_url_date_format
            path = self.config.archive_url_format.format(
                date = self._format_date(meta["date"], date_format, config)
            )

            # Create file for archive if it doesn't exist
            path = self._resolve(path + ".md")
            if path not in self.archive_map:
                self.archive_map[path] = []

                # Generate file for archive if it doesn't exist
                if not files.get_file_from_path(path):
                    self._generate_file(path, f"# {name}")

                # Register file for archive
                self._register_file(path, config, files)

            # Assign current post to archive
            self.archive_map[path].append(file)

        # Return generated archive files
        return list(self.archive_map.keys())

    # Generate and register files for categories
    def _generate_files_for_categories(self, config, files):
        allowed = set(self.config.categories_allowed)
        for path, meta in self.post_meta_map.items():
            file = files.get_file_from_path(path)
            if self._is_draft(path):
                continue

            # Ensure category is in (non-empty) allow list
            categories = set(meta.get("categories", []))
            if allowed:
                for name in categories - allowed:
                    log.error(
                        f"Blog post '{file.src_uri}' uses category '{name}' "
                        f"which is not in allow list."
                    )
                    sys.exit(1)

            # Traverse all categories of the post
            for name in categories:
                path = self.config.categories_url_format.format(
                    slug = self.config.categories_slugify(
                        name, self.config.categories_slugify_separator
                    )
                )

                # Create file for category if it doesn't exist
                path = self._resolve(path + ".md")
                if path not in self.category_map:
                    self.category_map[path] = []

                    # Generate file for category if it doesn't exist
                    if not files.get_file_from_path(path):
                        self._generate_file(path, f"# {name}")

                    # Register file for category
                    self._register_file(path, config, files)

                    # Link category path to name
                    self.category_name_map[name] = path

                # Assign current post to category
                self.category_map[path].append(file)

        # Sort categories alphabetically (ascending)
        self.category_map = dict(sorted(self.category_map.items()))

        # Return generated category files
        return list(self.category_map.keys())

    # -------------------------------------------------------------------------

    # Check if a post is a draft
    def _is_draft(self, path):
        meta = self.post_meta_map[path]
        if not self.config.draft:

            # Check if post date is in the future
            future = False
            if self.config.draft_if_future_date:
                future = meta["date"] > date.today()

            # Check if post is marked as draft
            return meta.get("draft", future)

        # Post is not a draft
        return False

    # Resolve template
    def _template(self, path):
        if self.config.blog_custom_dir:
            return posixpath.join(self.config.blog_custom_dir, path)
        else:
            return path

    # Generate a post excerpt relative to base
    def _generate_excerpt(self, file, base, config, files):
        page = file.page

        # Check if we already generated the post excerpt
        if file.src_uri in self.post_excerpt_map:
            return self.post_excerpt_map[file.src_uri]

        # Generate temporary file and page for post excerpt
        temp = self._register_file(file.src_uri, config)
        excerpt = Page(page.title, temp, config)

        # Check for separator, if post excerpt is required
        separator = self.config.post_excerpt_separator
        if self.config.post_excerpt == "required":
            if separator not in page.markdown:
                log.error(f"Blog post '{temp.src_uri}' has no excerpt.")
                sys.exit(1)

        # Increase level of h1-h5 headlines for excerpts
        markdown = page.markdown
        markdown = re.sub(
            r"(^#{1,5})", "#\\1",
            markdown, flags = re.MULTILINE
        )

        # Extract content and metadata from original post
        excerpt.file.url = base.url
        excerpt.markdown = markdown
        excerpt.meta     = page.meta

        # Render post
        excerpt.render(config, files)

        # Extract excerpt and revert page URL
        excerpt.file.url = page.url
        excerpt.content  = excerpt.content.split(separator)[0]

        # Determine maximum number of authors and categories
        max_authors    = self.config.post_excerpt_max_authors
        max_categories = self.config.post_excerpt_max_categories

        # Obtain computed metadata from original post
        excerpt.authors    = page.authors[:max_authors]
        excerpt.categories = page.categories[:max_categories]

        # Return post excerpt after caching
        self.post_excerpt_map[file.src_uri] = excerpt
        return excerpt

    # Generate a file with the given template and content
    def _generate_file(self, path, content):
        content = f"---\nsearch:\n  exclude: true\n---\n\n{content}"
        utils.write_file(
            bytes(content, "utf-8"),
            os.path.join(self.temp_dir, path)
        )

    # Register a file
    def _register_file(self, path, config, files = Files([])):
        file = files.get_file_from_path(path)
        if not file:
            urls = config.use_directory_urls
            file = File(path, self.temp_dir, config.site_dir, urls)
            files.append(file)

        # Return file
        return file

    # Register and populate a page
    def _register_page(self, file, config, files):
        page = Page(None, file, config)
        _populate_page(page, config, files)
        return page

    # Translate the given placeholder value
    def _translate(self, config, value):
        env = config.theme.get_env()

        # Load language template and return translation for placeholder
        language = "partials/language.html"
        template = env.get_template(language, None, { "config": config })
        return template.module.t(value)

    # Resolve path relative to blog root
    def _resolve(self, *args):
        path = posixpath.join(self.config.blog_dir, *args)
        return posixpath.normpath(path)

    # Format date according to locale
    def _format_date(self, date, format, config):
        return format_date(
            date,
            format = format,
            locale = config.theme["language"]
        )

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

# Search the given navigation section (from the configuration) recursively to
# find the section to host all generated pages (archive, categories, etc.)
def _host(nav, path):

    # Search navigation dictionary
    if isinstance(nav, dict):
        for _, item in nav.items():
            result = _host(item, path)
            if result:
                return result

    # Search navigation list
    elif isinstance(nav, list):
        if path in nav:
            return nav

        # Search each list item
        for item in nav:
            if isinstance(item, dict) and path in item.values():
                if path in item.values():
                    return nav
            else:
                result = _host(item, path)
                if result:
                    return result

# Copied and adapted from MkDocs, because we need to return existing pages and
# support anchor names as subtitles, which is pretty fucking cool.
def _data_to_navigation(nav, config, files):

    # Search navigation dictionary
    if isinstance(nav, dict):
        return [
            _data_to_navigation((key, value), config, files)
            if isinstance(value, str) else
            Section(
                title = key,
                children = _data_to_navigation(value, config, files)
            )
                for key, value in nav.items()
        ]

    # Search navigation list
    elif isinstance(nav, list):
        return [
            _data_to_navigation(item, config, files)[0]
            if isinstance(item, dict) and len(item) == 1 else
            _data_to_navigation(item, config, files)
                for item in nav
        ]

    # Extract navigation title and path and split anchors
    title, path = nav if isinstance(nav, tuple) else (None, nav)
    path, _, anchor = path.partition("#")

    # Try to load existing file
    file = files.get_file_from_path(path)
    if not file:
        return Link(title, path)

    # Generate temporary file as for post excerpts
    else:
        urls = config.use_directory_urls
        link = File(path, config.docs_dir, config.site_dir, urls)
        page = Page(title or file.page.title, link, config)

        # Set destination file system path and URL from original file
        link.dest_uri      = file.dest_uri
        link.abs_dest_path = file.abs_dest_path
        link.url           = file.url

        # Retrieve name of anchor by misusing the search index
        if anchor:
            item = SearchIndex()._find_toc_by_id(file.page.toc, anchor)

            # Set anchor name as subtitle
            page.meta["subtitle"] = item.title
            link.url += f"#{anchor}"

        # Return navigation item
        return page

# -----------------------------------------------------------------------------
# Data
# -----------------------------------------------------------------------------

# Set up logging
log = logging.getLogger("mkdocs")
log.addFilter(DuplicateFilter())
