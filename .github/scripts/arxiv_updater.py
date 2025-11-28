#!/usr/bin/env python
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

import requests
from openai import OpenAI

client = OpenAI()

# --- CONFIG --------------------------------------------------------------

# Adjust this search query if needed. This is a simple starting point.
ARXIV_SEARCH = 'au:"Jason Hartford"'
ARXIV_MAX_RESULTS = 50          # how many recent papers to scan
NEWS_WINDOW_DAYS = 7            # "new" = published in the last N days

WEBSITE_ROOT = Path(".")
BIB_PATH = WEBSITE_ROOT / "_bibliography" / "papers.bib"
NEWS_DIR = WEBSITE_ROOT / "_news"
POSTS_DIR = WEBSITE_ROOT / "_posts"
SEEN_FILE = WEBSITE_ROOT / ".github" / "data" / "seen_arxiv_ids.json"

# ------------------------------------------------------------------------


@dataclass
class ArxivPaper:
    arxiv_id: str
    title: str
    abstract: str
    authors: List[str]
    primary_category: str
    published: datetime
    url: str


def fetch_arxiv_papers() -> List[ArxivPaper]:
    """
    Query arXiv's API for your papers and return a list of ArxivPaper objects.
    """
    base = "http://export.arxiv.org/api/query"
    params = {
        "search_query": ARXIV_SEARCH,
        "start": 0,
        "max_results": ARXIV_MAX_RESULTS,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    resp = requests.get(base, params=params, timeout=30)
    resp.raise_for_status()

    import xml.etree.ElementTree as ET

    root = ET.fromstring(resp.text)
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

    entries: List[ArxivPaper] = []
    for entry in root.findall("atom:entry", ns):
        id_text = entry.find("atom:id", ns).text  # e.g. 'http://arxiv.org/abs/2301.12345v1'
        arxiv_id = id_text.rsplit("/", 1)[-1]

        title = (entry.find("atom:title", ns).text or "").strip().replace("\n", " ")
        abstract = (entry.find("atom:summary", ns).text or "").strip()
        published_text = entry.find("atom:published", ns).text  # 'YYYY-MM-DDTHH:MM:SSZ'
        published = datetime.fromisoformat(published_text.replace("Z", "+00:00"))

        authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]
        cat_el = entry.find("atom:category", ns)
        primary_cat = cat_el.attrib.get("term", "") if cat_el is not None else ""
        url = f"https://arxiv.org/abs/{arxiv_id}"

        entries.append(
            ArxivPaper(
                arxiv_id=arxiv_id,
                title=title,
                abstract=abstract,
                authors=authors,
                primary_category=primary_cat,
                published=published,
                url=url,
            )
        )

    return entries


def load_seen_ids() -> set[str]:
    """
    IDs we've already generated news/blog posts for.
    """
    if not SEEN_FILE.exists():
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return set(data)


def save_seen_ids(ids: set[str]) -> None:
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, indent=2)


def read_bib_text() -> str:
    if not BIB_PATH.exists():
        return ""
    return BIB_PATH.read_text(encoding="utf-8")


def append_bib_entries(new_entries: List[str]) -> None:
    """
    Append new BibTeX entries to _bibliography/papers.bib.
    """
    BIB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if BIB_PATH.exists():
        with open(BIB_PATH, "a", encoding="utf-8") as f:
            for e in new_entries:
                f.write("\n\n" + e.strip() + "\n")
    else:
        with open(BIB_PATH, "w", encoding="utf-8") as f:
            for i, e in enumerate(new_entries):
                if i > 0:
                    f.write("\n\n")
                f.write(e.strip() + "\n")


def make_bibtex_key(paper: ArxivPaper) -> str:
    """
    e.g. hartford2025scalableflowmatching
    """
    last_name = paper.authors[0].split()[-1].lower() if paper.authors else "unknown"
    year = paper.published.year

    import re

    words = re.findall(r"[A-Za-z0-9]+", paper.title.lower())
    key_words = "".join(words[:3])
    return f"{last_name}{year}{key_words}"


def paper_to_bibtex(paper: ArxivPaper) -> str:
    key = make_bibtex_key(paper)
    authors = " and ".join(paper.authors)
    year = paper.published.year
    lines = [
        f"@article{{{key},",
        f"  title = {{{paper.title}}},",
        f"  author = {{{authors}}},",
        f"  year = {{{year}}},",
        f"  eprint = {{{paper.arxiv_id}}},",
        f"  archivePrefix = {{arXiv}},",
        f"  primaryClass = {{{paper.primary_category}}},",
        f"  url = {{{paper.url}}},",
        "}",
    ]
    return "\n".join(lines)


def slugify(text: str) -> str:
    import re

    s = text.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s


