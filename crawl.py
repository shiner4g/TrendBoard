#!/usr/bin/env python3
# TrendBoard crawler + page builder — run by .github/workflows/update.yml
# Crawls 5 Korean community boards, keeps the top-10-by-view-count posts from each
# (falling back to the previous index.html's data for any board that fails this run),
# and writes the result into index.html for GitHub Pages to serve.
#
# Candidate pool per board = latest PAGES_PER_BOARD pages of the "recent posts" list
# (not just page 1), so posts that are a bit older but still highly viewed aren't
# missed just because they scrolled off the very first page. None of these 5 sites
# offer a native "sort by view count" option (Clien, for example, only offers
# 등록일순/댓글등록순/공감순/댓글순), so we still have to pull the recency-ordered
# list and re-rank it ourselves — pulling more pages just widens that window.

import urllib.request
import re
import html
import json
import datetime
import os

TOP_N = 10
PAGES_PER_BOARD = 3
OUT_PATH = "index.html"


def fetch(url, encoding):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
    return raw.decode(encoding, errors="replace")


def decode_entities(s):
    return html.unescape(s)


def strip_tags(s):
    return decode_entities(re.sub(r"<[^>]+>", "", s)).strip()


def parse_clien(h):
    posts = []
    parts = h.split('<div class="list_item')
    for p in parts[1:]:
        if re.match(r"^\s*notice", p):
            continue
        m_count = re.search(r'data-comment-count="?(\d+)"?', p)
        if not m_count:
            continue
        m_href = re.search(r'href="(/service/board/park/\d+[^"]*)"', p)
        if not m_href:
            continue
        m_title = re.search(r'title="([^"]+)"', p)
        if not m_title:
            continue
        views = 0
        mv = re.search(r'class="hit">(\d+)</span>', p)
        if mv:
            views = int(mv.group(1))
        posts.append(
            {
                "title": decode_entities(m_title.group(1)),
                "url": "https://www.clien.net" + decode_entities(m_href.group(1)),
                "comments": int(m_count.group(1)),
                "views": views,
            }
        )
    return posts


def parse_mlbpark(h):
    posts = []
    parts = h.split("<div class='tit'>")
    for p in parts[1:]:
        m = re.match(r"^<a href='([^']+)' alt='[^']*' class='txt'>([^<]*)</a>", p)
        if not m:
            continue
        comments = 0
        mc = re.search(r"class='replycnt'><span class='replycnt'>\[(\d+)\]", p)
        if mc:
            comments = int(mc.group(1))
        views = 0
        mv = re.search(r"class='viewV'>(\d+)</span>", p)
        if mv:
            views = int(mv.group(1))
        posts.append(
            {
                "title": decode_entities(m.group(2)).strip(),
                "url": decode_entities(m.group(1)),
                "comments": comments,
                "views": views,
            }
        )
    return posts


def parse_82cook(h):
    posts = []
    parts = h.split('<td class="title">')
    for p in parts[1:]:
        m = re.match(r'^<a\s+href="([^"]+)"[^>]*>([\s\S]*?)</a>\s*(?:<em>(\d+)</em>)?', p)
        if not m:
            continue
        views = 0
        mv = re.search(r'<td class="numbers">(\d+)</td>\s*</tr>', p)
        if mv:
            views = int(mv.group(1))
        posts.append(
            {
                "title": strip_tags(m.group(2)),
                "url": "https://www.82cook.com/entiz/" + decode_entities(m.group(1)),
                "comments": int(m.group(3)) if m.group(3) else 0,
                "views": views,
            }
        )
    return posts


def parse_ppomppu(h):
    posts = []
    parts = h.split('<tr align="center" class="baseList')
    for p in parts[1:]:
        m = re.search(r"<a class=['\"]baseList-title['\"]\s+href=\"([^\"]+)\"[^>]*>([\s\S]*?)</a>", p)
        if not m:
            continue
        comments = 0
        mc = re.search(r'baseList-c"[^>]*>(\d+)<', p)
        if mc:
            comments = int(mc.group(1))
        views = 0
        mv = re.search(r'baseList-views"[^>]*>(\d+)</td>', p)
        if mv:
            views = int(mv.group(1))
        posts.append(
            {
                "title": strip_tags(m.group(2)),
                "url": "https://www.ppomppu.co.kr/zboard/" + decode_entities(m.group(1)),
                "comments": comments,
                "views": views,
            }
        )
    return posts


