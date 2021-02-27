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
  distinctUntilKeyChanged,
  finalize,
  map,
  switchMap,
  tap,
  withLatestFrom
} from "rxjs/operators"

import { resetFocusable, setFocusable } from "~/actions"
import {
  Viewport,
  getElementContentSize,
  getElementSize,
  getElements,
  watchMedia
} from "~/browser"
import { renderAnnotation, renderClipboardButton } from "~/templates"

import { Component } from "../../../_"

/* ----------------------------------------------------------------------------
 * Types
 * ------------------------------------------------------------------------- */

/**
 * Code block
 */
export interface CodeBlock {
  scroll: boolean                      /* Code block overflows */
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
            ...getElements("input", container)
              .map(input => fromEvent(input, "change"))
          )
        }
        return NEVER
      })
    )

  /* Check overflow on resize and tab change */
  return merge(
    viewport$.pipe(distinctUntilKeyChanged("size")),
    container$
  )
    .pipe(
      map(() => {
        const visible = getElementSize(el)
        const content = getElementContentSize(el)
        return {
          scroll: content.width > visible.width
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

  /* Render button for Clipboard.js integration */
  if (ClipboardJS.isSupported()) {
    const parent = el.closest("pre")!
    parent.id = `__code_${++index}`
    parent.insertBefore(
      renderClipboardButton(parent.id),
      el
    )
  }

  // const comments = getElements(".c, .c1, .cm", el)
  // for (const comment of comments) {
  //   const tip = document.createElement("div")
  //   tip.innerText = "heyho!"
  //   comment.appendChild(tip)
  // }

  if (el.closest(".annotate")) {
    let annoIndex = 0
    const container = el.closest(".annotate")!
    if (container.nextElementSibling && container.nextElementSibling!.tagName === "OL") {
      const list = container.nextElementSibling!
      const items = getElements(":scope > li", list)
      list.remove()

      const comments = getElements(".c, .c1, .cm", el)

      for (const comment of comments) {
        const capture = comment.textContent!.match(/\((\d+)\)/)
        if (capture) {
          const [, id] = capture

          // TODO: match ids!
          comment.replaceWith(renderAnnotation(++annoIndex, items[+id - 1]))

          // // + focus-within?
          // const link = document.createElement("button") // this should be a container
          // link.className = "md-annotation"
          // // link.href = `#__annotation_${index}_${++annoIndex}`
          // link.textContent = id

          // mapping.set(link, items[+id - 1])

          // comment.replaceWith(link)
          // items[+id - 1].id = `__annotation_${index}_${annoIndex}`
          // items[+id - 1].remove()
          // replacewith anchor!!!

           // only convert, if there is an entry in the list!
        }
      }
      // console.log(mapping)
    }

  }



  /* Create and return component */
  return watchCodeBlock(el, options)
    .pipe(
      tap(internal$),
      finalize(() => internal$.complete()),
      map(state => ({ ref: el, ...state }))
    )
}
