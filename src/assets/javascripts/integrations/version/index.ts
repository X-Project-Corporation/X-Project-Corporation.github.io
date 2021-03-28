/*
 * Copyright (c) 2016-2021 Martin Donath <martin.donath@squidfunk.com>
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to
 * deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
 * sell copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 * FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { configuration } from "~/_"
import { getElementOrThrow, requestJSON } from "~/browser"
import { getComponentElements } from "~/components"
import { Version, renderVersionSelector } from "~/templates"

/* ----------------------------------------------------------------------------
 * Functions
 * ------------------------------------------------------------------------- */

/**
 * Set up version selector
 */
export function setupVersionSelector(): void {
  const config = configuration()
  requestJSON<Version[]>(new URL("versions.json", config.base))
    .subscribe(versions => {
      const [, current] = config.base.match(/([^/]+)\/?$/)!
      const active =
        versions.find(({ version, aliases }) => (
          version === current || aliases.includes(current)
        )) || versions[0]

      /* Render version selector */
      const topic = getElementOrThrow(".md-header__topic")
      topic.appendChild(renderVersionSelector(versions, active))

      /* Check if version state was already determined */
      if (!sessionStorage.getItem(__prefix("__outdated"))) {
        const latest  = config.version?.default || "latest"
        const outdated = !active.aliases.includes(latest)

        /* Persist version state in session storage */
        sessionStorage.setItem(__prefix("__outdated"), JSON.stringify(outdated))
        if (outdated)
          for (const warning of getComponentElements("outdated"))
            warning.hidden = false
      }
    })
}
