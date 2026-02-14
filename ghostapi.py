import time
import json
import requests
import jwt
import re
import hashlib
from datetime import datetime, timezone


class GhostContentImporter:
    def __init__(self, ghost_url, admin_key):
        self.ghost_url = ghost_url.rstrip("/")
        self.admin_key = admin_key

    def _jwt(self):
        kid, secret = self.admin_key.split(":")
        payload = {
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
            "aud": "/admin/"
        }
        return jwt.encode(
            payload,
            bytes.fromhex(secret),
            algorithm="HS256",
            headers={"kid": kid}
        )

    def _clean_html(self, html: str) -> str:
        html = re.sub(r"\[\d+\]", "", html)
        html = re.sub(r"\(\d+\)", "", html)
        html = re.sub(r"<p>\s*</p>", "", html)
        return html.strip()

    def _generate_slug(self, title: str, source_url: str) -> str:
        slug = title.lower()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"\s+", "-", slug).strip("-")
        slug = slug[:80].rstrip("-")

        short_hash = hashlib.md5(source_url.encode()).hexdigest()[:6]
        return f"{slug}-{short_hash}"

    def _get_existing_slugs(self):
        token = self._jwt()
        r = requests.get(
            f"{self.ghost_url}/ghost/api/admin/posts/",
            headers={"Authorization": f"Ghost {token}"},
            params={"limit": "all"},
            timeout=30
        )

        slugs = set()
        if r.ok:
            for post in r.json().get("posts", []):
                if post.get("slug"):
                    slugs.add(post["slug"])

        return slugs

    def import_posts_from_file(self, filepath, publish=True):
        posts = json.load(open(filepath, encoding="utf-8")).get("posts", [])
        existing_slugs = self._get_existing_slugs()

        for post in posts:
            title = post.get("title")
            source_url = post.get("source_url")

            if not title or not source_url:
                continue

            slug = self._generate_slug(title, source_url)

            if slug in existing_slugs:
                print(f"⏭️ Skipping duplicate: {title}")
                continue

            self.create_post(post, slug, publish)
            existing_slugs.add(slug)

    def create_post(self, post, slug, publish=True):
        clean_html = self._clean_html(post["html"])

        payload = {
            "posts": [{
                "title": post["title"],
                "slug": slug,
                "html": clean_html,
                "feature_image": post.get("image_url"),
                "status": "published" if publish else "draft",
                "tags": [{"name": t} for t in post.get("tags", [])],
                "published_at": datetime.now(timezone.utc)
                    .isoformat().replace("+00:00", "Z")
            }]
        }

        token = self._jwt()

        r = requests.post(
            f"{self.ghost_url}/ghost/api/admin/posts/?source=html",
            headers={
                "Authorization": f"Ghost {token}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )

        if r.ok:
            print(f"✅ Published: {post['title']}")
        else:
            print("❌ Failed:", r.text)
