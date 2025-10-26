"""Web scraper for fetching actress information from Ragalahari.com"""

import re
import asyncio
from typing import List, Optional, Dict, Set, Any, Tuple
from datetime import datetime, timedelta
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

# Cache TTL: 1 hour for list endpoints, 6 hours for detail
CACHE_TTL_LIST = timedelta(hours=1)
CACHE_TTL_DETAIL = timedelta(hours=6)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds


class ActressScraper:
    """Async web scraper for Ragalahari.com actress data"""
    def __init__(self):
        """Initialize scraper with session and cache"""
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache: Dict[str, Tuple[Any, datetime]] = {}

    def _get_cache(self, key: str) -> Optional[Any]:
        """Get cached value if not expired"""
        if key in self.cache:
            value, timestamp = self.cache[key]
            # Check if detail cache (longer TTL)
            is_detail = key.endswith('_albums') or key.endswith('_detail')
            ttl = CACHE_TTL_DETAIL if is_detail else CACHE_TTL_LIST
            if datetime.now() - timestamp < ttl:
                return value
            # Expired, remove
            del self.cache[key]

        # Periodically clean expired cache (every 100 reads)
        if len(self.cache) > 100:
            self._clear_expired_cache()

        return None

    def _set_cache(self, key: str, value: Any) -> None:
        """Set cache with timestamp"""
        self.cache[key] = (value, datetime.now())

    def _clear_expired_cache(self) -> None:
        """Clear expired cache entries"""
        now = datetime.now()
        expired_keys = [
            key for key, (_, timestamp) in self.cache.items()
            if now - timestamp > CACHE_TTL_DETAIL
        ]
        for key in expired_keys:
            del self.cache[key]

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with connection pooling"""
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(
                limit=100,  # Max 100 concurrent connections
                limit_per_host=30,  # Max 30 per host
                ttl_dns_cache=300  # DNS cache for 5 mins
            )
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": settings.USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT),
                connector=connector
            )
        return self.session

    async def close(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def _fetch_with_retry(
        self, url: str, retries: int = MAX_RETRIES
    ) -> Optional[str]:
        """Fetch URL with exponential backoff retry"""
        session = await self._get_session()

        for attempt in range(retries):
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 429:  # Rate limited
                        wait_time = RETRY_DELAY * (2 ** attempt)
                        msg = f"Rate limited, waiting {wait_time}s..."
                        print(msg)
                        await asyncio.sleep(wait_time)
                    else:
                        status = response.status
                        print(f"Error fetching {url}: Status {status}")
                        if attempt < retries - 1:
                            await asyncio.sleep(RETRY_DELAY * (2 ** attempt))
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                print(f"Request failed (attempt {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(RETRY_DELAY * (2 ** attempt))

        return None

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
        title = gallery_title.split(' at ')[0]
        title = title.split(' in ')[0].split(',')[0]
        name_parts = title
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

    def _extract_images_from_soup(
        self, soup: BeautifulSoup, actress_id: str
    ) -> List[str]:
        """Extract HD images from HTML soup"""
        images = []
        seen: Set[str] = set()

        for img_tag in soup.find_all('img'):
            img_src = self._extract_thumbnail(img_tag)
            is_thumb = img_src and img_src.endswith('t.jpg')
            is_not_thumb_file = not img_src.endswith('thumb.jpg')
            if img_src and is_thumb and is_not_thumb_file:
                hd_src = img_src[:-5] + '.jpg'
                if hd_src not in seen:
                    images.append(hd_src)
                    seen.add(hd_src)

        fallback = f"https://picsum.photos/seed/{actress_id}/800/1200"
        return images if images else [fallback]

    def _create_actress(
        self, actress_id: str, name: str, thumbnail: str
    ) -> Actress:
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
            slug = parts[3].replace('.aspx', '') if len(parts) > 3 else ''
            gallery_slug = slug
            text = link.get_text(strip=True)
            name = self._extract_actress_name(text) if is_latest else text

            cache_key = f"rh_{gallery_id}"
            absolute_url = self._make_absolute_url(href)
            self._set_cache(f"{cache_key}_url", absolute_url)
            self._set_cache(f"{cache_key}_slug", gallery_slug)
            if is_latest:
                self._set_cache(f"{cache_key}_title", text)
                self._set_cache(f"{cache_key}_is_latest", True)

            base_url = f"https://www.ragalahari.com{href}"
            thumbnail_url = base_url.replace('.aspx', '') + '-thumbnail.jpg'
            thumbnail = image_map.get(href) or thumbnail_url
            return self._create_actress(cache_key, name, thumbnail)

        elif '/stars/profile/' in href and len(parts) >= 5:
            actress_id = parts[3]
            actress_slug = parts[4].replace('.aspx', '')
            name = link.get_text(strip=True)

            cache_key = f"rh_{actress_id}"
            absolute_url = self._make_absolute_url(href)
            self._set_cache(f"{cache_key}_url", absolute_url)
            self._set_cache(f"{cache_key}_slug", actress_slug)

            base_url = f"https://www.ragalahari.com{href}"
            thumbnail_url = base_url.replace('.aspx', '') + '-thumbnail.jpg'
            thumbnail = image_map.get(href) or thumbnail_url
            return self._create_actress(cache_key, name, thumbnail)

        return None

    async def scrape_ragalahari_latest(self) -> List[Actress]:
        """Scrape latest 20 galleries from Ragalahari homepage"""
        # Check cache first
        cached = self._get_cache('latest_galleries')
        if cached:
            return cached

        url = "https://www.ragalahari.com/actress/starzone.aspx"
        actresses = []

        html = await self._fetch_with_retry(url)
        if not html:
            return actresses

        soup = BeautifulSoup(html, 'lxml')
        image_map = self._build_image_map(soup)

        for link in soup.find_all('a', class_='galleryname'):
            href = link.get('href')
            if href and '/actress/' in href:
                actress = self._process_actress_link(link, href, image_map, is_latest=True)
                if actress:
                    actresses.append(actress)

        msg = f"Scraped {len(actresses)} latest galleries"
        print(msg)
        self._set_cache('latest_galleries', actresses)
        return actresses


    async def scrape_ragalahari_by_letter(
        self, letter: str = 'a'
    ) -> List[Actress]:
        """Scrape actresses by first letter (A-Z browsing)"""
        letter = letter.lower()

        # Check cache first
        cache_key = f'letter_{letter}'
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        base = "https://www.ragalahari.com/actress"
        url = (f"{base}/starzonesearch.aspx" if letter == 'a'
               else f"{base}/{letter}/starzonesearch.aspx")

        actresses = []

        html = await self._fetch_with_retry(url)
        if not html:
            return actresses

        soup = BeautifulSoup(html, 'lxml')

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

        msg = f"Scraped {len(actresses)} actresses from letter '{letter}'"
        print(msg)
        self._set_cache(cache_key, actresses)
        return actresses


    async def get_ragalahari_actress_detail(
        self, actress_id: str
    ) -> Optional[ActressDetail]:
        """Get complete actress profile with images and albums"""
        url_key = f"{actress_id}_url"
        slug_key = f"{actress_id}_slug"

        # Get from cache (with TTL check)
        profile_url = self._get_cache(url_key)
        actress_slug = self._get_cache(slug_key)

        if not profile_url or not actress_slug:
            print(f"URL not found in cache for {actress_id}")
            return None

        html = await self._fetch_with_retry(profile_url)
        if not html:
            return None

        soup = BeautifulSoup(html, 'lxml')

        name_elem = soup.find('h1')
        name = (
            name_elem.get_text(strip=True) if name_elem
            else actress_slug.replace('-', ' ').title()
        )

        bio = ""
        bio_elem = soup.find('div', id='bio')
        bio_section = bio_elem or soup.find('section', class_='biography')
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

            has_no_href = not album_href or album_href in seen_urls
            is_not_actress = '/actress/' not in album_href
            if has_no_href or is_not_actress:
                continue

            is_profile = 'profile' in album_href.lower()
            is_search = 'search' in album_href.lower()
            if is_profile or is_search:
                continue

            belongs = self._is_actress_album(
                album_name, album_href, name, actress_slug
            )
            if not belongs:
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

        self._set_cache(f"{actress_id}_albums", albums)

        images = []
        is_from_latest = self._get_cache(f"{actress_id}_is_latest")
        is_from_latest = is_from_latest or False

        if is_from_latest:
            images = self._extract_images_from_soup(soup, actress_id)

        album_objects = [
            Album(
                name=album['name'],
                url=album['url'],
                thumbnail=album.get('thumbnail')
            )
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

        img_cnt = len(images)
        alb_cnt = len(albums)
        print(f"Scraped detail for {name}: {img_cnt} images, {alb_cnt} albums")
        return detail

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
                born_info = text[born_start:born_end]
                birth_info = born_info.replace('Born:', '').strip()
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
        last_name_idx = -1
        last_name = name_parts[last_name_idx].lower() if len(name_parts) > 1 else ""

        slug_in_url = False
        if actress_slug:
            slug_in_url = actress_slug.lower() in album_url_lower

        url_parts = album_href.split('/')[-1]
        url_parts = url_parts.replace('.aspx', '').split('-')
        name_parts = actress_slug.split('-') if actress_slug else []

        matching_parts = sum(1 for part in name_parts if part in url_parts)
        threshold = len(name_parts) * 0.6
        has_similar_slug = matching_parts >= threshold

        return (
            (first_name and first_name in album_name_lower) or
            (last_name and last_name in album_name_lower) or
            slug_in_url or
            has_similar_slug
        )


    async def get_ragalahari_actress_albums(
        self, actress_id: str
    ) -> List[dict]:
        """Get all albums for an actress"""
        cache_key = f"{actress_id}_albums"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        detail = await self.get_ragalahari_actress_detail(actress_id)
        if detail:
            cached = self._get_cache(cache_key)
            if cached:
                return cached

        return []

    async def _extract_pagination_urls(
        self, soup: BeautifulSoup, base_url: str
    ) -> List[str]:
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

    async def _scrape_album_page(self, page_url: str) -> List[str]:
        """Scrape images from a single album page"""
        html = await self._fetch_with_retry(page_url)
        return self._filter_images(html) if html else []

    async def get_ragalahari_album_photos(self, album_url: str) -> List[str]:
        """Get all high-quality photos from an album with pagination support"""
        html = await self._fetch_with_retry(album_url)
        if not html:
            return []

        soup = BeautifulSoup(html, 'lxml')
        pagination_urls = await self._extract_pagination_urls(
            soup, album_url
        )

        if len(pagination_urls) == 1:
            photos = self._filter_images(html)
            photos.sort(
                key=lambda url: int(m.group(1))
                if (m := IMAGE_NUMBER_PATTERN.search(url)) else 0
            )
            msg = f"Scraped {len(photos)} photos from album: {album_url}"
            print(msg)
            return photos

        page_count = len(pagination_urls)
        print(f"Found {page_count} pages for album: {album_url}")

        page_photos_list = await gather(
            *[self._scrape_album_page(url) for url in pagination_urls]
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
        photo_cnt = len(all_photos)
        page_cnt = len(pagination_urls)
        msg = f"Scraped {photo_cnt} photos across {page_cnt} pages: {album_url}"
        print(msg)
        return all_photos
