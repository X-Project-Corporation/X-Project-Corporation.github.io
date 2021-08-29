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

/* ----------------------------------------------------------------------------
 * Types
 * ------------------------------------------------------------------------- */

/**
 * Position
 */
export interface Position {
  table: number[]                  /* Position table */
  index: number                    /* Position index */
}

/* ----------------------------------------------------------------------------
 * Helper types
 * ------------------------------------------------------------------------- */

/**
 * String section
 *
 * A section consists of a start and end position, as well as a block index to
 * denote to which top-level block it belongs.
 */
type Section = [number, number, number]

/* ----------------------------------------------------------------------------
 * Helper functions
 * ------------------------------------------------------------------------- */

/**
 * Split a string into sections
 *
 * This function preprocesses the given string by isolating all non-HTML parts
 * of a string, in order to ensure that HTML tags are removed before indexing.
 *
 * @param value - String value
 *
 * @returns String sections
 */
function split(value: string): Section[] {

  let start = 0                        /* Current start offset */
  let end = 0                          /* Current end offset */
  let block = 0                        /* Current block */

  /* Split string into sections */
  const sections: Section[] = []
  for (let stack = 0; end < value.length; end++) {

    /* Opening tag after non-empty section */
    if (value.charAt(end) === "<" && end > start) {
      sections.push([start, start = end, block])

    /* Closing tag */
    } else if (value.charAt(end) === ">") {
      if (value.charAt(start + 1) === "/") {
        if (--stack === 0)
          sections.push([end + 1, end + 1, ++block])

      /* Self-closing tag */
      } else if (value.charAt(end - 1) !== "/") {
        stack++
      }

      /* New section */
      start = end + 1
    }
  }

  /* Add trailing section */
  if (end > start)
    sections.push([start, end, block])

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
 * @param value - String value
 *
 * @returns Tokens
 */
export function tokenizer(value: string): lunr.Token[] {
  const tokens: lunr.Token[] = []
  if (typeof value === "string") {
    const table = [0]

    /* Tokenize section */
    for (const [start, end, block] of split(value)) {
      const section = value.slice(start, end)
      const separator = new RegExp(lunr.tokenizer.separator, "g")

      /* Split section into tokens */
      let match: RegExpExecArray
      let index = 0
      do {
        match = separator.exec(section)!

        /* Add table entry for non-empty section */
        const until = match?.index ?? section.length
        if (index < until) {
          table.push(
            start + index << 14 |
            until - index <<  8 |
            block         <<  2
          )

          /* Add token */
          tokens.push(
            new lunr.Token(
              section.slice(index, until).toLowerCase(), {
                position: {
                  table,
                  index: table.length - 1
                }
              }
            )
          )
        }

        /* Update index */
        if (match)
          index = match.index + match[0].length
      } while (match)
    }
  }

  /* Return tokens */
  return tokens
}

/**
 * Highlight all occurrences in a string
 *
 * @param value - String value
 * @param positions - Positions of occurrences
 *
 * @returns Highlighted string value
 */
export function highlighter(
  value: string, positions: Position[]
): string {
  for (const { table, index } of positions
    .sort((a, b) => b.index - a.index)
  ) {
    const offset = table[index] >> 14
    const length = table[index] >>  8 & 0x3F

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
