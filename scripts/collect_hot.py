#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自动收录 Jev / TypeSafe System One 生态的 GitHub 热门项目。

用法：
    GITHUB_TOKEN=xxx python3 scripts/collect_hot.py            # 更新 README 与快照
    GITHUB_TOKEN=xxx python3 scripts/collect_hot.py --dry-run  # 只打印，不写文件

设计取舍：
- Jev 于 2026-09-15 发布，所以「2026-09-10 之后创建」这一条就能滤掉绝大多数同名噪音
  （jevois 智能相机、jEveAssets、Jevix、JEvents、jevil-simulator 等十几年前的老仓库）。
- typesafe-ai 官方组织的仓库无条件放行。
- 剩下的漏网之鱼走 scripts/denylist.txt 人工拉黑，一行一个 owner/repo。
- 只改 README 里 <!-- HOT:START --> 与 <!-- HOT:END --> 之间的内容，人工精选区永不被机器覆盖。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
SNAPSHOT = ROOT / "data" / "hot.json"
DENYLIST = ROOT / "scripts" / "denylist.txt"

API = "https://api.github.com"
MARK_START = "<!-- HOT:START -->"
MARK_END = "<!-- HOT:END -->"

# Jev 发布于 2026-09-15，留 5 天缓冲
BORN_AFTER = "2026-09-10"
OFFICIAL_ORG = "typesafe-ai"
MIN_STARS = 3
MAX_ROWS = 60
SELF = "yzfly/awesome-jev-zh"

SEARCH_QUERIES = [
    f"jev in:name,description,readme created:>={BORN_AFTER}",
    f"typesafe jev in:name,description,readme created:>={BORN_AFTER}",
    f'"system one" model in:name,description,readme created:>={BORN_AFTER}',
    f"typesafe-ai in:name,description,readme created:>={BORN_AFTER}",
    f"org:{OFFICIAL_ORG}",
]

# 必须命中其一，否则不算 Jev 生态
RELEVANT = re.compile(r"jev|typesafe|system[\s-]one", re.I)

# 同名但无关的历史项目（老仓库已被 created 过滤，这里兜底）
UNRELATED = re.compile(
    r"jevois|jeveassets|jevix|jevil|jevents|jevmacho|jevxpc|jevonscamera"
    r"|jeve_|jevo\b|jeval\b|\bjeva\b|jevgeni|jeverything",
    re.I,
)

# 语言 → 中文标签
LANG_ZH = {
    "TypeScript": "TS", "JavaScript": "JS", "Python": "Python", "Rust": "Rust",
    "Go": "Go", "Ruby": "Ruby", "PHP": "PHP", "Java": "Java", "C#": "C#",
    "Elixir": "Elixir", "Scala": "Scala", "Swift": "Swift", "Kotlin": "Kotlin",
    "Shell": "Shell", "HTML": "HTML", "CSS": "CSS", "C++": "C++", "C": "C",
    "Jupyter Notebook": "Notebook", "MDX": "MDX", "Markdown": "Markdown",
    "Julia": "Julia", "MoonBit": "MoonBit", "Lua": "Lua", "Dart": "Dart",
}


