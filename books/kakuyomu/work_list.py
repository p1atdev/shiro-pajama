from typing import Optional

from pydantic import BaseModel

from bs4 import BeautifulSoup, Tag

from utils import SEARCH_ORDER, get_soup, KakuyomuURL


class SearchCondition(BaseModel):
    order: SEARCH_ORDER = "popular"
    min_star: int
    max_star: Optional[int]
    page: int = 1


# それぞれ検索結果のページ数が 500 を超えないように絞られている
search_conditions = [
    SearchCondition(min_star=1000, max_star=None),
    SearchCondition(min_star=500, max_star=999),
    SearchCondition(min_star=250, max_star=499),
    SearchCondition(min_star=125, max_star=249),
    SearchCondition(min_star=100, max_star=124),
    SearchCondition(min_star=80, max_star=99),
    SearchCondition(min_star=60, max_star=79),
    SearchCondition(min_star=40, max_star=59),
    SearchCondition(min_star=35, max_star=39),
    SearchCondition(min_star=30, max_star=34),
    SearchCondition(min_star=27, max_star=29),
    SearchCondition(min_star=24, max_star=26),
    SearchCondition(min_star=20, max_star=23),
    SearchCondition(min_star=17, max_star=19),
    SearchCondition(min_star=15, max_star=16),
    SearchCondition(min_star=13, max_star=14),
    SearchCondition(min_star=12, max_star=12),
    SearchCondition(min_star=11, max_star=11),
    SearchCondition(min_star=10, max_star=10),
    SearchCondition(min_star=9, max_star=9),
]

MIN_PAGE = 1
MAX_PAGE = 500

SEARCH_RESULT_SELECTOR = "div.NewBox_padding-pt-3l__OKZhP:nth-child(1) > div:nth-child(1) > div:nth-child(2) > div:nth-child(4)"
EMPTY_MESSAGE_CLASSNAME = "div.EmptyMessage_emptyMessage__u2slN"

WORK_LINK_IN_H3 = "h3 > span:nth-child(1) > a:nth-child(1)"


def is_no_result(soup: BeautifulSoup):
    return len(soup.select(EMPTY_MESSAGE_CLASSNAME)) == 1


def results_element(soup: BeautifulSoup) -> Tag | None:
    result = soup.select(SEARCH_RESULT_SELECTOR)
    if len(result) != 1:
        return None
    return result[0]


def extract_urls(soup: BeautifulSoup):
    result_el = results_element(soup)
    if not isinstance(result_el, Tag):
        raise ValueError("no result element")

    link_els = result_el.select(WORK_LINK_IN_H3)  # 最大20個
    print(f"found {len(link_els)} works")

    links = [link["href"] for link in link_els]
    links = [link for link in links if isinstance(link, str)]  # list 除去
    links = [
        f"{KakuyomuURL.BASE_URL}{link}" for link in links if link.startswith("/works/")
    ]

    return links


def main():
    kakuyomu = KakuyomuURL()

    soups: list[BeautifulSoup] = []

    for condition in search_conditions:
        for index in range(MIN_PAGE, MAX_PAGE + 1):
            url = kakuyomu.compose_search_url(
                order=condition.order,
                min_star=condition.min_star,
                max_star=condition.max_star,
                page=index,
            )

            print(url)

            soup = get_soup(url)

            if is_no_result(soup):  # 小説は見つかりませんでした
                print(f"no result. page: {index}")
                break  # もうない

            soups.append(soup)

    urls: list[str] = []

    # まとめて抽出
    for soup in soups:
        urls.extend(extract_urls(soup))
        print(f"found {len(urls)} works")

    # 重複除去
    urls = list(set(urls))

    print(f"found {len(urls)} works")

    # save as txt
    with open("work_list/urls.txt", "w", encoding="utf-8") as f:
        for url in urls:
            f.write(url + "\n")


if __name__ == "__main__":
    main()
