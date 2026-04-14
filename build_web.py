#!/usr/bin/env python3
"""
build_web.py — Bennett's New Latin Grammar
Transform loosies/ HTML source files → bennett-web/ with:
  - Semantic HTML cleanup (blockquotes→divs, headings, table attrs, anchors)
  - Native Popover API footnotes (content embedded at build time)
  - Sub-lettered rules converted to <ol class="rule-list">
  - Pjax-ready multi-page structure (new bennett.js)

Usage:  python3 build_web.py
Output: ../bennett-web/
"""

import json, re, shutil
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag

# ── Paths ────────────────────────────────────────────────────────────────────

REPO   = Path(__file__).parent
SRC    = REPO / 'loosies'
OUT    = REPO.parent / 'bennett-web'
FONTS  = REPO / 'fonts'
CSS_IN = REPO / 'bennett.css'


# ═══════════════════════════════════════════════════════════════════════════
# PRE-PASS: Build footnote map from appendix.html
# ═══════════════════════════════════════════════════════════════════════════

def build_footnote_map():
    """
    Parse appendix.html, find each <a name="Nt_N"> anchor, extract the
    inner HTML of its <p> parent (minus the [N] anchor itself).
    Returns dict: { 'Nt_1': '<html content>', ... }
    """
    fn_map = {}
    src = SRC / 'appendix.html'
    soup = BeautifulSoup(src.read_text(encoding='utf-8'), 'html.parser')

    for a in soup.find_all('a'):
        name = a.get('name', '')
        if not re.match(r'^Nt_\d+$', name):
            continue
        p = a.find_parent('p')
        if not p:
            continue
        # Clone p, remove the [N] anchor, grab remaining inner HTML
        p_copy = BeautifulSoup(str(p), 'html.parser').find('p')
        for fn_a in list(p_copy.find_all('a')):
            if re.match(r'^Nt_\d+$', fn_a.get('name', '')):
                fn_a.decompose()
        fn_map[name] = p_copy.decode_contents().strip()

    return fn_map


# ═══════════════════════════════════════════════════════════════════════════
# TRANSFORMATION 1: Remove <br> (direct article children) and all <hr>
# ═══════════════════════════════════════════════════════════════════════════

def remove_hr_br(soup):
    for hr in list(soup.find_all('hr')):
        hr.decompose()

    article = soup.find('article')
    if not article:
        return
    for child in list(article.children):
        if getattr(child, 'name', None) == 'br':
            child.decompose()


# ═══════════════════════════════════════════════════════════════════════════
# TRANSFORMATION 2: Deprecate <a name> + embed footnote popovers
# ═══════════════════════════════════════════════════════════════════════════

def process_anchors(soup, fn_map):
    """
    Three patterns:
      NtA_N + href  → <button class="fn-ref" popovertarget="fn-N"> + popover div
      name only, empty text → remove tag (and leave empty <p> for cleanup)
      name only, has text  → unwrap (keep text, discard tag)
    Popover divs are appended after <article> inside <main>.
    """
    popover_divs = []

    for a in list(soup.find_all('a')):
        name = a.get('name', '')
        href = a.get('href', '')

        if re.match(r'^NtA_\d+$', name) and href:
            # Footnote reference
            m = re.search(r'Nt_(\d+)', href)
            if not m:
                continue
            num    = m.group(1)
            fn_key = f'Nt_{num}'
            fn_id  = f'fn-{num}'
            fn_html = fn_map.get(fn_key, f'Footnote {num}.')

            btn = soup.new_tag('button', type='button')
            btn['class'] = 'fn-ref'
            btn['popovertarget'] = fn_id
            btn.string = f'[{num}]'

            sup = soup.new_tag('sup')
            sup.append(btn)
            a.replace_with(sup)

            # Build popover div (placed after article)
            div = soup.new_tag('div', id=fn_id)
            div['class'] = 'fn-popover'
            div['popover'] = ''

            # Inner content from footnote map (may contain inline HTML)
            content_soup = BeautifulSoup(f'<p>{fn_html}</p>', 'html.parser')
            content_p = content_soup.find('p')
            div.append(content_p)

            link_p = soup.new_tag('p')
            link_p['class'] = 'fn-popover__link'
            link_a = soup.new_tag('a', href=f'appendix.html#{fn_key}')
            link_a.string = 'Full note in appendix →'
            link_p.append(link_a)
            div.append(link_p)

            popover_divs.append(div)

        elif name and not href and not a.get_text().strip():
            # Empty anchor — remove it
            a.decompose()

        elif name and not href:
            # Section signpost with visible text — strip tag, keep text
            a.unwrap()

    # Place popover divs after <article> inside <main>
    if popover_divs:
        main = soup.find('main')
        if main:
            for div in popover_divs:
                main.append(div)


