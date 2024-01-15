import os

from typing import Optional, Tuple, Literal

from pydantic import BaseModel

from bs4 import BeautifulSoup, Tag

from utils import parse_episode_id, parse_int


class CachedEpisode(BaseModel):
    id: str
    title: str
    published_at: str


class CachedChapter(BaseModel):
    title: Optional[str]
    episodes: list[CachedEpisode] = []


#### 概要セクション


def get_stars(soup: BeautifulSoup) -> int:
    stars_el = soup.select_one("p#workPoints > a > span")
    if stars_el is None:
        raise ValueError("stars not found")

    return parse_int(stars_el.text.strip())


def get_catchphrase(soup: BeautifulSoup) -> str | None:
    catchphrase_el = soup.select_one("span#catchphrase-body")
    if catchphrase_el is None:
        print("catchphrase not found")
        return None
    else:
        return catchphrase_el.text.strip()


def get_introduction(soup: BeautifulSoup) -> str | None:
    introduction_el = soup.select_one("p#introduction")
    if introduction_el is None:
        print("introduction not found")
        return None

    introduction = introduction_el.text.strip()

    truncate_button_el = introduction_el.select_one(
        "span.ui-truncateTextButton-expandButton > span"
    )
    if truncate_button_el is None:
        return introduction

    truncate_button_text = truncate_button_el.text.strip()

    # 最後に存在する「続きを読む」ボタンを削除
    introduction = introduction[: -len(truncate_button_text)]
    return introduction.strip()


#### 目次セクション


def get_chapters(soup: BeautifulSoup) -> list[CachedChapter]:
    chapters: list[CachedChapter] = [CachedChapter(title=None, episodes=[])]

    li_els = soup.select("div.widget-toc-main > ol > li")
    if li_els is None:
        raise ValueError("episodes not found")

    chapter_index = 0
    for li_el in li_els:
        li_class = li_el.get("class")
        if li_class is None:
            raise ValueError("li class not found")

        if "widget-toc-episode" in li_class:  # episode
            link_el = li_el.select_one("a")
            if link_el is None:
                raise ValueError("episode link not found")

            href = link_el.get("href")
            if not isinstance(href, str):
                raise ValueError("episode href not found")

            episode_label_el = link_el.select_one("span")
            if episode_label_el is None:
                raise ValueError("episode label not found")

            episode_label = episode_label_el.text.strip()

            episode_time_el = link_el.select_one("time")
            if episode_time_el is None:
                raise ValueError("episode time not found")

            episode_time = episode_time_el.get("datetime")
            if not isinstance(episode_time, str):
                raise ValueError("episode time not found")

            chapters[chapter_index].episodes.append(
                CachedEpisode(
                    id=parse_episode_id(href),
                    title=episode_label,
                    published_at=episode_time,
                )
            )
        elif "widget-toc-chapter" in li_class:  # chapter
            if len(chapters[0].episodes) == 0:
                chapters[0].title = li_el.text.strip()
            else:
                chapters.append(
                    CachedChapter(
                        title=li_el.text.strip(),
                        episodes=[],
                    )
                )
                chapter_index += 1
        else:
            raise ValueError("li class is invalid")

    return chapters


#### 情報セクション


class CachedInformation(BaseModel):
    is_ended: bool
    number_of_episodes: int
    type: str
    genre: str
    self_ratings: list[str]
    tags: list[str]
    derivative_original_work: str | None
    total_characters: int
    published_at: str
    updated_at: str

    number_of_reviews: int
    number_of_comments: int | None
    number_of_follows: int


INFORMATION_KEY = Literal[
    "執筆状況",
    "エピソード",
    "種類",
    "ジャンル",
    "セルフレイティング",
    "タグ",
    "総文字数",
    "公開日",
    "最終更新日",
    "おすすめレビュー",
    "応援コメント",
    "小説フォロー数",
    "二次創作原作",
]

