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
import pickle
import posixpath

from copy import deepcopy
from concurrent.futures import Future, ProcessPoolExecutor
from jinja2 import pass_context
from jinja2.runtime import Context
from mkdocs.commands.build import build
from mkdocs.config.base import Config, ConfigErrors, ConfigWarnings
from mkdocs.config.config_options import Plugins
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.exceptions import Abort, PluginError
from mkdocs.plugins import BasePlugin, event_priority
from mkdocs.structure.pages import Page
from mkdocs.structure.nav import Link, Section
from mkdocs.utils import get_theme_dir
from mkdocs.utils.templates import url_filter
from typing import Union
from urllib.parse import ParseResult as URL, urlparse
from watchdog.events import FileSystemEvent, FileSystemEventHandler

from material.plugins.projects.config import ProjectsConfig
from material.plugins.projects.nav.link import ProjectsLink

# -----------------------------------------------------------------------------
# Class
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
        self.pool_jobs: dict[str, Future] = dict()

        # Initialize projects
        self.projects: dict[str, MkDocsConfig] = dict()

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

        # Compute path to persist project configurations
        path = os.path.join(self.config.cache_dir, "config.pickle")
        path = os.path.normpath(path)

        # Disable building of projects in projects - we manage all processes on
        # the top-level for maximum efficiency when allocating resources
        os.makedirs(os.path.dirname(path), exist_ok = True)
        if os.path.dirname(config.config_file_path) != os.getcwd():
            self.config.projects = False

            # We're building a project, so we try to load all adjacent project
            # configurations from the cache, as they are necessary for correct
            # link resolution between projects. Note that the only sane reason
            # to disable caching is for debugging purposes.
            if self.config.cache and os.path.isfile(path):
                with open(path, "rb") as f:
                    self.projects = pickle.load(f)

        # Initialize process pool - we must initialize a new process pool for
        # every build and get rid of it when we're done, because the process
        # pool executor doesn't allow to ignore keyboard interrupts. Otherwise,
        # each process would print to stdout when we stop serving the site.
        if self.config.projects:
            self.pool = ProcessPoolExecutor(self.config.concurrency)

        # Traverse projects directory and load the configuration for each
        # project, as the author may use the site URL to specify the path at
        # which a project should be stored. If the configuration file changes,
        # settings are reloaded before starting the next build.
        if not self.projects:
            for slug, project in self._find_all(os.getcwd()):
                self.projects[slug] = self._prepare(slug, project, config)

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

        # Skip if projects should not be built
        if not self.config.projects:
            return

        # Spawn concurrent job to build each project and add a future to the
        # projects dictionary to associate build results to built projects.
        # In order to support efficient incremental builds, only build projects
        # we haven't built yet, or when something changed.
        for slug, project in self.projects.items():
            if not slug in self.pool_jobs:
                self.pool_jobs[slug] = self.pool.submit(
                    _build, project, self.is_dirty
                )

    # Patch environment to allow for hoisting of media files provided by the
    # theme itself, which will also work for other themes, not only this one
    def on_env(self, env, *, config, files):
        if not self.config.enabled:
            return

        # We're building the top-level project
        if self.config.projects:
            return

        # If hoisting is enabled and we're building a project, remove all media
        # files that are provided by the theme, as they are hoisted
        if self.config.hoisting:
            theme = get_theme_dir(config.theme.name)
            paths: list[str] = []

            # Remove all media files that are provided by the theme
            for file in files.media_files():
                if file.abs_src_path.startswith(theme):
                    files.remove(file)
                    paths.append(file.url)

            # Wrap template URL filter to correctly resolve media files hoisted
            # to the top-level that we identified in the previous step
            @pass_context
            def url_filter_with_hoisting(context: Context, value: str):
                if not value in paths:
                    return url_filter(context, value)
                else:
                    return posixpath.join(
                        os.path.relpath(".", self.config.internal_slug),
                        url_filter(context, value)
                    )

            # Override template URL filter to allow for hoisting
            env.filters["url"] = url_filter_with_hoisting

    # Merge project navigation (run latest) - we need to do it at this stage,
    # because other plugins might modify the navigation, e.g., the blog plugin
    @event_priority(-100)
    def on_page_context(self, context, *, page, config, nav):
        if not self.config.enabled:
            return

        # Replace project links in navigation
        self._replace(self.config.internal_slug, nav.items)

    # Reconcile jobs and copy projects to output directory
    def on_post_build(self, *, config):
        if not self.config.enabled:
            return

        # Skip if projects should not be built
        if not self.config.projects:
            return

        # Reconcile concurrent jobs - if an exception occurred in one of the
        # jobs, catch and print it without interrupting the server. Moreover,
        # when we're serving the site, we must create a symbolic link for each
        # project in its parent site directory, or incremental builds will not
        # work correctly, as MkDocs will clear the site directory on each and
        # every build, except for when using the bugged dirty build flag.
        for slug, future in self.pool_jobs.items():
            if future.exception():
                raise future.exception()
            else:
                _print(slug, *future.result())
                project = self.projects[slug]

                # If we're serving the site, create a symbolic link for the
                # project inside the site directory of the parent project
                path = os.path.join(config.site_dir, slug)
                if not os.path.exists(path):
                    up = os.path.dirname(slug)
                    if up in self.projects:
                        parent = self.projects[up]

                        # Recompute path, as we need to create the symbolic
                        # link in the site directory of the parent project
                        path = os.path.join(
                            parent.site_dir,
                            os.path.basename(slug)
                        )

                    # Create symbolic link, if we haven't already
                    if not os.path.exists(path):
                        os.makedirs(os.path.dirname(path), exist_ok = True)
                        os.symlink(project.site_dir, path)

        # Shutdown process pool
        self.pool.shutdown()

    # Register projects to detect changes and schedule rebuilds
    def on_serve(self, server, *, config, builder):
        if not self.config.enabled:
            return

        # Skip if projects should not be built
        if not self.config.projects:
            return

        # Resolve callback - if a file changes, we need to resolve the project
        # that contains the file and rebuild it. As projects are in post-order,
        # we can be sure that leafs will always be checked before projects that
        # are higher up the tree, so a simple prefix check is enough.
        def resolve(event: FileSystemEvent):
            for slug, project in self.projects.items():
                path = os.path.dirname(project.config_file_path)
                if not event.src_path.startswith(path):
                    continue

                # If the project configuration file changed, reload it for a
                # better user experience, as we need to do a full build anyway
                if event.src_path == project.config_file_path:
                    self.projects[slug] = self._prepare(
                        slug, self._resolve_config(path), config
                    )

                # Remove finished job from pool to schedule rebuild and return
                # early, as we don't need to rebuild other projects
                log.debug(f"Detected file changes in '{slug}'")
                del self.pool_jobs[slug]
                return

        # Initialize file system event handler
        handler = FileSystemEventHandler()
        handler.on_any_event = resolve

        # Register projects for watching
        for project in self.projects.values():
            for path in [
                os.path.join(
                    os.path.dirname(project.config_file_path),
                    project.docs_dir
                ),
                project.config_file_path
            ]:
                server.observer.schedule(handler, path, recursive = True)
                server.watch(path)

    # -------------------------------------------------------------------------

    # Find and yield projects for the given path
    def _find(self, path: str, base: str = "."):
        if not os.path.isdir(path):
            return

        # Find and yield all projects with their configurations
        for slug in sorted(os.listdir(path)):
            full = os.path.join(path, slug)
            if not os.path.isdir(full):
                continue

            # Try to resolve project configuration
            project = self._resolve_config(full)
            if project:
                slug = os.path.join(base, slug)
                slug = os.path.normpath(slug)

                # Yield normalized path, because otherwise, concatenation of
                # directories when we're serving the site will not work
                yield slug, project

    # Find and yield projects recursively for the given path - traverse the
    # projects directories recursively, yielding projects and projects inside
    # projects in reverse post-order. The caller needs to reverse all yielded
    # values, so that projects can be built in the correct order.
    def _find_all(self, path: str, base: str = "."):
        if not os.path.isdir(path):
            return

        # Add the top-level project to the stack, and perform a post-order
        # traversal, resolving and yielding all projects in reverse
        stack = [(base, self._resolve_config(path))]
        while stack:
            slug, project = stack.pop()
            if slug != ".":
                yield slug, project

            # Resolve project configuration and check if the current project
            # has a projects directory. If yes, add all projects to the stack.
            plugin = self._resolve_project_config(slug, project)
            if plugin and plugin.projects:
                stack.extend(self._find(os.path.join(
                    os.path.dirname(project.config_file_path),
                    plugin.projects_dir
                ), slug))

    # -------------------------------------------------------------------------

    # Try to resolve the project configuration for the given path
    def _resolve_config(self, path: str):
        for name in ["mkdocs.yml", "mkdocs.yaml"]:
            file = os.path.join(path, name)
            if not os.path.isfile(file):
                continue

            # Load and return project configuration file
            with open(file, encoding = "utf-8") as f:
                config: MkDocsConfig = MkDocsConfig(config_file_path = file)
                config.load_file(f)
                return config

    # Make sure that every project has a plugin configuration set - we need to
    # deep copy the configuration object, as MkDocs mutates it during parsing.
    # We're using an internal method of the Plugins class to ensure that we
    # always stick to the syntaxes allowed by MkDocs (list and dictionary).
    def _resolve_project_config(self, slug: str, config: MkDocsConfig):
        plugins = Plugins._parse_configs(deepcopy(config.plugins))
        for index, (key, value) in enumerate(plugins):
            if key != "projects":
                continue

            # Pass the computed slug of the project, so it can be used to
            # resolve information from the top-level and allow for hoisting
            value["internal_slug"] = slug
            value["cache"] = self.config.cache

            # Initialize and expand the plugin configuration, and mutate the
            # plugin collection to persist the configuration for hoisting
            plugin: ProjectsConfig = ProjectsConfig()
            plugin.load_dict(value)
            if isinstance(config.plugins, list):
                config.plugins[index] = { key: dict(plugin.items()) }
            else:
                config.plugins[key] = dict(plugin.items())

            # Validate plugin configuration, print errors and warnings and
            # return validated configuration to be used by the plugin
            _print(slug, *plugin.validate())
            return plugin

        # If no plugin configuration was found, add the default configuration
        # and call this function recursively, so we ensure that it's present
        config.plugins.append("projects")
        return self._resolve_project_config(slug, config)

    # Resolve project link
    def _resolve_project_url(self, slug: str, url: URL):
        return url.hostname

    # -------------------------------------------------------------------------

    # Prepare project configuration to be used by the plugin
    def _prepare(self, slug: str, project: MkDocsConfig, config: MkDocsConfig):
        root = urlparse(config.site_url or "")

        # If the project defines a site URL, replace the slug with the path
        # suffix starting from the top-level project. This is a very powerful
        # feature that allows the author to define the directory structure
        # independent of the directory structure of the project.
        if project.site_url:
            url = urlparse(project.site_url)
            if url.path.startswith(root.path):
                slug = os.path.join(".", url.path[len(root.path):])

            # If we're serving the site, replace the project's host name with
            # the dev server address, so we can serve it
            if self.is_serve:
                url = url._replace(netloc = str(config.dev_addr))
                project.site_url = url.geturl()

        # Adjust the project's site directory and associate the project to the
        # computed slug from the concatenation of paths, or from comparing the
        # site URLs of the project and the top-level project, but if and only
        # if we're building the site. If we're serving the site, we must fall
        # back to symbolic links, because MkDocs will empty the site directory
        # each and every time it performs a build, and thus resolve the site
        # directory within the project itself to an absolute path, as otherwise
        # MkDocs will try to resolve it from the project directory.
        if not self.is_serve:
            project.site_dir = os.path.join(config.site_dir, slug)
        else:
            project.site_dir = os.path.join(
                os.path.dirname(project.config_file_path),
                project.site_dir
            )

        # Return project prepared for building
        return project

    # -------------------------------------------------------------------------

    # Replace project links in the given list of navigaton items
    def _replace(self, slug: str, items: "list[Union[Link, Page, Section]]"):
        for index, item in enumerate(items):
            if isinstance(item, Link):
                items[index] = self._replace_link(slug, item)

            # If this is a section and we haven't found the navigation item to
            # inject the navigation up to this point, go one level deeper
            elif isinstance(item, Section):
                return self._replace(slug, item.children)

    # Replace project link
    def _replace_link(self, slug: str, item: Link):
        url = urlparse(item.url)
        if url.scheme != "project":
            return item

        # Resolve fully qualified project slug - the given slug is the context
        # of the project that is currently being built. When we're building a
        # nested project, we need to prepend the slug of the project that is
        # currently being built to the slug of the project that is referenced.
        slug = posixpath.join(slug, url.hostname)
        slug = posixpath.normpath(slug)

        # Abort, since the project could not be resolved
        if slug not in self.projects:
            raise PluginError(f"Couldn't find project '{slug}'")

        # If the link or section does not include a title, we just use the name
        # of the project as a title, allowing to manage it inside the project
        title = item.title or self.projects[slug].site_name

        # Resolve and return project link
        url = self._resolve_project_url(slug, url)
        return ProjectsLink(title, url)

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

# Build project - note that regardless of whether MkDocs was started in build
# or serve mode, projects must always be built, as they're served by the root.
# Additionally, since we can't use the configured logger from a child process,
# we must stop the build once errors are encountered and log them outside.
def _build(config: Config, dirty: bool):
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
def _print(slug: str, errors: ConfigErrors, warnings: ConfigWarnings):

    # Print warnings
    for value, message in warnings:
        log.warning(f"[{slug}] Config value '{value}': {message}")

    # Print errors
    for value, message in errors:
        log.error(f"[{slug}] Config value '{value}': {message}")

    # Abort if there were errors
    if errors:
        raise Abort(f"Aborted with {len(errors)} configuration errors")

# -----------------------------------------------------------------------------
# Data
# -----------------------------------------------------------------------------

# Set up logging
log = logging.getLogger("mkdocs.material.projects")
