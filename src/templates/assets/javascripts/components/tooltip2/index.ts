/*
 * Copyright (c) 2016-2024 Martin Donath <martin.donath@squidfunk.com>
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
  BehaviorSubject,
  EMPTY,
  Observable,
  Subject,
  animationFrameScheduler,
  combineLatest,
  debounce,
  defer,
  distinctUntilChanged,
  endWith,
  filter,
  finalize,
  first,
  ignoreElements,
  map,
  mergeMap,
  observeOn,
  queueScheduler,
  share,
  skip,
  startWith,
  switchMap,
  tap,
  timer,
  withLatestFrom,
  zip
} from "rxjs"

import {
  ElementOffset,
  Viewport,
  getElementContainers,
  getElementOffsetAbsolute,
  getElementSize,
  watchElementContentOffset,
  watchElementFocus,
  watchElementHover
} from "~/browser"
import { renderTooltip2 } from "~/templates"

import { Component } from "../_"

/* ----------------------------------------------------------------------------
 * Types
 * ------------------------------------------------------------------------- */

/**
 * Tooltip
 */
export interface Tooltip {
  active: boolean                      // Tooltip is active
  offset: ElementOffset                // Tooltip offset
}

/* ----------------------------------------------------------------------------
 * Helper types
 * ------------------------------------------------------------------------- */

/**
 * Dependencies
 */
interface Dependencies {
  viewport$: Observable<Viewport>      // Viewport observable
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
 * This function tracks the tooltip host element, and deduces the active state
 * and offset of the tooltip from it. The active state is determined by whether
 * the host element is focused or hovered, and the offset is determined by the
 * host element's absolute position in the document.
 *
 * @param el - Tooltip host element
 *
 * @returns Tooltip observable
 */
export function watchTooltip2(
  el: HTMLElement
): Observable<Tooltip> {

  // Compute whether tooltip should be shown - we need to watch both focus and
  // hover events on the host element and emit if one of them is active. In case
  // of a hover event, we keep the element visible for a short amount of time
  // after the pointer left the host element.
  const active$ =
    combineLatest([
      watchElementFocus(el),
      watchElementHover(el, 250)
    ])
      .pipe(
        map(([focus, hover]) => focus || hover),
        distinctUntilChanged()
      )

  // We need to determine all parent elements of the host element that are
  // currently scrollable, as they might affect the position of the tooltip
  // depending on their horizontal of vertical offset. We must track all of
  // them and recompute the position of the tooltip if they change.
  const offset$ =
    defer(() => getElementContainers(el)).pipe(
      mergeMap(container => watchElementContentOffset(container).pipe(
        skip(1)
      )),
      startWith(undefined),
      map(() => getElementOffsetAbsolute(el))
    )

  // Only track parent elements and compute offset of the tooltip host if the
  // tooltip should be shown - we defer the computation of the offset until the
  // tooltip becomes active for the first time. This is necessary, because we
  // must also keep the tooltip active as long as it is focused or hovered.
  return active$.pipe(
    first(active => active),
    switchMap(() => combineLatest([active$, offset$])),
    map(([active, offset]) => ({ active, offset })),
    share()
  )
}

/**
 * Mount tooltip
 *
 * @todo this is our new tooltip implementation, which will become the standard,
 * as it doesn't suffer from the same positioning issues as the previous one.
 * However, we first test it on footnotes, and see if we don't introduce any new
 * issues, before moving entirely to it.
 *
 * @param el - Tooltip host element
 * @param factory - Node factory
 * @param dependencies - Dependencies
 *
 * @returns Tooltip component observable
 */
export function mountTooltip2(
  el: HTMLElement, factory: () => Node | string, dependencies: Dependencies
): Observable<Component<Tooltip>> {
  const { viewport$ } = dependencies

  // Create a tooltip - @todo move this outside this function
  const id = `__tooltip2_${sequence++}`
  const tooltip$ = new Observable<HTMLElement>(observer => {
    const tooltip = renderTooltip2(id, factory())
    observer.next(tooltip)

    // Append tooltip and remove on unsubscription
    document.body.append(tooltip)
    return () => tooltip.remove()
  })

  // Create component on subscription
  return defer(() => {
    const push$ = new Subject<Tooltip>()

    // Create subject to track tooltip presence and visibility - we use another
    // purely internal subject to track the tooltip's presence and visibility,
    // as the tooltip should be shown if the host element or tooltip itself is
    // focused or hovered to allow for smooth pointer migration
    const show$ = new BehaviorSubject(false)
    push$.pipe(ignoreElements(), endWith(false))
      .subscribe(show$)

    // Create observable controlling tooltip element - we create and attach the
    // tooltip only if it is actually present, in order to keep the number of
    // elements down. We need to keep the tooltip visible for a short time after
    // the pointer left the host element or tooltip itself. For this, we use an
    // inner subscription to the tooltip observable, which we terminate when the
    // tooltip should not be shown, automatically removing the element. Moreover
    // we use the queue scheduler, which will schedule synchronously in case the
    // tooltip should be shown, and asynchronously if it should be hidden.
    const node$ = show$.pipe(
      debounce(active => timer(+!active * 250, queueScheduler)),
      distinctUntilChanged(),
      switchMap(active => active ? tooltip$ : EMPTY),
      share()
    )

    // Compute tooltip presence and visibility - the tooltip should be shown if
    // the host element is focused or hovered, or the tooltip itself
    combineLatest([
      push$.pipe(map(({ active }) => active)),
      node$.pipe(
        switchMap(node => watchElementHover(node, 250)),
        startWith(false)
      )
    ])
      .pipe(map(states => states.some(active => active)))
      .subscribe(show$)

    // Compute tooltip origin - we need to compute the tooltip origin depending
    // on the position of the host element, the viewport size, as well as the
    // actual size of the tooltip, if positioned above. The tooltip must about
    // to be rendered for this to be correct, which is why we do it here.
    const origin$ = show$.pipe(
      filter(active => active),
      withLatestFrom(node$, viewport$),
      map(([_, tooltip, { size }]) => {
        const host = el.getBoundingClientRect()
        if (host.y >= size.height / 2) {
          const { height } = getElementSize(tooltip)
          return -16 - height
        } else {
          return +16 + host.height
        }
      })
    )

    // Update tooltip position - we always need to update the position of the
    // tooltip, as it might change depending on the viewport offset of the host
    combineLatest([push$, origin$, node$])
      .subscribe(([{ offset }, origin, tooltip]) => {
        tooltip.style.setProperty("--md-tooltip-x", `${offset.x}px`)
        tooltip.style.setProperty("--md-tooltip-y", `${offset.y + origin}px`)

        // Update tooltip origin, i.e., whether the tooltip is rendered above
        // or below the host element, which depends on the available space
        tooltip.classList.toggle("md-tooltip2--top",    origin <  0)
        tooltip.classList.toggle("md-tooltip2--bottom", origin >= 0)
      })

    // Update tooltip visibility - we defer to the next animation frame, because
    // the tooltip must first be added to the document before we make it appear,
    // or it will appear instantly without delay. Additionally, we need to keep
    // the tooltip visible for a short time after the pointer left the host.
    show$.pipe(
      distinctUntilChanged(),
      observeOn(animationFrameScheduler),
      withLatestFrom(node$)
    )
      .subscribe(([active, tooltip]) => {
        tooltip.classList.toggle("md-tooltip2--active", active)
      })

    // Create and return component
    return watchTooltip2(el)
      .pipe(
        tap(state => push$.next(state)),
        finalize(() => push$.complete()),
        map(state => ({ ref: el, ...state }))
      )
  })
}