def gh_get(url: str, token: str | None) -> dict:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "awesome-jev-zh-collector")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429) and attempt < 3:
                wait = 20 * (attempt + 1)
                print(f"  限流，{wait}s 后重试…", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError:
            if attempt < 3:
                time.sleep(5)
                continue
            raise
    return {}


def search(query: str, token: str | None) -> list[dict]:
    out: list[dict] = []
    for page in (1, 2):
        url = (
            f"{API}/search/repositories?q={urllib.parse.quote(query)}"
            f"&sort=stars&order=desc&per_page=100&page={page}"
        )
        data = gh_get(url, token)
        items = data.get("items", [])
        out.extend(items)
        if len(items) < 100:
            break
        time.sleep(2)
    return out


def load_denylist() -> set[str]:
    if not DENYLIST.exists():
        return set()
    names = set()
    for line in DENYLIST.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            names.add(line.lower())
    return names


def keep(repo: dict, deny: set[str]) -> bool:
    full = repo.get("full_name", "")
    if not full or full.lower() in deny or full == SELF:
        return False
    if repo.get("archived") or repo.get("fork") or repo.get("private"):
        return False
    if repo.get("stargazers_count", 0) < MIN_STARS:
        return False

    owner = full.split("/")[0]
    blob = " ".join(
        filter(None, [full, repo.get("description") or "", " ".join(repo.get("topics") or [])])
    )
    if UNRELATED.search(blob):
        return False
    if owner.lower() == OFFICIAL_ORG:
        return True
    if not RELEVANT.search(blob):
        return False
    created = (repo.get("created_at") or "")[:10]
    return created >= BORN_AFTER


def clean_desc(text: str | None) -> str:
    if not text:
        return "—"
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("|", "/")
    # 去掉描述开头的 emoji 装饰，表格里更整齐
    text = re.sub(r"^[\W_]*([←-⯿\U0001F000-\U0001FAFF]\s*)+", "", text)
    if len(text) > 96:
        text = text[:95].rstrip() + "…"
    return text or "—"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("提示：未设置 GITHUB_TOKEN，未认证请求限流很紧（10 次/分钟）。", file=sys.stderr)

    deny = load_denylist()
    found: dict[str, dict] = {}
    for query in SEARCH_QUERIES:
        print(f"→ 搜索：{query}", file=sys.stderr)
        try:
            for repo in search(query, token):
                if keep(repo, deny):
                    found[repo["full_name"]] = repo
        except Exception as exc:  # noqa: BLE001
            print(f"  查询失败（跳过）：{exc}", file=sys.stderr)
        time.sleep(2)

    if not found:
        print("没有搜到任何项目，保持 README 原样退出。", file=sys.stderr)
        return 1

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    prev = {}
    if SNAPSHOT.exists():
        prev = json.loads(SNAPSHOT.read_text(encoding="utf-8")).get("repos", {})

    rows = []
    snapshot: dict[str, dict] = {}
    for full, repo in found.items():
        stars = repo.get("stargazers_count", 0)
        old = prev.get(full, {})
        first_seen = old.get("first_seen", today)
        delta = stars - old.get("stars", stars)
        snapshot[full] = {"stars": stars, "first_seen": first_seen}
        rows.append(
            {
                "full": full,
                "stars": stars,
                "delta": delta,
                "new": first_seen >= week_ago,
                "lang": LANG_ZH.get(repo.get("language") or "", repo.get("language") or "—"),
                "desc": clean_desc(repo.get("description")),
                "official": full.split("/")[0].lower() == OFFICIAL_ORG,
            }
        )

    rows.sort(key=lambda r: (-r["stars"], r["full"].lower()))
    rows = rows[:MAX_ROWS]

    lines = [
        "",
        f"> 🤖 由 [`scripts/collect_hot.py`](scripts/collect_hot.py) 每日自动抓取并排序，"
        f"最后更新：**{today}**（UTC）。收录规则：2026-09-10 之后创建、"
        f"名称/描述/README 命中 Jev 生态关键词、Star ≥ {MIN_STARS}，外加 "
        f"[`typesafe-ai`](https://github.com/typesafe-ai) 官方组织全量。"
        "`🆕` = 本周新进榜，`▲` = 相比上次抓取的 Star 增量。",
        "",
        "| # | 项目 | Star | 变化 | 语言 | 一句话 |",
        "| :-- | :-- | :-- | :-- | :-- | :-- |",
    ]
    for i, r in enumerate(rows, 1):
        badge = f"![](https://badgen.net/github/stars/{r['full']})"
        name = f"[**{r['full']}**](https://github.com/{r['full']})"
        if r["official"]:
            name += " `官方`"
        if r["new"]:
            name += " `🆕`"
        change = f"▲ {r['delta']}" if r["delta"] > 0 else "—"
        lines.append(f"| {i} | {name} | {badge} | {change} | {r['lang']} | {r['desc']} |")
    lines.append("")
    block = "\n".join(lines)

    if args.dry_run:
        print(block)
        print(f"\n共 {len(rows)} 条（候选 {len(found)}）", file=sys.stderr)
        return 0

    text = README.read_text(encoding="utf-8")
    if MARK_START not in text or MARK_END not in text:
        print("README 里找不到 HOT 标记块。", file=sys.stderr)
        return 1
    head, rest = text.split(MARK_START, 1)
    _, tail = rest.split(MARK_END, 1)
    README.write_text(head + MARK_START + block + MARK_END + tail, encoding="utf-8")

    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(
        json.dumps({"updated": today, "repos": snapshot}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"已更新 README：{len(rows)} 条（候选 {len(found)}）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
