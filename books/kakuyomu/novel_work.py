import os
from pathlib import Path

from typing import Optional, Callable
import json

from pydantic import BaseModel

from bs4 import BeautifulSoup, Tag

import numpy as np
from concurrent.futures import ThreadPoolExecutor

from tqdm import tqdm

from utils import (
    get_soup,
    KakuyomuURL,
    NovelWork,
    Metadata,
    Review,
    Comment,
    Episode,
    Chapter,
    Rating,
    Access,
    parse_rating,
    PageNotFound,
)

import retriver
from retriver.metadata import CachedChapter, CachedInformation
from retriver.comments import CachedComment
from retriver.reviews import CachedReview

DEBUG = False

URL_LIST_PATH = "./work_list/20230916.txt"

# URL のリストをこの数に分割して、それぞれ順番に処理する
NUMBER_OF_CHUNKS = 100

NUMBER_OF_THREADS = 2  # 並列処理のスレッド数

OUTPUT_PATH = "./novel_work"
OUTPUT_FILE_NAME: Callable[[int], str] = lambda i: os.path.join(
    OUTPUT_PATH, f"novel_work_{i}.json"
)
CACHE_PATH = "./cache_novel_work"
CACHE_FILE_NAME: Callable[[int], str] = lambda i: os.path.join(
    CACHE_PATH, f"cache_{i}.json"
)

kakuyomu = KakuyomuURL()


class CachedURLPair(BaseModel):
    work_id: str
    metadata: str
    # reviews: str
    comments: str
    accesses: str


class CachedMetadata(BaseModel):
    title: str
    author_name: str
    author_id: str
    stars: int
    catchphrase: str | None
    introduction: str | None
    info: CachedInformation
    chapters: list[CachedChapter] = []


class WorkInfoCache(BaseModel):
    id: str
    metadata: CachedMetadata
    accesses: Access
    reviews: list[CachedReview]
    # review_urls: list[str]
    comments: list[CachedComment]


def load_url_list(path: str):
    with open(path) as f:
        return [line.strip() for line in f.readlines()]


def get_existed_cache_index():
    return max(
        [-1]
        + [
            int(Path(file_name).stem.split("_")[-1])
            for file_name in os.listdir(CACHE_PATH)
            if file_name.startswith("cache_")
        ],  # 存在しなかったら0、存在したら最大の数字が得られる
    )


def get_existed_work_index():
    return max(
        [-1]
        + [
            int(Path(file_name).stem.split("_")[-1])
            for file_name in os.listdir(OUTPUT_PATH)
            if file_name.startswith("novel_work_")
        ],  # 存在しなかったら0、存在したら最大の数字が得られる
    )


def save_cache(cache: list[WorkInfoCache], index: int):
    with open(CACHE_FILE_NAME(index), "w", encoding="utf-8") as f:
        json.dump(
            [data.model_dump() for data in cache], f, indent=2, ensure_ascii=False
        )


def parse_work_id(url: str):
    return url.split("/")[-1]


# 作品のメタデータ。タイトルや公開日、章など
def extract_metadata(soup: BeautifulSoup):
    title = retriver.metadata.get_title(soup)
    author_name, author_id = retriver.metadata.get_author(soup)

    stars = retriver.metadata.get_stars(soup)

    # print("| metadata:", title, author_name, author_id, stars)

    info = retriver.metadata.get_info(soup)

    # print(info)

    catchphrase = retriver.metadata.get_catchphrase(soup)
    introduction = retriver.metadata.get_introduction(soup)

    print(
        catchphrase[:10] if catchphrase is not None else catchphrase,
        (introduction[:10], introduction[-10:])
        if introduction is not None
        else introduction,
    )

    chapters = retriver.metadata.get_chapters(soup)

    return CachedMetadata(
        title=title,
        author_name=author_name,
        author_id=author_id,
        stars=stars,
        catchphrase=catchphrase,
        introduction=introduction,
        info=info,
        chapters=chapters,
    )


# レビュー (おすすめ文)
def extract_reviews(soup: BeautifulSoup):
    review_links = retriver.reviews.get_review_links(soup)
    return review_links


def retrive_reviews(work_id: str) -> list[CachedReview]:
    page = 1
    reviews: list[CachedReview] = []

    while True:
        url = kakuyomu.compose_review_url(work_id, page)
        soup = get_soup(url)
        new_review = extract_reviews(soup)

        if len(new_review) == 0:
            break

        reviews += new_review

        page += 1

    return reviews


