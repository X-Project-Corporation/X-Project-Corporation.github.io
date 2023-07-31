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

from copy import deepcopy
from concurrent.futures import Future, ProcessPoolExecutor
from mkdocs.commands.build import build
from mkdocs.config.base import Config, ConfigErrors, ConfigWarnings
from mkdocs.config.config_options import Plugins
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.exceptions import Abort, PluginError
from mkdocs.plugins import BasePlugin, event_priority
from urllib.parse import urlparse
from watchdog.events import FileSystemEvent, FileSystemEventHandler

from material.plugins.projects.config import ProjectsConfig

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
        self.is_serve = (command == "serve")
        self.is_dirty = dirty

    # Initialize plugin – this plugin is forced to use a process pool in order
    # to guarantee proper isolation, as MkDocs itself is not thread-safe
    def on_config(self, config):
        if not self.config.enabled:
            return

        # Disable building of projects in projects - we manage all processes on
        # the top-level for maximum efficiency when allocating resources
        if os.getcwd() != os.path.dirname(config.config_file_path):
            self.config.projects = False

        # Initialize process pool - we must initialize a new process pool for
        # every build and get rid of it when we're done, because the process
        # pool executor doesn't allow to ignore keyboard interrupts. Otherwise,
        # each process would print to stdout when we stop serving the site.
        if self.config.projects:
            self.pool = ProcessPoolExecutor(self.config.concurrency)

            # Traverse projects directory and load the configuration for each
            # project, as the author may use site URL to specify the path at
            # which a project should be stored. If the configuration file
            # changes, settings are reloaded before starting the next build.
            if not self.projects:
                for name, project in self._find_all(os.getcwd()):
                    self.projects[name] = self._prepare(name, project, config)

                # Reverse projects to adhere to post-order
                self.projects = dict(reversed(self.projects.items()))

        # Remember last error, so we can disable the plugin if necessary. This
        # allows for a much better editing experience, as the user can fix the
        # issue and the plugin will pick up the changes, so there's no need to
        # restart the preview server.
        self.error = None

    # Schedule projects for building (run latest) - in general, projects are
    # considered to be independent, which is why we schedule them at this stage
    @event_priority(-100)
    def on_files(self, files, *, config):
        if not self.config.enabled or self.error:
            return

        # Skip if projects should not be built
        if not self.config.projects:
            return

        # Spawn concurrent job to build each project and add a future to the
        # projects dictionary to associate build results to built projects.
        # In order to support efficient incremental builds, only build projects
        # we haven't built yet, or something changed. Whether something changed
        # is tracked and detected in the on_serve hook that
        for name, project in self.projects.items():
            if not name in self.pool_jobs:
                self.pool_jobs[name] = self.pool.submit(
                    _build, project, self.is_dirty
                )

    # Reconcile jobs and copy projects to output directory
    def on_post_build(self, *, config):
        if not self.config.enabled or self.error:
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
        for name, future in self.pool_jobs.items():
            if future.exception():
                self._error(future.exception())
            else:
                _print(name, *future.result())
                project = self.projects[name]

                # If we're serving the site, create a symbol link for the
                # project inside the site directory of the parent project
                path = os.path.join(config.site_dir, name)
                if not os.path.exists(path):
                    up = os.path.dirname(name)
                    if up in self.projects:
                        parent = self.projects[up]

                        # Recompute path, as we need to create the symbolic
                        # link in the site directory of the parent project
                        path = os.path.join(
                            os.path.dirname(parent.config_file_path),
                            parent.site_dir,
                            os.path.basename(name)
                        )

                    # Create symbolic link, if we haven't already
                    if not os.path.exists(path):
                        os.makedirs(os.path.dirname(path), exist_ok = True)
                        os.symlink(os.path.join(
                            os.path.dirname(project.config_file_path),
                            project.site_dir
                        ), path)

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
            for name, project in self.projects.items():
                path = os.path.dirname(project.config_file_path)
                if not event.src_path.startswith(path):
                    continue

                # If the project configuration file changed, reload it for a
                # better user experience, as we need to do a full build anyway
                if event.src_path == project.config_file_path:
                    self.projects[name] = self._prepare(
                        name, self._resolve_config(path), config
                    )

                # Remove finished job from pool to schedule rebuild and return
                # early, as we don't need to rebuild other projects
                log.debug(f"Detected file changes in '{name}'")
                del self.pool_jobs[name]
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
        for name in sorted(os.listdir(path)):
            project = self._resolve_config(os.path.join(path, name))
            if project:
                name = os.path.join(base, name)
                name = os.path.normpath(name)

                # Yield normalized path, because otherwise, concatenation of
                # directories when we're serving the site will not work
                yield name, project

    # Find and yield projects for the given path and recurse - traverse the
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
            name, project = stack.pop()
            if name != ".":
                yield name, project

            # Resolve project configuration and check if the current project
            # has a projects directory. If yes, add all projects to the stack.
            plugin = self._resolve_plugin_config(name, project)
            if plugin and plugin.projects:
                stack.extend(self._find(os.path.join(
                    os.path.dirname(project.config_file_path),
                    plugin.projects_dir
                ), name))

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

    # Try to resolve the plugin configuration for the given project - we need
    # to deep copy the configuration object, as MkDocs seems to mutate it when
    # parsing. We're using an internal method of the Plugins class to ensure
    # that we always stick to the syntax allowed by MkDocs.
    def _resolve_plugin_config(self, name: str, config: Config):
        plugins = deepcopy(config.plugins)
        for name, data in Plugins._parse_configs(plugins):
            if not name == "projects":
                continue

            # Initialize configuration
            config: ProjectsConfig = ProjectsConfig()
            config.load_dict(data)

            # Validate configuration
            errors, warnings = config.validate()

            # Print errors and warnings and return configuration
            _print(name, errors, warnings)
            return config

    # -------------------------------------------------------------------------

    # Prepare project configuration to be used by plugin
    def _prepare(self, name: str, project: MkDocsConfig, config: MkDocsConfig):
        root = urlparse(config.site_url or "")

        # If the project defines a site URL, replace the name with the path
        # suffix when compared to the top-level project
        if project.site_url:
            url = urlparse(project.site_url)
            if url.path.startswith(root.path):
                name = os.path.join(".", url.path[len(root.path):])

            # If we're serving the site, replace the project's host name with
            # the dev server address, so we can serve it
            if self.is_serve:
                url = url._replace(netloc = str(config.dev_addr))
                project.site_url = url.geturl()

        # Adjust the project's site directory and associate the project to the
        # computed name from the concatenation of paths, or from comparing the
        # site URLs of the project and the top-level project, but if and only
        # if we're building the site. If we're serving the site, we must fall
        # back to symbolic links, because MkDocs will empty the site directory
        # each and every time it performs a build.
        if not self.is_serve:
            project.site_dir = os.path.join(config.site_dir, name)

        # Return project prepared for building
        return project

    # -------------------------------------------------------------------------

    # Handle error - if we're serving, we just log the first error we encounter.
    # If we're building, we raise an exception, so the build fails.
    def _error(self, e: Exception):
        if not self.is_serve:
            raise PluginError(str(e))

        # Remember first error
        if not self.error:
            self.error = e

            # If we're serving, just log the error
            log.error(e)
            log.warning(
                "Skipping projects plugin for this build. "
                "Please fix the error to enable the projects plugin again."
            )

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

    # Return warnings and errors for printing
    return errors, warnings

# Print errors and warnings resulting from building a project
def _print(name: str, errors: ConfigErrors, warnings: ConfigWarnings):
    name = os.path.normpath(name)

    # Print warnings
    for value, message in warnings:
        log.warning(f"[{name}] Config value '{value}': {message}")

    # Print errors
    for value, message in errors:
        log.error(f"[{name}] Config value '{value}': {message}")

    # Abort if there were errors
    if errors:
        raise Abort(f"Aborted with {len(errors)} configuration errors")

# -----------------------------------------------------------------------------
# Data
# -----------------------------------------------------------------------------

# Set up logging
log = logging.getLogger("mkdocs.material.projects")
