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

import ClipboardJS from "clipboard"
import {
  NEVER,
  Observable,
  Subject,
  fromEvent,
  merge,
  of
} from "rxjs"
import {
  combineLatestWith,
  distinctUntilKeyChanged,
  finalize,
  map,
  mergeWith,
  switchMap,
  take,
  takeWhile,
  tap,
  withLatestFrom
} from "rxjs/operators"

import { resetFocusable, setFocusable } from "~/actions"
import {
  Viewport,
  getElementContentSize,
  getElementOrThrow,
  getElementSize,
  getElements,
  watchMedia
} from "~/browser"
import {
  renderAnnotation,
  renderClipboardButton
} from "~/templates"

import { Component } from "../../../_"

/* ----------------------------------------------------------------------------
 * Types
 * ------------------------------------------------------------------------- */

/**
 * Code block
 */
export interface CodeBlock {
  scroll: boolean                      /* Code block overflows */
  annotations?: HTMLElement[]          /* Code block annotations */
}

/* ----------------------------------------------------------------------------
 * Helper types
 * ------------------------------------------------------------------------- */

/**
 * Watch options
 */
interface WatchOptions {
  viewport$: Observable<Viewport>      /* Viewport observable */
}

/**
 * Mount options
 */
interface MountOptions {
  viewport$: Observable<Viewport>      /* Viewport observable */
}

/* ----------------------------------------------------------------------------
 * Data
 * ------------------------------------------------------------------------- */

/**
 * Global index for Clipboard.js integration
 */
let index = 0

/* ----------------------------------------------------------------------------
 * Functions
 * ------------------------------------------------------------------------- */

/**
 * Watch code block
 *
 * This function monitors size changes of the viewport, as well as switches of
 * content tabs with embedded code blocks, as both may trigger overflow.
 *
 * @param el - Code block element
 * @param options - Options
 *
 * @returns Code block observable
 */
export function watchCodeBlock(
  el: HTMLElement, { viewport$ }: WatchOptions
): Observable<CodeBlock> {
  const container$ = of(el)
    .pipe(
      switchMap(child => {
        const container = child.closest("[data-tabs]")
        if (container instanceof HTMLElement) {
          return merge(
            ...getElements(":scope > input", container)
              .map(input => fromEvent(input, "change"))
          )
        }
        return NEVER
      })
    )

  /* Transform annotations */
  const annotations: HTMLElement[] = []
  const container =
    el.closest(".annotate.highlighttable") ||
    el.closest(".annotate.highlight")
  if (container) {
    const list = container.nextElementSibling
    if (list instanceof HTMLOListElement) {
      const items = Array.from(list.children)
      list.remove()

      /* Replace comments with annotations */
      for (const comment of getElements(".c, .c1, .cm", el)) {
        const [, j = -1] = comment.textContent!.match(/\((\d+)\)/) || []
        const content = items[+j - 1]
        if (typeof content !== "undefined") {
          const annotation = renderAnnotation(+j, content)
          comment.replaceWith(annotation)
          annotations.push(annotation)
        }
      }
    }
  }

  /* Check overflow on resize and tab change */
  return viewport$
    .pipe(
      distinctUntilKeyChanged("size"),
      mergeWith(container$),
      map(() => {
        const visible = getElementSize(el)
        const content = getElementContentSize(el)
        return {
          scroll: content.width > visible.width,
          ...annotations.length && { annotations }
        }
      }),
      distinctUntilKeyChanged("scroll")
    )
}

/**
 * Mount code block
 *
 * This function ensures that an overflowing code block is focusable through
 * keyboard, so it can be scrolled without a mouse to improve on accessibility.
 *
 * @param el - Code block element
 * @param options - Options
 *
 * @returns Code block component observable
 */
export function mountCodeBlock(
  el: HTMLElement, options: MountOptions
): Observable<Component<CodeBlock>> {
  const internal$ = new Subject<CodeBlock>()
  internal$
    .pipe(
      withLatestFrom(watchMedia("(hover)"))
    )
      .subscribe(([{ scroll }, hover]) => {
        if (scroll && hover)
          setFocusable(el)
        else
          resetFocusable(el)
      })

  /* Compute annotation position */
  internal$
    .pipe(
      take(1),
      takeWhile(({ annotations }) => !!annotations?.length),
      map(({ annotations }) => annotations!
        .map(annotation => getElementOrThrow(".md-tooltip", annotation))
      ),
      combineLatestWith(viewport$
        .pipe(
          distinctUntilKeyChanged("size")
        )
      )
    )
      .subscribe(([tooltips, { size }]) => {
        for (const tooltip of tooltips) {
          const { x, width } = tooltip.getBoundingClientRect()
          if (x + width > size.width)
            tooltip.classList.add("md-tooltip--end")
          else
            tooltip.classList.remove("md-tooltip--end")
        }
      })

  /* Render button for Clipboard.js integration */
  if (ClipboardJS.isSupported()) {
    const parent = el.closest("pre")!
    parent.id = `__code_${++index}`
    parent.insertBefore(
      renderClipboardButton(parent.id),
      el
    )
  }

  /* Create and return component */
  return watchCodeBlock(el, options)
    .pipe(
      tap(internal$),
      finalize(() => internal$.complete()),
      map(state => ({ ref: el, ...state }))
    )
}
