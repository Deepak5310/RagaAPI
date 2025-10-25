"""Web scraper for fetching actress information from Ragalahari.com"""

import logging
import re
import time
from typing import List, Optional, Dict, Set
from datetime import datetime
from asyncio import gather

import aiohttp
from bs4 import BeautifulSoup

from .models import Actress, ActressDetail, ScraperSource, Album
from .config import settings

STARZONE_IMAGE_PATTERN = re.compile(
    r'https://starzone\.ragalahari\.com/[^\s"\'<>]+\.jpg', re.IGNORECASE
)
IMAGE_NUMBER_PATTERN = re.compile(r'(\d+)\.jpg$')
SKIP_KEYWORDS = frozenset(['logo', 'banner', 'icon'])
SKIP_DOMAINS = frozenset(['images.taboola.com', 'cdn.taboola.com'])


class ActressScraper:
    """Async web scraper for Ragalahari.com actress data"""

    def __init__(self):
        """Initialize scraper with session and cache"""
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache: Dict[str, any] = {}
        self._cache_expiry: Dict[str, float] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(
                limit=settings.HTTP_CONNECT_LIMIT,
                limit_per_host=settings.HTTP_CONNECT_LIMIT_PER_HOST,
            )
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": settings.USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT),
                connector=connector,
            )
        return self.session

    async def close(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
        self.session = None

    @staticmethod
    def _make_absolute_url(url: str) -> str:
        """Convert relative URL to absolute"""
        if url.startswith('//'):
            return f"https:{url}"
        if url.startswith('/'):
            return f"https://www.ragalahari.com{url}"
        if url.startswith('http'):
            return url
        return f"https://www.ragalahari.com/{url}"

    @staticmethod
    def _extract_actress_name(gallery_title: str) -> str:
        """Extract clean actress name from gallery title"""
        name_parts = gallery_title.split(' at ')[0].split(' in ')[0].split(',')[0]
        return (name_parts.replace('Actress ', '')
                .replace('Heroine ', '')
                .replace('Model ', '')
                .strip())

    def _extract_thumbnail(self, img_tag) -> Optional[str]:
        """Extract thumbnail URL from img tag"""
        if not img_tag:
            return None

        img_src = (img_tag.get('data-srcset') or img_tag.get('srcset') or
                   img_tag.get('data-src') or img_tag.get('src'))

        if img_src and img_src != '/img/galthumb.jpg':
            return self._make_absolute_url(img_src)
        return None

    def _build_image_map(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Build href to thumbnail URL mapping"""
        image_map = {}
        for img_link in soup.find_all('a', class_='galimg'):
            href = img_link.get('href')
            is_valid = (href and
                       ('/actress/' in href or '/stars/profile/' in href) and
                       href not in image_map)
            if is_valid:
                thumbnail = self._extract_thumbnail(img_link.find('img'))
                if thumbnail:
                    image_map[href] = thumbnail
        return image_map

    def _extract_images_from_soup(self, soup: BeautifulSoup, actress_id: str) -> List[str]:
        """Extract HD images from HTML soup"""
        images = []
        seen: Set[str] = set()

        for img_tag in soup.find_all('img'):
            img_src = self._extract_thumbnail(img_tag)
            if img_src and img_src.endswith('t.jpg') and not img_src.endswith('thumb.jpg'):
                hd_src = img_src[:-5] + '.jpg'
                if hd_src not in seen:
                    images.append(hd_src)
                    seen.add(hd_src)

        return images if images else [f"https://picsum.photos/seed/{actress_id}/800/1200"]

    def _create_actress(self, actress_id: str, name: str, thumbnail: str) -> Actress:
        """Create Actress model instance"""
        return Actress(
            id=actress_id,
            name=name,
            thumbnail=thumbnail,
            age=None,
            nationality="Indian",
            profession="Actress",
            source=ScraperSource.RAGALAHARI
        )

    def _process_actress_link(self, link, href: str, image_map: Dict[str, str],
                              is_latest: bool = False) -> Optional[Actress]:
        """Process a single actress link and return Actress object"""
        parts = href.split('/')

        if '/actress/' in href and len(parts) >= 4:
            gallery_id = parts[2]
            gallery_slug = parts[3].replace('.aspx', '') if len(parts) > 3 else ''
            text = link.get_text(strip=True)
            name = self._extract_actress_name(text) if is_latest else text

            cache_key = f"rh_{gallery_id}"
            self.cache[f"{cache_key}_url"] = self._make_absolute_url(href)
            self.cache[f"{cache_key}_slug"] = gallery_slug
            if is_latest:
                self.cache[f"{cache_key}_title"] = text
                self.cache[f"{cache_key}_is_latest"] = True

            thumbnail = (image_map.get(href) or
                        f"https://www.ragalahari.com{href.replace('.aspx', '')}-thumbnail.jpg")
            return self._create_actress(cache_key, name, thumbnail)

        elif '/stars/profile/' in href and len(parts) >= 5:
            actress_id = parts[3]
            actress_slug = parts[4].replace('.aspx', '')
            name = link.get_text(strip=True)

            cache_key = f"rh_{actress_id}"
            self.cache[f"{cache_key}_url"] = self._make_absolute_url(href)
            self.cache[f"{cache_key}_slug"] = actress_slug

            thumbnail = (image_map.get(href) or
                        f"https://www.ragalahari.com{href.replace('.aspx', '')}-thumbnail.jpg")
            return self._create_actress(cache_key, name, thumbnail)

        return None

    async def scrape_ragalahari_latest(self) -> List[Actress]:
        """Scrape latest 20 galleries from Ragalahari homepage"""
        cached = self._get_cached_list("latest")
        if cached is not None:
            self.logger.debug("Returning cached latest galleries")
            return list(cached)

        url = "https://www.ragalahari.com/actress/starzone.aspx"
        session = await self._get_session()
        actresses = []

        try:
            async with session.get(url) as response:
                if response.status != 200:
                    print(f"Error fetching {url}: Status {response.status}")
                    return actresses

                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                image_map = self._build_image_map(soup)

                for link in soup.find_all('a', class_='galleryname'):
                    href = link.get('href')
                    if href and '/actress/' in href:
                        actress = self._process_actress_link(link, href, image_map, is_latest=True)
                        if actress:
                            actresses.append(actress)

                self.logger.info("Scraped %s latest galleries", len(actresses))
                self._set_cached_list("latest", actresses)
                return actresses

        except (aiohttp.ClientError, TimeoutError) as e:
            self.logger.warning("Error scraping Ragalahari latest: %s", e)
            return actresses


    async def scrape_ragalahari_by_letter(self, letter: str = 'a') -> List[Actress]:
        """Scrape actresses by first letter (A-Z browsing)"""
        letter = letter.lower()
        cached = self._get_cached_list(f"letter:{letter}")
        if cached is not None:
            self.logger.debug("Returning cached actress list for letter '%s'", letter)
            return list(cached)

        url = ("https://www.ragalahari.com/actress/starzonesearch.aspx" if letter == 'a'
               else f"https://www.ragalahari.com/actress/{letter}/starzonesearch.aspx")

        session = await self._get_session()
        actresses = []

        try:
            async with session.get(url) as response:
                if response.status != 200:
                    print(f"Error fetching {url}: Status {response.status}")
                    return actresses

                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                galleries_section = soup.find('div', {'id': 'galleries'})
                if galleries_section:
                    soup = galleries_section

                image_map = self._build_image_map(soup)

                for link in soup.find_all('a', class_='galleryname'):
                    href = link.get('href')
                    if href:
                        actress = self._process_actress_link(link, href, image_map)
                        if actress:
                            actresses.append(actress)

                self.logger.info("Scraped %s actresses from letter '%s'", len(actresses), letter)
                self._set_cached_list(f"letter:{letter}", actresses)
                return actresses

        except (aiohttp.ClientError, TimeoutError) as e:
            self.logger.warning("Error scraping Ragalahari letter '%s': %s", letter, e)
            return actresses


    async def get_ragalahari_actress_detail(self, actress_id: str) -> Optional[ActressDetail]:
        """Get complete actress profile with images and albums"""
        url_key = f"{actress_id}_url"
        slug_key = f"{actress_id}_slug"

        if url_key not in self.cache:
            self.logger.debug("URL not found in cache for %s", actress_id)
            return None

        profile_url = self.cache[url_key]
        actress_slug = self.cache[slug_key]
        session = await self._get_session()

        try:
            async with session.get(profile_url) as response:
                if response.status != 200:
                    self.logger.warning(
                        "Error fetching %s: Status %s", profile_url, response.status
                    )
                    return None

                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                name_elem = soup.find('h1')
                name = (
                    name_elem.get_text(strip=True) if name_elem
                    else actress_slug.replace('-', ' ').title()
                )

                bio = ""
                bio_section = soup.find('div', id='bio') or soup.find('section', class_='biography')
                if bio_section:
                    paragraphs = bio_section.find_all('p')
                    bio = ' '.join([p.get_text(strip=True) for p in paragraphs[:2]])

                info_text = soup.get_text()
                height = self._extract_info(info_text, 'Height:')
                birth_date = self._extract_birth_date(info_text)

                gallery_map = self._build_image_map(soup)
                name_links = soup.find_all('a', class_='galleryname')

                albums = []
                seen_urls = set()

                for link in name_links:
                    album_href = link.get('href')
                    album_name = link.get_text(strip=True)

                    if not album_href or album_href in seen_urls or '/actress/' not in album_href:
                        continue

                    if 'profile' in album_href.lower() or 'search' in album_href.lower():
                        continue

                    if not self._is_actress_album(album_name, album_href, name, actress_slug):
                        continue

                    if not album_name or len(album_name) < 3:
                        url_parts = album_href.split('/')
                        if len(url_parts) >= 3:
                            slug = url_parts[-1].replace('.aspx', '').replace('-', ' ')
                            album_name = slug.title()

                    if album_name and len(album_name) > 3:
                        album_url = self._make_absolute_url(album_href)
                        thumbnail = gallery_map.get(album_href)

                        albums.append({
                            "name": album_name,
                            "url": album_url,
                            "thumbnail": thumbnail
                        })
                        seen_urls.add(album_href)

                self.cache[f"{actress_id}_albums"] = albums

                images = []
                is_from_latest = self.cache.get(f"{actress_id}_is_latest", False)

                if is_from_latest:
                    images = self._extract_images_from_soup(soup, actress_id)

                album_objects = [
                    Album(name=album['name'], url=album['url'], thumbnail=album.get('thumbnail'))
                    for album in albums
                ]

                detail = ActressDetail(
                    id=actress_id,
                    name=name,
                    images=images,
                    albums=album_objects,
                    age=None,
                    birth_date=birth_date,
                    nationality="Indian",
                    profession="Actress",
                    height=height,
                    bio=bio[:500] if bio else f"{name} is an Indian actress.",
                    known_for=[],
                    social_media={},
                    source=ScraperSource.RAGALAHARI,
                    last_updated=datetime.now()
                )

                self.logger.info(
                    "Scraped detail for %s: %s images, %s albums",
                    name,
                    len(images),
                    len(albums),
                )
                return detail

        except (aiohttp.ClientError, TimeoutError) as e:
            self.logger.warning("Error scraping actress detail: %s", e)
            return None

    def _extract_info(self, text: str, label: str) -> Optional[str]:
        """Extract labeled information from text"""
        if label in text:
            start = text.find(label)
            end = text.find('\n', start)
            if end > start:
                return text[start:end].replace(label, '').strip()
        return None

    def _extract_birth_date(self, text: str) -> Optional[str]:
        """Extract birth date from bio text"""
        if 'Born:' in text:
            born_start = text.find('Born:')
            born_end = text.find('\n', born_start)
            if born_end > born_start:
                birth_info = text[born_start:born_end].replace('Born:', '').strip()
                parts = birth_info.split(',')
                if len(parts) >= 2:
                    return ','.join(parts[:2]).strip()
        return None

    def _is_actress_album(self, album_name: str, album_href: str,
                          actress_name: str, actress_slug: str) -> bool:
        """Check if album belongs to the actress"""
        album_name_lower = album_name.lower()
        album_url_lower = album_href.lower()

        first_name = actress_name.split()[0].lower() if actress_name else ""
        name_parts = actress_name.split() if actress_name else []
        last_name = name_parts[-1].lower() if len(name_parts) > 1 else ""

        slug_in_url = actress_slug.lower() in album_url_lower if actress_slug else False

        url_parts = album_href.split('/')[-1].replace('.aspx', '').split('-')
        name_parts = actress_slug.split('-') if actress_slug else []

        matching_parts = sum(1 for part in name_parts if part in url_parts)
        has_similar_slug = matching_parts >= len(name_parts) * 0.6

        return (
            (first_name and first_name in album_name_lower) or
            (last_name and last_name in album_name_lower) or
            slug_in_url or
            has_similar_slug
        )


    async def get_ragalahari_actress_albums(self, actress_id: str) -> List[dict]:
        """Get all albums for an actress"""
        cache_key = f"{actress_id}_albums"
        if cache_key in self.cache:
            return self.cache[cache_key]

        detail = await self.get_ragalahari_actress_detail(actress_id)
        if detail and cache_key in self.cache:
            return self.cache[cache_key]

        return []

    async def _extract_pagination_urls(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract all pagination URLs from album page"""
        seen = {base_url}
        pagination_urls = [base_url]

        for link in soup.find_all('a', class_='otherPage'):
            href = link.get('href')
            if href:
                page_url = self._make_absolute_url(href)
                if page_url not in seen:
                    pagination_urls.append(page_url)
                    seen.add(page_url)

        return pagination_urls

    def _filter_images(self, html: str) -> List[str]:
        """Extract and filter images from HTML"""
        photos = []
        seen = set()

        for img_url in STARZONE_IMAGE_PATTERN.findall(html):
            if img_url.endswith('t.jpg'):
                img_url = img_url[:-5] + '.jpg'
            elif img_url.endswith('thumb.jpg'):
                continue

            if (img_url not in seen and
                not any(domain in img_url for domain in SKIP_DOMAINS) and
                not any(skip in img_url.lower() for skip in SKIP_KEYWORDS)):
                seen.add(img_url)
                photos.append(img_url)

        return photos

    async def _scrape_album_page(self, page_url: str, session: aiohttp.ClientSession) -> List[str]:
        """Scrape images from a single album page"""
        try:
            async with session.get(page_url) as response:
                if response.status != 200:
                    self.logger.warning(
                        "Error fetching album page %s: Status %s", page_url, response.status
                    )
                    return []

                html = await response.text()
                return self._filter_images(html)

        except (aiohttp.ClientError, TimeoutError) as e:
            self.logger.warning("Error scraping album page %s: %s", page_url, e)
            return []

    async def get_ragalahari_album_photos(self, album_url: str) -> List[str]:
        """Get all high-quality photos from an album with pagination support"""
        session = await self._get_session()

        try:
            async with session.get(album_url) as response:
                if response.status != 200:
                    self.logger.warning(
                        "Error fetching album %s: Status %s", album_url, response.status
                    )
                    return []

                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                pagination_urls = await self._extract_pagination_urls(soup, album_url)

                if len(pagination_urls) == 1:
                    photos = self._filter_images(html)
                    photos.sort(
                        key=lambda url: int(m.group(1))
                        if (m := IMAGE_NUMBER_PATTERN.search(url)) else 0
                    )
                    self.logger.info(
                        "Scraped %s photos from album: %s", len(photos), album_url
                    )
                    return photos

                self.logger.debug(
                    "Found %s pages for album: %s", len(pagination_urls), album_url
                )

            page_photos_list = await gather(
                *[self._scrape_album_page(url, session) for url in pagination_urls]
            )

            all_photos = []
            seen = set()
            for page_photos in page_photos_list:
                for photo in page_photos:
                    if photo not in seen:
                        all_photos.append(photo)
                        seen.add(photo)

            all_photos.sort(
                key=lambda url: int(m.group(1))
                if (m := IMAGE_NUMBER_PATTERN.search(url)) else 0
            )
            self.logger.info(
                "Scraped %s photos across %s pages: %s",
                len(all_photos),
                len(pagination_urls),
                album_url,
            )
            return all_photos

        except (aiohttp.ClientError, TimeoutError) as e:
            self.logger.warning("Error scraping album photos: %s", e)
            return []

    def _set_cached_list(self, cache_key: str, actresses: List[Actress]) -> None:
        """Cache list responses for reuse with an expiry window."""
        list_key = f"list:{cache_key}"
        if settings.CACHE_TTL_SECONDS <= 0:
            return
        self.cache[list_key] = list(actresses)
        self._cache_expiry[list_key] = time.time() + settings.CACHE_TTL_SECONDS

    def _get_cached_list(self, cache_key: str) -> Optional[List[Actress]]:
        """Return cached list data if still valid."""
        list_key = f"list:{cache_key}"
        expiry = self._cache_expiry.get(list_key)
        if not expiry or expiry <= time.time():
            self.cache.pop(list_key, None)
            self._cache_expiry.pop(list_key, None)
            return None
        cached = self.cache.get(list_key)
        if isinstance(cached, list):
            return cached
        return None