# それぞれの話に対するコメント (非公開の場合もあり)
def extract_comment_urls(soup: BeautifulSoup):
    comment_links = retriver.comments.get_review_links(soup)
    return comment_links


def retrive_comment_urls(work_id: str):
    page = 1
    comments = []

    while True:
        url = kakuyomu.compose_comment_url(work_id, page)
        soup = get_soup(url)
        new_comment = extract_comment_urls(soup)

        if len(new_comment) == 0:
            break

        comments += new_comment

        page += 1

    return comments


# PV数などの情報
def extract_accesses(soup: BeautifulSoup):
    total_pv = retriver.access.get_total_pv(soup)

    accesses = retriver.access.get_accesses(soup)

    access = Access(total_pv=total_pv, episodes=accesses)

    return access


def process_url_chunk(urls: list[str]):
    url_pairs: list[CachedURLPair] = []

    for url in urls:
        work_id = parse_work_id(url)

        metadata_url = url
        comments_url = kakuyomu.compose_comment_url(work_id)
        accesses_url = kakuyomu.compose_access_url(work_id)

        url_pairs.append(
            CachedURLPair(
                work_id=work_id,
                metadata=metadata_url,
                comments=comments_url,
                accesses=accesses_url,
            )
        )

    print("total", len(url_pairs))

    def process_url_pairs(url_pairs: list[CachedURLPair], pbar: tqdm):
        work_caches = []
        for url_pair in url_pairs:
            try:
                print("\n", url_pair.metadata)
                metadata = extract_metadata(get_soup(url_pair.metadata))
                access = extract_accesses(get_soup(url_pair.accesses))
                reviews = retrive_reviews(url_pair.work_id)  # これはレビューの URL のみ
                comments = retrive_comment_urls(url_pair.work_id)

                # print("|", len(metadata.chapters), "章")
                # print("|", access.total_pv, "PV")
                # print("|", len(reviews), "レビュー")
                # print("|", len(comments), "コメント")

                work_caches.append(
                    WorkInfoCache(
                        id=url_pair.work_id,
                        metadata=metadata,
                        accesses=access,
                        reviews=reviews,
                        comments=comments,
                    )
                )
                pbar.update(1)

            except PageNotFound:
                print(f"[WARNING] PageNotFound: {url_pair.metadata}")
                pbar.update(1)
                continue

            except Exception as e:
                print(f"Error: {url_pair.metadata}")
                raise e

            # print(f"- total {len(caches)} works processed")

        return work_caches

    caches: list[WorkInfoCache] = []

    chunks = np.array_split(url_pairs, NUMBER_OF_THREADS)

    with tqdm(total=len(url_pairs)) as pbar:
        with ThreadPoolExecutor(max_workers=NUMBER_OF_THREADS) as executor:
            futures = []
            for chunk in chunks:
                futures.append(executor.submit(process_url_pairs, chunk, pbar))

            for future in futures:
                caches.extend(future.result())

    print(f"{len(url_pairs)} urls processed")

    return caches


def create_cache():
    urls = load_url_list(URL_LIST_PATH)
    print(f"found {len(urls)} work urls")

    url_chunks = np.array_split(urls, NUMBER_OF_CHUNKS)
    print(f"split into {len(url_chunks)} chunks")

    current_index = 0

    if DEBUG:
        url_chunks = url_chunks[:1]
        print(f"debug mode: use only {len(url_chunks)} chunk(s)")
    else:
        existed_file_index = get_existed_cache_index() + 1
        print(f"existed file index: {existed_file_index}")

        url_chunks = url_chunks[existed_file_index:]
        print(f"start from {existed_file_index}th chunk")
        print(f"remaining {len(url_chunks)} chunks")

        current_index = existed_file_index

    for chunk in url_chunks:
        caches = process_url_chunk(chunk.tolist())
        save_cache(caches, current_index)

        current_index += 1

    print("done")


def retrive_episodes(
    work_id: str, cached_chapters: list[CachedChapter]
) -> list[Chapter]:
    chapters: list[Chapter] = []

    for cache in cached_chapters:
        chapter = Chapter(
            title=cache.title,
            episodes=[],
        )

        index = 1

        for episode in cache.episodes:
            url = kakuyomu.compose_episode_url(work_id, episode.id)
            try:
                soup = get_soup(url)

                body = retriver.episode.get_body(soup)

                chapter.episodes.append(
                    Episode(
                        id=episode.id,
                        title=episode.title,
                        published_at=episode.published_at,
                        body=body,
                        index=index,
                    )
                )
            except PageNotFound:
                print(f"[WARNING] PageNotFound: {url}")
                continue
            except Exception as e:
                print(f"Error: {url}")
                raise e
            finally:
                index += 1

        chapters.append(chapter)

    return chapters


