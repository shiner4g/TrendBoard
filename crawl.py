#!/usr/bin/env python3
# TrendBoard crawler + page builder — run by .github/workflows/update.yml
# Crawls 5 Korean community boards, keeps the top-10-by-comment-count posts from each
# (falling back to the previous index.html's data for any board that fails this run),
# and writes the result into index.html for GitHub Pages to serve.

import urllib.request
import re
import html
import json
import datetime
import os

TOP_N = 10
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
        posts.append(
            {
                "title": decode_entities(m_title.group(1)),
                "url": "https://www.clien.net" + decode_entities(m_href.group(1)),
                "comments": int(m_count.group(1)),
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
        posts.append(
            {
                "title": decode_entities(m.group(2)).strip(),
                "url": decode_entities(m.group(1)),
                "comments": comments,
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
        posts.append(
            {
                "title": strip_tags(m.group(2)),
                "url": "https://www.82cook.com/entiz/" + decode_entities(m.group(1)),
                "comments": int(m.group(3)) if m.group(3) else 0,
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
        posts.append(
            {
                "title": strip_tags(m.group(2)),
                "url": "https://www.ppomppu.co.kr/zboard/" + decode_entities(m.group(1)),
                "comments": comments,
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
        posts.append(
            {
                "title": decode_entities(m.group(2).strip()),
                "url": "https://www.todayhumor.co.kr" + decode_entities(m.group(1)),
                "comments": int(m.group(3)) if m.group(3) else 0,
            }
        )
    return posts


COMMUNITIES = [
    {"name": "클리앙", "board": "모두의공원", "url": "https://www.clien.net/service/board/park", "encoding": "utf-8", "parse": parse_clien},
    {"name": "MLB파크", "board": "BULLPEN", "url": "https://mlbpark.donga.com/mp/b.php?m=list&b=bullpen", "encoding": "utf-8", "parse": parse_mlbpark},
    {"name": "뽐뿌", "board": "자유게시판", "url": "https://www.ppomppu.co.kr/zboard/zboard.php?id=freeboard", "encoding": "euc-kr", "parse": parse_ppomppu},
    {"name": "오늘의유머", "board": "베스트", "url": "https://www.todayhumor.co.kr/board/list.php?table=humorbest", "encoding": "utf-8", "parse": parse_todayhumor},
    {"name": "82cook", "board": "자유게시판", "url": "https://www.82cook.com/entiz/enti.php?bn=15", "encoding": "utf-8", "parse": parse_82cook},
]

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TrendBoard</title>
<style>
  :root { --bg: #f4f5f7; --card-bg: #ffffff; --border: #e3e5e8; --text: #222; --text-sub: #888; --accent: #3b82f6; --badge-bg: #eef2ff; }
  :root[data-theme="dark"] { --bg: #16181d; --card-bg: #1f2228; --border: #2c2f36; --text: #e6e6e6; --text-sub: #8a8f98; --accent: #6ea8fe; --badge-bg: #1d2740; }
  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg: #16181d; --card-bg: #1f2228; --border: #2c2f36; --text: #e6e6e6; --text-sub: #8a8f98; --accent: #6ea8fe; --badge-bg: #1d2740; } }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 24px 16px 60px; background: var(--bg); color: var(--text); font-family: "Malgun Gothic", "Apple SD Gothic Neo", "Segoe UI", sans-serif; }
  header { max-width: 1620px; margin: 0 auto 24px; text-align: center; }
  header h1 { margin: 0 0 6px; font-size: 28px; letter-spacing: -0.5px; text-wrap: balance; }
  .updated { font-size: 12px; color: var(--text-sub); }
  .grid { max-width: 1620px; margin: 24px auto 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(min(520px, 100%), 1fr)); gap: 18px; }
  .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; display: flex; flex-direction: column; transition: opacity 0.15s, border-color 0.15s; }
  .card.dragging { opacity: 0.4; }
  .card.drag-over { border-color: var(--accent); }
  .card-header { padding: 14px 16px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 8px; background: color-mix(in srgb, var(--card-bg) 92%, var(--text)); cursor: grab; }
  .card-header:active { cursor: grabbing; }
  .drag-handle { flex: 0 0 auto; color: var(--text-sub); font-size: 14px; letter-spacing: -1px; user-select: none; }
  .card-header .title { font-weight: 700; font-size: 15px; }
  .card-header .board { margin-left: auto; font-size: 12px; color: var(--text-sub); }
  ol.post-list { list-style: none; margin: 0; padding: 6px 0; }
  ol.post-list li { display: flex; align-items: baseline; gap: 8px; padding: 9px 16px; border-bottom: 1px dashed var(--border); }
  ol.post-list li:last-child { border-bottom: none; }
  .rank { flex: 0 0 auto; font-size: 12px; color: var(--text-sub); font-weight: 700; width: 16px; font-variant-numeric: tabular-nums; }
  .post-title { flex: 1 1 auto; font-size: 14px; color: var(--text); text-decoration: none; line-height: 1.4; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .post-title:hover { color: var(--accent); text-decoration: underline; }
  .post-title:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 2px; }
  .comments { flex: 0 0 auto; font-size: 12px; color: var(--accent); background: var(--badge-bg); border-radius: 10px; padding: 1px 7px; font-weight: 600; min-width: 20px; text-align: center; font-variant-numeric: tabular-nums; }
  .empty-note { padding: 24px 16px; color: var(--text-sub); font-size: 13px; text-align: center; }
  footer { max-width: 1620px; margin: 36px auto 0; text-align: center; font-size: 12px; color: var(--text-sub); }
  footer a { color: var(--accent); }
</style>
</head>
<body>
<header>
  <h1>TrendBoard</h1>
  <div class="updated" id="updatedAt">불러오는 중...</div>
</header>
<div class="grid" id="grid"></div>
<footer>
  카드 제목 부분을 드래그하면 순서를 바꿀 수 있어요 (이 브라우저에 저장됩니다). <a href="#" id="resetOrder">순서 초기화</a><br>
  클리앙 · MLB파크 · 뽐뿌 · 오늘의유머 · 82cook의 인기글(댓글 많은 순 10개)을 GitHub Actions가 10분마다 자동으로 갱신합니다.
</footer>
<script>
  const COMMUNITY_DATA = __DATA_JSON__;
  (function () {
    const STORAGE_KEY = 'communityViewerOrder';
    const grid = document.getElementById('grid');
    const updatedEl = document.getElementById('updatedAt');
    const resetLink = document.getElementById('resetOrder');
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
    let currentOrder = applyOrder(COMMUNITY_DATA.communities, getSavedOrder());
    let dragSrcIndex = null;
    resetLink.addEventListener('click', function (e) { e.preventDefault(); localStorage.removeItem(STORAGE_KEY); currentOrder = COMMUNITY_DATA.communities.slice(); render(); });
    function render() {
      grid.innerHTML = '';
      currentOrder.forEach(function (community, index) {
        const card = document.createElement('div'); card.className = 'card'; card.draggable = true;
        card.addEventListener('dragstart', function (e) { dragSrcIndex = index; card.classList.add('dragging'); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', String(index)); });
        card.addEventListener('dragend', function () { card.classList.remove('dragging'); });
        card.addEventListener('dragover', function (e) { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; card.classList.add('drag-over'); });
        card.addEventListener('dragleave', function () { card.classList.remove('drag-over'); });
        card.addEventListener('drop', function (e) {
          e.preventDefault(); card.classList.remove('drag-over');
          if (dragSrcIndex === null || dragSrcIndex === index) return;
          const reordered = currentOrder.slice(); const moved = reordered.splice(dragSrcIndex, 1)[0]; reordered.splice(index, 0, moved);
          currentOrder = reordered; saveOrder(currentOrder.map(function (c) { return c.name; })); render();
        });
        const header = document.createElement('div'); header.className = 'card-header';
        header.innerHTML = '<span class="drag-handle" aria-hidden="true">⠿</span><span class="title">' + escapeHtml(community.name) + '</span><span class="board">' + escapeHtml(community.board || '') + (community.stale ? ' · 캐시' : '') + '</span>';
        card.appendChild(header);
        if (!community.posts || community.posts.length === 0) {
          const empty = document.createElement('div'); empty.className = 'empty-note';
          empty.textContent = community.error ? ('불러오지 못했습니다 (' + community.error + ')') : '표시할 게시글이 없습니다.';
          card.appendChild(empty);
        } else {
          const list = document.createElement('ol'); list.className = 'post-list';
          community.posts.forEach(function (post, idx) {
            const li = document.createElement('li');
            li.innerHTML = '<span class="rank">' + (idx + 1) + '</span><a class="post-title" href="' + escapeAttr(post.url) + '" target="_blank" rel="noopener noreferrer" title="' + escapeAttr(post.title) + '">' + escapeHtml(post.title) + '</a><span class="comments">' + post.comments + '</span>';
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
            html_content = fetch(cfg["url"], cfg["encoding"])
            posts = cfg["parse"](html_content)
            posts.sort(key=lambda x: x["comments"], reverse=True)
            top = posts[:TOP_N]
            if not top:
                raise ValueError("no posts parsed - site markup may have changed")
            result["communities"].append({"name": cfg["name"], "board": cfg["board"], "posts": top, "error": None})
        except Exception as e:
            cached = prev_by_name.get(cfg["name"])
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
