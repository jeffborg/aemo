from __future__ import annotations

import re
import subprocess
import urllib.parse
import urllib.request
from datetime import date, timedelta
from html.parser import HTMLParser
from urllib.error import HTTPError


BASE_URL = "https://nemweb.com.au/Reports/Current"
DEFAULT_HEADERS = {"User-Agent": "aemo-forecast-publisher/0.1"}
FILENAME_DATE_PATTERN = re.compile(r"_(\d{8})(?:_|\.|$)")


class DirectoryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers=DEFAULT_HEADERS)


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(_request(url)) as response:
        return response.read().decode("utf-8", "ignore")


def fetch_bytes(url: str) -> bytes:
    try:
        with urllib.request.urlopen(_request(url)) as response:
            return response.read()
    except HTTPError as exc:
        if exc.code != 403:
            raise
        result = subprocess.run(
            ["curl", "-A", DEFAULT_HEADERS["User-Agent"], "-L", "--fail", url],
            check=True,
            capture_output=True,
        )
        return result.stdout


def list_links(directory_url: str) -> list[str]:
    parser = DirectoryParser()
    parser.feed(fetch_text(directory_url))
    return parser.links


def matching_files(directory_name: str, prefix: str) -> list[str]:
    directory_url = f"{BASE_URL}/{directory_name}/"
    return sorted(
        urllib.parse.urljoin(directory_url, link)
        for link in list_links(directory_url)
        if prefix in link and link.endswith(".zip")
    )


def latest_matching_file(directory_name: str, prefix: str) -> str:
    links = matching_files(directory_name, prefix)
    if not links:
        raise RuntimeError(f"No files found for {directory_name} matching {prefix}")
    return sorted(links)[-1]


def recent_market_notice_files() -> list[str]:
    directory_url = f"{BASE_URL}/Market_Notice/"
    links = [
        urllib.parse.urljoin(directory_url, link)
        for link in list_links(directory_url)
        if "MKTNOTICE" in link and ".R" in link
    ]
    if not links:
        return []

    dated_links: list[tuple[date, str]] = []
    for link in links:
        match = FILENAME_DATE_PATTERN.search(link)
        if not match:
            continue
        year = int(match.group(1)[0:4])
        month = int(match.group(1)[4:6])
        day = int(match.group(1)[6:8])
        dated_links.append((date(year, month, day), link))

    if not dated_links:
        return []

    latest_date = max(item[0] for item in dated_links)
    earliest_date = latest_date - timedelta(days=1)
    selected = [link for item_date, link in dated_links if item_date >= earliest_date]
    return sorted(selected)
