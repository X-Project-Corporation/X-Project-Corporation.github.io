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

import functools
import logging
import os
import pickle
import posixpath
import re

from click import style
from copy import deepcopy
from concurrent.futures import Future, ProcessPoolExecutor
from glob import iglob
from jinja2 import pass_context
from jinja2.runtime import Context
from logging import Logger
from mkdocs.__main__ import ColorFormatter
from mkdocs.commands.build import build
from mkdocs.config.base import Config, ConfigErrors, ConfigWarnings
from mkdocs.config.config_options import Plugins
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.exceptions import Abort, PluginError
from mkdocs.plugins import BasePlugin, event_priority
from mkdocs.structure import StructureItem
from mkdocs.structure.files import Files
from mkdocs.structure.nav import Link, Section
from mkdocs.utils import get_relative_url, get_theme_dir
from urllib.parse import ParseResult as URL, urlparse
from watchdog.events import FileSystemEvent, FileSystemEventHandler

from .config import ProjectsConfig
from .structure import Project

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

# Projects plugin
class ProjectsPlugin(BasePlugin[ProjectsConfig]):

    # Initialize plugin
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialize incremental builds
        self.is_serve = False
        self.is_dirty = False

        # Initialize process pool
        self.pool: ProcessPoolExecutor
        self.pool_jobs: dict[str, Future] = {}

        # Initialize projects
        self.projects: dict[str, MkDocsConfig] = {}

    # Determine whether we're serving the site
    def on_startup(self, *, command, dirty):
        self.is_serve = command == "serve"
        self.is_dirty = dirty

    # Resolve projects – compared to our other concurrent plugins, this plugin
    # is forced to use a process pool in order to guarantee proper isolation, as
    # MkDocs itself is not thread-safe. Additionally, all project configurations
    # are resolved and written to the cache (if enabled), as it's sufficient to
    # resolve them once on the top-level before projects are built. We might
    # need adjacent project configurations for interlinking projects.
    def on_config(self, config):
        if not self.config.enabled:
            return

        # Skip if projects should not be built - we can only exit here if we're
        # at the top-level, but not when building a nested project
        self.is_root = os.path.dirname(config.config_file_path) == os.getcwd()
        if not self.config.projects and self.is_root:
            return

        # Initialize process pool - we must initialize a new process pool for
        # every build and get rid of it when we're done, because the process
        # pool executor doesn't allow to ignore keyboard interrupts. Otherwise,
        # each process errors when we stop serving the site.
        if self.is_root:
            self.pool = ProcessPoolExecutor(self.config.concurrency)

        # Compute and normalize path to project configurations
        path = os.path.join(self.config.cache_dir, "config.pickle")
        path = os.path.normpath(path)

        # If caching is enabled or we're building a project, we try to load all
        # adjacent project configurations from the cache, as they are necessary
        # for correct link resolution between projects. Note that the only sane
        # reason to disable caching is for debugging purposes.
        os.makedirs(os.path.dirname(path), exist_ok = True)
        if self.config.cache or not self.is_root:
            if os.path.isfile(path):
                with open(path, "rb") as f:
                    self.projects = pickle.load(f)

        # Traverse projects directory and load the configuration for each
        # project, as the author may use the site URL to specify the path at
        # which a project should be stored. If the configuration file changes,
        # settings are reloaded before starting the next build.
        if not self.projects:
            for slug, project in self._find_all(config.config_file_path):
                self.projects[slug] = project

            # Prepare projects for building
            for slug, project in self._resolve_projects():
                self._prepare(slug, project, config)

            # Reverse projects to adhere to post-order and write them to cache,
            # so the projects don't need to be resolved in spawned jobs
            self.projects = dict(reversed(self.projects.items()))
            with open(path, "wb") as f:
                pickle.dump(self.projects, f)

    # Schedule projects for building - the general case is that all projects
    # can be considered independent of each other, so we build them in parallel
    def on_pre_build(self, *, config):
        if not self.config.enabled:
            return

        # Skip if projects should not be built or we're not at the top-level
        if not self.config.projects or not self.is_root:
            return

        # Retrieve log level for nested projects
        level = self._get_logger_level()

        # Spawn concurrent job to build each project and add a future to the
        # projects dictionary to associate build results to built projects.
        # In order to support efficient incremental builds, only build projects
        # we haven't built yet or that have changed since the last build.
        for slug, project in self._resolve_projects():
            if slug not in self.pool_jobs:
                self.pool_jobs[slug] = self.pool.submit(
                    _build, slug, project, self.is_dirty, level
                )

    # Patch environment to allow for hoisting of media files provided by the
    # theme itself, which will also work for other themes, not only this one
    def on_env(self, env, *, config, files):
        if not self.config.enabled:
            return

        # Skip if projects should not be built or we're at the top-level
        if not self.config.projects or self.is_root:
            return

        # If hoisting is enabled and we're building a project, remove all media
        # files that are provided by the theme and hoist them to the top
        if self.config.hoisting:
            theme = get_theme_dir(config.theme.name)
            hoist = Files([])

            # Retrieve top-level project and check if the current project uses
            # the same theme as the top-level project - if not, don't hoist
            project = self.projects["."]
            if config.theme.name != project.theme["name"]:
                return

            # Remove all media files that are provided by the theme
            for file in files.media_files():
                if file.abs_src_path.startswith(theme):
                    files.remove(file)
                    hoist.append(file)

            # Compute slug from configuration of project and relative path for
            # hoisting all media files provided by the theme to the top
            slug = self._slug_from_config(config)
            path = get_relative_url(
                self._path_from_slug(slug, config),
                self._path_from_slug(slug, project)
            )

            # Fetch URL template filter from environment - the filter might
            # be overridden by other plugins, so we must retrieve and wrap it
            url_filter = env.filters["url"]

            # Patch URL template filter to add support for correctly resolving
            # media files that were hoisted to the top-level project
            @pass_context
            def url_filter_with_hoisting(context: Context, url: str | None):
                if url and hoist.get_file_from_path(url):
                    return posixpath.join(path, url_filter(context, url))
                else:
                    return url_filter(context, url)

            # Register custom template filters
            env.filters["url"] = url_filter_with_hoisting

    # Adjust project navigation in page (run latest) - as always, allow
    # other plugins to alter the navigation before we process it here
    @event_priority(-100)
    def on_page_context(self, context, *, page, config, nav):
        if not self.config.enabled:
            return

        # Skip if projects should not be built
        if not self.config.projects:
            return

        # Replace project URLs in navigation
        self._replace(nav.items, config)

    # Adjust project navigation in template (run latest) - as always, allow
    # other plugins to alter the navigation before we process it here
    @event_priority(-100)
    def on_template_context(self, context, *, template_name, config):
        if not self.config.enabled:
            return

        # Skip if projects should not be built
        if not self.config.projects:
            return

        # Replace project URLs in navigation
        self._replace(context["nav"].items, config)

    # Reconcile jobs and copy projects to output directory
    def on_post_build(self, *, config):
        if not self.config.enabled:
            return

        # Skip if projects should not be built or we're not at the top-level
        if not self.config.projects or not self.is_root:
            return

        # Reconcile concurrent jobs - when we're serving the site, we create a
        # symbolic link for each project in its parent site directory to ensure
        # that incremental builds work correctly, since MkDocs clears the site
        # directory on every build, except for when using the dirty build flag
        slugs: dict[str, str] = {}
        for slug, future in self.pool_jobs.items():
            if future.exception():
                raise future.exception()
            else:
                _print(self._get_logger(slug), *future.result())

                # We only need to create symbolic links when serving the site
                if not self.is_serve:
                    continue

                # Compute path from slug or site URL - normalize the path, as
                # paths computed from slugs or site URLs use forward slashes
                path = self._path_from_slug(slug, config)
                path = os.path.normpath(path)

                # Map path to slug
                slugs[path] = slug

        # When we're serving the site, we must make sure to order slugs before
        # starting to create symbolic links, so we deterministically create the
        # necessary directories and symbolic links in the correct order to make
        # sure that MkDocs can serve the site correctly
        for path in sorted(slugs.keys()):
            project = self.projects[slugs[path]]

            # Create symbolic link, if we haven't already
            path = os.path.join(config.site_dir, path)
            if not os.path.islink(path):
                os.makedirs(os.path.dirname(path), exist_ok = True)
                os.symlink(project.site_dir, path)

        # Shutdown process pool
        self.pool.shutdown()

    # Register projects to detect changes and schedule rebuilds
    def on_serve(self, server, *, config, builder):
        if not self.config.enabled:
            return

        # Skip if projects should not be built or we're not at the top-level
        if not self.config.projects or not self.is_root:
            return

        # Resolve callback - if a file changes, we need to resolve the project
        # that contains the file and rebuild it. As projects are in post-order,
        # we can be sure that leafs will always be checked before projects that
        # are higher up the tree, so a simple prefix check is enough.
        def resolve(event: FileSystemEvent):
            for slug, project in self._resolve_projects():
                root = os.path.dirname(project.config_file_path)
                if not event.src_path.startswith(root):
                    continue

                # If the project configuration file changed, reload it for a
                # better user experience, as we need to do a rebuild anyway
                if event.src_path == project.config_file_path:
                    project = self._resolve_config(project.config_file_path)
                    self._prepare(slug, project, config)

                    # Compute and normalize path to project configurations
                    path = os.path.join(self.config.cache_dir, "config.pickle")
                    path = os.path.normpath(path)

                    # Update project configuration and write to the cache, to
                    # make sure that we're using the latest configuration. If
                    # we would not do that, changes to the configuration of a
                    # project will not be detected - see https://t.ly/kmeDH
                    self.projects[slug] = project
                    with open(path, "wb") as f:
                        pickle.dump(self.projects, f)

                # Compute project root and base directory
                root = os.path.dirname(project.config_file_path)
                base = os.path.join(root, project.docs_dir)

                # Resolve path relative to docs directory
                path = os.path.relpath(event.src_path, base)
                docs = os.path.relpath(base, os.curdir)

                # Print message that we're scheduling a rebuild - we're using
                # MkDocs' default logger here, as we're at the top-level
                log = logging.getLogger("mkdocs")
                log.info(f"Schedule build due to '{path}' in '{docs}'")

                # Remove finished job from pool to schedule rebuild and return
                # early, as we don't need to rebuild other projects
                self.pool_jobs.pop(slug, None)
                return

        # Initialize file system event handler
        handler = FileSystemEventHandler()
        handler.on_any_event = resolve

        # Add projects to watch list - we watch the project's configuration file
        # and its docs directory to trigger a rebuild if something changes
        for _, project in self._resolve_projects():
            root = os.path.dirname(project.config_file_path)
            for path in [
                os.path.join(root, project.docs_dir),
                project.config_file_path
            ]:
                server.observer.schedule(handler, path, recursive = True)
                server.watch(path)

    # -------------------------------------------------------------------------

    # Find and yield projects in the given projects directory - the given base
    # slug is prepended to the computed slug for a simple resolution of nested
    # projects, allowing authors to use the project:// protocol for linking to
    # projects from the top-level project or nested projects.
    def _find(self, path: str, base: str):
        paths: list[str] = []

        # Find and yield all projects with their configurations - note that we
        # need to filter nested projects at this point, as we're only interested
        # in the projects of the next level, not in projects inside projects as
        # they are resolved recursively to preserve ordering
        glob = os.path.join(path, self.config.projects_config_files)
        glob = iglob(os.path.normpath(glob), recursive = True)
        for file in sorted(glob, key = os.path.dirname):
            root = os.path.dirname(file)
            if any(root.startswith(_) for _ in paths):
                continue

            # Extract the first level of the project's directory relative to
            # the projects directory as the computed slug of the project. Note
            # that slugs might be explicitly overwritten if the author sets the
            # project's site URL, but this is done when preparing the project.
            slug = os.path.relpath(file, path)
            slug, *_ = slug.split(os.path.sep)

            # Normalize slug to an internal dot notation which we convert to
            # file system paths or URLs when necessary. Each slug starts with
            # a dot to denote that it is resolved from the top-level project,
            # which also allows for resolving slugs in nested projects.
            base = base.rstrip(".")
            slug = f"{base}.{slug}"

            # Resolve project configuration and yield project
            project = self._resolve_config(file)
            yield slug, project

    # Find and yield all projects recursively for the given configuration file -
    # traverse the projects directory recursively, yielding projects and nested
    # projects in reverse post-order. The caller needs to reverse all yielded
    # values, so that projects can be built in the correct order.
    def _find_all(self, file: str):

        # Add the top-level project to the stack, and perform a post-order
        # traversal, resolving and yielding all projects in reverse
        stack = [(".", self._resolve_config(file))]
        while stack:
            slug, project = stack.pop()
            yield slug, project

            # Resolve project configuration and check if the current project
            # has a projects directory. If yes, add all projects to the stack.
            plugin = self._resolve_project_plugin(slug, project)
            if plugin and plugin.projects:
                path = os.path.join(
                    os.path.dirname(project.config_file_path),
                    os.path.normpath(plugin.projects_dir)
                )

                # Continue with nested projects if projects directory exists
                if os.path.isdir(path):
                    stack.extend(self._find(path, slug))

    # -------------------------------------------------------------------------

    # Resolve project configuration for the given path
    def _resolve_config(self, file: str):
        with open(file, encoding = "utf-8") as f:
            config: MkDocsConfig = MkDocsConfig(config_file_path = file)
            config.load_file(f)
            return config

    # Resolve project plugin configuration
    def _resolve_project_plugin(self, slug: str, project: MkDocsConfig):

        # Make sure that every project has a plugin configuration set - we need
        # to deep copy the configuration object, as it's mutated during parsing.
        # We're using an internal method of the Plugins class to ensure that we
        # always stick to the syntaxes allowed by MkDocs (list and dictionary).
        plugins = Plugins._parse_configs(deepcopy(project.plugins))
        for index, (key, config) in enumerate(plugins):
            if not re.match(r"^(material/)?projects$", key):
                continue

            # Forward some settings of the plugin configuration to the project,
            # as we need to build nested projects consistently
            for setting in ["cache", "projects", "hoisting"]:
                config[setting] = self.config[setting]

            # Initialize and expand the plugin configuration, and mutate the
            # plugin collection to persist the configuration for hoisting
            plugin: ProjectsConfig = ProjectsConfig()
            plugin.load_dict(config)
            if isinstance(project.plugins, list):
                project.plugins[index] = { key: dict(plugin.items()) }
            else:
                project.plugins[key] = dict(plugin.items())

            # Validate plugin configuration, print errors and warnings and
            # return validated configuration to be used by the plugin
            _print(self._get_logger(slug), *plugin.validate())
            return plugin

        # If no plugin configuration was found, add the default configuration
        # and call this function recursively, so we ensure that it's present
        project.plugins.append("material/projects")
        return self._resolve_project_plugin(slug, project)

    # Resolve project URL and slug
    def _resolve_project_url(self, url: URL, config: MkDocsConfig):

        # Abort if the project URL contains a path, as we first need to collect
        # use cases for when, how and whether we need and want to support this
        if url.path != "":
            raise PluginError(
                f"Couldn't resolve project URL: paths currently not supported\n"
                f"Please only use 'project://{url.hostname}'"
            )

        # Compute slug from host name and convert to dot notation
        slug = url.hostname
        slug = slug if slug.startswith(".") else f".{slug}"

        # Abort if slug doesn't match a known project
        project = self.projects.get(slug)
        if not project:
            raise PluginError(f"Couldn't find project '{slug}'")

        # Compute path from slug or site URL and path of current project
        path = self._path_from_slug(slug, config)
        base = self._path_from_slug(self._slug_from_config(config), project)

        # Append file name if directory URLs are disabled
        if not project.use_directory_urls:
            path += "index.html"

        # Return project slug and path
        return slug, get_relative_url(path, base)

    # Resolve projects
    def _resolve_projects(self):
        for slug, project in self.projects.items():
            if slug != ".":
                yield slug, project

    # -------------------------------------------------------------------------

    # Prepare project configuration to be used by the plugin
    def _prepare(self, slug: str, project: MkDocsConfig, config: MkDocsConfig):
        self._transform(project, config)
        assert slug != "."

        # If the top-level project defines a site URL, we need to make sure that
        # the site URL of the project is set as well, setting it to the path we
        # derive from the slug. This allows to define the URL independent of
        # the entire project's directory structure.
        if config.site_url:
            path = self._path_from_slug(slug, config)

            # If the project doesn't have a site URL, compute it from the site
            # URL of the top-level project and the path derived from the slug
            if not project.site_url:
                project.site_url = posixpath.join(config.site_url, path)

            # If we're serving the site, replace the project's host name with
            # the dev server address, so we can serve nested projects as well
            if self.is_serve:
                url = urlparse(project.site_url)
                url = url._replace(
                    scheme = "http",
                    netloc = str(config.dev_addr)
                )

                # Update site URL with dev server address
                project.site_url = url.geturl()

        # Compute path from slug or site URL - normalize the path, as paths
        # computed from slugs or site URLs always use forward slashes
        path = self._path_from_slug(slug, config)
        path = os.path.normpath(path)

        # Adjust the project's site directory and associate the project to the
        # computed path derived from the slug, or from comparing the site URLs
        # of the project and the top-level project, but if and only if we're
        # building the site. If we're serving the site, we must fall back to
        # symbolic links, because MkDocs will empty the site directory each and
        # every time it performs a build, and thus resolve the site directory
        # within the project itself to an absolute path, as otherwise MkDocs
        # will try to resolve it from the project directory.
        root = os.path.dirname(project.config_file_path)
        if not self.is_serve:
            project.site_dir = os.path.join(config.site_dir, path)
        else:
            project.site_dir = os.path.join(root, project.site_dir)

    # Transform project configuration
    def _transform(self, project: MkDocsConfig, config: MkDocsConfig):
        self.config.projects_config_transform(project, config)

    # -------------------------------------------------------------------------

    # Replace project links in the given list of navigation items
    def _replace(self, items: list[StructureItem], config: MkDocsConfig):
        for index, item in enumerate(items):

            # Handle section
            if isinstance(item, Section):
                self._replace(item.children, config)

            # Handle link
            if isinstance(item, Link):
                url = urlparse(item.url)
                if url.scheme == "project":
                    slug, url = self._resolve_project_url(url, config)

                    # Replace link with project link
                    project = self.projects[slug]
                    items[index] = Project(
                        item.title or project.site_name,
                        url
                    )

    # -------------------------------------------------------------------------

    # Compute path from given slug
    def _path_from_slug(self, slug: str, config: MkDocsConfig):
        project = self.projects.get(slug)
        if not project:
            raise PluginError(f"Couldn't find project '{slug}'")

        # Compute path from slug if no configuration is given (when preparing
        # for building) or if the configuration doesn't define a site URL
        if not config.site_url or not project.site_url:
            _, *segments = slug.split(".")
            return posixpath.join(*segments, "")

        # Extract URLs for computing common path
        base = urlparse(config.site_url)
        dest = urlparse(project.site_url)

        # Compute and strip common path to only return suffix
        at = len(posixpath.commonpath([base.path or "/", dest.path]))
        return dest.path[at:].lstrip("/") or "/"

    # Compute slug from given configuration (reverse lookup)
    def _slug_from_config(self, config: MkDocsConfig):
        for slug, project in self.projects.items():
            if project.config_file_path == config.config_file_path:
                return slug

    # -------------------------------------------------------------------------

    # Compute log level for nested projects
    @functools.lru_cache(maxsize = None)
    def _get_logger(self, slug: str):
        log = logging.getLogger("".join(["mkdocs.material.projects", slug]))

        # Ensure logger does not propagate to parent logger, or messages will
        # be printed multiple times, and attach handler with color formatter
        log.propagate = False
        if not log.hasHandlers():
            log.addHandler(_handler(slug))
            log.setLevel(self._get_logger_level())

        # Return logger
        return log

    # Compute log level for nested projects
    @functools.lru_cache(maxsize = None)
    def _get_logger_level(self):
        level = logging.INFO

        # Determine log level as set in MkDocs - if the build is started with
        # the `--quiet` flag, the log level is set to `ERROR` to suppress all
        # log messages, except for errors. If it's started with `--verbose`,
        # MkDocs sets the log level to `DEBUG`.
        log = logging.getLogger("mkdocs")
        for handler in log.handlers:
            level = handler.level
            break

        # Determine if MkDocs was invoked with the `--quiet` flag and the log
        # level as configured in the plugin configuration. When `--quiet` is
        # set, or logging was disabled in the projects plugin, ignore the
        # configured log level and set it to `ERROR` to suppress logging.
        quiet = level == logging.ERROR
        level = self.config.log_level.upper()
        if quiet or not self.config.log:
            level = logging.ERROR

        # Retun log level
        return level

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

