# Centered Non-Table Elements

## In active use

1. `p.center`
   Defined by `.center, p.center { text-align: center; }` in `bennett.css`.
   Reference: `bennett.css:569`
   Current use: this is the only centered non-table pattern actually present in content.
   Occurrences found in `sections.json`: `139`
   Typical use: section titles, subsection labels, and front-matter lines such as `THE ALPHABET.`, `I. JULIAN CALENDAR.`, and centered front-page copy.
   Representative content references:
   - `sections.json:390`
   - `sections.json:2240`
   - `sections.json:2290`

## Defined in CSS but not currently used in content

1. `.figcenter`
   Defined as `text-align: center; margin: 1.5em auto; font-size: 0.85em;`
   Reference: `bennett.css:586`
   Current use in `sections.json`, `index.html`, and `temp/colonblow.md`: none

1. `.figure`
   Same rule as `.figcenter`
   Reference: `bennett.css:586`
   Current use in `sections.json`, `index.html`, and `temp/colonblow.md`: none

## Not found

1. No non-table elements with inline `text-align: center`

1. No non-table elements using `align='center'`

## Excluded on purpose

1. Centered table cells and table headers such as `<td align='center'>` and `<th>` content

1. Elements that are left- or right-aligned, such as headings (`h1`-`h6` are left-aligned) and `.author`
