#!/usr/bin/env python3
"""
2026Research — Automated Weekly Report Generator
Runs every Friday at 4:30pm ET via GitHub Actions.
Calls Claude with web search, gets a formatted report object,
inserts it at the top of the reports array in research.html.
"""

import anthropic
import json
import re
import sys
from datetime import datetime, timezone, timedelta

# ── CONFIG ──────────────────────────────────────────────
HTML_FILE = "research.html"
INSERT_MARKER = "const reports = ["
MODEL = "claude-sonnet-4-20250514"
# ────────────────────────────────────────────────────────

def get_week_info():
    """Return the current week number of the year and formatted date."""
    now = datetime.now(timezone(timedelta(hours=-5)))  # ET
    week_num = now.isocalendar()[1]
    date_str = now.strftime("%b %d, %Y")
    day = now.strftime("%d").lstrip("0")
    month = now.strftime("%b")
    return week_num, date_str, day, month


def generate_report(week_num, date_str, day, month):
    """Call Claude with web search to research the week and write the report."""
    client = anthropic.Anthropic()

    system_prompt = """You are the research engine for 2026Research — a weekly market research project run by a finance student at Fordham's Gabelli School of Business.

Your job is to research the current week's market events and write a Weekly Wrap report.

CRITICAL: You must return ONLY a valid JavaScript object — no markdown, no backticks, no explanation, nothing else. Just the raw JS object starting with { and ending with }.

The object must follow this EXACT structure:
{
  id:'rNEW', type:'weekly', week:'Week X', date:'Mon DD, YYYY', day:'DD', month:'Mon',
  title:'Your title here',
  excerpt:'One sentence summary of the week.',
  keyData:[
    {val:'X.X%', cls:'up', label:'Label'},
    {val:'X,XXX', cls:'', label:'Label'},
    {val:'X.X%', cls:'dn', label:'Label'}
  ],
  body:`
    <p>Opening paragraph...</p>
    <h3>Section Header</h3>
    <p>Content...</p>
    <h3>Section Header</h3>
    <p>Content...</p>
    <h3>What to Watch Next Week</h3>
    <p>Forward looking paragraph...</p>`,
  sources:'Source 1. Source 2. Source 3.'
}

Rules:
- cls values: 'up' for green (positive), 'dn' for red (negative), '' for neutral
- Use <strong> for key numbers in body text
- Use <em> for emphasis (renders in gold)
- 3-4 body sections with <h3> headers
- Always end with a "What to Watch Next Week" section
- Sources cited as a single string, comma or period separated
- All data must be real and from this week — use web search
- Writing tone: direct, analytical, no fluff, no financial advice framing
- Never mention trades or positions — pure market analysis only"""

    user_prompt = f"""Research and write this week's Weekly Wrap report for 2026Research.

Week number: {week_num}
Report date: {date_str}
Day: {day}
Month: {month}

Use web search to find:
1. S&P 500, Nasdaq, and Dow weekly performance (exact % changes)
2. Any Fed commentary, speeches, or data releases this week
3. Key economic data released (CPI, jobs, GDP, PMI, etc.)
4. Major earnings reports that moved markets
5. Any significant macro events, geopolitical developments, or sector moves
6. VIX level and 10Y Treasury yield

Write a thorough Weekly Wrap covering everything significant that happened this week. Return ONLY the JavaScript object, nothing else."""

    print(f"Calling Claude to research week {week_num}...")

    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=system_prompt,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": user_prompt}]
    )

    # Extract all text blocks from the response (handles tool use + text)
    full_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            full_text += block.text

    full_text = full_text.strip()

    # Strip any accidental markdown fences
    full_text = re.sub(r"^```[a-z]*\n?", "", full_text)
    full_text = re.sub(r"\n?```$", "", full_text)
    full_text = full_text.strip()

    print("Report generated successfully.")
    return full_text


def insert_report(report_js):
    """Insert the new report object at the top of the reports array in research.html."""
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    if INSERT_MARKER not in html:
        print(f"ERROR: Could not find '{INSERT_MARKER}' in {HTML_FILE}")
        sys.exit(1)

    # Insert after the opening of the array
    insertion_point = html.index(INSERT_MARKER) + len(INSERT_MARKER)

    new_html = (
        html[:insertion_point]
        + "\n  "
        + report_js
        + ","
        + html[insertion_point:]
    )

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(new_html)

    print(f"Report inserted into {HTML_FILE} successfully.")


def update_homepage_preview(report_js):
    """Update index.html latest report section with the new report's title and excerpt."""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()

        # Extract title and excerpt from the report JS
        title_match = re.search(r"title:'([^']+)'", report_js)
        excerpt_match = re.search(r"excerpt:'([^']+)'", report_js)
        week_match = re.search(r"week:'([^']+)'", report_js)
        date_match = re.search(r"date:'([^']+)'", report_js)

        if not all([title_match, excerpt_match, week_match, date_match]):
            print("Could not extract all fields for homepage update — skipping.")
            return

        title   = title_match.group(1)
        excerpt = excerpt_match.group(1)
        week    = week_match.group(1)
        date    = date_match.group(1)

        # Replace the section-eyebrow week label
        html = re.sub(
            r'<div class="section-eyebrow">Latest Report · Week \d+</div>',
            f'<div class="section-eyebrow">Latest Report · {week}</div>',
            html
        )

        # Replace the report title
        html = re.sub(
            r'(<h2 class="rf-title">)[^<]+(</h2>)',
            rf'\g<1>{title}\g<2>',
            html
        )

        # Replace the excerpt
        html = re.sub(
            r'(<p class="rf-excerpt">)[^<]+(</p>)',
            rf'\g<1>{excerpt}\g<2>',
            html
        )

        # Replace the date in rf-meta
        html = re.sub(
            r'(<span>)(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d+, 2026(</span>)',
            rf'\g<1>{date}\g<3>',
            html,
            count=1
        )

        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html)

        print("Homepage preview updated successfully.")

    except Exception as e:
        print(f"Homepage update failed (non-critical): {e}")


def main():
    week_num, date_str, day, month = get_week_info()
    print(f"Generating report for {date_str} (Week {week_num})...")

    report_js = generate_report(week_num, date_str, day, month)

    # Basic sanity check
    if not report_js.startswith("{") or not report_js.rstrip().endswith("}"):
        print("ERROR: Claude did not return a valid JS object.")
        print("Output was:")
        print(report_js[:500])
        sys.exit(1)

    insert_report(report_js)
    update_homepage_preview(report_js)

    print("Done. Report will be live after Cloudflare deploys (~30 seconds).")


if __name__ == "__main__":
    main()