def parse_todayhumor(h):
    posts = []
    parts = h.split('<td class="subject">')
    for p in parts[1:]:
        m = re.match(
            r"^<a\s+href=\"([^\"]+)\"[^>]*>([^<]*)</a>\s*(?:<span class=['\"]list_memo_count_span['\"]>\s*\[(\d+)\]</span>)?",
            p,
        )
        if not m:
            continue
        views = 0
        mv = re.search(r'class="hits">(\d+)</td>', p)
        if mv:
            views = int(mv.group(1))
        posts.append(
            {
                "title": decode_entities(m.group(2).strip()),
                "url": "https://www.todayhumor.co.kr" + decode_entities(m.group(1)),
                "comments": int(m.group(3)) if m.group(3) else 0,
                "views": views,
            }
        )
    return posts


def parse_natepann(h):
    posts = []
    parts = h.split('<h2><a href="')
    for p in parts[1:]:
        m = re.match(r'^([^"]+)"[^>]*title="([^"]*)"[^>]*>([^<]*)</a></h2>', p)
        if not m:
            continue
        views = 0
        mv = re.search(r'class="count">조회\s*([\d,]+)</span>', p)
        if mv:
            views = int(mv.group(1).replace(",", ""))
        posts.append(
            {
                "title": decode_entities(m.group(3).strip()),
                "url": "https://pann.nate.com" + decode_entities(m.group(1)),
                "comments": 0,
                "views": views,
            }
        )
    return posts


def parse_bobaedream(h):
    posts = []
    # split on bare "<tr" so each chunk starts with that row's own opening tag,
    # letting us check its class (to skip the pinned "베스트글" widget rows,
    # which reuse the same <a class="bsubject"> markup but sit in <tr class="best">)
    rows = h.split("<tr")
    for row in rows[1:]:
        tag_end = row.find(">")
        open_tag = row[:tag_end] if tag_end != -1 else row
        if 'class="best"' in open_tag:
            continue
        m = re.search(r'<a class="bsubject"[^>]*href="([^"]+)"[^>]*>([^<]*)</a>', row)
        if not m:
            continue
        views = 0
        mv = re.search(r'<td class="count"[^>]*>\s*([\d,]+)\s*</td>', row)
        if mv:
            views = int(mv.group(1).replace(",", ""))
        posts.append(
            {
                # use the anchor's visible text, not its `title` attribute - some
                # bsubject anchors carry an unrelated accessibility hint there
                # (literally the text "새 창", meaning "opens in new window")
                "title": decode_entities(m.group(2).strip()),
                "url": "https://www.bobaedream.co.kr" + decode_entities(m.group(1)),
                "comments": 0,
                "views": views,
            }
        )
    return posts


def parse_ruliweb(h):
    posts = []
    # split on "<tr class=\"table_body" so each chunk starts right after that,
    # letting us skip pinned notice rows (class="table_body notice inside")
    rows = h.split('<tr class="table_body')
    for row in rows[1:]:
        tag_end = row.find(">")
        open_tag = row[:tag_end] if tag_end != -1 else row
        if "notice" in open_tag:
            continue
        m = re.search(r'<a class="subject_link deco" href="([^"]+)"[^>]*>([\s\S]*?)</a>', row)
        if not m:
            continue
        if "/community/board/300143/" not in m.group(1):
            continue
        views = 0
        mv = re.search(r'<td class="hit">\s*([\d,]+)\s*</td>', row)
        if mv:
            views = int(mv.group(1).replace(",", ""))
        posts.append(
            {
                "title": strip_tags(m.group(2)),
                "url": decode_entities(m.group(1)),
                "comments": 0,
                "views": views,
            }
        )
    return posts