def cleanup_empty_paragraphs(soup):
    """Remove <p> elements left empty after anchor removal."""
    article = soup.find('article')
    if not article:
        return
    for p in list(article.find_all('p')):
        if not p.get_text().strip() and not p.find_all(True):
            p.decompose()


# ═══════════════════════════════════════════════════════════════════════════
# TRANSFORMATION 3: Clean deprecated table attributes
# ═══════════════════════════════════════════════════════════════════════════

def clean_table_attrs(soup):
    for table in soup.find_all('table'):
        for attr in ('width', 'summary', 'title', 'align'):
            table.attrs.pop(attr, None)

        # Wrap in .table-wrap if not already
        parent = table.parent
        if not (parent and 'table-wrap' in (parent.get('class') or [])):
            wrap = soup.new_tag('div', **{'class': 'table-wrap'})
            table.insert_before(wrap)
            wrap.append(table.extract())

    for tag in soup.find_all(['td', 'th', 'tr']):
        tag.attrs.pop('width', None)
        tag.attrs.pop('valign', None)
        align = tag.attrs.pop('align', None)
        if align == 'center':
            classes = tag.get('class') or []
            if isinstance(classes, str):
                classes = [classes]
            if 'tc' not in classes:
                tag['class'] = classes + ['tc']
        # align='left' → just removed


# ═══════════════════════════════════════════════════════════════════════════
# TRANSFORMATION 4: <p class="center"> → section title heading
# ═══════════════════════════════════════════════════════════════════════════

def convert_headings(soup):
    article = soup.find('article')
    if not article:
        return

    for p in list(soup.find_all('p')):
        classes = p.get('class') or []
        if isinstance(classes, str):
            classes = [classes]
        if 'center' not in classes:
            continue
        if p.parent != article:
            continue

        # Is this the first significant content in the article?
        is_first = True
        for sib in p.previous_siblings:
            sib_name = getattr(sib, 'name', None)
            if sib_name is None:
                if str(sib).strip():
                    is_first = False
                    break
            elif sib_name not in ('br', 'hr'):
                is_first = False
                break

        p.attrs.pop('style', None)
        new_cls = [c for c in classes if c != 'center']

        if is_first:
            p.name = 'h2'
            new_cls.append('section-title')
            p['class'] = new_cls
        else:
            p.name = 'h3'
            if new_cls:
                p['class'] = new_cls
            else:
                p.attrs.pop('class', None)


# ═══════════════════════════════════════════════════════════════════════════
# TRANSFORMATION 5: Extract section numbers into left-margin spans
# ═══════════════════════════════════════════════════════════════════════════

def extract_section_numbers(soup):
    """
    Find <p><b>NNN. [Title]</b>... inside <article> and pull the number
    out as <span class="sect-num">NNN</span> (period dropped, title stays bold).
    Matches all occurrences per page (intro has sub-numbered items 1-4).
    """
    article = soup.find('article', class_='section-content')
    if not article:
        return

    for p in article.find_all('p'):
        # First non-whitespace child must be a <b> with no nested tags
        children = [c for c in p.children
                    if not (isinstance(c, NavigableString) and not c.strip())]
        if not children or not isinstance(children[0], Tag) or children[0].name != 'b':
            continue

        b_tag = children[0]
        # Only process plain-text <b> elements
        if any(isinstance(c, Tag) for c in b_tag.children):
            continue

        b_text = b_tag.get_text()
        m = re.match(r'^(\d+[A-Z]?)\.\s*(.*)', b_text, re.DOTALL)
        if not m:
            continue

        sect_num = m.group(1)
        remaining = ' '.join(m.group(2).split())  # normalise whitespace

        span = soup.new_tag('span', **{'class': 'sect-num'})
        span.string = sect_num
        b_tag.insert_before(span)

        if not remaining:
            b_tag.decompose()
        else:
            b_tag.clear()
            b_tag.append(NavigableString(remaining))

        # Strip the whitespace text node that HTML would otherwise collapse
        # into a visible space between the margin number and the following text
        nxt = span.next_sibling
        if isinstance(nxt, NavigableString):
            stripped = nxt.lstrip()
            if stripped != str(nxt):
                nxt.replace_with(NavigableString(stripped))


