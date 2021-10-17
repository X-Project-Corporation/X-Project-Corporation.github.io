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

import {
  SearchDocument,
  SearchDocumentMap,
  setupSearchDocumentMap
} from "../document"
import {
  Position,
  Table,
  highlighter,
  tokenizer
} from "../internal"
import { SearchOptions } from "../options"
import {
  SearchQueryTerms,
  getSearchQueryTerms,
  parseSearchQuery
} from "../query"

/* ----------------------------------------------------------------------------
 * Types
 * ------------------------------------------------------------------------- */

/**
 * Search index configuration
 */
export interface SearchIndexConfig {
  lang: string[]                       /* Search languages */
  separator: string                    /* Search separator */
}

/**
 * Search index document
 */
export interface SearchIndexDocument {
  location: string                     /* Document location */
  title: string                        /* Document title */
  text: string                         /* Document text */
  tags?: string[]                      /* Document tags */
  boost?: number                       /* Document boost */
}

/* ------------------------------------------------------------------------- */

/**
 * Search index
 */
export interface SearchIndex {
  config: SearchIndexConfig            /* Search index configuration */
  docs: SearchIndexDocument[]          /* Search index documents */
  options: SearchOptions               /* Search options */
}

/* ------------------------------------------------------------------------- */

/**
 * Search metadata
 */
export interface SearchMetadata {
  score: number                        /* Score (relevance) */
  terms: SearchQueryTerms              /* Search query terms */
}

/* ------------------------------------------------------------------------- */

/**
 * Search result document
 */
export type SearchResultDocument = SearchDocument & SearchMetadata

/**
 * Search result item
 */
export type SearchResultItem = SearchResultDocument[]

/* ------------------------------------------------------------------------- */

/**
 * Search result
 */
export interface SearchResult {
  items: SearchResultItem[]            /* Search result items */
  suggestions?: string[]               /* Search suggestions */
}

/* ----------------------------------------------------------------------------
 * Functions
 * ------------------------------------------------------------------------- */

/**
 * Compute the difference of two lists of strings
 *
 * @param a - 1st list of strings
 * @param b - 2nd list of strings
 *
 * @returns Difference
 */
function difference(a: string[], b: string[]): string[] {
  const [x, y] = [new Set(a), new Set(b)]
  return [
    ...new Set([...x].filter(value => !y.has(value)))
  ]
}

/* ----------------------------------------------------------------------------
 * Class
 * ------------------------------------------------------------------------- */

/**
 * Search index
 */
export class Search {

  /**
   * Search document mapping
   *
   * A mapping of URLs (including hash fragments) to the actual articles and
   * sections of the documentation. The search document mapping must be created
   * regardless of whether the index was prebuilt or not, as Lunr.js itself
   * only stores the actual index.
   */
  protected documents: SearchDocumentMap

  /**
   * The underlying Lunr.js search index
   */
  protected index: lunr.Index

  /**
   * Search options
   */
  protected options: SearchOptions

  protected tables: Record<string, Partial<Record<keyof SearchDocument, Table>>>

  /**
   * Create the search integration
   *
   * @param data - Search index
   */
  public constructor({ config, docs, options }: SearchIndex) {
    this.options = options

    this.tables = {}
    const tables = this.tables

    /* Set up document map and index */
    this.documents = setupSearchDocumentMap(docs)
    this.index = lunr(function () {
      this.metadataWhitelist = ["position"]
      this.b(0)

      /* Set up (multi-)language support */
      if (config.lang.length === 1 && config.lang[0] !== "en") {
        // @ts-expect-error - namespace indexing not supported
        this.use(lunr[config.lang[0]])
      } else if (config.lang.length > 1) {
        this.use(lunr.multiLanguage(...config.lang))
      }

      /* Set up custom tokenizer (after language setup) */
      this.tokenizer = tokenizer as typeof lunr.tokenizer
      this.tokenizer.separator = new RegExp(config.separator)

      /* Compute functions to be removed from the pipeline */
      const fns = difference([
        "trimmer", "stopWordFilter", "stemmer"
      ], options.pipeline)

      /* Remove functions from the pipeline for registered languages */
      for (const lang of config.lang.map(language => (
        // @ts-expect-error - namespace indexing not supported
        language === "en" ? lunr : lunr[language]
      ))) {
        for (const fn of fns) {
          this.pipeline.remove(lang[fn])
          this.searchPipeline.remove(lang[fn])
        }
      }

      /* Set up reference */
      this.ref("location")

      function extractor(field: Partial<keyof SearchIndexDocument>): any {
        return (document: SearchIndexDocument) => {
          tables[document.location][field] = []
          if (Array.isArray(document[field])) {
            const values = document[field] as string[]
            return values.map(value => ({
              toString() { return value },
              table: tables[document.location][field]
            }))
          } else if (document[field]) {
            return {
              toString() { return document[field] },
              table: tables[document.location][field]
            }
          } else {
            return undefined
          }
        }
      }

      /* Set up fields */
      this.field("title", { boost: 1e3, extractor: extractor("title") })
      this.field("text", { extractor: extractor("text") })
      this.field("tags", { boost: 1e6, extractor: extractor("tags") })

      /* Index documents */
      for (const document of docs) {
        tables[document.location] = {}
        this.add(document, { boost: document.boost })
      }
    })
  }

