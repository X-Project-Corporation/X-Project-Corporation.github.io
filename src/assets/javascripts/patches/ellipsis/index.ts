/*
 * Copyright (c) 2016-2022 Martin Donath <martin.donath@squidfunk.com>
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

import {
  Observable,
  distinctUntilKeyChanged,
  filter,
  finalize,
  mergeMap,
  skip,
  switchMap,
  takeUntil
} from "rxjs"

import { Viewport, getElements } from "~/browser"
import { mountTooltip } from "~/components"

/* ----------------------------------------------------------------------------
 * Helper types
 * ------------------------------------------------------------------------- */

/**
 * Patch options
 */
interface PatchOptions {
  document$: Observable<Document>      /* Document observable */
  viewport$: Observable<Viewport>      /* Viewport observable */
}

/* ----------------------------------------------------------------------------
 * Functions
 * ------------------------------------------------------------------------- */

/**
 * Patch ellipsis
 *
 * @param options - Options
 */
export function patchEllipsis(
  { document$, viewport$ }: PatchOptions
): void {
  const poll$ = viewport$.pipe(distinctUntilKeyChanged("size"))
  document$
    .pipe(
      switchMap(() => poll$),
      switchMap(() => getElements(".md-ellipsis")),
      filter(el => el.offsetWidth < el.scrollWidth),
      mergeMap(el => {
        const text = el.innerText
        const host = el.closest("a") || el
        host.title = text

        /* Mount tooltip */
        return mountTooltip(host)
          .pipe(
            finalize(() => host.removeAttribute("title")),
            takeUntil(poll$.pipe(skip(1)))
          )
      })
    )
      .subscribe()
}
