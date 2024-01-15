import os

from typing import Optional, Tuple, Literal

from pydantic import BaseModel

from bs4 import BeautifulSoup, Tag

from utils import EpisodeAccess, parse_episode_id, parse_int, parse_user_id


class CachedComment(BaseModel):
    id: str
    user_id: str
    target_episode_id: str
    body: str
    published_at: str
    reply_to: str | None


def get_review_links(soup: BeautifulSoup):
    comment_els = soup.select("div.widget-cheerComment")

    comments: list[CachedComment] = []

    for comment_el in comment_els:
        id = comment_el.get("id")
        if not isinstance(id, str):
            raise ValueError("id is invalid")
        id = id.replace("comment-", "")

        inner_el = comment_el.select_one("div.widget-cheerComment-inner")
        if inner_el is None:
            raise ValueError("inner_el is None")

        user_el = inner_el.select_one("h5 > a")
        if user_el is None:
            raise ValueError("user_el is None")

        user_href = user_el.get("href")
        if not isinstance(user_href, str):
            raise ValueError("user_href is invalid")

        user_id = parse_user_id(user_href)

        episode_title_el = inner_el.select_one("p.widget-cheerComment-episodeTitle > a")
        if episode_title_el is None:
            raise ValueError("episode_title_el is None")

        episode_href = episode_title_el.get("href")
        if not isinstance(episode_href, str):
            raise ValueError("episode_href is invalid")

        episode_id = parse_episode_id(episode_href)

        date = inner_el.select_one("time")
        if date is None:
            raise ValueError("date is None")

        published_at = date.get("datetime")
        if not isinstance(published_at, str):
            raise ValueError("published_at is invalid")

        body_el = inner_el.select_one(
            "div.widget-cheerComment-body > p.js-vertical-composition-item"
        )
        if body_el is None:
            raise ValueError("body_el is None")

        body = body_el.text.strip()

        comments.append(
            CachedComment(
                id=id,
                user_id=user_id,
                target_episode_id=episode_id,
                body=body,
                published_at=published_at,
                reply_to=None,
            )
        )

        reply_el = comment_el.select_one("div.widget-cheerComment-reply")
        if reply_el is None:
            continue

        author_el = reply_el.select_one("a.widget-cheerComment-buttons-author")
        if author_el is None:
            raise ValueError("author_el is None")

        author_href = author_el.get("href")
        if not isinstance(author_href, str):
            raise ValueError("author_href is invalid")

        date = reply_el.select_one("p.widget-cheerComment-buttons > span > span")
        if date is None:
            raise ValueError("date is None")

        published_at = date.text.strip()  # これだけ datetime じゃない！！

        author_id = parse_user_id(author_href)

        reply_body_el = reply_el.select_one(
            "div.widget-cheerComment-body > p.js-vertical-composition-item"
        )
        if reply_body_el is None:
            raise ValueError("reply_body_el is None")

        reply_body = reply_body_el.text.strip()

        reply_id = f"{id}-reply"

        comments.append(
            CachedComment(
                id=reply_id,
                user_id=author_id,
                target_episode_id=episode_id,
                body=reply_body,
                published_at=published_at,
                reply_to=id,
            )
        )

    return comments