# Build project - note that regardless of whether MkDocs was started in build
# or serve mode, projects must always be built, as they're served by the root
def _build(slug: str, config: Config, dirty: bool, level = logging.WARN):

    # Retrieve and configure MkDocs logger
    log = logging.getLogger("mkdocs")
    log.addHandler(_handler(slug))
    log.setLevel(level)

    # Validate configuration
    errors, warnings = config.validate()
    if not errors:

        # Build project and dispatch startup and shutdown plugin events
        config.plugins.run_event("startup", command = "build", dirty = dirty)
        try:
            build(config, dirty = dirty)
        finally:
            config.plugins.run_event("shutdown")

    # Return errors and warnings for printing
    return errors, warnings

# Print errors and warnings resulting from building a project
def _print(log: Logger, errors: ConfigErrors, warnings: ConfigWarnings):

    # Print warnings
    for value, message in warnings:
        log.warning(f"Config value '{value}': {message}")

    # Print errors
    for value, message in errors:
        log.error(f"Config value '{value}': {message}")

    # Abort if there were errors after removing handler
    if errors:
        raise Abort(f"Aborted with {len(errors)} configuration errors")

# -----------------------------------------------------------------------------

# Create log handler for slug
def _handler(slug: str):
    prefix = style(f"project://{slug}", underline = True)

    # Create handler to prefix log messages with slug
    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter(f"[{prefix}] %(message)s"))

    # Return handler
    return handler