  /**
   * Search for matching documents
   *
   * The search index which MkDocs provides is divided up into articles, which
   * contain the whole content of the individual pages, and sections, which only
   * contain the contents of the subsections obtained by breaking the individual
   * pages up at `h1` ... `h6`. As there may be many sections on different pages
   * with identical titles (for example within this very project, e.g. "Usage"
   * or "Installation"), they need to be put into the context of the containing
   * page. For this reason, section results are grouped within their respective
   * articles which are the top-level results that are returned.
   *
   * @param query - Query value
   *
   * @returns Search results
   */
  public search(query: string): SearchResult {
    if (query) {
      try {

        /* Parse query to extract clauses for analysis */
        const clauses = parseSearchQuery(query)
          .filter(clause => (
            clause.presence !== lunr.Query.presence.PROHIBITED
          ))

        /* Perform search and post-process results */
        const groups = this.index.search(query)

          /* Apply post-query boosts based on title and search query terms */
          .reduce<SearchResultItem>((item, { ref, score, matchData }) => {
            let document = this.documents.get(ref)
            if (typeof document !== "undefined") {
              // TODO: make a copy, as we're editing in-place
              document = { ...document }
              const { tags, parent } = document

              /* Compute and analyze search query terms */
              const terms = getSearchQueryTerms(
                clauses,
                Object.keys(matchData.metadata)
              )

              const map: Record<string, Position[]> = {}
              for (const match of Object.values(matchData.metadata)) {
                for (const [field, data] of Object.entries(match)) {
                  const { position } = data as any // TODO: fix typings
                  map[field] ||= []
                  map[field].push(...position)
                }
              }

              type Key = "text" | "title"

              for (const [field, positions] of Object.entries(map))
                document[field as Key] = highlighter(
                  document[field as Key],
                  this.tables[document.location][field as Key]!,
                  positions
                )

              /* Highlight title and text and apply post-query boosts */
              const boost = +!parent +
                Object.values(terms)
                  .filter(t => t).length /
                Object.keys(terms).length

              item.push({
                ...document,
                ...tags && { tags }, // TODO: highlight tags, if present
                score: score * (1 + boost ** 2),
                terms
              })
            }
            return item
          }, [])

          /* Sort search results again after applying boosts */
          .sort((a, b) => b.score - a.score)

          /* Group search results by article */
          .reduce((items, result) => {
            const document = this.documents.get(result.location)
            if (typeof document !== "undefined") {
              const ref = "parent" in document
                ? document.parent!.location
                : document.location
              items.set(ref, [...items.get(ref) || [], result])
            }
            return items
          }, new Map<string, SearchResultItem>())

        /* Ensure that every item set has an article */
        for (const [ref, items] of groups)
          if (!items.find(item => item.location === ref)) {
            const document = this.documents.get(ref)!
            items.push({ ...document, score: 0, terms: {} })
          }

        /* Generate search suggestions, if desired */
        let suggestions: string[] | undefined
        if (this.options.suggestions) {
          const titles = this.index.query(builder => {
            for (const clause of clauses)
              builder.term(clause.term, {
                fields: ["title"],
                presence: lunr.Query.presence.REQUIRED,
                wildcard: lunr.Query.wildcard.TRAILING
              })
          })

          /* Retrieve suggestions for best match */
          suggestions = titles.length
            ? Object.keys(titles[0].matchData.metadata)
            : []
        }

        /* Return items and suggestions */
        return {
          items: [...groups.values()],
          ...typeof suggestions !== "undefined" && { suggestions }
        }

      /* Log errors to console */
      } catch (err) {
        console.warn(`Invalid query: ${query} – see https://bit.ly/2s3ChXG`)
      }
    }

    /* Return nothing in case of error or empty query */
    return { items: [] }
  }
}