def summarise_paper_with_llm(paper: ArxivPaper) -> Dict[str, str]:
    """
    Use OpenAI to generate a short news blurb and a longer blog-style summary.
    """
    system_msg = """
You help an academic maintain their personal website.

Given the title and abstract of a paper, produce:
- a short news title for the "News" section,
- a 1–3 sentence Markdown news blurb in the 1st person,
- a longer Markdown blog-style summary (3–7 paragraphs) explaining the motivation,
  main ideas, and key results at a level suitable for a technically literate ML person.

Return ONLY valid JSON with these fields:
- news_title: string
- news_body_md: string
- blog_title: string
- blog_body_md: string
"""

    user_msg = f"""Title: {paper.title}

Authors: {", ".join(paper.authors)}

arXiv: {paper.url}

Abstract:
{paper.abstract}
"""

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",  # swap for another model if you prefer
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
    )
    content = resp.choices[0].message.content
    data = json.loads(content)
    return data


def write_news_file(paper: ArxivPaper, summary: Dict[str, str]) -> Path:
    NEWS_DIR.mkdir(exist_ok=True)
    date_str = paper.published.date().isoformat()
    slug = slugify(summary.get("news_title") or paper.title)
    filename = f"{date_str}-{slug}.md"
    path = NEWS_DIR / filename

    frontmatter = {
        "layout": "post",
        "title": summary["news_title"],
        "date": date_str,
        "tags": ["paper"],
        "category": "news",
        "inline": True,
        "link": paper.url,
    }

    fm_lines = ["---"]
    for k, v in frontmatter.items():
        if isinstance(v, list):
            arr = "[" + ", ".join(f'"{x}"' for x in v) + "]"
            fm_lines.append(f"{k}: {arr}")
        else:
            fm_lines.append(f'{k}: "{v}"')
    fm_lines.append("---")

    body = summary["news_body_md"].strip()
    text = "\n".join(fm_lines) + "\n\n" + body + "\n"
    path.write_text(text, encoding="utf-8")
    return path


def write_blog_post(paper: ArxivPaper, summary: Dict[str, str]) -> Path:
    POSTS_DIR.mkdir(exist_ok=True)
    date_str = paper.published.date().isoformat()
    slug = slugify(summary.get("blog_title") or paper.title)
    filename = f"{date_str}-{slug}.md"
    path = POSTS_DIR / filename

    frontmatter = {
        "layout": "post",
        "title": summary["blog_title"],
        "date": date_str,
        "tags": ["paper"],
        "categories": ["research"],
    }

    fm_lines = ["---"]
    for k, v in frontmatter.items():
        if isinstance(v, list):
            arr = "[" + ", ".join(f'"{x}"' for x in v) + "]"
            fm_lines.append(f"{k}: {arr}")
        else:
            fm_lines.append(f'{k}: "{v}"')
    fm_lines.append("---")

    body = summary["blog_body_md"].strip()
    text = "\n".join(fm_lines) + "\n\n" + body + "\n"
    path.write_text(text, encoding="utf-8")
    return path


def main():
    papers = fetch_arxiv_papers()
    print(f"Fetched {len(papers)} papers from arXiv search '{ARXIV_SEARCH}'")

    seen_ids = load_seen_ids()
    bib_text = read_bib_text()

    new_bib_entries: List[str] = []
    new_seen_ids = set(seen_ids)
    now = datetime.utcnow()
    news_cutoff = now - timedelta(days=NEWS_WINDOW_DAYS)

    news_papers: List[ArxivPaper] = []

    for p in papers:
        # 1) BibTeX: add if not already present (simple substring check on arxiv_id)
        if p.arxiv_id not in bib_text:
            bib_entry = paper_to_bibtex(p)
            new_bib_entries.append(bib_entry)
            print(f"Will add BibTeX for {p.arxiv_id}")

        # 2) News/blog: only for "fresh" papers we haven't seen before
        if p.arxiv_id not in seen_ids and p.published >= news_cutoff:
            news_papers.append(p)
            new_seen_ids.add(p.arxiv_id)

    if new_bib_entries:
        append_bib_entries(new_bib_entries)
        print(f"Appended {len(new_bib_entries)} new BibTeX entries.")
    else:
        print("No new BibTeX entries needed.")

    for p in news_papers:
        print(f"Generating summary for new paper {p.arxiv_id}")
        summary = summarise_paper_with_llm(p)
        news_path = write_news_file(p, summary)
        blog_path = write_blog_post(p, summary)
        print(f"  Wrote news: {news_path}")
        print(f"  Wrote blog post: {blog_path}")

    if new_seen_ids != seen_ids:
        save_seen_ids(new_seen_ids)
        print(f"Updated seen_arxiv_ids.json with {len(new_seen_ids)} ids.")
    else:
        print("No changes to seen_arxiv_ids.json.")

    if not (new_bib_entries or news_papers):
        print("No changes made.")


if __name__ == "__main__":
    main()
