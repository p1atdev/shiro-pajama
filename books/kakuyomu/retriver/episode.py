import os

from typing import Optional, Tuple, Literal

from pydantic import BaseModel

from bs4 import BeautifulSoup, Tag

from utils import EpisodeAccess, parse_episode_id, parse_int


def get_body(soup: BeautifulSoup) -> str:
    body_el = soup.select_one("div.widget-episode-inner")
    if body_el is None:
        raise ValueError("body not found")

    return body_el.text.strip()
