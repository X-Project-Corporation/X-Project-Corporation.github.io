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

import { split } from "~/utilities"

/* ----------------------------------------------------------------------------
 * Types
 * ------------------------------------------------------------------------- */

/**
 * Block
 */
export interface Block {
  type?: string                        /* Block type */
  data: number[]                       /* Block data */
}

/**
 * Position
 */
export interface Position {
  table: Block[]                       /* Position table */
  index: number                        /* Position index */
}

/* ----------------------------------------------------------------------------
 * Helper types
 * ------------------------------------------------------------------------- */

/**
 * String section
 */
type Section = [number, number, number, number]

/* ----------------------------------------------------------------------------
 * Helper functions
 * ------------------------------------------------------------------------- */

/**
 * Extract all non-HTML parts of a string
 *
 * This function preprocesses the given string by isolating all non-HTML parts
 * of a string, in order to ensure that HTML tags are removed before indexing.
 *
 * @param value - String value
 *
 * @returns String sections
 */
function extract(value: string): Section[] {

  let block = 0                        /* Current block */
  let start = 0                        /* Current start offset */
  let end = 0                          /* Current end offset */

  /* Split string into sections */
  const sections: Section[] = []
  for (let stack = 0; end < value.length; end++) {

    /* Tag start after non-empty section */
    if (value.charAt(end) === "<" && end > start) {
      sections.push([block, 1, start, start = end])

    /* Tag end */
    } else if (value.charAt(end) === ">") {
      if (value.charAt(start + 1) === "/") {
        if (--stack === 0)
          block++
      } else if (value.charAt(end - 1) !== "/") {
        if (stack++ === 0)
          sections.push([block, 0, start + 1, end])
      }

      /* New section */
      start = end + 1
    }
  }

  /* Add trailing section */
  if (end > start)
    sections.push([block, 1, start, end])

  /* Return sections */
  return sections
}

/* ----------------------------------------------------------------------------
 * Functions
 * ------------------------------------------------------------------------- */

/**
 * Split a string into tokens
 *
 * This tokenizer supersedes the default tokenizer that is provided by Lunr.js,
 * as it is aware of HTML tags and allows for multi-character splitting.
 *
 * @param input - String value or token
 *
 * @returns Tokens
 */
export function tokenizer(input?: lunr.Token | string): lunr.Token[] {
  const tokens: lunr.Token[] = []
  if (input) {
    const value = input.toString()
    const table: Block[] = []

    /* Tokenize section */
    for (const [block, add, start, end] of extract(value)) {
      const section = value.slice(start, end)
      if (add) {
        split(section, lunr.tokenizer.separator, ([index, until]) => {

          /* Add table entry */
          table[block] ||= { data: [] }
          table[block].data.push(
            start + index << 8 |
            until - index
          )

          /* Add token to block */
          tokens.push(new lunr.Token(
            section.slice(index, until).toLowerCase(), {
              position: {
                table,
                index: block << 16 | table[block].data.length - 1
              }
            }
          ))
        })

      /* Start new block */
      } else {
        table[block] = {
          ...end > start && { type: value.slice(start, end) },
          data: []
        }
      }
    }
  }

  /* Return tokens */
  return tokens
}

/**
 * Highlight all occurrences in a string
 *
 * @param value - String value
 * @param positions - Occurrences
 *
 * @returns Highlighted string value
 */
export function highlighter(
  value: string, positions: Position[]
): string {
  for (const { table, index: i } of positions
    .sort((a, b) => b.index - a.index)
  ) {
    const block = i >> 16
    const index = i  & 0xFFFF

    /* Retrieve offset and length of match */
    const offset = table[block].data[index] >> 8
    const length = table[block].data[index]  & 0xFF

    /* Wrap occurrence with marker */
    value = [
      value.slice(0, offset),
      "<mark>", value.slice(offset, offset + length), "</mark>",
      value.slice(offset + length)
    ].join("")
  }

  /* Return highlighted string value */
  return value
}
