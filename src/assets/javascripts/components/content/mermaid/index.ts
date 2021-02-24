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

import { Observable } from "rxjs"
import { mapTo, shareReplay, tap } from "rxjs/operators"

import { watchScript } from "~/browser"

import { Component } from "../../_"

/* ----------------------------------------------------------------------------
 * Types
 * ------------------------------------------------------------------------- */

/**
 * Mermaid diagram
 */
export interface Mermaid {}

/* ----------------------------------------------------------------------------
 * Data
 * ------------------------------------------------------------------------- */

/**
 * Mermaid instance observable
 */
let mermaid$: Observable<void>

/**
 * Global index for Mermaid integration
 */
let index = 0

/* ----------------------------------------------------------------------------
 * Functions
 * ------------------------------------------------------------------------- */

/**
 * Mount Mermaid diagram
 *
 * @param el - Code block element
 *
 * @returns Mermaid component observable
 */
export function mountMermaid(
  el: HTMLElement
): Observable<Component<Mermaid>> {
  mermaid$ ||= watchScript(
    "https://unpkg.com/mermaid@8.8.4/dist/mermaid.min.js"
  )
    .pipe(
      tap(() => mermaid.initialize({
        startOnLoad: false,
        themeCSS
      })),
      shareReplay(1)
    )

  /* Render diagram */
  mermaid$.subscribe(() => {
    const code = el.innerText
    mermaid.mermaidAPI.render(`__mermaid_${index++}`, code, (svg: string) => {
      el.innerHTML = svg
    })
  })

  /* Create and return component */
  return mermaid$
    .pipe(
      mapTo({ ref: el })
    )
}

// Move to external CSS and load via `request`
const themeCSS = `
  rect.actor {
    fill: white;
  }
  .classLabel .box {
    background-color: var(--md-mermaid-label-bg-color);
    fill: var(--md-mermaid-label-bg-color);
    opacity: 1;
  }
  .classLabel .label {
    font-family: var(--md-mermaid-font-family);
    fill: var(--md-mermaid-label-fg-color)
  }
  .statediagram-cluster.statediagram-cluster .inner {
    fill: var(--md-default-bg-color);
  }
  .statediagram-state rect.divider {
    stroke: var(--md-default-fg-color--lighter);
    fill: var(--md-default-fg-color--lightest);
  }
  .cluster rect {
    stroke: var(--md-default-fg-color--lighter);
    fill: var(--md-default-fg-color--lightest);
  }
  .edgeLabel,
  .edgeLabel rect {
    background-color: var(--md-mermaid-label-bg-color);
    fill: var(--md-mermaid-label-bg-color);
  }
  .cardinality text {
    fill: inherit !important;
  }
  .cardinality,
  g.classGroup text {
    font-family: var(--md-mermaid-font-family);
    fill: var(--md-mermaid-label-fg-color);
  }
  .edgeLabel .label rect {
    fill: transparent;
  }
  .nodeLabel,
  .label,
  .label div .edgeLabel {
    font-family: var(--md-mermaid-font-family);
    color: var(--md-mermaid-label-fg-color);
  }
  .label foreignObject {
    overflow: visible;
  }
  .arrowheadPath,
  marker {
    fill: var(--md-mermaid-edge-color) !important;
  }
  .edgePath .path,
  .flowchart-link,
  .relation,
  .transition {
    stroke: var(--md-mermaid-edge-color);
  }
  .statediagram-cluster rect,
  g.classGroup line,
  g.classGroup rect,
  .node circle,
  .node ellipse,
  .node path,
  .node polygon,
  .node rect {
    fill: var(--md-mermaid-node-bg-color);
    stroke: var(--md-mermaid-node-fg-color);
  }
  .node circle.state-end {
    fill: var(--md-mermaid-label-bg-color);
    stroke: none;
  }
  .node circle.state-start {
    fill: var(--md-mermaid-label-fg-color);
    stroke: var(--md-mermaid-label-fg-color);
  }
`