# ═══════════════════════════════════════════════════════════════════════════
# TRANSFORMATION 6: span.sc cleanup  (applied to serialized HTML)
# ═══════════════════════════════════════════════════════════════════════════

def fix_sc_spans(html):
    # Pull preceding word-initial capital into the span
    html = re.sub(
        r'(?<![A-Za-z])([A-Z])<span class="sc">',
        r'<span class="sc">\1',
        html
    )
    # Merge consecutive sc spans (iterate until stable)
    prev = None
    while prev != html:
        prev = html
        html = re.sub(r'</span>(\s*)<span class="sc">', r'\1', html)
    return html


# ═══════════════════════════════════════════════════════════════════════════
# TRANSFORMATION 6: blockquote → div with semantic class names
# ═══════════════════════════════════════════════════════════════════════════

def convert_blockquotes(soup):
    for bq in list(soup.find_all('blockquote')):
        classes = bq.get('class') or []
        if isinstance(classes, str):
            classes = [classes]

        div = soup.new_tag('div')

        if 'b1' in classes:
            div['class'] = ['rule-sub']
        elif 'b2' in classes:
            div['class'] = ['example']
        elif 'b3' in classes:
            div['class'] = ['rule-sub', 'rule-sub--deep']
        elif 'small' in classes:
            div['class'] = ['example', 'example--sm']
        else:
            div['class'] = classes  # preserve unknown classes

        while bq.contents:
            div.append(bq.contents[0].extract())

        bq.replace_with(div)


# ═══════════════════════════════════════════════════════════════════════════
# TRANSFORMATION 7: Sub-lettered rules → <ol class="rule-list">
# ═══════════════════════════════════════════════════════════════════════════

def _is_labeled_rule_sub(tag):
    """
    True if tag is div.rule-sub whose first <p> opens with <i>X</i>)
    (X = single letter, possibly Greek char like α).
    """
    if not (tag.name == 'div' and 'rule-sub' in (tag.get('class') or [])):
        return False
    first_p = tag.find('p')
    if not first_p:
        return False
    first_child = None
    for c in first_p.children:
        if isinstance(c, Tag):
            first_child = c
            break
    if not (first_child and first_child.name == 'i'):
        return False
    letter = first_child.get_text().strip()
    if len(letter) > 3:
        return False
    nxt = first_child.next_sibling
    if isinstance(nxt, NavigableString) and str(nxt).lstrip().startswith(')'):
        return True
    return False


def _move_into_li(li_tag, src_div, strip_label=False):
    """Move contents of src_div into li_tag, optionally stripping <i>X</i>) label."""
    while src_div.contents:
        child = src_div.contents[0].extract()
        if strip_label and child.name == 'p' and not li_tag.find('p'):
            # Strip the <i>X</i>) label from the first <p>
            first_tag = None
            for c in list(child.children):
                if isinstance(c, Tag):
                    first_tag = c
                    break
            if first_tag and first_tag.name == 'i':
                after = first_tag.next_sibling
                first_tag.decompose()
                if isinstance(after, NavigableString):
                    new_text = str(after).lstrip()
                    if new_text.startswith(')'):
                        new_text = new_text[1:].lstrip()
                    after.replace_with(new_text)
        li_tag.append(child)


