/*
 * Copyright (c) 2016-2022 Martin Donath <martin.donath@squidfunk.com>
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
 * Class
 * ------------------------------------------------------------------------- */

export class Segmenter {

  /**
   * Segmentation map
   */
  protected set = new Set<string>()

  /**
   * Train segmenter
   *
   * @param value - Value
   */
  public add(value: string): void {
    const segments = value.split("\u200b")
    for (let i = 0; i < segments.length - 1; i++)
      this.set.add(segments[i])
  }

  /**
   * Cut string with segmenter
   *
   * This is not yet optimal, as we assume that we're always reading from the
   * beginning of the string. We should use better heuristics later on.
   *
   * @param value - Value
   *
   * @returns Segmented string
   */
  public cut(value: string): string[] {
    const segments: string[] = []
    const cuts = new Set([0])
    for (const i of cuts) {
      for (let j = i + 1; j < value.length; j++) {
        const segment = value.slice(i, j)
        if (this.set.has(segment)) {
          const prev = segments[segments.length - 1]
          if (segment.startsWith(prev)) {
            segments[segments.length - 1] = segment
            cuts.add(j)
            // @todo remove indexes from cuts array again
          } else if (typeof prev === "undefined" || !prev.endsWith(segment)) {
            segments.push(segment)
            cuts.add(j)
          }
        }
      }
    }
    return segments.length ? segments : [value]
  }
}
