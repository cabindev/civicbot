"""Reads recent posts from the CivicSpace Facebook page, on demand.

Gemini calls ``get_recent_page_posts`` as a tool only when a user asks about
the page's latest work, so ordinary chats never touch the Graph API. Results
are cached briefly so a burst of questions costs one Graph call.

Uses a *read-only* page token (FACEBOOK_PAGE_TOKEN), never the Messenger
token held by the Azure Bot channel: that one carries pages_messaging, so a
leak would let the holder message people as the page. Fetch logic mirrors
Hermes Agent's facebook-page-monitor skill (page_report.py).
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import aiohttp

from config import Config

logger = logging.getLogger(__name__)

GRAPH = "https://graph.facebook.com/v21.0/"
FIELDS = "id,created_time,message,permalink_url,status_type"
BANGKOK = timezone(timedelta(hours=7))
CACHE_SECONDS = 600
MAX_POSTS = 10
# Long posts are trimmed so a handful of them can't bloat the prompt.
MAX_MESSAGE_CHARS = 1200

_cache: Dict[int, tuple] = {}


def is_configured() -> bool:
    return bool(Config.FACEBOOK_PAGE_ID and Config.FACEBOOK_PAGE_TOKEN)


def _to_bangkok(created_time: str) -> str:
    try:
        when = datetime.strptime(created_time, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return created_time
    return when.astimezone(BANGKOK).strftime("%Y-%m-%d %H:%M")


async def _fetch(days: int) -> Dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    params = {
        "fields": FIELDS,
        "since": int(since.timestamp()),
        "limit": MAX_POSTS,
        "access_token": Config.FACEBOOK_PAGE_TOKEN,
    }
    url = f"{GRAPH}{Config.FACEBOOK_PAGE_ID}/posts"
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, params=params) as resp:
            data = await resp.json(content_type=None)

    if "error" in data:
        # Never echo Graph's message to the model verbatim; log it for us.
        logger.error("Graph API error fetching posts: %s", data["error"])
        return {"error": "ดึงโพสต์จากเพจไม่สำเร็จ"}

    posts = []
    for post in data.get("data", []):
        message = (post.get("message") or "").strip()
        posts.append({
            "posted_at": _to_bangkok(post.get("created_time", "")),
            "type": post.get("status_type", ""),
            "message": message[:MAX_MESSAGE_CHARS] or "(ไม่มีข้อความ — อาจเป็นรูป/วิดีโออย่างเดียว)",
            "url": post.get("permalink_url", ""),
        })
    return {
        "now": datetime.now(BANGKOK).strftime("%Y-%m-%d %H:%M"),
        "days": days,
        "posts": posts,
    }


async def get_recent_page_posts(days: int = 14) -> Dict[str, Any]:
    """Posts from the last ``days`` days, newest first, cached for 10 minutes."""
    if not is_configured():
        return {"error": "ยังไม่ได้ตั้งค่าการอ่านโพสต์จากเพจ"}

    days = max(1, min(int(days or 14), 90))
    hit = _cache.get(days)
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]

    try:
        result = await _fetch(days)
    except Exception:  # noqa: BLE001 - the bot should still answer
        logger.exception("Fetching page posts failed")
        return {"error": "ดึงโพสต์จากเพจไม่สำเร็จ"}

    if "error" not in result:
        _cache[days] = (time.monotonic(), result)
    return result