def group_rule_lists(soup):
    article = soup.find('article')
    if not article:
        return

    # Detach all direct children into a list
    children = []
    while article.contents:
        children.append(article.contents[0].extract())

    result      = []
    current_ol  = None
    current_li  = None

    def flush():
        nonlocal current_ol, current_li
        if current_ol is not None:
            result.append(current_ol)
        current_ol = None
        current_li = None

    for child in children:
        if not isinstance(child, Tag):
            # NavigableString — attach to current li or pass through
            if current_li is not None:
                current_li.append(child)
            else:
                result.append(child)
            continue

        classes  = child.get('class') or []
        # rule-sub--deep items are NOT grouped into ol — they're standalone sub-annotations
        is_rsub  = (child.name == 'div' and 'rule-sub' in classes
                    and 'rule-sub--deep' not in classes)
        is_ex    = child.name == 'div' and 'example' in classes
        labeled  = is_rsub and _is_labeled_rule_sub(child)

        if labeled:
            if current_ol is None:
                current_ol = soup.new_tag('ol', **{'class': 'rule-list'})
            current_li = soup.new_tag('li')
            _move_into_li(current_li, child, strip_label=True)
            current_ol.append(current_li)

        elif is_rsub and current_li is not None:
            # Non-labeled continuation inside current li
            _move_into_li(current_li, child, strip_label=False)

        elif is_ex and current_li is not None:
            current_li.append(child)

        else:
            flush()
            result.append(child)

    flush()

    for item in result:
        article.append(item)


# ═══════════════════════════════════════════════════════════════════════════
# APPENDIX: Special processing for appendix.html
# ═══════════════════════════════════════════════════════════════════════════

def process_appendix_anchors(soup):
    """
    In appendix.html:
      - <a name="Nt_N"> → add id="Nt_N" to its parent <p> (keep tag but drop name attr)
      - Empty section anchors (<a name="footnotes"></a> etc.) → remove
    """
    for a in list(soup.find_all('a')):
        name = a.get('name', '')
        href = a.get('href', '')

        if re.match(r'^Nt_\d+$', name):
            p = a.find_parent('p')
            if p and not p.get('id'):
                p['id'] = name
            del a.attrs['name']

        elif re.match(r'^NtA_\d+$', name) and href:
            # Back-reference from appendix to section page — remove name, keep href
            del a.attrs['name']

        elif name and not href and not a.get_text().strip():
            a.decompose()

        elif name and not href:
            a.unwrap()


# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR: Add jump input to pages that don't have one
# ═══════════════════════════════════════════════════════════════════════════

JUMP_HTML = '''\
<div class="sidebar-jump">
  <input class="sidebar-jump-input" id="sidebar-jump-input" type="search"
         placeholder="Jump to §N…" aria-label="Jump to section">
</div>'''

def add_sidebar_jump(soup):
    home = soup.find('a', class_='sidebar-home')
    if home and not soup.find(class_='sidebar-jump'):
        jump_soup = BeautifulSoup(JUMP_HTML, 'html.parser')
        home.insert_after(jump_soup)


# ═══════════════════════════════════════════════════════════════════════════
# HASH LINK CONVERSION (for index.html generation)
# ═══════════════════════════════════════════════════════════════════════════

NAMED_PAGES = {
    'intro':         'introduction.html',
    'index':         'index.html',
    'appendix':      'appendix.html',
    'syntax-index':  'appendix.html#ind1',
    'verb-index':    'appendix.html#ind3',
    'general-index': 'appendix.html#ind4',
    'footnotes':     'appendix.html#footnotes',
    'ind1':          'appendix.html#ind1',
    'ind2':          'appendix.html#ind2',
    'ind3':          'appendix.html#ind3',
    'ind4':          'appendix.html#ind4',
}

def convert_hash_links(soup):
    """Convert hash-based SPA links (#N, #intro, etc.) to .html file links."""
    for a in soup.find_all('a', href=True):
        href = a['href']
        if not href.startswith('#'):
            continue
        target = href[1:]
        if target in NAMED_PAGES:
            a['href'] = NAMED_PAGES[target]
        elif re.match(r'^\d+[A-Za-z]?$', target):
            a['href'] = f'{target}.html'