INFORMATION_KEYS: list[INFORMATION_KEY] = [
    "執筆状況",
    "エピソード",
    "種類",
    "ジャンル",
    "セルフレイティング",
    "タグ",
    "総文字数",
    "公開日",
    "最終更新日",
    "おすすめレビュー",
    "応援コメント",
    "小説フォロー数",
    "二次創作原作",
]


def get_info(soup: BeautifulSoup) -> CachedInformation:
    info_lists = soup.select("div#workInformationList > dl")
    if info_lists is None:
        raise ValueError("information not found")

    cached_info = CachedInformation(
        is_ended=False,
        number_of_episodes=0,
        type="",
        genre="",
        self_ratings=[],
        tags=[],
        derivative_original_work=None,
        total_characters=0,
        published_at="",
        updated_at="",
        number_of_reviews=0,
        number_of_comments=0,
        number_of_follows=0,
    )

    for info_list in info_lists:
        dts = info_list.select("dt")
        dds = info_list.select("dd")
        if len(dts) != len(dds):
            raise ValueError("dt and dd are not paired")

        for dt, dd in zip(dts, dds):
            key_name = dt.text.strip()
            if key_name not in INFORMATION_KEYS:
                print(f"[WARNING] key name is invalid: {key_name}")
            value = dd.text.strip()

            if key_name == "執筆状況":
                if value == "完結済":
                    cached_info.is_ended = True
                elif value == "連載中":
                    cached_info.is_ended = False
                else:
                    raise ValueError(f"ended is invalid: {value}")

            elif key_name == "エピソード":
                cached_info.number_of_episodes = parse_int(value.replace("話", ""))

            elif key_name == "種類":
                cached_info.type = value

            elif key_name == "ジャンル":
                cached_info.genre = value

            elif key_name == "セルフレイティング":
                cached_info.self_ratings = [
                    span.text.strip() for span in dd.select("span")
                ]

            elif key_name == "タグ":
                cached_info.tags = [a.text.strip() for a in dd.select("span")]

            elif key_name == "総文字数":
                cached_info.total_characters = parse_int(value[:-2])

            elif key_name == "公開日" or key_name == "最終更新日":
                time = dd.select_one("time")
                if time is None:
                    raise ValueError(f"time not found: {key_name}")

                date = time.get("datetime")
                if not isinstance(date, str):
                    raise ValueError(f"date is invalid: {key_name}")

                if key_name == "公開日":
                    cached_info.published_at = date
                elif key_name == "最終更新日":
                    cached_info.updated_at = date
                else:
                    raise ValueError(f"key name is invalid: {key_name}")

            elif key_name == "おすすめレビュー":
                cached_info.number_of_reviews = parse_int(value[:-1])  # 人を排除

            elif key_name == "応援コメント":
                try:
                    cached_info.number_of_comments = parse_int(value[:-1])  # 件を排除
                except:
                    # 作者の設定により非表示 の場合
                    cached_info.number_of_comments = None

            elif key_name == "小説フォロー数":
                cached_info.number_of_follows = parse_int(value[:-1])  # 人を排除

            elif key_name == "二次創作原作":
                cached_info.derivative_original_work = value

            elif key_name in ["コレクション"]:  # 収集しない
                continue

            else:
                raise ValueError(f"key name is invalid: {key_name}")

    return cached_info


def get_title(soup: BeautifulSoup) -> str:
    title_el = soup.select_one("section#work-information > header > h4")
    if title_el is None:
        raise ValueError("title not found")

    return title_el.text.strip()


def get_author(soup: BeautifulSoup) -> Tuple[str, str]:
    author_el = soup.select_one("section#work-information > header > h5 > a")
    if author_el is None:
        raise ValueError("author not found")

    author_id_el = author_el.select_one("span.screenName")
    if author_id_el is None:
        raise ValueError("author id not found")

    author_name_el = author_el.select_one("span.activityName")
    if author_name_el is None:
        print("author name not found")

        return (
            author_id_el.text.strip().replace("@", ""),  # ユーザー名にユーザーIDを使う
            author_id_el.text.strip().replace("@", ""),
        )
    else:
        return (
            author_name_el.text.strip(),
            author_id_el.text.strip().replace("@", ""),
        )
