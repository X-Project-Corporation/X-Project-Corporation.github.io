/*
 * Copyright (c) 2016-2020 Martin Donath <martin.donath@squidfunk.com>
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

import { Observable, OperatorFunction, pipe } from "rxjs"
import {
  distinctUntilChanged,
  filter,
  map,
  mapTo,
  startWith,
  switchMap,
  withLatestFrom
} from "rxjs/operators"

import { WorkerHandler, watchElementOffset } from "browser"
import {
  SearchMessage,
  SearchResultItem, // TODO: rename
  isSearchReadyMessage,
  isSearchResultMessage
} from "integrations"

import { SearchQuery } from "../../query"
import { applySearchResult } from "../react"

/* ----------------------------------------------------------------------------
 * Helper types
 * ------------------------------------------------------------------------- */

/**
 * Mount options
 */
interface MountOptions {
  query$: Observable<SearchQuery>      /* Search query observable */
}

/* ----------------------------------------------------------------------------
 * Functions
 * ------------------------------------------------------------------------- */

/**
 * Mount search result from source observable
 *
 * @param handler - Worker handler
 * @param options - Options
 *
 * @return Operator function
 */
export function mountSearchResult(
  { rx$ }: WorkerHandler<SearchMessage>, { query$ }: MountOptions
): OperatorFunction<HTMLElement, SearchResultItem[]> {
  return pipe(
    switchMap(el => {
      const container = el.parentElement!

      /* Compute if search is ready */
      const ready$ = rx$
        .pipe(
          filter(isSearchReadyMessage),
          mapTo(true)
        )

      /* Compute whether there are more search results to fetch */
      const fetch$ = watchElementOffset(container)
        .pipe(
          map(({ y }) => {
            return y >= container.scrollHeight - container.offsetHeight - 16
          }),
          distinctUntilChanged(),
          filter(Boolean)
        )

      // POC for suggestion rendering
      const query = document.querySelector<HTMLInputElement>("[data-md-component=search-query]")!
      query.addEventListener("keydown", ev => {
        setTimeout(() => {
          const span = document.querySelector(".md-search__suggest span")!
          if (span) {

            if (!span.innerHTML.startsWith(query.value) || query.value.endsWith(" ")) {
              span.innerHTML = ""
            }
          }
        }, 1)

        if (ev.key === "ArrowRight" && query.selectionStart === query.value.length) {
          const span = document.querySelector(".md-search__suggest span")!
          if (span) {
            query.value = span.innerHTML
          }
        }
      })

      // POC for search suggestions
      rx$.pipe(
        filter(isSearchResultMessage),
        map(({ data }) => data.suggestions),
        withLatestFrom(query$),
      )
        .subscribe(([suggestions, query]) => {
          const container = document.querySelector(".md-search__suggest")!

          // split using the tokenizer separator... for now just use the default
          // wrapped in parenthesis, so we know how much whitespace is stripped.
          const words = query.value.split(/([\s-]+)/)

          // now, take the last word and check how much we entered of it
          if (suggestions.length) {
            const [last] = suggestions.slice(-1)
            console.log(words, last)

            // now just replace the last word with the last suggestion!
            const span = document.createElement("span")
            span.innerHTML = [...words.slice(0, -1), last].join("")
            container.innerHTML = ""
            container.appendChild(span)

          } else {
            container.innerHTML = ""
          }

          // now, find query positions

        })

      /* Apply search results */
      return rx$
        .pipe(
          filter(isSearchResultMessage),
          map(({ data }) => data.items),
          applySearchResult(el, { query$, ready$, fetch$ }),
          startWith([])
        )
    })
  )
}