# ═══════════════════════════════════════════════════════════════════════════
# PROCESS ONE FILE
# ═══════════════════════════════════════════════════════════════════════════

def process_file(src_path, out_path, fn_map, is_appendix=False):
    html = src_path.read_text(encoding='utf-8')
    soup = BeautifulSoup(html, 'html.parser')

    if is_appendix:
        remove_hr_br(soup)
        clean_table_attrs(soup)
        process_appendix_anchors(soup)
        convert_blockquotes(soup)
    else:
        remove_hr_br(soup)
        process_anchors(soup, fn_map)
        cleanup_empty_paragraphs(soup)
        clean_table_attrs(soup)
        convert_headings(soup)
        convert_blockquotes(soup)
        group_rule_lists(soup)
        extract_section_numbers(soup)

    add_sidebar_jump(soup)

    result = str(soup)
    result = fix_sc_spans(result)
    out_path.write_text(result, encoding='utf-8')


# ═══════════════════════════════════════════════════════════════════════════
# GENERATE index.html
# ═══════════════════════════════════════════════════════════════════════════

def generate_index(fn_map):
    """
    Build index.html from:
      - Chrome: processed introduction.html (header + sidebar + footer)
      - Content: sections.json 'index' HTML (converted hash links)
    """
    # Use processed introduction.html as chrome template
    intro = BeautifulSoup(
        (OUT / 'introduction.html').read_text(encoding='utf-8'), 'html.parser'
    )

    # Get index content from sections.json
    with open(REPO / 'sections.json') as f:
        idx_html = json.load(f)['sections']['index']['html']

    # Replace article content
    article = intro.find('article')
    if article:
        while article.contents:
            article.contents[0].extract()
        article.attrs.pop('id', None)
        idx_soup = BeautifulSoup(f'<div id="_idx">{idx_html}</div>', 'html.parser')
        idx_div  = idx_soup.find(id='_idx')
        while idx_div.contents:
            article.append(idx_div.contents[0].extract())

    # Convert hash links
    convert_hash_links(intro)

    # Update <title> and breadcrumb
    title = intro.find('title')
    if title:
        title.string = "Bennett's New Latin Grammar — Contents"
    bc = intro.find(class_='breadcrumb')
    if bc:
        bc.string = ''

    # Update prev/next nav
    prev_a = intro.find('a', class_='page-nav__prev')
    if prev_a:
        span = intro.new_tag('span')
        span['class'] = 'page-nav__disabled'
        span.string   = '← Previous'
        prev_a.replace_with(span)

    next_a = intro.find('a', class_='page-nav__next')
    if next_a:
        next_a['href']  = 'introduction.html'
        next_a['title'] = 'Introduction'

    # Remove any leftover popovers from the introduction template
    for div in list(intro.find_all('div', class_='fn-popover')):
        div.decompose()

    # Apply standard content transforms
    remove_hr_br(intro)
    process_anchors(intro, fn_map)
    cleanup_empty_paragraphs(intro)
    convert_blockquotes(intro)
    group_rule_lists(intro)

    result = str(intro)
    result = fix_sc_spans(result)
    (OUT / 'index.html').write_text(result, encoding='utf-8')
    print('  Generated index.html')


# ═══════════════════════════════════════════════════════════════════════════
# CSS
# ═══════════════════════════════════════════════════════════════════════════

OLD_BQ = """\
/* ── Blockquotes / indented Latin examples — Blue Card ────── */

/* b1 = annotation prose ("a. Yet instead of…") — indent only, no card */
blockquote.b1 {
  background: none;
  border: none;
  padding: 0 0 0 1.5em;
  margin: 0.5em 0;
}

/* b2, b3 = actual example lists — Blue Card */
blockquote.b2,
blockquote.b3 {
  background: #f4f7fe;
  border: 1px solid #c8d4f0;
  /* border-left: 3px solid #1f40c4; */
  padding: 0.15em 1em;
  margin: 0.6em 0 0.6em 5rem;
  line-height: 1.35rem;
  font-size: .9rem;
}

blockquote.b1 p,
blockquote.b2 p,
blockquote.b3 p {
  margin: 0.2em 0;
  text-align: left;
  hyphens: none;
}

blockquote.b2 p + p {margin-top: .5rem;}
blockquote.b3 p + p {margin-top: .5rem;}

/* Latin phrases */
blockquote b { color: #0d1a52; }

/* English translations */
blockquote i { color: #3a4060; font-style: italic; }

blockquote.small {
  font-size: 0.88rem;
}"""

