import os

from typing import Optional, Tuple, Literal

from pydantic import BaseModel

from bs4 import BeautifulSoup, Tag

from utils import EpisodeAccess, parse_episode_id, parse_int


class CachedReview(BaseModel):
    url: str
    is_spoiler: bool


def get_review_links(soup: BeautifulSoup) -> list[CachedReview]:
    review_link_els = soup.select("div#workReview-list > article > h4 > span > a")

    reviews: list[CachedReview] = []

    for review_link_el in review_link_els:
        href = review_link_el.get("href")
        if not isinstance(href, str):
            raise ValueError("href is invalid")

        spoiler_span = review_link_el.select_one(
            "p.widget-workReview-reviewBody > span"
        )
        is_spoiler = spoiler_span is not None and "全文を読む" in spoiler_span.text

        reviews.append(
            CachedReview(
                url=href,
                is_spoiler=is_spoiler,
            )
        )

    return reviews
