---
template: overrides/main.html
icon: material/comment-processing-outline
---

# Abbreviations

Technical documentation often incurs the usage of many acronyms, which may
need additional explanation, especially for new user of your project. For these
matters, Material for MkDocs uses a combination of Markdown extensions to
enable site-wide glossaries.

## Configuration

This configuration enables abbreviations and allows to build a simple
project-wide glossary, sourcing definitions from a central location. Add the
following line to `mkdocs.yml`:

``` yaml
markdown_extensions:
  - abbr
  - attr_list
  - pymdownx.snippets
```

See additional configuration options:

- [Abbreviations]
- [Attribute Lists]
- [Snippets]

  [Abbreviations]: ../setup/extensions/python-markdown.md#abbreviations
  [Attribute Lists]: ../setup/extensions/python-markdown.md#attribute-lists
  [Snippets]: ../setup/extensions/python-markdown-extensions.md#snippets

## Usage

### Adding tooltips

The [Markdown syntax] allows to specify a `title` for each link, which will
render as a beautiful tooltip when [improved tooltips] are enabled. Add a 
tooltip to a link with the following lines:

``` markdown title="Link with tooltip, inline syntax"
[Hover me](https://example.com "I'm a tooltip!")
```

<div class="result" markdown>

[Hover me](https://example.com "I'm a tooltip!")

</div>

Tooltips can also be added to link references:

``` markdown title="Link with tooltip, reference syntax"
[Hover me][example]

  [example]: https://example.com "I'm a tooltip!"
```

<div class="result" markdown>

[Hover me](https://example.com "I'm a tooltip!")

</div>

For all other elements, a `title` can be added by using the [Attribute Lists]
extension:

``` markdown title="Icon with tooltip"
:material-information-outline:{ title="Important information" }
```

<div class="result" markdown>

:material-information-outline:{ title="Important information" }

</div>

  [Markdown syntax]: https://daringfireball.net/projects/markdown/syntax#link
  [improved tooltips]: #improved-tooltips

### Adding abbreviations

Abbreviations can be defined by using a special syntax similar to URLs and 
[footnotes], starting with a `*` and immediately followed by the term or
acronym to be associated in square brackets:

``` markdown title="Text with abbreviations"
The HTML specification is maintained by the W3C.

*[HTML]: Hyper Text Markup Language
*[W3C]: World Wide Web Consortium
```

<div class="result" markdown>

The HTML specification is maintained by the W3C.

*[HTML]: Hyper Text Markup Language
*[W3C]: World Wide Web Consortium

</div>

  [footnotes]: footnotes.md

### Adding a glossary

The [Snippets] extension can be used to implement a simple glossary by moving
all abbreviations in a dedicated file[^1], and embedding it with the
[`--8<--` notation][Snippets notation] at the end of each document:

  [^1]:
    It's highly recommended to put the Markdown file containing the
    abbreviations outside of the `docs` folder (here, a folder with the name 
    `includes` is used), as MkDocs might otherwise complain about an
    unreferenced file.

=== ":octicons-file-code-16: docs/example.md"

    ```` markdown
    The HTML specification is maintained by the W3C.

    --8<-- "includes/abbreviations.md"
    ````

=== ":octicons-file-code-16: includes/abbreviations.md"

    ```` markdown
    *[HTML]: Hyper Text Markup Language
    *[W3C]: World Wide Web Consortium
    ````

  [Snippets notation]: https://facelessuser.github.io/pymdown-extensions/extensions/snippets/#snippets-notation