NEW_BQ = """\
/* ── Rule sub-annotations and Latin example blocks ────────── */

/* rule-sub = annotation prose (a) …) — indent only, no card */
div.rule-sub {
  background: none;
  border: none;
  padding: 0 0 0 1.5em;
  margin: 0.5em 0;
}

/* rule-sub--deep = third-level annotation (αα, ββ…) — deeper indent */
div.rule-sub.rule-sub--deep {
  padding-left: 3em;
}

/* example = Latin example block — Blue Card */
div.example {
  background: #f4f7fe;
  border: 1px solid #c8d4f0;
  padding: 0.15em 1em;
  margin: 0.6em 0 0.6em 5rem;
  line-height: 1.35rem;
  font-size: .9rem;
}

div.example.example--sm { font-size: 0.88rem; }

div.rule-sub p,
div.example p {
  margin: 0.2em 0;
  text-align: left;
  hyphens: none;
}

div.example p + p { margin-top: .5rem; }

/* Latin phrases */
div.example b { color: #0d1a52; }

/* English translations */
div.example i { color: #3a4060; font-style: italic; }

/* ── Sub-lettered rule lists ─────────────────────────────── */

ol.rule-list {
  list-style: none;
  padding: 0;
  margin: 0.5em 0;
  counter-reset: rule-alpha;
}

ol.rule-list > li {
  counter-increment: rule-alpha;
  position: relative;
  padding-left: 2em;
  margin: 0.5em 0;
}

ol.rule-list > li::before {
  content: counter(rule-alpha, lower-alpha) ") ";
  position: absolute;
  left: 0;
  color: #555;
  font-style: italic;
}"""

OLD_FN = """\
/* ── Footnote popovers ───────────────────────────────────── */

/* The inline superscript reference */
a.fn-ref {
  text-decoration: none;
  color: #1f40c4;
  font-variant-position: super;
  cursor: pointer;
}

/* The popover box */
.fn-popover {
  position: fixed;
  z-index: 200;
  background: #fff;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.14);
  padding: 0.75rem 1rem;
  max-width: 340px;
  font-size: 0.85rem;
  line-height: 1.5;
  color: #1a1a1a;
  pointer-events: none;
  opacity: 0;
  transform: translateY(4px);
  transition: opacity 0.15s, transform 0.15s;
}

.fn-popover.fn-popover--visible {
  opacity: 1;
  transform: translateY(0);
  pointer-events: auto;
}

.fn-popover p {
  margin: 0;
  text-align: left;
  hyphens: none;
}"""

NEW_FN = """\
/* ── Footnote references (native Popover API) ───────────── */

button.fn-ref {
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  color: #1f40c4;
  font-size: 0.8em;
  vertical-align: super;
  font-family: inherit;
  line-height: 1;
  text-decoration: underline;
  text-underline-offset: 2px;
}

button.fn-ref:hover { color: #0d2a8a; }

/* Popover box — Popover API positions this; margin:auto centres it */
.fn-popover {
  position: fixed;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  box-shadow: 0 4px 16px rgba(0,0,0,.14);
  padding: 0.75rem 1rem;
  max-width: 340px;
  font-size: 0.85rem;
  line-height: 1.5;
  background: #fff;
  color: #1a1a1a;
  margin: auto;
}

.fn-popover p {
  margin: 0.25em 0;
  text-align: left;
  hyphens: none;
}

.fn-popover__link {
  font-size: 0.8em;
  margin-top: 0.5em;
  border-top: 1px solid #eee;
  padding-top: 0.4em;
}"""

