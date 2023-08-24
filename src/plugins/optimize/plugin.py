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

import json
import logging
import os
import subprocess

from colorama import Fore, Style
from concurrent.futures import Future, ThreadPoolExecutor
from hashlib import sha1
from mkdocs import utils
from mkdocs.exceptions import PluginError
from mkdocs.plugins import BasePlugin
from mkdocs.structure.files import File
from PIL import Image

from .config import OptimizeConfig

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

# Optimize plugin
class OptimizePlugin(BasePlugin[OptimizeConfig]):
    supports_multiple_instances = True

    # Initialize plugin
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialize incremental builds
        self.is_serve = False

    # Determine whether we're serving the site
    def on_startup(self, *, command, dirty):
        self.is_serve = command == "serve"

        # Initialize thread pool
        self.pool = ThreadPoolExecutor(self.config.concurrency)
        self.pool_jobs: dict[str, Future] = {}

    # Resolve and load manifest
    def on_config(self, config):
        if not self.config.enabled:
            return

        # Initialize cache
        self.cache: dict[str, str] = {}
        self.cache_file = os.path.join(self.config.cache_dir, "manifest.json")
        self.cache_file = os.path.normpath(self.cache_file)

        # Load cache map, if it exists and the cache should be used
        os.makedirs(os.path.dirname(self.cache_file), exist_ok = True)
        if self.config.cache and os.path.isfile(self.cache_file):
            with open(self.cache_file) as f:
                try:
                    self.cache = json.load(f)
                except:
                    pass

    # Initialize optimization pipeline
    def on_env(self, env, *, config, files):
        if not self.config.enabled:
            return

        # Filter all optimizable media files and steal reponsibility from MkDocs
        # by removing them from the files collection. Then, start a concurrent
        # job that checks if an image was already optimized and can be returned
        # from the cache, or optimize it accordingly.
        for file in files.media_files():
            if not self._is_optimizable(file):
                continue

            # Compute path to cached image
            path = os.path.join(self.config.cache_dir, file.src_path)
            path = os.path.normpath(path)

            # Spawn concurrent job to optimize the given image and add future
            # to job dictionary, as it returns the file we need to copy later
            self.pool_jobs[file.abs_src_path] = self.pool.submit(
                self._optimize_image, file, path
            )

            # Steal responsibility from MkDocs
            files.remove(file)

    # Finish optimization pipeline
    def on_post_build(self, *, config):
        if not self.config.enabled:
            return

        # Reconcile concurrent jobs - we need to wait for all jobs to finish
        # before we can copy the optimized files to the output directory. If an
        # exception occurred in one of the jobs, we raise it here, so the build
        # fails and the author can fix the issue.
        for path, future in self.pool_jobs.items():
            if future.exception():
                raise future.exception()
            else:
                file: File = future.result()
                file.copy_file()

        # Shutdown thread pool if we're not serving the site
        if not self.is_serve:
            self.pool.shutdown()

        # Compute and print gains through optimization
        if self.config.print_gain_summary:
            print(Style.NORMAL)
            print(f"  Optimizations:")

            # Print summary for file extension
            for seek in [".png", ".jpg"]:
                size = size_opt = 0
                for path, future in self.pool_jobs.items():
                    file: File = future.result()

                    # Skip files that are not of the given type
                    _, extension = os.path.splitext(path)
                    extension = ".jpg" if extension == ".jpeg" else extension
                    if extension != seek:
                        continue

                    # Compute size before and after optimization
                    size     += os.path.getsize(path)
                    size_opt += os.path.getsize(file.abs_dest_path)

                # Compute absolute and relative gain
                if size and size_opt:
                    gain_abs = size - size_opt
                    gain_rel = (1 - size_opt / size) * 100

                    # Print summary for files
                    print(
                        f"    *{seek} {Fore.GREEN}{_size(size_opt)}"
                        f"{Fore.WHITE}{Style.DIM} ↓ "
                        f"{_size(gain_abs)} [{gain_rel:3.1f}%]"
                        f"{Style.RESET_ALL}"
                    )

            # Reset all styles
            print(Style.RESET_ALL)

    # -------------------------------------------------------------------------

    # Check if a file can be optimized
    def _is_optimizable(self, file: File):
        _, extension = os.path.splitext(file.url)

        # Check if PNG images should be optimized
        if extension in [".png"]:
            return self.config.optimize_png

        # Check if JPG images should be optimized
        if extension in [".jpg", ".jpeg"]:
            return self.config.optimize_jpg

        # File can not be optimized by the plugin
        return False

    # Optimize image and write to cache
    def _optimize_image(self, file: File, path: str):
        with open(file.abs_src_path, "rb") as f:
            data = f.read()
            hash = sha1(data).hexdigest()

            # Check if file hash changed, so we need to optimize again
            prev = self.cache.get(file.url, "")
            if hash != prev or not os.path.isfile(path):
                os.makedirs(os.path.dirname(path), exist_ok = True)

                # Optimize PNG image using pngquant
                if file.url.endswith(".png"):
                    self._optimize_image_png(file, path)

                # Optimize JPG image using pillow
                if file.url.endswith(".jpg"):
                    self._optimize_image_jpg(file, path)

                # Compute size before and after optimization
                size     = len(data)
                size_opt = os.path.getsize(path)

                # Compute absolute and relative gain
                gain_abs = size - size_opt
                gain_rel = (1 - size_opt / size) * 100

                # Print how much we gained, if we did and desired
                gain = ""
                if gain_abs and self.config.print_gain:
                    gain += " ↓ "
                    gain += " ".join([_size(gain_abs), f"[{gain_rel:3.1f}%]"])

                # Print summary for file
                log.info(
                    f"Optimized media file: {file.src_uri} "
                    f"{Fore.GREEN}{_size(size_opt)}"
                    f"{Fore.WHITE}{Style.DIM}{gain}"
                    f"{Style.RESET_ALL}"
                )

                # Update cache map and write it immediately, so we keep
                # intermediate results when doing incremental builds
                self.cache[file.url] = hash
                with open(self.cache_file, "w") as f:
                    f.write(json.dumps(self.cache, indent = 2))

        # Compute source file system path
        file.src_path     = path
        file.abs_src_path = os.path.abspath(path)

        # Return file to be copied from cache
        return file

    # Optimize PNG image - we first tried to use libimagequant, but encountered
    # the occassional segmentation fault, which means it's probably not a good
    # choice. Instead, we just rely on pngquant which seems much more stable.
    def _optimize_image_png(self, file: File, path: str):
        args = ["pngquant",
            "--force", "--skip-if-larger",
            "--output", path,
            "--speed", f"{self.config.optimize_png_speed}"
        ]

        # Add flag to remove optional metadata
        if self.config.optimize_png_strip:
            args.append("--strip")

        # Set input file and run, then check if pngquant actually wrote a file,
        # as we instruct it not to if the size of the optimized file is larger.
        # This can happen if files are already compressed and optimized by
        # the author. In that case, just copy the original file.
        subprocess.run([*args, file.abs_src_path])
        if not os.path.isfile(path):
            utils.copy_file(file.abs_src_path, path)

    # Optimize JPG image
    def _optimize_image_jpg(self, file: File, path: str):
        image = Image.open(file.abs_src_path)
        image.save(path, "jpeg",
            quality     = self.config.optimize_jpg_quality,
            progressive = self.config.optimize_jpg_progressive
        )

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

# Print human-readable size
def _size(value):
    for unit in ["B", "kB", "MB", "GB", "TB", "PB", "EB", "ZB"]:
        if abs(value) < 1000.0:
            return f"{value:3.1f} {unit}"
        value /= 1000.0

# -----------------------------------------------------------------------------
# Data
# -----------------------------------------------------------------------------

# Set up logging
log = logging.getLogger("mkdocs.material.optimize")
