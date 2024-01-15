import os

from typing import Optional, Tuple, Literal

from pydantic import BaseModel

from bs4 import BeautifulSoup, Tag


def get_body(soup: BeautifulSoup) -> str:
    body_el = soup.select_one("div.widget-episodeBody")
    if body_el is None:
        raise ValueError("body not found")

    body = body_el.text.strip()

    return body
