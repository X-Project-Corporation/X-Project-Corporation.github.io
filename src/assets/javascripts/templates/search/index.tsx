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

import {
  ArticleDocument,
  SearchResult,
  SearchResultDocument,
  SectionDocument
} from "integrations/search"
import { h, truncate } from "utilities"

/* ----------------------------------------------------------------------------
 * Data
 * ------------------------------------------------------------------------- */

/**
 * CSS classes
 */
const css = {
  item:    "md-search-result__item",
  link:    "md-search-result__link",
  more:    "md-search-result__more",
  article: "md-search-result__article md-search-result__article--document",
  section: "md-search-result__article",
  title:   "md-search-result__title",
  teaser:  "md-search-result__teaser",
  terms:   "md-search-result__terms"
}

/* ------------------------------------------------------------------------- */

/**
 * Path of `content-copy` icon
 */
const path =
  "M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H13C12.59,21.75 12.2,21.44 " +
  "11.86,21.1C11.53,20.77 11.25,20.4 11,20H6V4H13V9H18V10.18C18.71,10.34 " +
  "19.39,10.61 20,11V8L14,2M20.31,18.9C21.64,16.79 21,14 " +
  "18.91,12.68C16.8,11.35 14,12 12.69,14.08C11.35,16.19 12,18.97 " +
  "14.09,20.3C15.55,21.23 17.41,21.23 " +
  "18.88,20.32L22,23.39L23.39,22L20.31,18.9M16.5,19A2.5,2.5 0 0,1 " +
  "14,16.5A2.5,2.5 0 0,1 16.5,14A2.5,2.5 0 0,1 19,16.5A2.5,2.5 0 0,1 16.5,19Z"

/* ----------------------------------------------------------------------------
 * Helper function
 * ------------------------------------------------------------------------- */

/**
 * Render an article document
 *
 * @param document - Article document
 * @param teaser - Whether to render the teaser
 *
 * @return Element
 */
function renderArticleDocument(
  document: SearchResultDocument<ArticleDocument>, teaser: boolean
) {

  /* Render icon */
  const icon = (
    <div class="md-search-result__icon md-icon">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
        <path d={path}></path>
      </svg>
    </div>
  )

  /* Render article */
  const { location, title, text, terms } = document
  return (
    <a href={location} class={css.link} tabIndex={-1}>
      <article class={css.article}>
        {icon}
        <h1 class={css.title}>{title}</h1>
        {text.length > 0 && teaser &&
          <p class={css.teaser}>{truncate(text, 320)}</p>
        }
        {teaser && terms.length > 0 && <p class={css.terms}>
          Missing: <del>{terms.join(", ")}</del>
        </p>}
      </article>
    </a>
  )
}

/**
 * Render a section document
 *
 * @param document - Section document
 *
 * @return Element
 */
function renderSectionDocument(
  document: SearchResultDocument<SectionDocument>
) {
  const { location, title, text, terms } = document
  return (
    <a href={location} class={css.link} tabIndex={-1}>
      <article class={css.section}>
        <h1 class={css.title}>{title}</h1>
        {text.length > 0 &&
          <p class={css.teaser}>{truncate(text, 320)}</p>
        }
        {terms.length > 0 && <p class={css.terms}>
          Missing: <del>{terms.join(", ")}</del>
        </p>}
      </article>
    </a>
  )
}

/* ----------------------------------------------------------------------------
 * Functions
 * ------------------------------------------------------------------------- */

/**
 * Render a search result
 *
 * @param result - Search result
 *
 * @return Element
 */
export function renderSearchResult(
  result: SearchResult, threshold: number = Infinity, query: string
) {
  const docs = [...result]

  // TODO: write a function that removes control characters
  query = query.replace(/[*+\-~^]/g, "")
  // TODO: also add query terms as a URL parameter, so we can highlight
  // them when moving to the respective page. Every word with "-" should be
  // filtered out.

  /* Only leave terms which we didn't find */ // TODO: get tokenizer configuration
  const terms = query.split(/[\s\-]+/g)
  for (const doc of docs) {
    doc.terms = terms.filter(term => (
      doc.terms.every(t => !t.startsWith(term)) // TODO: could be more efficient
    ))
  }

  /* Find and extract parent article */
  const parent = docs.findIndex(x => !("parent" in x))
  const [article] = docs.splice(parent, 1)

  /* Determine last index above threshold */
  let index = docs.findIndex(x => x.score < threshold)
  if (index === -1)
    index = docs.length

  /* Partition sections */
  const best = docs.slice(0, index)
  const more = docs.slice(index)

  /* Render children */
  const children = [
    renderArticleDocument(article as any, !parent && index === 0),
    ...best.map(renderSectionDocument as any), // TODO: fix typings
    ...more.length ? [
      <details class={css.more}>
        <summary>{more.length} more on this page</summary>
        {...more.map(renderSectionDocument as any)}
      </details>
    ] : []
  ]

  /* Render search result */
  return (
    <li class={css.item}>
      {children}
    </li>
  )
}
