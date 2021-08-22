const lunr = require("lunr")

const data = "<p> Source \u00b7 Experimental \u00b7 Insiders only</p><p>The SuperFences extension, which is part of Python Markdown Extensions, allows for adding custom fences, which can be used to render Mermaid.js diagrams with zero effort:</p><pre><code>markdown_extensions:\n  - pymdownx.superfences:\n      custom_fences:\n        - name: mermaid\n          class: mermaid\n          format: !!python/name:pymdownx.superfences.fence_code_format\n</code></pre><p>No further configuration is necessary. Material for MkDocs will automatically load and initialize the Mermaid.js runtime when a page includes a fenced<code>mermaid</code> block. Furthermore:</p><ul><li> Works with instant loading without any additional effort</li><li> Diagrams automatically use fonts and colors defined in <code>mkdocs.yml</code>1</li><li> Fonts and colors can be customized with additional stylesheets</li><li> Support for both, light and dark color schemes</li></ul><p>While it&#x27;s also possible to integrate Mermaid.js using existing third-party plugins2, the new native integration is recommended as it ensures interoperability with all Material for MkDocs features.</p>"

const data2 = "abc def <code><span>with</span> <a>code<br /> </code>"
const data3 = ""

// console.log(
//   "abc def <code><span>with</span> <a>code<br /> </code>"
//     .split(/[\s\-]+|(?:<.*?>)/)
// )

// TODO: record stack during tokenization...

function tokenizer(value) {
  // return as array later...
  const position = [0] // TODO: also record boundaries...

  const tokens = []
  if (typeof value === "string") {
    value = value.toLowerCase()

    let block = 0

    /* Consume characters from string and group into tokens */
    const stack = []
    for (let start = 0, end = 0; end <= value.length; end++) {
      const char = value.charAt(end)
      if (
        lunr.tokenizer.separator.test(char) ||
        char === "<" || end === value.length
      ) {
        // console.log(value.slice(start, end))

        /* Create token */
        if (end > start) {
          const index = position.length
          position[index] =
            (start       << 14) |  // start ()
            (end - start <<  8) |  // length
            (block       <<  2)    // block index
          tokens.push(
            new lunr.Token(value.slice(start, end), {
              position,
              index
            })
          )
        }

        /* Always skip HTML tags */
        if (char === "<") {
          start = end
          // console.log(start, end)
          while (value.charAt(end) !== ">")
            end++

          // closing tag
          // console.log(stack)
          if (value.charAt(start + 1) === "/") {
            stack.pop()
            const index = position.length
            if (stack.length === 0) {
              block++ // TODO: remember where we set the last block, because

              // no length = block marker
              position[index] =
                ((end + 1) << 14) |
                (block << 2)
            }

              // we there might be paragraph-less tokens floating. thus, if
              // there were tokens since the last block before the next one,
              // we must increment it again...

          // opening tag, i.e. no self closing
          } else if (value.charAt(end) !== "/") {
            stack.push(value.slice(start + 1, end))
          }

          // console.log(value.slice(start, end + 1))
          // compute
        }

        /* Adjust start position */
        start = end + 1
      }
    }
  }

  /* Return tokens */
  return tokens
}

lunr.tokenizer.separator = /[\s\-.,:!="'/]/ // TODO: drop "." later on

const matches = []

const tokens = tokenizer(data)
console.dir(tokens, { depth: 3 })
const list = tokens[0].metadata.position
console.log(list)
for (const item of list) {
  const start  = item >> 14       // (width: 16)
  const length = item >> 8 & 0x3F // (width: 6)
  const block  = item >> 2 & 0x3F // (width: 6)

  console.log(block, start, length, data.slice(start, start + length))

  const word = data.slice(start, start + length).toLowerCase()

  // test: search for "mermaid" or "diagrams"
  if (word === "mermaid" || word === "diagrams") {
    matches.push(item)
  }
}

console.log("---")

for (const item of matches) {
  const start  = item >> 14       // (width: 16)
  const length = item >> 8 & 0x3F // (width: 6)
  const block  = item >> 2 & 0x3F // (width: 6)

  console.log(block, start, length, data.slice(start, start + length))
}

// let's say, we isolate block 1, isolate all tokens there... thus get the
// indexes of it... so, get block 1
// get block ranges
const blocks = []
for (const item of list) {
  const start  = item >> 14       // (width: 16)
  const length = item >> 8 & 0x3F // (width: 6)
  const block  = item >> 2 & 0x3F // (width: 6)

  if (!length)
    blocks[block] = start
}

// this allows for easy extraction of top-level blocks
const id = 1
console.log("_", data.slice(blocks[id], blocks[id + 1]), "_")

// - if the text is not too long, just show everything
// - if it is too long, try to squeeze it in out budget
// - implement line-based highlighting of code blocks

// now, we have to shorten the text...
