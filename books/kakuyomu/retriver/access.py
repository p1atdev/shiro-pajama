import os

from typing import Optional, Tuple, Literal

from pydantic import BaseModel

from bs4 import BeautifulSoup, Tag

from utils import EpisodeAccess, parse_episode_id, parse_int


def get_total_pv(soup: BeautifulSoup) -> int:
    total_pv_el = soup.select_one("span#workStatsCount-label")
    if total_pv_el is None:
        raise ValueError("total_pv not found")

    total_pv = total_pv_el.text.strip()
    total_pv = total_pv.replace(",", "")

    return int(total_pv)


def get_accesses(soup: BeautifulSoup) -> list[EpisodeAccess]:
    accesses: list[EpisodeAccess] = []

    trs = soup.select("table#episodeStats-table > tbody > tr")

    for tr in trs:
        link_el = tr.select_one("td.episodeTitle > a")
        if link_el is None:
            raise ValueError("link not found")

        href = link_el.get("href")
        if not isinstance(href, str):
            raise ValueError("href is invalid")

        likes_el = tr.select_one("td.barCheerCount > span")
        if likes_el is None:
            likes = 0
        else:
            likes = parse_int(likes_el.text.strip())

        pv_el = tr.select_one("td.barCount > span.barCount-label")
        if pv_el is None:
            raise ValueError("pv not found")

        pv = parse_int(pv_el.text.strip())

        accesses.append(EpisodeAccess(id=parse_episode_id(href), likes=likes, pv=pv))

    return accesses