CSS_ADDITIONS = """
/* ── Table centering utility ─────────────────────────────── */

.tc { text-align: center; }

/* ── Centered section title headings ─────────────────────── */

h2.section-title {
  text-align: center;
  margin-top: 1.5em;
  font-size: 1.2rem;
}

/* ── Sidebar home active state ───────────────────────────── */

.sidebar-home.active {
  color: #1f40c4;
  font-weight: bold;
  background: #eef1fb;
}

/* ── Section number left-margin markers ──────────────────── */

.sect-num {
  position: relative;
  display: inline-block;
  box-sizing: border-box;
  left: -2.5rem;
  width: 2.5rem;
  margin-right: -2.5rem;
  padding-right: 0.55rem;
  text-align: right;
  font-size: 0.72rem;
  color: #aaa;
  font-weight: normal;
  font-style: normal;
  font-family: inherit;
  vertical-align: baseline;
  user-select: none;
}
"""


def build_css():
    css = CSS_IN.read_text(encoding='utf-8')

    if OLD_BQ in css:
        css = css.replace(OLD_BQ, NEW_BQ)
    else:
        print('  WARNING: blockquote CSS block not matched exactly — appending')
        css += '\n\n' + NEW_BQ

    if OLD_FN in css:
        css = css.replace(OLD_FN, NEW_FN)
    else:
        print('  WARNING: footnote CSS block not matched exactly — appending')
        css += '\n\n' + NEW_FN

    css += CSS_ADDITIONS
    return css


# ═══════════════════════════════════════════════════════════════════════════
# JAVASCRIPT
# ═══════════════════════════════════════════════════════════════════════════

