import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

from .models import Page


class Crawler:
    def __init__(self, base_url, max_pages=50, max_depth=3, timeout=30, delay=0.3):
        self.base_url = base_url.rstrip("/")
        self.domain = urlparse(self.base_url).netloc
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.timeout = timeout
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; SEOAuditBot/1.0; +https://github.com/seo-audit)",
            "Accept": "text/html,application/xhtml+xml",
        })
        self.rp = self._parse_robots()
        self.visited = set()
        self.pages: list[Page] = []
        self.errors: list[str] = []

    def _parse_robots(self):
        rp = RobotFileParser()
        try:
            rp.set_url(urljoin(self.base_url, "/robots.txt"))
            rp.read()
        except Exception:
            rp = None
        return rp

    def _can_fetch(self, url):
        if self.rp is None:
            return True
        return self.rp.can_fetch("*", url)

    def _fetch(self, url):
        try:
            start = time.time()
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            elapsed = time.time() - start
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return None
            soup = BeautifulSoup(resp.text, "html.parser")
            return Page(
                url=resp.url,
                status_code=resp.status_code,
                content=resp.text,
                soup=soup,
                headers=dict(resp.headers),
                load_time=round(elapsed, 3),
                content_type=content_type,
            )
        except requests.exceptions.Timeout:
            self.errors.append(f"Timeout: {url}")
        except requests.exceptions.RequestException as e:
            self.errors.append(f"Request failed: {url} - {e}")
        except Exception as e:
            self.errors.append(f"Error parsing {url}: {e}")
        return None

    def _extract_links(self, page):
        links = set()
        for a in page.soup.find_all("a", href=True):
            href = a["href"].strip()
            full_url = urljoin(page.url, href)
            parsed = urlparse(full_url)
            if parsed.scheme not in ("http", "https"):
                continue
            if parsed.netloc != self.domain:
                continue
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
            if not clean:
                continue
            if clean != self.base_url.rstrip("/") or len(self.pages) == 0:
                links.add(clean)
        return links

    def _check_single_url(self, url):
        if url in self.visited:
            return
        if not self._can_fetch(url):
            return
        self.visited.add(url)
        return self._fetch(url)

    def crawl(self):
        self.visited.add(self.base_url)
        page = self._fetch(self.base_url)
        if page is None:
            return self.pages
        self.pages.append(page)

        queue = [(link, 1) for link in self._extract_links(page)]
        processed = set()
        processed.add(self.base_url)

        while queue and len(self.pages) < self.max_pages:
            url, depth = queue.pop(0)
            if url in processed:
                continue
            if depth > self.max_depth:
                continue
            processed.add(url)

            page = self._fetch(url)
            if page is None:
                continue
            self.pages.append(page)

            if depth < self.max_depth:
                new_links = self._extract_links(page)
                for link in new_links:
                    if link not in processed:
                        queue.append((link, depth + 1))
            time.sleep(self.delay)

        return self.pages

    def fetch_single(self, url):
        return self._fetch(url)
