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
  EMPTY,
  Observable,
  Subject,
  animationFrameScheduler,
  auditTime,
  combineLatest,
  debounceTime,
  defer,
  filter,
  finalize,
  map,
  merge,
  tap
} from "rxjs"

import {
  ElementOffset,
  getElement,
  getElementOffset,
  getElementSize,
  watchElementFocus,
  watchElementHover
} from "~/browser"
import { renderTooltip } from "~/templates"

import { Component } from "../_"

/* ----------------------------------------------------------------------------
 * Types
 * ------------------------------------------------------------------------- */

/**
 * Tooltip
 */
export interface Tooltip {
  active: boolean                      /* Tooltip is active */
  offset: ElementOffset                /* Tooltip offset */
}

/* ----------------------------------------------------------------------------
 * Data
 * ------------------------------------------------------------------------- */

/**
 * Global sequence number for tooltips
 */
let sequence = 0

/* ----------------------------------------------------------------------------
 * Functions
 * ------------------------------------------------------------------------- */

/**
 * Watch tooltip
 *
 * This function will append the tooltip temporarily to compute its width,
 * which is necessary for correct centering, and then removing it again.
 *
 * @param el - Tooltip element
 * @param host - Host element
 *
 * @returns Tooltip observable
 */
export function watchTooltip(
  el: HTMLElement, host: HTMLElement
): Observable<Tooltip> {
  document.body.append(el)

  /* Compute width and remove tooltip immediately */
  const { width } = getElementSize(el)
  el.style.setProperty("--md-tooltip-width", `${width}px`)
  el.remove()

  /* Actively watch tooltip on focus/hover */
  return combineLatest([
    watchElementFocus(host),
    watchElementHover(host)
  ])
    .pipe(
      map(([focus, hover]) => focus || hover),
      map(active => {
        const parent = getElementSize(host)
        const { x, y } = getElementOffset(host)
        return {
          active,
          offset: {
            x: x + parent.width / 2 - width / 2,
            y: y + parent.height + 8
          }
        }
      })
    )
}

/**
 * Mount tooltip
 *
 * @param el - Host element
 *
 * @returns Tooltip component observable
 */
export function mountTooltip(
  el: HTMLElement
): Observable<Component<Tooltip>> {
  const title = el.title
  if (!title.length)
    return EMPTY

  /* Render tooltip and set title from host element */
  const id = `__tooltip_${sequence++}`
  const tooltip = renderTooltip(id, "inline")
  const typeset = getElement(".md-typeset", tooltip)
  typeset.innerHTML = title

  /* Mount component on subscription */
  return defer(() => {
    const push$ = new Subject<Tooltip>()
    push$.subscribe({

      /* Handle emission */
      next({ offset }) {
        tooltip.style.setProperty("--md-tooltip-x", `${offset.x}px`)
        tooltip.style.setProperty("--md-tooltip-y", `${offset.y}px`)
      },

      /* Handle complete */
      complete() {
        tooltip.style.removeProperty("--md-tooltip-x")
        tooltip.style.removeProperty("--md-tooltip-y")
      }
    })

    /* Toggle tooltip presence to mitigate empty lines when copying */
    merge(
      push$.pipe(filter(({ active }) => active)),
      push$.pipe(debounceTime(250), filter(({ active }) => !active))
    )
      .subscribe({

        /* Handle emission */
        next({ active }) {
          if (active) {
            el.insertAdjacentElement("afterend", tooltip)
            el.setAttribute("aria-describedby", id)
            el.removeAttribute("title")
          } else {
            tooltip.remove()
            el.removeAttribute("aria-describedby")
            el.setAttribute("title", title)
          }
        },

        /* Handle complete */
        complete() {
          tooltip.remove()
          el.removeAttribute("aria-describedby")
          el.setAttribute("title", title)
        }
      })

    /* Toggle tooltip visibility */
    push$
      .pipe(
        auditTime(16, animationFrameScheduler)
      )
        .subscribe(({ active }) => {
          tooltip.classList.toggle("md-tooltip--active", active)
        })

    /* Create and return component */
    return watchTooltip(tooltip, el)
      .pipe(
        tap(state => push$.next(state)),
        finalize(() => push$.complete()),
        map(state => ({ ref: el, ...state }))
      )
  })
}
