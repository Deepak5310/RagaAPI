"""Web scraper for fetching actress information from Ragalahari.com"""

import re
import traceback
from typing import List, Optional, Dict, Set
from datetime import datetime

import aiohttp
from bs4 import BeautifulSoup

from .models import Actress, ActressDetail, ScraperSource, Album
from .config import settings


class ActressScraper:
    """Main scraper class for fetching actress data from Ragalahari.com"""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache: Dict[str, any] = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": settings.USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT)
            )
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    @staticmethod
    def _make_absolute_url(url: str) -> str:
        if url.startswith('//'):
            return f"https:{url}"
        if url.startswith('/'):
            return f"https://www.ragalahari.com{url}"
        if url.startswith('http'):
            return url
        return f"https://www.ragalahari.com/{url}"

    @staticmethod
    def _extract_actress_name(gallery_title: str) -> str:
        name_parts = gallery_title.split(' at ')[0].split(' in ')[0].split(',')[0]
        return (name_parts.replace('Actress ', '')
                .replace('Heroine ', '')
                .replace('Model ', '')
                .strip())

    def _extract_thumbnail(self, img_tag) -> Optional[str]:
        if not img_tag:
            return None

        img_src = (
            img_tag.get('data-srcset') or
            img_tag.get('srcset') or
            img_tag.get('data-src') or
            img_tag.get('src')
        )

        if not img_src or img_src == '/img/galthumb.jpg':
            return None

        return self._make_absolute_url(img_src)

    def _build_image_map(self, soup: BeautifulSoup) -> Dict[str, str]:
        image_map = {}
        img_links = soup.find_all('a', class_='galimg')

        for img_link in img_links:
            href = img_link.get('href')
            is_valid_href = (
                href and
                ('/actress/' in href or '/stars/profile/' in href) and
                href not in image_map
            )
            if is_valid_href:
                thumbnail = self._extract_thumbnail(img_link.find('img'))
                if thumbnail:
                    image_map[href] = thumbnail

        return image_map

    def _extract_images_from_soup(self, soup: BeautifulSoup, actress_id: str) -> List[str]:
        images = []
        seen_images: Set[str] = set()

        for img_tag in soup.find_all('img'):
            img_src = self._extract_thumbnail(img_tag)

            if not img_src:
                continue

            if img_src.endswith('t.jpg') and not img_src.endswith('thumb.jpg'):
                hd_src = img_src[:-5] + '.jpg'
                if hd_src not in seen_images:
                    images.append(hd_src)
                    seen_images.add(hd_src)

        if not images:
            images = [f"https://picsum.photos/seed/{actress_id}/800/1200"]

        return images

    def _create_actress(self, actress_id: str, name: str, thumbnail: str) -> Actress:
        return Actress(
            id=actress_id,
            name=name,
            thumbnail=thumbnail,
            age=None,
            nationality="Indian",
            profession="Actress",
            source=ScraperSource.RAGALAHARI
        )

    async def scrape_ragalahari_latest(self) -> List[Actress]:
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
                name_links = soup.find_all('a', class_='galleryname')

                for link in name_links:
                    href = link.get('href')
                    gallery_title = link.get_text(strip=True)

                    if not gallery_title or not href or '/actress/' not in href:
                        continue

                    name = self._extract_actress_name(gallery_title)
                    parts = href.split('/')

                    if len(parts) >= 4:
                        gallery_id = parts[2]
                        gallery_slug = parts[3].replace('.aspx', '') if len(parts) > 3 else ''
                        gallery_url = self._make_absolute_url(href)

                        cache_key = f"rh_{gallery_id}"
                        self.cache[f"{cache_key}_url"] = gallery_url
                        self.cache[f"{cache_key}_slug"] = gallery_slug
                        self.cache[f"{cache_key}_title"] = gallery_title
                        self.cache[f"{cache_key}_is_latest"] = True

                        thumbnail = image_map.get(href) or (
                            f"https://www.ragalahari.com"
                            f"{href.replace('.aspx', '')}-thumbnail.jpg"
                        )

                        actress = self._create_actress(cache_key, name, thumbnail)
                        actresses.append(actress)

                print(f"Scraped {len(actresses)} latest galleries")
                return actresses

        except (aiohttp.ClientError, ValueError, KeyError) as e:
            print(f"Error scraping Ragalahari latest: {str(e)}")
            traceback.print_exc()
            return actresses


    async def scrape_ragalahari_by_letter(self, letter: str = 'a') -> List[Actress]:
        letter = letter.lower()
        url = "https://www.ragalahari.com/actress/starzonesearch.aspx" if letter == 'a' \
              else f"https://www.ragalahari.com/actress/{letter}/starzonesearch.aspx"

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
                name_links = soup.find_all('a', class_='galleryname')

                for link in name_links:
                    href = link.get('href')
                    name = link.get_text(strip=True)

                    if not name or not href:
                        continue

                    parts = href.split('/')

                    if '/actress/' in href and len(parts) >= 4:
                        gallery_id = parts[2]
                        gallery_slug = parts[3].replace('.aspx', '') if len(parts) > 3 else ''
                        actress_name = self._extract_actress_name(name)

                        gallery_url = self._make_absolute_url(href)
                        cache_key = f"rh_{gallery_id}"
                        self.cache[f"{cache_key}_url"] = gallery_url
                        self.cache[f"{cache_key}_slug"] = gallery_slug

                        thumbnail = image_map.get(href) or (
                            f"https://www.ragalahari.com"
                            f"{href.replace('.aspx', '')}-thumbnail.jpg"
                        )

                        actress = self._create_actress(cache_key, actress_name, thumbnail)
                        actresses.append(actress)

                    elif '/stars/profile/' in href and len(parts) >= 5:
                        actress_id = parts[3]
                        actress_slug = parts[4].replace('.aspx', '')

                        profile_url = self._make_absolute_url(href)
                        cache_key = f"rh_{actress_id}"
                        self.cache[f"{cache_key}_url"] = profile_url
                        self.cache[f"{cache_key}_slug"] = actress_slug

                        thumbnail = image_map.get(href) or (
                            f"https://www.ragalahari.com"
                            f"{href.replace('.aspx', '')}-thumbnail.jpg"
                        )

                        actress = self._create_actress(cache_key, name, thumbnail)
                        actresses.append(actress)

                print(f"Scraped {len(actresses)} actresses from letter '{letter}'")
                return actresses

        except (aiohttp.ClientError, ValueError, KeyError) as e:
            print(f"Error scraping Ragalahari letter '{letter}': {str(e)}")
            traceback.print_exc()
            return actresses


    async def get_ragalahari_actress_detail(self, actress_id: str) -> Optional[ActressDetail]:
        url_key = f"{actress_id}_url"
        slug_key = f"{actress_id}_slug"

        if url_key not in self.cache:
            print(f"URL not found in cache for {actress_id}")
            return None

        profile_url = self.cache[url_key]
        actress_slug = self.cache[slug_key]
        session = await self._get_session()

        try:
            async with session.get(profile_url) as response:
                if response.status != 200:
                    print(f"Error fetching {profile_url}: Status {response.status}")
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
                            album_name = url_parts[-1].replace('.aspx', '').replace('-', ' ').title()

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

                print(f"Scraped detail for {name}: {len(images)} images, {len(albums)} albums")
                return detail

        except (aiohttp.ClientError, ValueError, KeyError) as e:
            print(f"Error scraping actress detail: {str(e)}")
            traceback.print_exc()
            return None

    def _extract_info(self, text: str, label: str) -> Optional[str]:
        if label in text:
            start = text.find(label)
            end = text.find('\n', start)
            if end > start:
                return text[start:end].replace(label, '').strip()
        return None

    def _extract_birth_date(self, text: str) -> Optional[str]:
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
        album_name_lower = album_name.lower()
        album_url_lower = album_href.lower()

        first_name = actress_name.split()[0].lower() if actress_name else ""
        last_name = actress_name.split()[-1].lower() if actress_name and len(actress_name.split()) > 1 else ""

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
        cache_key = f"{actress_id}_albums"
        if cache_key in self.cache:
            return self.cache[cache_key]

        detail = await self.get_ragalahari_actress_detail(actress_id)
        if detail and cache_key in self.cache:
            return self.cache[cache_key]

        return []

    async def get_ragalahari_album_photos(self, album_url: str) -> List[str]:
        session = await self._get_session()

        try:
            async with session.get(album_url) as response:
                if response.status != 200:
                    print(f"Error fetching album {album_url}: Status {response.status}")
                    return []

                html = await response.text()
                pattern = r'https://starzone\.ragalahari\.com/[^\s"\'<>]+\.jpg'
                matches = re.findall(pattern, html, re.IGNORECASE)

                photos = []
                seen = set()

                for img_url in matches:
                    if img_url.endswith('t.jpg'):
                        img_url = img_url[:-5] + '.jpg'
                    elif img_url.endswith('thumb.jpg'):
                        continue

                    if img_url in seen:
                        continue

                    if 'images.taboola.com' in img_url or 'cdn.taboola.com' in img_url:
                        continue

                    if any(skip in img_url.lower() for skip in ['logo', 'banner', 'icon']):
                        continue

                    seen.add(img_url)
                    photos.append(img_url)

                photos.sort(key=lambda url: int(m.group(1)) if (m := re.search(r'(\d+)\.jpg$', url)) else 0)

                print(f"Scraped {len(photos)} high-quality photos from album: {album_url}")
                return photos

        except (aiohttp.ClientError, ValueError, KeyError) as e:
            print(f"Error scraping album photos: {str(e)}")
            traceback.print_exc()
            return []
