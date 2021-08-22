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
 * Functions
 * ------------------------------------------------------------------------- */

/**
 * Custom tokenizer with support for HTML tags
 *
 * This tokenizer implementation is adapted from the original tokenizer, but
 * skips all HTML tags and attributes to prevent interference with search.
 *
 * @param value - String value
 *
 * @returns Tokens
 */
export function tokenizer(value: string): lunr.Token[] {
  const tokens: lunr.Token[] = []
  if (typeof value === "string") {
    value = value.toLowerCase()

    /* Consume characters from string and group into tokens */
    for (let start = 0, end = 0; end <= value.length; end++) {
      const char = value.charAt(end)
      if (
        lunr.tokenizer.separator.test(char) ||
        char === "<" || end === value.length
      ) {

        /* Create token */
        if (end > start)
          tokens.push(
            new lunr.Token(value.slice(start, end), {
              position: [start, end],
              // index: tokens.length,
              pointer: tokens[tokens.length - 1] // or just the START number of the last top-level block?
            })
          )

        /* Always skip HTML tags */
        if (char === "<")
          while (value.charAt(end) !== ">")
            end++

        /* Adjust start position */
        start = end + 1
      }
    }
  }

  /* Return tokens */
  return tokens
}