NEW_JS = """\
/* bennett.js — Bennett's New Latin Grammar — pjax multi-page navigation */

(function () {
  'use strict';

  // ── Sidebar toggle (mobile) ─────────────────────────────────────────────

  const sidebar = document.getElementById('sidebar');
  const toggle  = document.querySelector('.sidebar-toggle');

  if (toggle && sidebar) {
    toggle.addEventListener('click', () => {
      const open = sidebar.classList.toggle('sidebar--open');
      toggle.setAttribute('aria-expanded', String(open));
    });

    document.addEventListener('click', e => {
      if (
        sidebar.classList.contains('sidebar--open') &&
        !sidebar.contains(e.target) &&
        !toggle.contains(e.target)
      ) {
        sidebar.classList.remove('sidebar--open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  // ── Named page map ──────────────────────────────────────────────────────

  const NAMED = {
    index:          'index.html',
    intro:          'introduction.html',
    introduction:   'introduction.html',
    appendix:       'appendix.html',
    'syntax-index': 'appendix.html',
    'verb-index':   'appendix.html',
    'general-index':'appendix.html',
    footnotes:      'appendix.html',
  };

  // ── Active sidebar link ─────────────────────────────────────────────────

  function setActive(filename) {
    if (!sidebar) return;
    sidebar.querySelectorAll('a.active').forEach(a => a.classList.remove('active'));

    const base = (filename || '').split('#')[0];

    // Special case: index page → highlight sidebar-home
    if (base === 'index.html' || base === '') {
      const home = sidebar.querySelector('.sidebar-home');
      if (home) home.classList.add('active');
      return;
    }

    const link = sidebar.querySelector(`a[href="${base}"]`);
    if (!link) return;
    link.classList.add('active');
    const details = link.closest('details');
    if (details && !details.open) details.open = true;
    setTimeout(() => link.scrollIntoView({ block: 'nearest', behavior: 'instant' }), 50);
  }

  // ── Pjax navigation ─────────────────────────────────────────────────────

  let inflight = null;

  async function navigate(url, push) {
    if (inflight) { inflight.abort(); }
    inflight = new AbortController();

    const wrap = document.querySelector('.content-wrap');
    if (!wrap) return;

    try {
      const res = await fetch(url, { signal: inflight.signal });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const text = await res.text();

      const doc     = new DOMParser().parseFromString(text, 'text/html');
      const newWrap = doc.querySelector('.content-wrap');
      if (!newWrap) return;

      wrap.innerHTML     = newWrap.innerHTML;
      document.title     = doc.title;

      const newBc = doc.querySelector('.breadcrumb');
      const curBc = document.querySelector('.breadcrumb');
      if (curBc && newBc) curBc.textContent = newBc.textContent;

      if (push !== false) history.pushState({ url }, '', url);

      const parsed = new URL(url, location.href);
      if (parsed.hash) {
        requestAnimationFrame(() => {
          const id     = parsed.hash.slice(1);
          const target = document.getElementById(id) ||
                         document.querySelector('[name="' + id + '"]');
          if (target) target.scrollIntoView({ block: 'start', behavior: 'instant' });
        });
      } else {
        window.scrollTo(0, 0);
      }

      setActive(parsed.pathname.split('/').pop());

    } catch (e) {
      if (e.name !== 'AbortError') location.href = url;
    }
  }

  // ── Click intercept ─────────────────────────────────────────────────────

  document.addEventListener('click', e => {
    const a = e.target.closest('a');
    if (!a) return;
    const href = a.getAttribute('href');
    if (!href) return;

    const url = new URL(href, location.href);
    if (url.origin !== location.origin)       return;
    if (!url.pathname.endsWith('.html'))       return;
    if (a.target === '_blank')                 return;
    if (a.classList.contains('fn-popover__link')) return;

    e.preventDefault();
    navigate(url.href);
  });

  // ── Back / forward ──────────────────────────────────────────────────────

  window.addEventListener('popstate', () => {
    navigate(location.href, false);
  });

  // ── Jump input ──────────────────────────────────────────────────────────

  const jump = document.getElementById('sidebar-jump-input');
  if (jump) {
    function doJump(val) {
      const v = val.trim().replace(/^#/, '');
      if (!v) return;
      jump.value = '';

      const lower = v.toLowerCase();
      if (NAMED[lower]) { navigate(NAMED[lower]); return; }

      const m = v.match(/^§?\\s*([0-9]+[A-Za-z]?)$/);
      if (m) { navigate(m[1] + '.html'); return; }
    }

    jump.addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); doJump(jump.value); }
    });
    jump.addEventListener('change', () => doJump(jump.value));
  }

  // ── Initial state ────────────────────────────────────────────────────────

  history.replaceState({ url: location.href }, '', location.href);
  setActive((location.pathname.split('/').pop()) || 'index.html');

})();
"""


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print(f'Bennett Web Builder')
    print(f'  Source : {SRC}')
    print(f'  Output : {OUT}')
    print()

    # Setup
    OUT.mkdir(parents=True, exist_ok=True)

    # Copy fonts
    if FONTS.exists():
        out_fonts = OUT / 'fonts'
        if out_fonts.exists():
            shutil.rmtree(out_fonts)
        shutil.copytree(FONTS, out_fonts)
        print(f'  Copied fonts/  ({len(list(out_fonts.glob("*")))} files)')

    # Build footnote map
    fn_map = build_footnote_map()
    print(f'  Footnote map  : {len(fn_map)} notes')

    # Write CSS
    css = build_css()
    (OUT / 'bennett.css').write_text(css, encoding='utf-8')
    print(f'  Wrote bennett.css')

    # Write JS
    (OUT / 'bennett.js').write_text(NEW_JS, encoding='utf-8')
    print(f'  Wrote bennett.js')

    # Process all loosies HTML files
    html_files = sorted(SRC.glob('*.html'))
    print(f'\n  Processing {len(html_files)} HTML files...')

    for i, src_path in enumerate(html_files, 1):
        fname = src_path.name
        out_path = OUT / fname
        is_appendix = (fname == 'appendix.html')
        process_file(src_path, out_path, fn_map, is_appendix=is_appendix)
        if i % 50 == 0:
            print(f'    {i}/{len(html_files)}...')

    print(f'    {len(html_files)}/{len(html_files)} done')

    # Generate index.html (uses processed introduction.html as template)
    generate_index(fn_map)

    total_html = len(list(OUT.glob('*.html')))
    print(f'\n✓ Done  →  {OUT}')
    print(f'  HTML files : {total_html}')
    print(f'\nTo serve:')
    print(f'  cd {OUT} && python3 -m http.server 8766')


if __name__ == '__main__':
    main()
