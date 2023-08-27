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

from __future__ import annotations

import logging
import os
import posixpath
import re
import readtime
import yaml

from babel.dates import format_date
from copy import copy
from datetime import datetime
from fnmatch import fnmatch
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.exceptions import PluginError
from mkdocs.plugins import BasePlugin, event_priority
from mkdocs.structure import StructureItem
from mkdocs.structure.files import File, Files, InclusionLevel
from mkdocs.structure.nav import Link, Navigation, Section
from mkdocs.structure.pages import Page
from mkdocs.structure.toc import AnchorLink, TableOfContents
from mkdocs.utils import get_relative_url
from paginate import Page as Pagination
from shutil import rmtree
from tempfile import mkdtemp
from urllib.parse import urlparse
from yaml import SafeLoader

from .author import Author, Authors
from .config import BlogConfig
from .structure import Archive, Category, Excerpt, Reference, Post, View
from .templates import url_filter

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

# Blog plugin
class BlogPlugin(BasePlugin[BlogConfig]):
    supports_multiple_instances = True

    # Initialize plugin
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialize incremental builds
        self.is_serve = False
        self.is_dirty = False

        # Initialize a temporary directory
        self.temp_dir = mkdtemp()

    # Determine whether we're serving the site
    def on_startup(self, *, command, dirty):
        self.is_serve = command == "serve"
        self.is_dirty = dirty

    # Initialize authors and set defaults
    def on_config(self, config):
        if not self.config.enabled:
            return

        # Initialize entrypoint
        self.blog: View

        # Initialize and resolve authors, if enabled
        if self.config.authors:
            self.authors = self._resolve_authors(config)

        # Initialize table of contents settings
        if not isinstance(self.config.archive_toc, bool):
            self.config.archive_toc = self.config.blog_toc
        if not isinstance(self.config.categories_toc, bool):
            self.config.categories_toc = self.config.blog_toc

        # By default, drafts are rendered when the documentation is served,
        # but not when it is built, for a better user experience
        if self.is_serve and self.config.draft_on_serve:
            self.config.draft = True

    # Remove posts before constructing navigation (run later) - allow other
    # plugins to alter the list of files and navigation prior to this plugin
    @event_priority(-50)
    def on_files(self, files, *, config):
        if not self.config.enabled:
            return

        # Resolve path to entrypoint and site directory
        root = posixpath.normpath(self.config.blog_dir)
        site = config.site_dir

        # Compute path to posts directory
        path = self.config.post_dir.format(blog = root)
        path = posixpath.normpath(path)

        # Generate entrypoint, if it does not exist, and temporarily remove
        # posts and views provided by the author (custom index pages)
        self._generate(config, files)
        for file in files:
            if not file.src_uri.startswith(root):
                continue

            # Temporarily remove posts and adjust destination paths for assets
            if file.src_uri.startswith(path):

                # We must exclude all files related to posts from here on, so
                # MkDocs doesn't attach them to the navigation when populating.
                # Adding them back in `on_nav` ensures they are processed unless
                # excluded by being tagged as a draft or through other means.
                if file.is_documentation_page():
                    file.inclusion = InclusionLevel.EXCLUDED

                # We also need to adjust destination paths for assets to remove
                # the purely functional posts directory prefix when building
                if file.is_media_file():
                    file.dest_uri      = file.dest_uri.replace(path, root)
                    file.abs_dest_path = os.path.join(site, file.dest_path)
                    file.url           = file.url.replace(path, root)

                # Continue with next file
                continue

            # Temporarily remove views, i.e., generated pages
            if self._is_generated(file):
                file.inclusion = InclusionLevel.EXCLUDED

    # Resolve and load posts and generate indexes (run later) - we resolve all
    # posts after the navigation is constructed in order to allow other plugins
    # to alter the navigation (e.g. awesome-pages) before we start to add pages
    # generated by this plugin. Post URLs must be computed before any Markdown
    # processing, so that when linking to and from posts, MkDocs behaves exactly
    # the same as with regular documentation pages. We create all pages related
    # to posts as part of this plugin, so we control the entire process.
    @event_priority(-50)
    def on_nav(self, nav, *, config, files):
        if not self.config.enabled:
            return

        # Resolve entrypoint and posts sorted by descending date - if the posts
        # directory or entrypoint do not exist, they are automatically created
        self.blog = self._resolve(files, config, nav)
        self.blog.posts = sorted(
            self._resolve_posts(files, config),
            key = lambda post: post.config.date.created,
            reverse = True
        )

        # Attach posts to entrypoint without adding them to the navigation, so
        # that the entrypoint is considered to be the active page for each post.
        # Hack: MkDocs has a bug where pages that are marked to be not in the
        # navigation are auto-populated nonetheless - see https://t.ly/7aYnO
        self._attach(self.blog, [None, *reversed(self.blog.posts), None])
        for post in self.blog.posts:
            post.file.inclusion = InclusionLevel.NOT_IN_NAV

        # Generate and attach views for archive
        if self.config.archive:
            views = [*self._generate_archive(config, files)]
            self.blog.views.extend(views)

            # Attach and link views for archive
            title = self._translate(self.config.archive_name, config)
            self._attach_to(self.blog, Section(title, views), nav)

        # Generate and attach views for categories
        if self.config.categories:
            views = [*self._generate_categories(config, files)]
            self.blog.views.extend(views)

            # Attach and link views for categories
            title = self._translate(self.config.categories_name, config)
            self._attach_to(self.blog, Section(title, views), nav)

        # Paginate generated views, if enabled
        if self.config.pagination:
            for view in [*self._resolve_views(self.blog)]:
                for page in self._generate_pages(view, config, files):
                    view.pages.append(page)

    # Prepare post for rendering (run later) - allow other plugins to alter
    # the contents or metadata of a post before it is rendered and make sure
    # that the post includes a separator, which is essential for rendering
    # excerpts that should be included in views
    @event_priority(-50)
    def on_page_markdown(self, markdown, *, page, config, files):
        if not self.config.enabled:
            return

        # Skip if page is not a post managed by this instance - this plugin has
        # support for multiple instances, which is why this check is necessary
        if page not in self.blog.posts:
            if not self.config.pagination:
                return

            # We set the contents of the view to its title if pagination should
            # not keep the content of the original view on paginaged views
            if not self.config.pagination_keep_content:
                if page in self._resolve_views(self.blog):
                    assert isinstance(page, View)
                    if 0 < page.pages.index(page):
                        return f"# {page.title}"

            # Nothing more to be done for views
            return

        # Extract and assign authors to post, if enabled
        if self.config.authors:
            for name in page.config.authors:
                if name not in self.authors:
                    raise PluginError(f"Couldn't find author '{name}'")

                # Append to list of authors
                page.authors.append(self.authors[name])

        # Compute readtime of post, if enabled and not explicitly set
        if self.config.post_readtime:
            rate = self.config.post_readtime_words_per_minute

            # There's a bug in the readtime library which causes it to fail if
            # the input string contains emojis - see https://t.ly/qEoHq
            if not page.config.readtime:
                data = markdown.encode("unicode_escape")
                read = readtime.of_markdown(data, rate)
                page.config.readtime = read.minutes

        # Extract settings for excerpts
        separator      = self.config.post_excerpt_separator
        max_authors    = self.config.post_excerpt_max_authors
        max_categories = self.config.post_excerpt_max_categories

        # Ensure presence of separator and throw, if its absent and required -
        # we append the separator to the end of the contents of the post, if it
        # is not already present, so we can remove footnotes or other content
        # from the excerpt without affecting the content of the excerpt
        if separator not in page.markdown:
            path = page.file.src_path
            if self.config.post_excerpt == "required":
                raise PluginError(
                    f"Couldn't find '{separator}' separator in '{path}'"
                )
            else:
                page.markdown += f"\n\n{separator}"

        # Create excerpt for post and inherit authors and categories - excerpts
        # can contain a subset of the authors and categories of the post
        page.excerpt            = Excerpt(page, config, files)
        page.excerpt.authors    = page.authors[:max_authors]
        page.excerpt.categories = page.categories[:max_categories]

    # Register template filters for plugin
    def on_env(self, env, *, config, files):
        if not self.config.enabled:
            return

        # Transform links to point to posts and pages
        for post in self.blog.posts:
            self._generate_links(post, config, files)

        # Filter for formatting dates related to posts
        def date_filter(date: datetime):
            return self._format_date_for_post(date, config)

        # Register custom template filters
        env.filters["date"] = date_filter
        env.filters["url"]  = url_filter

    # Prepare view for rendering (run latest) - views are rendered last, as we
    # need to mutate the navigation to account for pagination. The main problem
    # is that we need to replace the view in the navigation, because otherwise
    # the view would not be considered active.
    @event_priority(-100)
    def on_page_context(self, context, *, page, config, nav):
        if not self.config.enabled:
            return

        # Skip if page is not a view managed by this instance - this plugin has
        # support for multiple instances, which is why this check is necessary
        if page not in self._resolve_views(self.blog):
            return

        # Retrieve parent view or section
        assert isinstance(page, View)
        main = page.parent

        # If this page is a view, and the parent page is a view as well, we got
        # a paginated view and need to replace the parent with the current view.
        # Paginated views are always rendered at the end of the build, which is
        # why we can safely mutate the navigation at this point
        if isinstance(main, View):
            page.parent = main.parent

            # Replace view in navigation and rewire it - the current view in the
            # navigation becomes the main view, thus the entire chain moves one
            # level up. It's essential that the rendering order is linear, or
            # else we might end up with a broken navigation.
            items = self._resolve_siblings(main, nav)
            items[items.index(main)] = page

        # Render excerpts and prepare pagination
        posts, pagination = self._render(page)

        # Render pagination links
        def pager(args: object):
            return pagination.pager(
                format = self.config.pagination_format,
                show_if_single_page = self.config.pagination_if_single_page,
                **args
            )

        # Assign posts and pagination to context
        context["posts"]      = posts
        context["pagination"] = pager if pagination else None

    # Remove temporary directory on shutdown
    def on_shutdown(self):
        rmtree(self.temp_dir)

    # -------------------------------------------------------------------------

    # Check if the given post is excluded
    def _is_excluded(self, post: Post):
        if self.config.draft:
            return False

        # If a post was not explicitly marked or unmarked as draft, and the
        # date should be taken into account, we automatically mark it as draft
        # if the publishing date is in the future. This, of course, is opt-in
        # and must be explicitly enabled by the author.
        if not isinstance(post.config.draft, bool):
            if self.config.draft_if_future_date:
                return post.config.date.created > datetime.now()

        # Post might be a draft
        return bool(post.config.draft)

    # Check if the given file is generated
    def _is_generated(self, file: File):
        for slug in [
            self.config.archive_url_format,
            self.config.categories_url_format
        ]:
            slug = re.sub(r"{[^}]+}", "*", slug)

            # Normalize path and strip slashes at the beginning and end, and
            # check if the given file is usually generated by this plugin
            path = posixpath.normpath(slug.strip("/"))
            path = posixpath.join(self.config.blog_dir, f"{path}.md")
            if fnmatch(file.src_uri, path):
                return True

        # File is not generated
        return False

    # -------------------------------------------------------------------------

    # Resolve entrypoint - the entrypoint of the blog must have been created
    # if it did not exist before, and hosts all posts sorted by descending date
    def _resolve(self, files: Files, config: MkDocsConfig, nav: Navigation):
        path = os.path.join(self.config.blog_dir, "index.md")
        path = os.path.normpath(path)

        # Obtain entrypoint page
        file = files.get_file_from_path(path)
        page = file.page

        # Create entrypoint view and attach to parent
        view = View(page.title, file, config)
        self._attach(page.parent, [
            page.previous_page,
            view,
            page.next_page
        ])

        # Update entrypoint in navigation
        for items in [self._resolve_siblings(view, nav), nav.pages]:
            items[items.index(page)] = view

        # Return view
        return view

    # Resolve post - the caller must make sure that the given file points to an
    # actual post (and not a page), or behavior might be unpredictable
    def _resolve_post(self, file: File, config: MkDocsConfig):
        post = Post(file, config)

        # Compute path and create a temporary file for path resolution
        path = self._format_path_for_post(post, config)
        temp = self._path_to_file(path, config, temp = False)

        # Replace destination file system path and URL
        file.dest_uri      = temp.dest_uri
        file.abs_dest_path = temp.abs_dest_path
        file.url           = temp.url

        # Replace canonical URL and return post
        post._set_canonical_url(config.site_url)
        return post

    # Resolve posts from directory - traverse all documentation pages and filter
    # and yield those that are located in the posts directory
    def _resolve_posts(self, files: Files, config: MkDocsConfig):
        path = self.config.post_dir.format(blog = self.config.blog_dir)
        path = os.path.normpath(path)

        # Create posts directory, if it does not exist
        docs = os.path.relpath(config.docs_dir)
        name = os.path.join(docs, path)
        if not os.path.isdir(name):
            os.makedirs(name, exist_ok = True)

        # Filter posts from pages - prior to calling this function, the caller
        # should've excluded all posts, so they're not listed in the navigation
        inclusion = InclusionLevel.is_excluded
        for file in files.documentation_pages(inclusion = inclusion):
            if not file.src_path.startswith(path):
                continue

            # Resolve post - in order to determine whether a post should be
            # excluded, we must load it and analyze its metadata. All posts
            # marked as drafts are excluded, except for when the author has
            # configured drafts to be included in the navigation.
            post = self._resolve_post(file, config)
            if not self._is_excluded(post):
                yield post

    # Resolve authors - check if there's an authors file at the configured
    # location, and if one was found, load and validate it
    def _resolve_authors(self, config: MkDocsConfig):
        path = self.config.authors_file.format(blog = self.config.blog_dir)
        path = os.path.normpath(path)

        # Resolve path relative to docs directory
        docs = os.path.relpath(config.docs_dir)
        file = os.path.join(docs, path)

        # If the authors file does not exist, return here
        config: Authors = Authors()
        if not os.path.isfile(file):
            return config.authors

        # Open file and parse as YAML
        with open(file, encoding = "utf-8") as f:
            config.config_file_path = os.path.abspath(file)
            try:
                config.load_dict(yaml.load(f, SafeLoader) or {})

            # The authors file could not be loaded because of a syntax error,
            # which we display to the author with a nice error message
            except Exception as e:
                raise PluginError(
                    f"Error reading authors file '{path}' in '{docs}':\n"
                    f"{e}"
                )

        # Validate authors and throw if errors occurred
        errors, warnings = config.validate()
        if not config.authors and warnings:
            log.warning(
                f"Action required: the format of the authors file changed.\n"
                f"All authors must now be located under the 'authors' key.\n"
                f"Please adjust '{file}' to match:\n"
                f"\n"
                f"authors:\n"
                f"  squidfunk:\n"
                f"    avatar: https://avatars.githubusercontent.com/u/932156\n"
                f"    description: Creator\n"
                f"    name: Martin Donath\n"
                f"\n"
            )
        for _, w in warnings:
            log.warning(w)
        for _, e in errors:
            raise PluginError(
                f"Error reading authors file '{path}' in '{docs}':\n"
                f"{e}"
            )

        # Return authors
        return config.authors

    # Resolve views and pages of the given view that were generated by this
    # plugin when building the site and yield them in pre-order
    def _resolve_views(self, view: View):
        yield view

        # Resolve views recursively
        for page in view.views:
            for next in self._resolve_views(page):
                assert isinstance(next, View)
                yield next

        # Resolve pages
        for page in view.pages:
            assert isinstance(page, View)
            yield page

    # Resolve siblings of a navigation item
    def _resolve_siblings(self, item: StructureItem, nav: Navigation):
        if isinstance(item.parent, Section):
            return item.parent.children
        else:
            return nav.items

    # -------------------------------------------------------------------------

    # Attach a list of pages to each other and to the given parent item without
    # explicitly adding them to the navigation, which can be done by the caller
    def _attach(self, parent: StructureItem, pages: list[Page]):
        for tail, page, head in zip(pages, pages[1:], pages[2:]):

            # Link page to parent and siblings
            page.parent        = parent
            page.previous_page = tail
            page.next_page     = head

    # Attach a section as a sibling to the given view, make sure it's pages are
    # part of the navigation, and ensure all pages are linked correctly
    def _attach_to(self, view: View, section: Section, nav: Navigation):
        section.parent = view.parent

        # Resolve siblings, which are the children of the parent section, or
        # the top-level list of navigation items if the view is at the root of
        # the project, and append the given section to it. It's currently not
        # possible to chose the position of a section.
        items = self._resolve_siblings(view, nav)
        items.append(section)

        # Find last sibling that is a page, skipping sections, as we need to
        # append the given section after all other pages
        tail = next(item for item in reversed(items) if isinstance(item, Page))
        head = tail.next_page

        # Attach section to navigation and pages to each other
        nav.pages.extend(section.children)
        self._attach(section, [tail, *section.children, head])

    # -------------------------------------------------------------------------

    # Generate entrypoint - the entrypoint must always be present, and thus is
    # created before the navigation is constructed if it does not exist
    def _generate(self, config: MkDocsConfig, files: Files):
        path = os.path.join(self.config.blog_dir, "index.md")
        path = os.path.normpath(path)

        # Create entrypoint, if it does not exist - note that the entrypoint is
        # added to the docs directory, not to the temporary directory
        docs = os.path.relpath(config.docs_dir)
        file = os.path.join(docs, path)
        if not os.path.isfile(file):
            file = self._path_to_file(path, config, temp = False)
            self._save_to_file(file.abs_src_path, "# Blog\n\n")

            # Append entrypoint to files
            files.append(file)

    # Generate views for archive - analyze posts and generate the necessary
    # views, taking the date format provided by the author into account
    def _generate_archive(self, config: MkDocsConfig, files: Files):
        for post in self.blog.posts:
            date = post.config.date.created

            # Compute name and path of archive view
            name = self._format_date_for_archive(date, config)
            path = self._format_path_for_archive(post, config)

            # Create file for view, if it does not exist
            file = files.get_file_from_path(path)
            if not file:
                file = self._path_to_file(path, config)
                self._save_to_file(file.abs_src_path, f"# {name}")

                # Append view to files
                files.append(file)

            # Create and yield view - we don't explicitly set the title of
            # the view, so authors can override them in the page's content
            if not isinstance(file.page, Archive):
                yield Archive(None, file, config)
                file.inclusion = InclusionLevel.INCLUDED

            # Assign post to archive
            assert isinstance(file.page, Archive)
            file.page.posts.append(post)

    # Generate views for categories - analyze posts and generate the necessary
    # views, taking the allowed categories as set by the author into account
    def _generate_categories(self, config: MkDocsConfig, files: Files):
        for post in self.blog.posts:
            for name in post.config.categories:
                path = self._format_path_for_category(name)

                # Ensure category is in non-empty allow list
                categories = self.config.categories_allowed or [name]
                if name not in categories:
                    docs = os.path.relpath(config.docs_dir)
                    path = os.path.relpath(post.file.abs_src_path, docs)
                    raise PluginError(
                        f"Error reading categories of post '{path}' in "
                        f"'{docs}': category '{name}' not in allow list"
                    )

                # Create file for view, if it does not exist
                file = files.get_file_from_path(path)
                if not file:
                    file = self._path_to_file(path, config)
                    self._save_to_file(file.abs_src_path, f"# {name}")

                    # Append view to files
                    files.append(file)

                # Create and yield view - we don't explicitly set the title of
                # the view, so authors can override them in the page's content
                if not isinstance(file.page, Category):
                    yield Category(None, file, config)
                    file.inclusion = InclusionLevel.INCLUDED

                # Assign post to category and vice versa
                assert isinstance(file.page, Category)
                file.page.posts.append(post)
                post.categories.append(file.page)

    # Generate pages for pagination - analyze view and generate the necessary
    # pages, creating a chain of views for simple rendering and replacement
    def _generate_pages(self, view: View, config: MkDocsConfig, files: Files):
        yield view

        # Extract settings for pagination
        step = self.config.pagination_per_page
        prev = view

        # Compute pagination boundaries and create pages - pages are internally
        # handled as copies of a view, as they map to the same source location
        for at in range(step, len(view.posts), step):
            base, _ = posixpath.splitext(view.file.src_uri)

            # Compute path and create a file for pagination
            path = self._format_path_for_pagination(base, 1 + at // step)
            file = self._path_to_file(path, config)

            # Replace source file system path and append to files
            file.src_uri      = view.file.src_uri
            file.abs_src_path = view.file.abs_src_path
            files.append(file)

            # Create view and attach to parent - we don't set the title of the
            # view, so authors can override them in the page's content
            next = View(None, file, config)
            self._attach(prev, [
                view.previous_page,
                next,
                view.next_page
            ])

            # Assign posts and pages to view
            next.posts = view.posts
            next.pages = view.pages

            # Continue with next page
            prev = next
            yield next

    # Generate links from the given post to other posts, pages, and sections -
    # this can only be done once all posts and pages have been parsed
    def _generate_links(self, post: Post, config: MkDocsConfig, files: Files):
        if not post.config.links:
            return

        # Resolve path relative to docs directory for error reporting
        docs = os.path.relpath(config.docs_dir)
        path = os.path.relpath(post.file.abs_src_path, docs)

        # Find all links to pages and replace them with references - while all
        # internal links are processed, external links remain as they are
        for link in _find_links(post.config.links.items):
            url = urlparse(link.url)
            if url.scheme:
                continue

            # Resolve file for link, and throw if the file could not be found -
            # authors can link to other pages, as well as to assets or files of
            # any kind, but it is essential that the file that is linked to is
            # found, so errors are actually catched and reported
            file = files.get_file_from_path(url.path)
            if not file:
                raise PluginError(
                    f"Error reading metadata of post '{path}' in '{docs}':\n"
                    f"Couldn't find file for link '{url.path}'"
                )

            # If the file linked to is not a page, but an asset or any other
            # file, we resolve the destination URL and continue
            if not isinstance(file.page, Page):
                link.url = file.url
                continue

            # Cast link to reference
            link.__class__ = Reference
            assert isinstance(link, Reference)

            # Assign page title, URL and metadata to link
            link.title = link.title or file.page.title
            link.url   = file.page.url
            link.meta  = copy(file.page.meta)

            # If the link has no fragment, we can continue - if it does, we
            # need to find the matching anchor in the table of contents
            if not url.fragment:
                continue

            # Resolve anchor for fragment, and throw if the anchor could not be
            # found - authors can link to any anchor in the table of contents
            anchor = _find_anchor(file.page.toc, url.fragment)
            if not anchor:
                raise PluginError(
                    f"Error reading metadata of post '{path}' in '{docs}':\n"
                    f"Couldn't find anchor '{url.fragment}' in '{url.path}'"
                )

            # Append anchor to URL and set subtitle
            link.url += f"#{anchor.id}"
            link.meta["subtitle"] = anchor.title

    # -------------------------------------------------------------------------

    # Render excerpts and pagination for the given view
    def _render(self, view: View):
        posts, pagination = view.posts, None

        # Create pagination, if enabled
        if self.config.pagination:
            at = view.pages.index(view)

            # Compute pagination boundaries
            step = self.config.pagination_per_page
            p, q = at * step, at * step + step

            # Extract posts in pagination boundaries
            posts = view.posts[p:q]
            pagination = self._render_pagination(view, (p, q))

        # Render excerpts for selected posts
        posts = [
            self._render_post(post.excerpt, view)
                for post in posts
        ]

        # Return posts and pagination
        return posts, pagination

    # Render excerpt in the context of the given view
    def _render_post(self, excerpt: Excerpt, view: View):
        excerpt.render(view, self.config.post_excerpt_separator)

        # Determine whether to add posts to the table of contents of the view -
        # note that those settings can be changed individually for each type of
        # view, which is why we need to check the type of view and the table of
        # contents setting for that type of view
        toc = self.config.blog_toc
        if isinstance(view, Archive):
            toc = self.config.archive_toc
        if isinstance(view, Category):
            toc = self.config.categories_toc

        # Attach top-level table of contents item to view if it should be added
        # and both, the view and excerpt contain table of contents items
        if toc and excerpt.toc.items and view.toc.items:
            view.toc.items[0].children.append(excerpt.toc.items[0])

        # Return excerpt
        return excerpt

    # Create pagination for the given view and range
    def _render_pagination(self, view: View, range: tuple[int, int]):
        p, q = range

        # Create URL from the given page to another page
        def url_maker(n: int):
            return get_relative_url(view.pages[n - 1].url, view.url)

        # Return pagination
        return Pagination(
            view.posts, page = q // (q - p),
            items_per_page = q - p,
            url_maker = url_maker
        )

    # -------------------------------------------------------------------------

    # Format path for post
    def _format_path_for_post(self, post: Post, config: MkDocsConfig):
        categories = post.config.categories[:self.config.post_url_max_categories]
        categories = [self._slugify_category(name) for name in categories]

        # Replace placeholders in format string
        date = post.config.date.created
        path = self.config.post_url_format.format(
            categories = "/".join(categories),
            date = self._format_date_for_post_url(date, config),
            file = post.file.name,
            slug = post.config.slug or self._slugify_post(post)
        )

        # Normalize path and strip slashes at the beginning and end
        path = posixpath.normpath(path.strip("/"))
        return posixpath.join(self.config.blog_dir, f"{path}.md")

    # Format path for archive
    def _format_path_for_archive(self, post: Post, config: MkDocsConfig):
        date = post.config.date.created
        path = self.config.archive_url_format.format(
            date = self._format_date_for_archive_url(date, config)
        )

        # Normalize path and strip slashes at the beginning and end
        path = posixpath.normpath(path.strip("/"))
        return posixpath.join(self.config.blog_dir, f"{path}.md")

    # Format path for category
    def _format_path_for_category(self, name: str):
        path = self.config.categories_url_format.format(
            slug = self._slugify_category(name)
        )

        # Normalize path and strip slashes at the beginning and end
        path = posixpath.normpath(path.strip("/"))
        return posixpath.join(self.config.blog_dir, f"{path}.md")

    # Format path for pagination
    def _format_path_for_pagination(self, base: str, page: int):
        path = self.config.pagination_url_format.format(
            page = page
        )

        # Normalize path and strip slashes at the beginning and end
        path = posixpath.normpath(path.strip("/"))
        return posixpath.join(base, f"{path}.md")

    # -------------------------------------------------------------------------

    # Format date
    def _format_date(self, date: datetime, format: str, config: MkDocsConfig):
        locale = config.theme["language"]
        return format_date(date, format = format, locale = locale)

    # Format date for post
    def _format_date_for_post(self, date: datetime, config: MkDocsConfig):
        format = self.config.post_date_format
        return self._format_date(date, format, config)

    # Format date for post URL
    def _format_date_for_post_url(self, date: datetime, config: MkDocsConfig):
        format = self.config.post_url_date_format
        return self._format_date(date, format, config)

    # Format date for archive
    def _format_date_for_archive(self, date: datetime, config: MkDocsConfig):
        format = self.config.archive_date_format
        return self._format_date(date, format, config)

    # Format date for archive URL
    def _format_date_for_archive_url(self, date: datetime, config: MkDocsConfig):
        format = self.config.archive_url_date_format
        return self._format_date(date, format, config)

    # -------------------------------------------------------------------------

    # Slugify post title
    def _slugify_post(self, post: Post):
        separator = self.config.post_slugify_separator
        return self.config.post_slugify(post.title, separator)

    # Slugify category
    def _slugify_category(self, name: str):
        separator = self.config.categories_slugify_separator
        return self.config.categories_slugify(name, separator)

    # -------------------------------------------------------------------------

    # Create a file for the given path, which must point to a valid source file,
    # either inside the temporary directory or the docs directory
    def _path_to_file(self, path: str, config: MkDocsConfig, *, temp = True):
        assert path.endswith(".md")
        file = File(
            path,
            config.docs_dir if not temp else self.temp_dir,
            config.site_dir,
            config.use_directory_urls
        )

        # Hack: mark file as generated, so other plugins don't think it's part
        # of the file system. This is more or less a new quasi-standard that
        # still needs to be adopted by MkDocs, and was introduced by the
        # git-revision-date-localized-plugin - see https://bit.ly/3ZUmdBx
        if temp:
            file.generated_by = "material/blog"

        # Return file
        return file

    # Create a file on the system with the given content
    def _save_to_file(self, path: str, content: str):
        os.makedirs(os.path.dirname(path), exist_ok = True)
        with open(path, "w") as f:
            f.write(content)

    # -------------------------------------------------------------------------

    # Translate the placeholder referenced by the given key
    def _translate(self, key: str, config: MkDocsConfig) -> str:
        env = config.theme.get_env()
        template = env.get_template(
            "partials/language.html", globals = { "config": config }
        )

        # Translate placeholder
        return template.module.t(key)

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

# Find all links in the given list of items
def _find_links(items: list[StructureItem]):
    for item in items:

        # Resolve link
        if isinstance(item, Link):
            yield item

        # Resolve sections recursively
        if isinstance(item, Section):
            for item in _find_links(item.children):
                assert isinstance(item, Link)
                yield item

# Find anchor in table of contents for the given id
def _find_anchor(toc: TableOfContents, id: str):
    for anchor in toc:
        if anchor.id == id:
            return anchor

        # Resolve anchors recursively
        anchor = _find_anchor(anchor.children, id)
        if isinstance(anchor, AnchorLink):
            return anchor

# -----------------------------------------------------------------------------
# Data
# -----------------------------------------------------------------------------

# Set up logging
log = logging.getLogger("mkdocs.material.blog")