def parse_dcbest(h):
    posts = []
    # split on "<tr class=\"ub-content" so each chunk starts right after that,
    # letting us skip the pinned notice/survey row (data-type="icon_notice",
    # missing the "us-post" class real posts have)
    rows = h.split('<tr class="ub-content')
    for row in rows[1:]:
        tag_end = row.find(">")
        open_tag = row[:tag_end] if tag_end != -1 else row
        if "us-post" not in open_tag:
            continue
        # note: raw source sometimes has "<a  href=" with a doubled space - \s+
        # (not a literal single space) is required here
        m = re.search(r'<td class="gall_tit ub-word">\s*<a\s+href="([^"]+)"[^>]*>([\s\S]*?)</a>', row)
        if not m:
            continue
        views = 0
        mv = re.search(r'<td class="gall_count">\s*([\d,]+)\s*</td>', row)
        if mv:
            views = int(mv.group(1).replace(",", ""))
        posts.append(
            {
                "title": strip_tags(m.group(2)),
                "url": "https://gall.dcinside.com" + decode_entities(m.group(1)),
                "comments": 0,
                "views": views,
            }
        )
    return posts


# page_url(n) builds the URL for the n-th page (n = 1, 2, 3, ...) of each board's
# recent-posts list. None of these sites support "sort by views" natively, so this is
# how we widen the candidate pool instead (see PAGES_PER_BOARD above). (네이트판은
# 예외로, 사이트 자체가 이미 실시간 조회수 랭킹을 제공해서 1페이지만 사용합니다.)
COMMUNITIES = [
    {
        "name": "클리앙", "board": "모두의공원", "encoding": "utf-8", "parse": parse_clien,
        "page_url": lambda n: f"https://www.clien.net/service/board/park?&od=T31&category=0&po={n - 1}",
    },
    {
        "name": "MLB파크", "board": "BULLPEN", "encoding": "utf-8", "parse": parse_mlbpark,
        "page_url": lambda n: f"https://mlbpark.donga.com/mp/b.php?m=list&b=bullpen&page={n}",
    },
    {
        "name": "뽐뿌", "board": "자유게시판", "encoding": "euc-kr", "parse": parse_ppomppu,
        "page_url": lambda n: f"https://www.ppomppu.co.kr/zboard/zboard.php?id=freeboard&page={n}",
        "no_cache": True,  # 이 크롤이 실패해도 이전 회차 캐시로 대체하지 않음
    },
    {
        "name": "오늘의유머", "board": "베스트30", "encoding": "utf-8", "parse": parse_todayhumor,
        "page_url": lambda n: "https://www.todayhumor.co.kr/board/list.php?kind=todaybest",
        "pages": 1,  # 오늘 하루 기준 베스트 30개만 보여주는 페이지라 페이지네이션이 없음
        "no_cache": True,  # 이 크롤이 실패해도 이전 회차 캐시로 대체하지 않음
    },
    {
        "name": "82cook", "board": "자유게시판", "encoding": "utf-8", "parse": parse_82cook,
        "page_url": lambda n: f"https://www.82cook.com/entiz/enti.php?bn=15&page={n}",
    },
    {
        "name": "네이트판", "board": "톡커들의 선택", "encoding": "utf-8", "parse": parse_natepann,
        "page_url": lambda n: "https://pann.nate.com/talk/ranking",
        "pages": 1,  # 사이트가 이미 실시간 조회수 랭킹을 제공해서 페이지네이션 불필요
    },
    {
        "name": "보배드림", "board": "자유게시판", "encoding": "utf-8", "parse": parse_bobaedream,
        "page_url": lambda n: f"https://www.bobaedream.co.kr/board/bulletin/list.php?code=freeb&page={n}",
    },
    {
        "name": "루리웹", "board": "유머 게시판", "encoding": "utf-8", "parse": parse_ruliweb,
        "page_url": lambda n: f"https://bbs.ruliweb.com/community/board/300143?page={n}",
    },
    # 인스티즈는 뺐습니다 - 이 사이트는 서버/클라우드 IP 대역을 광범위하게 차단해서
    # (이 저장소를 실행하는 샌드박스에서 직접 테스트해도 403 Forbidden), GitHub
    # Actions에서도 마찬가지로 막힐 수밖에 없습니다.
    {
        "name": "디시인사이드", "board": "실시간베스트", "encoding": "utf-8", "parse": parse_dcbest,
        "page_url": lambda n: f"https://gall.dcinside.com/board/lists/?id=dcbest&page={n}",
    },
]

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TrendBoard</title>
<style>
  :root { --bg: #f4f5f7; --card-bg: #ffffff; --border: #e3e5e8; --text: #222; --text-sub: #888; --accent: #3b82f6; --badge-bg: #eef2ff; --post-size: 16px; }
  :root[data-theme="dark"] { --bg: #16181d; --card-bg: #1f2228; --border: #2c2f36; --text: #e6e6e6; --text-sub: #8a8f98; --accent: #6ea8fe; --badge-bg: #1d2740; }
  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg: #16181d; --card-bg: #1f2228; --border: #2c2f36; --text: #e6e6e6; --text-sub: #8a8f98; --accent: #6ea8fe; --badge-bg: #1d2740; } }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 24px 16px 60px; background: var(--bg); color: var(--text); font-family: "Malgun Gothic", "Apple SD Gothic Neo", "Segoe UI", sans-serif; }
  header { max-width: 1620px; margin: 0 auto 24px; }
  .header-top { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  header h1 { margin: 0; font-size: 20px; letter-spacing: -0.5px; }
  .header-icons { display: flex; gap: 8px; flex: 0 0 auto; }
  .icon-btn { border: 1px solid var(--border); background: var(--card-bg); color: var(--text); border-radius: 6px; width: 34px; height: 34px; padding: 0; display: inline-flex; align-items: center; justify-content: center; font-size: 18px; line-height: 1; cursor: pointer; }
  .icon-btn:hover { border-color: var(--accent); color: var(--accent); }
  .updated { font-size: 15px; color: var(--text-sub); text-align: center; margin-top: 8px; }
  .grid { max-width: 1620px; margin: 24px auto 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(min(520px, 100%), 1fr)); gap: 18px; }
  .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; display: flex; flex-direction: column; transition: opacity 0.15s, border-color 0.15s; }
  .card.dragging { opacity: 0.4; }
  .card.drag-over { border-color: var(--accent); }
  .card-header { padding: 14px 16px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 8px; background: color-mix(in srgb, var(--card-bg) 92%, var(--text)); cursor: pointer; }
  .card-header:hover { background: color-mix(in srgb, var(--card-bg) 85%, var(--text)); }
  .card-header:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  .drag-handle { flex: 0 0 auto; color: var(--text-sub); font-size: 16px; letter-spacing: -1px; user-select: none; cursor: grab; touch-action: none; }
  .drag-handle:active { cursor: grabbing; }
  .card-header .title { font-weight: 700; font-size: 18px; }
  .card-header .board { margin-left: auto; font-size: 15px; color: var(--text-sub); }
  .toggle-icon { flex: 0 0 auto; color: var(--text-sub); font-size: 14px; padding: 2px 4px; line-height: 1; }
  .card.collapsed .post-list, .card.collapsed .empty-note { display: none; }
  ol.post-list { list-style: none; margin: 0; padding: 6px 0; }
  ol.post-list li { display: flex; align-items: baseline; gap: 8px; padding: 9px 16px; border-bottom: 1px dashed var(--border); }
  ol.post-list li:last-child { border-bottom: none; }
  .post-title { flex: 1 1 auto; font-size: var(--post-size); color: var(--text); text-decoration: none; line-height: 1.4; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .post-title:hover { color: var(--accent); text-decoration: underline; }
  .post-title:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 2px; }
  .views { flex: 0 0 auto; font-size: calc(var(--post-size) - 2px); color: var(--accent); background: var(--badge-bg); border-radius: 10px; padding: 1px 7px; font-weight: 600; min-width: 20px; text-align: center; font-variant-numeric: tabular-nums; }
  .empty-note { padding: 24px 16px; color: var(--text-sub); font-size: 16px; text-align: center; }
  footer { max-width: 1620px; margin: 36px auto 0; text-align: center; }
  .controls { display: flex; justify-content: center; align-items: center; gap: 16px; flex-wrap: wrap; margin-top: 10px; }
  .controls button { border: 1px solid var(--border); background: var(--card-bg); color: var(--text); border-radius: 6px; padding: 5px 14px; font-size: 14px; cursor: pointer; }
  .controls button:hover { border-color: var(--accent); color: var(--accent); }
  .font-controls { display: inline-flex; align-items: center; gap: 6px; }
  .font-controls button { padding: 5px 12px; line-height: 1.4; }
  #fontSizeLabel { min-width: 44px; display: inline-block; text-align: center; font-size: 14px; color: var(--text-sub); font-variant-numeric: tabular-nums; }
</style>
</head>
<body>
<header>
  <div class="header-top">
    <h1>TrendBoard</h1>
    <div class="header-icons">
      <button id="collapseAll" type="button" class="icon-btn" title="모두 접기" aria-label="모두 접기">⊟</button>
      <button id="expandAll" type="button" class="icon-btn" title="모두 펼치기" aria-label="모두 펼치기">⊞</button>
    </div>
  </div>
  <div class="updated" id="updatedAt">불러오는 중...</div>
</header>
<div class="grid" id="grid"></div>
<footer>
  <div class="controls">
    <button id="resetOrder" type="button">순서 초기화</button>
    <span class="font-controls">
      <span id="fontSizeLabel">16px</span>
      <button id="fontDec" type="button" aria-label="글자 작게">가-</button>
      <button id="fontInc" type="button" aria-label="글자 크게">가+</button>
    </span>
  </div>
</footer>
<script>
  const COMMUNITY_DATA = __DATA_JSON__;
  (function () {
    const STORAGE_KEY = 'communityViewerOrder';
    const COLLAPSE_KEY = 'communityViewerCollapsed';
    const FONT_KEY = 'communityViewerFontSize';
    const FONT_MIN = 12;
    const FONT_MAX = 26;
    const FONT_DEFAULT = 16;
    const grid = document.getElementById('grid');
    const updatedEl = document.getElementById('updatedAt');
    const resetLink = document.getElementById('resetOrder');
    const fontDecBtn = document.getElementById('fontDec');
    const fontIncBtn = document.getElementById('fontInc');
    const fontSizeLabel = document.getElementById('fontSizeLabel');
    const collapseAllBtn = document.getElementById('collapseAll');
    const expandAllBtn = document.getElementById('expandAll');

    function getFontSize() {
      const raw = parseInt(localStorage.getItem(FONT_KEY), 10);
      return (!isNaN(raw) && raw >= FONT_MIN && raw <= FONT_MAX) ? raw : FONT_DEFAULT;
    }
    function setFontSize(px) {
      px = Math.max(FONT_MIN, Math.min(FONT_MAX, px));
      document.documentElement.style.setProperty('--post-size', px + 'px');
      try { localStorage.setItem(FONT_KEY, String(px)); } catch (e) {}
      fontSizeLabel.textContent = px + 'px';
      return px;
    }
    let currentFontSize = setFontSize(getFontSize());
    fontDecBtn.addEventListener('click', function () { currentFontSize = setFontSize(currentFontSize - 1); });
    fontIncBtn.addEventListener('click', function () { currentFontSize = setFontSize(currentFontSize + 1); });

    if (typeof COMMUNITY_DATA === 'undefined' || !COMMUNITY_DATA.communities) { updatedEl.textContent = '데이터가 없습니다.'; return; }
    updatedEl.textContent = '마지막 업데이트: ' + COMMUNITY_DATA.generatedAt;
    function getSavedOrder() { try { const raw = localStorage.getItem(STORAGE_KEY); const arr = raw ? JSON.parse(raw) : null; return Array.isArray(arr) ? arr : null; } catch (e) { return null; } }
    function saveOrder(names) { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(names)); } catch (e) {} }
    function applyOrder(communities, order) {
      if (!order) return communities.slice();
      const byName = {}; communities.forEach(function (c) { byName[c.name] = c; });
      const ordered = [];
      order.forEach(function (name) { if (byName[name]) { ordered.push(byName[name]); delete byName[name]; } });
      communities.forEach(function (c) { if (byName[c.name]) ordered.push(c); });
      return ordered;
    }
    function getCollapsedSet() {
      try {
        const raw = localStorage.getItem(COLLAPSE_KEY);
        const arr = raw ? JSON.parse(raw) : [];
        return new Set(Array.isArray(arr) ? arr : []);
      } catch (e) { return new Set(); }
    }
    function saveCollapsedSet(set) { try { localStorage.setItem(COLLAPSE_KEY, JSON.stringify(Array.from(set))); } catch (e) {} }
    const collapsedSet = getCollapsedSet();

    let currentOrder = applyOrder(COMMUNITY_DATA.communities, getSavedOrder());
    resetLink.addEventListener('click', function (e) { e.preventDefault(); localStorage.removeItem(STORAGE_KEY); currentOrder = COMMUNITY_DATA.communities.slice(); render(); });

    collapseAllBtn.addEventListener('click', function () {
      currentOrder.forEach(function (c) { collapsedSet.add(c.name); });
      saveCollapsedSet(collapsedSet);
      render();
    });
    expandAllBtn.addEventListener('click', function () {
      collapsedSet.clear();
      saveCollapsedSet(collapsedSet);
      render();
    });

    // ---------- drag-to-reorder (Pointer Events, not native HTML5 DnD) ----------
    // Native HTML5 drag-and-drop (draggable="true" + dragstart/dragover/drop) has
    // spotty touch support - it works in some mobile browsers (e.g. Chrome for
    // Android) but not others (e.g. Samsung Internet, which doesn't translate touch
    // gestures into HTML5 drag events at all). Pointer Events unify mouse/touch/pen
    // input and work consistently across both, so we drive the whole interaction
    // through pointerdown/pointermove/pointerup on the drag-handle instead.
    let dragSrcIndex = null;
    let dragActive = false;

    function attachDragHandle(handle, card, index) {
      handle.style.touchAction = 'none';
      handle.addEventListener('pointerdown', function (e) {
        dragSrcIndex = index;
        dragActive = true;
        card.classList.add('dragging');
        try { handle.setPointerCapture(e.pointerId); } catch (err) {}
      });
      handle.addEventListener('pointermove', function (e) {
        if (!dragActive) return;
        const el = document.elementFromPoint(e.clientX, e.clientY);
        const targetCard = el && el.closest ? el.closest('.card') : null;
        Array.from(grid.querySelectorAll('.card.drag-over')).forEach(function (c) { c.classList.remove('drag-over'); });
        if (targetCard && targetCard !== card) targetCard.classList.add('drag-over');
      });
      function endDrag(e) {
        if (!dragActive) return;
        dragActive = false;
        card.classList.remove('dragging');
        Array.from(grid.querySelectorAll('.card.drag-over')).forEach(function (c) { c.classList.remove('drag-over'); });
        const el = document.elementFromPoint(e.clientX, e.clientY);
        const targetCard = el && el.closest ? el.closest('.card') : null;
        if (targetCard && targetCard !== card) {
          const targetIndex = Array.from(grid.children).indexOf(targetCard);
          if (dragSrcIndex !== null && targetIndex !== -1 && targetIndex !== dragSrcIndex) {
            const reordered = currentOrder.slice();
            const moved = reordered.splice(dragSrcIndex, 1)[0];
            reordered.splice(targetIndex, 0, moved);
            currentOrder = reordered;
            saveOrder(currentOrder.map(function (c) { return c.name; }));
            render();
          }
        }
        dragSrcIndex = null;
      }
      handle.addEventListener('pointerup', endDrag);
      handle.addEventListener('pointercancel', endDrag);
    }

    function render() {
      grid.innerHTML = '';
      currentOrder.forEach(function (community, index) {
        const card = document.createElement('div'); card.className = 'card';
        const isCollapsed = collapsedSet.has(community.name);
        if (isCollapsed) card.classList.add('collapsed');

        const header = document.createElement('div'); header.className = 'card-header';
        header.setAttribute('role', 'button');
        header.setAttribute('tabindex', '0');
        header.setAttribute('aria-expanded', String(!isCollapsed));
        header.innerHTML = '<span class="drag-handle" aria-hidden="true">⠿</span><span class="title">' + escapeHtml(community.name) + '</span><span class="board">' + escapeHtml(community.board || '') + (community.stale ? ' · 캐시' : '') + '</span><span class="toggle-icon" aria-hidden="true">' + (isCollapsed ? '▸' : '▾') + '</span>';
        card.appendChild(header);

        attachDragHandle(header.querySelector('.drag-handle'), card, index);

        const toggleIcon = header.querySelector('.toggle-icon');
        function toggleCollapse() {
          const nowCollapsed = card.classList.toggle('collapsed');
          if (nowCollapsed) { collapsedSet.add(community.name); } else { collapsedSet.delete(community.name); }
          saveCollapsedSet(collapsedSet);
          toggleIcon.textContent = nowCollapsed ? '▸' : '▾';
          header.setAttribute('aria-expanded', String(!nowCollapsed));
        }
        header.addEventListener('click', function (e) {
          if (e.target.closest('.drag-handle')) return;
          toggleCollapse();
        });
        header.addEventListener('keydown', function (e) {
          if (e.target.closest('.drag-handle')) return;
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleCollapse(); }
        });
        if (!community.posts || community.posts.length === 0) {
          const empty = document.createElement('div'); empty.className = 'empty-note';
          empty.textContent = community.error ? ('불러오지 못했습니다 (' + community.error + ')') : '표시할 게시글이 없습니다.';
          card.appendChild(empty);
        } else {
          const list = document.createElement('ol'); list.className = 'post-list';
          community.posts.forEach(function (post, idx) {
            const li = document.createElement('li');
            li.innerHTML = '<a class="post-title" href="' + escapeAttr(post.url) + '" target="_blank" rel="noopener noreferrer" title="' + escapeAttr(post.title) + '">' + escapeHtml(post.title) + '</a><span class="views">' + (post.views != null ? post.views : 0) + '</span>';
            list.appendChild(li);
          });
          card.appendChild(list);
        }
        grid.appendChild(card);
      });
    }
    render();
    function escapeHtml(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
    function escapeAttr(s) { return escapeHtml(s).replace(/"/g, '&quot;'); }
  })();
</script>
</body>
</html>
"""


def load_prev_data():
    if not os.path.exists(OUT_PATH):
        return {}
    try:
        with open(OUT_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        m = re.search(r"const COMMUNITY_DATA = (\{.*?\});", content, re.S)
        if not m:
            return {}
        data = json.loads(m.group(1))
        return {c["name"]: c for c in data.get("communities", [])}
    except Exception:
        return {}


def main():
    prev_by_name = load_prev_data()

    result = {
        "generatedAt": (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S") + " KST",
        "communities": [],
    }

    for cfg in COMMUNITIES:
        try:
            seen_urls = set()
            posts = []
            page_errors = []
            for page_num in range(1, cfg.get("pages", PAGES_PER_BOARD) + 1):
                page_url = cfg["page_url"](page_num)
                try:
                    html_content = fetch(page_url, cfg["encoding"])
                    page_posts = cfg["parse"](html_content)
                except Exception as page_e:
                    page_errors.append(f"page {page_num}: {page_e}")
                    continue
                for post in page_posts:
                    if post["url"] not in seen_urls:
                        seen_urls.add(post["url"])
                        posts.append(post)
            if not posts:
                raise ValueError(
                    "no posts parsed from any of "
                    + f"{cfg.get('pages', PAGES_PER_BOARD)} pages - site markup may have changed"
                    + (f" ({'; '.join(page_errors)})" if page_errors else "")
                )
            posts.sort(key=lambda x: x["views"], reverse=True)
            top = posts[:TOP_N]
            result["communities"].append({"name": cfg["name"], "board": cfg["board"], "posts": top, "error": None})
            if page_errors:
                print(f"[warn] {cfg['name']} had partial page failures: {'; '.join(page_errors)}")
        except Exception as e:
            cached = None if cfg.get("no_cache") else prev_by_name.get(cfg["name"])
            if cached and cached.get("posts"):
                result["communities"].append(
                    {"name": cfg["name"], "board": cfg["board"], "posts": cached["posts"], "error": None, "stale": True}
                )
            else:
                result["communities"].append({"name": cfg["name"], "board": cfg["board"], "posts": [], "error": str(e)})
            print(f"[warn] {cfg['name']} failed: {e}")

    data_json = json.dumps(result, ensure_ascii=False)
    page = PAGE_TEMPLATE.replace("__DATA_JSON__", data_json)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(page)

    print("Wrote", OUT_PATH, "-", len(page), "bytes")


if __name__ == "__main__":
    main()
