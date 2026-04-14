/* bennett.js — Bennett's New Latin Grammar — hash SPA router */

(async function () {
  'use strict';

  // ── Load data ──────────────────────────────────────────────────────────────

  let data;
  try {
    data = await fetch('sections.json').then(r => r.json());
  } catch (e) {
    document.getElementById('main-content').innerHTML =
      '<p style="color:red;padding:2rem">Failed to load sections.json.</p>';
    return;
  }

  const { order, sections } = data;
  const routeAliases = {
    appendix: 'verb-index',
    ind1: 'syntax-index',
    ind2: 'syntax-index',
    ind3: 'verb-index',
    ind4: 'general-index'
  };

  function resolveId(rawId) {
    const trimmed = (rawId || '').trim().replace(/^#/, '');
    if (!trimmed) return 'index';

    const lower = trimmed.toLowerCase();
    if (routeAliases[lower]) return routeAliases[lower];
    if (sections[trimmed]) return trimmed;
    if (sections[lower]) return lower;

    const upper = trimmed.toUpperCase();
    if (sections[upper]) return upper;
    return trimmed;
  }

  function scrollToInlineAnchor(rawId) {
    const anchorId = (rawId || '').trim().replace(/^#/, '');
    if (!anchorId || anchorId === resolveId(anchorId)) return;

    const anchor = mainEl.querySelector(`[name="${anchorId}"], [id="${anchorId}"]`);
    if (anchor) anchor.scrollIntoView({ block: 'start', behavior: 'auto' });
  }

  function scrollPageToTop() {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  }

  function scrollSidebarLinkIntoView(link) {
    if (!sidebar || !link) return;

    const sidebarRect = sidebar.getBoundingClientRect();
    const linkRect = link.getBoundingClientRect();
    const offsetTop = linkRect.top - sidebarRect.top;
    const targetTop =
      sidebar.scrollTop + offsetTop - (sidebar.clientHeight / 2) + (linkRect.height / 2);

    sidebar.scrollTo({
      top: Math.max(0, targetTop),
      behavior: 'auto'
    });
  }

  function closeOtherSidebarSections(currentDetails) {
    if (!sidebar || !currentDetails) return;

    sidebar.querySelectorAll('details[open]').forEach(details => {
      if (details !== currentDetails) details.open = false;
    });
  }

  // ── Build footnote map from footnotes page (parsed once) ───────────────────

  const fnMap = {};
  if (sections['footnotes']) {
    const parser = new DOMParser();
    const doc    = parser.parseFromString(
      '<div>' + sections['footnotes'].html + '</div>', 'text/html'
    );
    doc.querySelectorAll('a[name^="Nt_"], [id^="Nt_"]').forEach(el => {
      const p    = el.closest('p') || el.parentElement;
      const text = p ? p.textContent.trim().replace(/^\[\d+\]\s*/, '') : '';
      const key = el.getAttribute('name') || el.id;
      if (key) fnMap[key] = text;
    });
  }

  // ── DOM references ─────────────────────────────────────────────────────────

  const mainEl     = document.getElementById('main-content');
  const pageNav    = document.getElementById('page-nav');
  const breadcrumb = document.getElementById('breadcrumb');
  const sidebar    = document.getElementById('sidebar');
  const toggle     = document.querySelector('.sidebar-toggle');
  const jumpInput  = document.getElementById('sidebar-jump-input');

  // ── Footnote popover ───────────────────────────────────────────────────────

  const popover = document.createElement('div');
  popover.className = 'fn-popover';
  popover.setAttribute('role', 'tooltip');
  document.body.appendChild(popover);
  let hideTimer = null;

  function positionPopover(trigger) {
    const rect = trigger.getBoundingClientRect();
    const vw   = window.innerWidth;
    const pw   = Math.min(340, vw - 32);
    let left   = rect.left;
    let top    = rect.bottom + 8;

    if (left + pw > vw - 16) left = Math.max(16, vw - pw - 16);
    if (top + 120 > window.innerHeight) {
      top = rect.top - 8;
      popover.style.transform = 'translateY(-100%)';
    } else {
      popover.style.transform = '';
    }

    popover.style.left  = left + 'px';
    popover.style.top   = top  + 'px';
    popover.style.width = pw   + 'px';
  }

  function showPopover(trigger, text) {
    clearTimeout(hideTimer);
    if (!text) return;
    popover.innerHTML = '';
    const p = document.createElement('p');
    p.textContent = text;
    popover.appendChild(p);
    positionPopover(trigger);
    popover.classList.add('fn-popover--visible');
  }

  function hidePopover() {
    hideTimer = setTimeout(() => popover.classList.remove('fn-popover--visible'), 120);
  }

  popover.addEventListener('mouseenter', () => clearTimeout(hideTimer));
  popover.addEventListener('mouseleave', hidePopover);

  // ── Per-render enhancements ────────────────────────────────────────────────

  function initEnhancements() {
    // Footnote popovers
    mainEl.querySelectorAll('a[data-footnote]').forEach(ref => {
      ref.classList.add('fn-ref');
      const text = fnMap[ref.dataset.footnote] || '';
      if (!text) return;

      ref.addEventListener('mouseenter', () => showPopover(ref, text));
      ref.addEventListener('mouseleave', hidePopover);
      ref.addEventListener('focus',      () => showPopover(ref, text));
      ref.addEventListener('blur',       hidePopover);
      ref.addEventListener('click', e => {
        if (popover.classList.contains('fn-popover--visible') && popover.textContent.trim())
          e.preventDefault();
      });
    });
  }

  // ── Sidebar active state ───────────────────────────────────────────────────

  function setActive(id) {
    sidebar.querySelectorAll('a.active').forEach(a => a.classList.remove('active'));
    const link = sidebar.querySelector(`a[href="#${id}"]`);
    if (!link) return;
    link.classList.add('active');
    const details = link.closest('details');
    if (details) {
      closeOtherSidebarSections(details);
      details.open = true;
    }
    requestAnimationFrame(() => scrollSidebarLinkIntoView(link));
  }

  function navigateToJump(value) {
    const raw = value.trim();
    if (!raw) return;

    const namedMatch = raw.match(
      /^#?\s*(index|intro|syntax-index|verb-index|general-index|footnotes|appendix|ind1|ind2|ind3|ind4)\b/i
    );
    const sectionMatch = raw.match(/^#?\s*§?\s*([0-9]+[A-Za-z]?)\b/i);
    const target = resolveId(namedMatch ? namedMatch[1] : sectionMatch ? sectionMatch[1] : '');
    if (!sections[target]) return;

    if (jumpInput) jumpInput.value = '';
    location.hash = '#' + target;
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  function render(id) {
    const targetId = resolveId(id);
    const section = sections[targetId];
    if (!section) {
      mainEl.innerHTML = `<p style="padding:2rem">Section not found: ${id}</p>`;
      return;
    }

    mainEl.innerHTML = section.html;
    document.title   = section.title;
    if (breadcrumb) breadcrumb.textContent = section.breadcrumb || '';

    const idx    = order.indexOf(targetId);
    const prevId = idx > 0 ? order[idx - 1] : null;
    const nextId = idx < order.length - 1 ? order[idx + 1] : null;

    pageNav.innerHTML =
      (prevId
        ? `<a href="#${prevId}" class="page-nav__prev">&#8592; Previous</a>`
        : `<span class="page-nav__prev page-nav__disabled">&#8592; Previous</span>`)
      + (nextId
        ? `<a href="#${nextId}" class="page-nav__next">Next &#8594;</a>`
        : `<span class="page-nav__next page-nav__disabled">Next &#8594;</span>`);

    setActive(targetId);
    initEnhancements();
    requestAnimationFrame(() => {
      scrollPageToTop();
      scrollToInlineAnchor(id);
    });
  }

  // ── Hash routing ───────────────────────────────────────────────────────────

  window.addEventListener('hashchange', () => {
    render(location.hash.replace(/^#/, ''));
  });

  render(location.hash.replace(/^#/, ''));

  if (jumpInput) {
    jumpInput.addEventListener('keydown', e => {
      if (e.key !== 'Enter') return;
      e.preventDefault();
      navigateToJump(jumpInput.value);
    });

    jumpInput.addEventListener('change', () => navigateToJump(jumpInput.value));
  }

  // ── Mobile sidebar toggle ──────────────────────────────────────────────────

  if (toggle && sidebar) {
    toggle.addEventListener('click', () => {
      const isOpen = sidebar.classList.toggle('sidebar--open');
      toggle.setAttribute('aria-expanded', String(isOpen));
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

  if (sidebar) {
    sidebar.querySelectorAll('details').forEach(details => {
      details.addEventListener('toggle', () => {
        if (details.open) closeOtherSidebarSections(details);
      });
    });
  }

})();
