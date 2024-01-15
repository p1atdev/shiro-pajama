from typing import Optional, Literal
import time

from pydantic import BaseModel

import requests
from bs4 import BeautifulSoup

SEARCH_ORDER = Literal[
    "weekly_ranking",  # 週間ランキング
    "popular",  # 累計ランキング
    "published_at",  # 新作順
    "last_episode_published_at",  # 更新順
]


class KakuyomuURL:
    BASE_URL = "https://kakuyomu.jp"
    SEARCH_URL = BASE_URL + "/search"

    def compose_search_url(
        self,
        order: SEARCH_ORDER = "popular",
        min_star: int = 0,
        max_star: Optional[int] = None,
        page: int = 1,
    ):
        return "&".join(
            [
                f"{self.SEARCH_URL}?order={order}",
                "total_review_point_range=custom",
                f"total_review_point_min={min_star}",
                f"total_review_point_max={max_star}",
                f"page={page}",
            ]
        )

    def compose_work_url(self, work_id: str):
        return f"{self.BASE_URL}/works/{work_id}"

    def compose_review_url(self, work_id: str, page: int = 1):
        return f"{self.BASE_URL}/works/{work_id}/reviews?page={page}"

    def compose_comment_url(self, work_id: str, page: int = 1):
        return f"{self.BASE_URL}/works/{work_id}/comments?page={page}"

    def compose_access_url(self, work_id: str):
        return f"{self.BASE_URL}/works/{work_id}/accesses"

    def compose_episode_url(self, work_id: str, episode_id: str):
        return f"{self.BASE_URL}/works/{work_id}/episodes/{episode_id}"


def is_not_published(text: str):
    anti_words = [
        "オススメ",
        "おすすめ",
        "紹介",
        "個人的",
        "面白い",
        "してほしい",
        "して欲しい",
        "待望",
        "個人の感想",
        "アドバイス",
        "大手出版社",
        "人気作品",
    ]
    return not any([anti_word in text for anti_word in anti_words])


def is_book_published(text: str):
    flag_words = ["書籍刊行", "書籍化", "書籍発売中", "書籍・漫画化", "Web版", "書籍版"]
    return any([flag_word in text for flag_word in flag_words])


def is_manga_published(text: str):
    flag_words = ["漫画化", "コミカライズ", "漫画・書籍化", "漫画配信中", "コミック版"]
    return any([flag_word in text for flag_word in flag_words])


def is_anime_published(text: str):
    flag_words = ["アニメ化", "アニメ配信中", "アニメ放送中"]
    return any([flag_word in text for flag_word in flag_words])


class Review(BaseModel):
    id: str
    title: str
    user_id: str
    body: str
    star: int
    published_at: str
    upvotes: int  # レビューに対するいいね数
    is_spoiler: bool  # ネタバレあり


class Comment(BaseModel):
    id: str
    episode_id: str
    user_id: str
    is_author: bool
    body: str
    published_at: str


class Episode(BaseModel):
    id: str
    # episode_number: int  # 何話目として設定されているか (作者が設定したもの)
    index: int  # 何話目か (普通に数えて)
    title: str
    published_at: str
    body: str


class Chapter(BaseModel):
    title: Optional[str]
    episodes: list[Episode]


Rating = Literal[
    "cruel",
    "violence",
    "sexual",
]

RATING_MAP: dict[str, Rating] = {
    "残酷描写有り": "cruel",
    "暴力描写有り": "violence",
    "性描写有り": "sexual",
}


def parse_rating(text: str) -> Rating:
    return RATING_MAP[text]


class Metadata(BaseModel):
    title: str
    author_id: str
    author_name: str
    stars: int
    catchphrase: str | None
    introduction: str | None
    type: str
    genre: str
    tags: list[str]
    derivative_original_work_id: str | None
    total_characters: int
    self_ratings: list[Rating]
    is_ended: bool
    published_at: str
    updated_at: str


class EpisodeAccess(BaseModel):  # エピソードごとのアクセス数など
    id: str
    pv: int
    likes: int


class Access(BaseModel):
    total_pv: int
    episodes: list[EpisodeAccess]


class NovelWork(BaseModel):
    id: str
    metadata: Metadata
    number_of_episodes: int
    chapters: list[Chapter]
    number_of_reviews: int
    reviews: list[Review]
    number_of_comments: Optional[int]
    comments: list[Comment]
    number_of_followers: int

    access: Access


proxies = {
    # "http": "http://plat:password@tunnel:8081",
    # "https": "http://plat:password@tunnel:8081",
}


class PageNotFound(Exception):
    pass


def get_soup(url: str):
    max_retry = 3
    for i in range(max_retry):
        try:
            res = requests.get(url, proxies=proxies)
            if res.status_code == 404:
                raise PageNotFound(f"Page not found: {url}")  # 存在しない！！
            res.raise_for_status()
            return BeautifulSoup(res.text, "lxml")
        except PageNotFound as e:
            raise e
        except Exception as e:
            print(e)
            print(f"Retry {i+1}/{max_retry}")
            # wait 10 sec
            time.sleep(10)
    raise Exception(f"Max retry exceeded: {url}")


def parse_episode_id(url: str) -> str:
    return url.replace("/comments", "").split("/")[-1]


def parse_int(text: str) -> int:
    return int(text.replace(",", ""))


def parse_user_id(text: str) -> str:
    return text.split("/")[-1]