def retrive_all_episodes_from_cache(
    caches: list[WorkInfoCache], pbar: tqdm
) -> list[NovelWork]:
    novel_works: list[NovelWork] = []

    for cache in caches:
        print("\n", cache.metadata.title, kakuyomu.compose_work_url(cache.id))

        novel_work = NovelWork(
            id=cache.id,
            number_of_episodes=cache.metadata.info.number_of_episodes,
            metadata=Metadata(
                title=cache.metadata.title,
                author_name=cache.metadata.author_name,
                author_id=cache.metadata.author_id,
                stars=cache.metadata.stars,
                catchphrase=cache.metadata.catchphrase,
                introduction=cache.metadata.introduction,
                type=cache.metadata.info.type,
                genre=cache.metadata.info.genre,
                tags=cache.metadata.info.tags,
                derivative_original_work_id=cache.metadata.info.derivative_original_work,
                total_characters=cache.metadata.info.total_characters,
                self_ratings=[
                    parse_rating(rating) for rating in cache.metadata.info.self_ratings
                ],
                is_ended=cache.metadata.info.is_ended,
                published_at=cache.metadata.info.published_at,
                updated_at=cache.metadata.info.updated_at,
            ),
            chapters=[],
            number_of_reviews=cache.metadata.info.number_of_reviews,
            reviews=[],  # TODO: あとでやる
            number_of_comments=cache.metadata.info.number_of_comments,
            comments=[
                Comment(
                    id=comment.id,
                    episode_id=comment.target_episode_id,
                    user_id=comment.user_id,
                    is_author=comment.user_id == cache.metadata.author_id,
                    body=comment.body,
                    published_at=comment.published_at,
                )
                for comment in cache.comments
            ],
            number_of_followers=cache.metadata.info.number_of_follows,
            access=cache.accesses,
        )

        # chapter について取得
        chapters = retrive_episodes(cache.id, cache.metadata.chapters)

        novel_work.chapters = chapters

        novel_works.append(novel_work)

        # print(f"total {len(novel_works)} works processed")
        pbar.update(1)

    return novel_works


def save_works(works: list[NovelWork], index: int):
    with open(OUTPUT_FILE_NAME(index), "w", encoding="utf-8") as f:
        json.dump(
            [data.model_dump() for data in works], f, indent=2, ensure_ascii=False
        )


def retrive_full_works():
    cache_jsons = [
        Path(CACHE_PATH, file_name).resolve()
        for file_name in os.listdir(CACHE_PATH)
        if file_name.startswith("cache_")
    ]
    # cache_jsons.sort(key=lambda x: int(x.stem.split("_")[-1]))  # sort by index
    # print(cache_jsons)

    current_index = get_existed_work_index() + 1

    cache_jsons = cache_jsons[current_index:]
    print(cache_jsons)

    if DEBUG:
        cache_jsons = cache_jsons[:2]
        print(f"debug mode: use only {len(cache_jsons)} cache file(s)")

    print(f"start from {current_index}th cache file")

    for cache_json in cache_jsons:
        print(f"\n{cache_json}")
        with open(cache_json, "r", encoding="utf-8") as f:
            caches = json.load(f)
        if DEBUG:
            caches = caches[:10]
        print(f"{len(caches)} works found in {cache_json.stem}")

        chunks = np.array_split(caches, NUMBER_OF_THREADS)

        with tqdm(total=len(caches)) as pbar:
            with ThreadPoolExecutor(max_workers=NUMBER_OF_THREADS) as executor:
                futures = []
                for chunk in chunks:
                    futures.append(
                        executor.submit(
                            retrive_all_episodes_from_cache,
                            [WorkInfoCache(**data) for data in chunk],
                            pbar,
                        )
                    )

                full_works = []
                for future in futures:
                    full_works.extend(future.result())

        save_works(full_works, current_index)

        current_index += 1

    print("done")


def main():
    if not os.path.exists(OUTPUT_PATH):
        os.mkdir(OUTPUT_PATH)
    if not os.path.exists(CACHE_PATH):
        os.mkdir(CACHE_PATH)

    # create_cache()
    retrive_full_works()


if __name__ == "__main__":
    main()
