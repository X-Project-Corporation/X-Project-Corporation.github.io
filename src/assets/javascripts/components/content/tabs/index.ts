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

import { Observable, Subject, fromEvent, of } from "rxjs"
import {
  finalize,
  map,
  mapTo,
  mergeMap,
  switchMap,
  tap
} from "rxjs/operators"

import { feature } from "~/_"
import { getElements } from "~/browser"

import { Component } from "../../_"

/* ----------------------------------------------------------------------------
 * Types
 * ------------------------------------------------------------------------- */

/**
 * Content tabs
 */
export interface ContentTabs {
  active: HTMLLabelElement             /* Active tab label */
}

/* ----------------------------------------------------------------------------
 * Functions
 * ------------------------------------------------------------------------- */

/**
 * Watch content tabs
 *
 * @param el - Content tabs element
 *
 * @returns Content tabs observable
 */
export function watchContentTabs(
  el: HTMLElement
): Observable<ContentTabs> {
  return of(getElements<HTMLLabelElement>(":scope > label", el))
    .pipe(
      switchMap(labels => of(...labels)
        .pipe(
          mergeMap(label => {
            const input = label.previousElementSibling as HTMLInputElement
            return fromEvent(input, "change")
              .pipe(
                mapTo({ active: label })
              )
          })
        )
      )
    )
}

/**
 * Mount content tabs
 *
 * This function intercepts label changes on the given content tabs element and
 * switches all co-occurring content tabs to the tab with the same label. The
 * underlying implementation leverages an ordered set and adds new active tabs
 * to the front of the set. This ensures that all other active tabs are kept.
 *
 * @param el - Content tabs element
 *
 * @returns Content tabs component observable
 */
export function mountContentTabs(
  el: HTMLElement
): Observable<Component<ContentTabs>> {
  const internal$ = new Subject<ContentTabs>()
  internal$.subscribe(({ active }) => {

    /* Set up linking of content tabs, if enabled */
    if (feature("content.tabs.link")) {
      const tab = active.innerText.trim()
      for (const set of getElements("[data-tabs]"))
        for (const label of getElements(":scope > label", set))
          if (label.innerText.trim() === tab) {
            const input = label.previousElementSibling as HTMLInputElement
            input.checked = true
            break
          }

      /* Persist active tabs in local storage */
      const tabs = __get<string[]>("__tabs") || []
      __set("__tabs", [...new Set([tab, ...tabs])])
    }
  })

  /* Create and return component */
  return watchContentTabs(el)
    .pipe(
      tap(internal$),
      finalize(() => internal$.complete()),
      map(state => ({ ref: el, ...state }))
    )
}
