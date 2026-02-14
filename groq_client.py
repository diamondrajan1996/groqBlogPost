import time
from pathlib import Path
from groq import Groq
from datetime import datetime, timedelta

MIN_WORDS = 100
MAX_WORDS = 150

# Rate limiting (Groq free tier: 30 requests/min)
REQUEST_LIMIT_PER_MINUTE = 30
REQUESTS_HISTORY = []


def _trim_to_word_count(text: str, min_words: int = MIN_WORDS, max_words: int = MAX_WORDS) -> str:
    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words]).rstrip() + "…"
    return text


def _check_rate_limit():
    global REQUESTS_HISTORY
    now = datetime.now()
    REQUESTS_HISTORY = [ts for ts in REQUESTS_HISTORY if now - ts < timedelta(minutes=1)]

    if len(REQUESTS_HISTORY) >= REQUEST_LIMIT_PER_MINUTE:
        oldest = min(REQUESTS_HISTORY)
        wait_time = (oldest + timedelta(minutes=1) - now).total_seconds()
        if wait_time > 0:
            print(f"⏳ Rate limit reached. Waiting {wait_time:.1f}s")
            time.sleep(wait_time + 0.5)
            REQUESTS_HISTORY = []

    REQUESTS_HISTORY.append(now)


def fetch_latest_news(api_key: str, max_results: int = 1):
    _check_rate_limit()

    client = Groq(api_key=api_key)

    # Load prompt
    prompt_path = Path(__file__).parent / "prompts.txt"
    if not prompt_path.exists():
        raise RuntimeError("prompts.txt must exist.")

    prompt_text = prompt_path.read_text(encoding="utf-8")
    prompt = prompt_text.format(max_results=max_results)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
        max_tokens=800
    )

    text = response.choices[0].message.content.strip()
    print(f"📝 Groq preview:\n{text[:500]}...\n")

    posts = []
    current = {}
    content_lines = []
    in_content = False

    for line in text.splitlines():
        clean = line.strip().replace("**", "")

        if clean.startswith("TITLE:"):
            current = {"title": clean.replace("TITLE:", "").strip()}

        elif clean.startswith("CONTENT:"):
            in_content = True
            content_lines = [clean.replace("CONTENT:", "").strip()]

        elif in_content and not any(
            clean.startswith(x) for x in ["SOURCE:", "URL:", "TAGS:"]
        ):
            content_lines.append(clean)

        elif clean.startswith("SOURCE:"):
            in_content = False
            current["content"] = _trim_to_word_count(" ".join(content_lines))
            current["source"] = clean.replace("SOURCE:", "").strip()

        elif clean.startswith("URL:"):
            current["source_url"] = clean.replace("URL:", "").strip()

        elif clean.startswith("TAGS:"):
            tags = [t.strip() for t in clean.replace("TAGS:", "").split(",") if t.strip()]

            if current.get("title") and current.get("content") and current.get("source_url"):

                source_url = current["source_url"]
                if not source_url.startswith(("http://", "https://")):
                    source_url = "https://" + source_url

                html_content = f"""
<p>{current["content"]}</p>

<hr>

<p><strong>Source:</strong>
<a href="{source_url}" target="_blank" rel="noopener noreferrer nofollow external">
{current.get('source', source_url)}
</a>
</p>
""".strip()

                posts.append({
                    "title": current["title"],
                    "html": html_content,
                    "tags": tags[:3] if tags else ["News"],
                    "source_url": source_url
                })

            current = {}

    print(f"✅ Parsed {len(posts)} post(s)")
    return posts
