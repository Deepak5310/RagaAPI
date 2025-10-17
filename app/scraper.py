"""
Web scraper for fetching actress information from Ragalahari.com
"""

import re
import hashlib
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
        """Get or create aiohttp session with proper configuration"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": settings.USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT)
            )
        return self.session

    async def close(self):
        """Close the aiohttp session to prevent resource leaks"""
        if self.session and not self.session.closed:
            await self.session.close()

    @staticmethod
    def _generate_id(name: str, source: str) -> str:
        """
        Generate unique ID for actress

        Args:
            name: Actress name
            source: Source identifier

        Returns:
            12-character MD5 hash
        """
        unique_string = f"{name}_{source}".lower()
        return hashlib.md5(unique_string.encode()).hexdigest()[:12]

    @staticmethod
    def _make_absolute_url(url: str) -> str:
        """
        Convert relative or protocol-relative URLs to absolute URLs

        Args:
            url: URL to convert

        Returns:
            Absolute URL
        """
        if url.startswith('//'):
            return f"https:{url}"
        if url.startswith('/'):
            return f"https://www.ragalahari.com{url}"
        if url.startswith('http'):
            return url
        return f"https://www.ragalahari.com/{url}"

    @staticmethod
    def _extract_actress_name(gallery_title: str) -> str:
        """
        Extract clean actress name from gallery title

        Args:
            gallery_title: Gallery title like "Actress Name at Event"

        Returns:
            Clean actress name
        """
        # Pattern: "Actress Name at Event" or "Actress Name in Dress"
        name_parts = gallery_title.split(' at ')[0].split(' in ')[0].split(',')[0]
        # Remove common prefixes
        return (name_parts.replace('Actress ', '')
                .replace('Heroine ', '')
                .replace('Model ', '')
                .strip())

    def _extract_thumbnail(self, img_tag) -> Optional[str]:
        """
        Extract thumbnail URL from img tag

        Args:
            img_tag: BeautifulSoup img tag

        Returns:
            Absolute thumbnail URL or None
        """
        if not img_tag:
            return None

        # Try multiple attributes in priority order
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
        """
        Build a mapping of gallery URLs to their thumbnail images

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            Dictionary mapping href to thumbnail URL
        """
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

    # Ragalahari scraping methods
    async def scrape_ragalahari_latest(self) -> List[Actress]:
        """
        Scrape latest actress galleries from Ragalahari.com main page

        Returns:
            List of latest Actress objects with their latest gallery info
        """
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

                # Build image mapping
                image_map = self._build_image_map(soup)

                # Find all gallery name links
                name_links = soup.find_all('a', class_='galleryname')

                for link in name_links:
                    href = link.get('href')
                    gallery_title = link.get_text(strip=True)

                    if not gallery_title or not href or '/actress/' not in href:
                        continue

                    # Extract actress name from gallery title
                    name = self._extract_actress_name(gallery_title)

                    # Extract ID from URL: /actress/{id}/{gallery-name}.aspx
                    parts = href.split('/')
                    if len(parts) >= 4:
                        gallery_id = parts[2]  # ID is at index 2
                        gallery_slug = parts[3].replace('.aspx', '') if len(parts) > 3 else ''

                        # Full gallery URL
                        gallery_url = self._make_absolute_url(href)

                        # Cache gallery information
                        cache_key = f"rh_{gallery_id}"
                        self.cache[f"{cache_key}_url"] = gallery_url
                        self.cache[f"{cache_key}_slug"] = gallery_slug
                        self.cache[f"{cache_key}_title"] = gallery_title

                        # Get thumbnail from image_map or use fallback
                        thumbnail = image_map.get(href) or (
                            f"https://www.ragalahari.com"
                            f"{href.replace('.aspx', '')}-thumbnail.jpg"
                        )

                        actress = Actress(
                            id=cache_key,
                            name=name,
                            thumbnail=thumbnail,
                            age=None,
                            nationality="Indian",
                            profession="Actress",
                            source=ScraperSource.RAGALAHARI
                        )
                        actresses.append(actress)

                print(f"Scraped {len(actresses)} latest galleries")
                return actresses

        except (aiohttp.ClientError, ValueError, KeyError) as e:
            print(f"Error scraping Ragalahari latest: {str(e)}")
            traceback.print_exc()
            return actresses

    async def scrape_ragalahari_by_letter(self, letter: str = 'a') -> List[Actress]:
        """
        Scrape actresses from Ragalahari.com by letter (A-Z)
        Uses the starzonesearch.aspx page for browsing all galleries

        Args:
            letter: Letter to scrape (a-z), default 'a'

        Returns:
            List of Actress objects
        """
        letter = letter.lower()

        # All letters use starzonesearch.aspx (accessible from "View More" on main page)
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

                # Check if "Galleries" section exists and use it if available
                galleries_section = soup.find('div', {'id': 'galleries'})
                if galleries_section:
                    soup = galleries_section

                # Build image mapping
                image_map = self._build_image_map(soup)

                # Find all actress profile/gallery name links
                name_links = soup.find_all('a', class_='galleryname')

                for link in name_links:
                    href = link.get('href')
                    name = link.get_text(strip=True)

                    if not name or not href:
                        continue

                    parts = href.split('/')

                    # Check if it's a gallery link or profile link
                    if '/actress/' in href and len(parts) >= 4:
                        # Gallery link format: /actress/{id}/{gallery}.aspx
                        gallery_id = parts[2]
                        gallery_slug = parts[3].replace('.aspx', '') if len(parts) > 3 else ''

                        # Extract actress name from gallery title
                        actress_name = self._extract_actress_name(name)

                        gallery_url = self._make_absolute_url(href)
                        cache_key = f"rh_{gallery_id}"
                        self.cache[f"{cache_key}_url"] = gallery_url
                        self.cache[f"{cache_key}_slug"] = gallery_slug

                        thumbnail = image_map.get(href) or (
                            f"https://www.ragalahari.com"
                            f"{href.replace('.aspx', '')}-thumbnail.jpg"
                        )

                        actress = Actress(
                            id=cache_key,
                            name=actress_name,
                            thumbnail=thumbnail,
                            age=None,
                            nationality="Indian",
                            profession="Actress",
                            source=ScraperSource.RAGALAHARI
                        )
                        actresses.append(actress)

                    elif '/stars/profile/' in href and len(parts) >= 5:
                        # Profile link format: /stars/profile/{id}/{name}.aspx
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

                        actress = Actress(
                            id=cache_key,
                            name=name,
                            thumbnail=thumbnail,
                            age=None,
                            nationality="Indian",
                            profession="Actress",
                            source=ScraperSource.RAGALAHARI
                        )
                        actresses.append(actress)

                print(f"Scraped {len(actresses)} actresses from letter '{letter}'")
                return actresses

        except (aiohttp.ClientError, ValueError, KeyError) as e:
            print(f"Error scraping Ragalahari letter '{letter}': {str(e)}")
            traceback.print_exc()
            return actresses

    def _extract_albums(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """
        Extract photo albums from actress page

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            List of album dictionaries with name, url, thumbnail
        """
        # First, create a map of gallery URLs to their thumbnails
        gallery_map = self._build_image_map(soup)

        # Find gallery names
        name_links = soup.find_all('a', class_='galleryname')

        albums = []
        seen_urls: Set[str] = set()

        for link in name_links:
            album_href = link.get('href')
            album_name = link.get_text(strip=True)

            if not album_href or album_href in seen_urls:
                continue

            # Only process actress gallery links
            if '/actress/' not in album_href:
                continue

            # Skip profile pages
            if 'profile' in album_href.lower() or 'search' in album_href.lower():
                continue

            # Extract name from URL if not available
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

        return albums

    def _extract_images_for_latest(
        self,
        soup: BeautifulSoup,
        albums: List[Dict[str, str]],
        actress_id: str
    ) -> List[str]:
        """
        Extract high-quality images for Latest/Home page galleries

        Args:
            soup: BeautifulSoup object of the page
            albums: List of album dictionaries
            actress_id: Actress ID for fallback placeholder

        Returns:
            List of image URLs
        """
        images = []
        seen_images: Set[str] = set()

        # Find ALL images ending with t.jpg (low quality) and convert to HD
        all_img_tags = soup.find_all('img')

        for img_tag in all_img_tags:
            img_src = self._extract_thumbnail(img_tag)

            if not img_src:
                continue

            # Convert t.jpg to .jpg for HD quality
            # Pattern: ...1t.jpg -> ...1.jpg, ...2t.jpg -> ...2.jpg
            if img_src.endswith('t.jpg') and not img_src.endswith('thumb.jpg'):
                hd_src = img_src[:-5] + '.jpg'  # Remove 't.jpg' and add '.jpg'
                if hd_src not in seen_images:
                    images.append(hd_src)
                    seen_images.add(hd_src)
            # Skip thumbnail images (they're for galleries)
            elif not img_src.endswith('thumb.jpg'):
                # Add other high quality images directly
                if 'szcdn.ragalahari.com' in img_src and img_src not in seen_images:
                    images.append(img_src)
                    seen_images.add(img_src)

        # If no images found, try album thumbnails as fallback
        if not images and albums:
            for album in albums[:5]:
                thumb = album.get('thumbnail')
                if thumb:
                    # Convert thumbnail to HD image
                    if thumb.endswith('thumb.jpg'):
                        hd_img = thumb.replace('thumb.jpg', '1.jpg')
                        images.append(hd_img)
                    elif thumb not in seen_images:
                        images.append(thumb)

        # Final fallback: use placeholder
        if not images:
            images = [f"https://picsum.photos/seed/{actress_id}/800/1200"]

        return images

    async def get_ragalahari_actress_detail(self, actress_id: str) -> Optional[ActressDetail]:
        """
        Get detailed information about a specific actress from Ragalahari

        Args:
            actress_id: Actress ID (format: rh_{id})

        Returns:
            ActressDetail object or None
        """
        # Check if we have the URL in cache
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
                    print(
                        f"Error fetching {profile_url}: "
                        f"Status {response.status}"
                    )
                    return None

                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                # Extract actress name from title or h1
                name_elem = soup.find('h1')
                name = (
                    name_elem.get_text(strip=True) if name_elem
                    else actress_slug.replace('-', ' ').title()
                )

                # Extract bio if available
                bio = ""
                bio_section = soup.find('div', id='bio') or soup.find('section', class_='biography')
                if bio_section:
                    paragraphs = bio_section.find_all('p')
                    bio = ' '.join([p.get_text(strip=True) for p in paragraphs[:2]])  # First 2 paragraphs

                # Extract basic info (height, nationality, etc.)
                info_text = soup.get_text()
                height = None
                birth_date = None

                # Try to find height
                if 'Height:' in info_text:
                    height_start = info_text.find('Height:')
                    height_end = info_text.find('\n', height_start)
                    if height_end > height_start:
                        height = info_text[height_start:height_end].replace('Height:', '').strip()

                # Try to find birth date
                if 'Born:' in info_text:
                    born_start = info_text.find('Born:')
                    born_end = info_text.find('\n', born_start)
                    if born_end > born_start:
                        birth_info = info_text[born_start:born_end].replace('Born:', '').strip()
                        # Extract just the date part
                        parts = birth_info.split(',')
                        if len(parts) >= 2:
                            birth_date = ','.join(parts[:2]).strip()

                # Scrape photo galleries/albums using 'galimg' class
                # HTML Pattern: <a class="galimg" href="/actress/166825/...">
                #                   <img srcset="..." data-srcset="..." />
                #               </a>

                # First, create a map of gallery URLs to their thumbnails
                gallery_map = {}
                img_links = soup.find_all('a', class_='galimg')

                for img_link in img_links:
                    href = img_link.get('href')
                    if href and '/actress/' in href and href not in gallery_map:
                        img_tag = img_link.find('img')
                        if img_tag:
                            # Try to get thumbnail from srcset, data-srcset, or src
                            thumbnail = (
                                img_tag.get('data-srcset') or
                                img_tag.get('srcset') or
                                img_tag.get('src')
                            )

                            if thumbnail:
                                # Make absolute URL
                                if thumbnail.startswith('//'):
                                    thumbnail = f"https:{thumbnail}"
                                elif thumbnail.startswith('/'):
                                    thumbnail = f"https://www.ragalahari.com{thumbnail}"
                                elif not thumbnail.startswith('http'):
                                    thumbnail = f"https://www.ragalahari.com/{thumbnail}"

                                gallery_map[href] = thumbnail

                # Now find gallery names using 'galleryname' class
                name_links = soup.find_all('a', class_='galleryname')

                albums = []
                seen_urls = set()

                for link in name_links:
                    album_href = link.get('href')
                    album_name = link.get_text(strip=True)

                    if not album_href or album_href in seen_urls:
                        continue

                    # Only process actress gallery links
                    if '/actress/' not in album_href:
                        continue

                    # Skip profile pages
                    is_unwanted_page = (
                        'profile' in album_href.lower() or
                        'search' in album_href.lower()
                    )
                    if is_unwanted_page:
                        continue

                    # If no name from galleryname, extract from URL
                    if not album_name or len(album_name) < 3:
                        url_parts = album_href.split('/')
                        if len(url_parts) >= 3:
                            album_name = (
                                url_parts[-1]
                                .replace('.aspx', '')
                                .replace('-', ' ')
                                .title()
                            )

                    if album_name and len(album_name) > 3:
                        # Make absolute URL
                        album_url = (
                            f"https://www.ragalahari.com{album_href}"
                            if album_href.startswith('/')
                            else album_href
                        )

                        # Get thumbnail from gallery_map
                        thumbnail = gallery_map.get(album_href)

                        # Fallback: try to construct thumbnail from album structure
                        if not thumbnail:
                            # Try to find associated galimg link
                            for galimg_link in img_links:
                                if galimg_link.get('href') == album_href:
                                    img_tag = galimg_link.find('img')
                                    if img_tag:
                                        thumbnail = (
                                            img_tag.get('data-srcset') or
                                            img_tag.get('srcset') or
                                            img_tag.get('src')
                                        )
                                        if thumbnail and thumbnail.startswith('//'):
                                            thumbnail = f"https:{thumbnail}"
                                    break

                        albums.append({
                            "name": album_name,
                            "url": album_url,
                            "thumbnail": thumbnail
                        })
                        seen_urls.add(album_href)

                # Store albums in cache for later fetching
                self.cache[f"{actress_id}_albums"] = albums

                # Get profile thumbnail/images
                images = []

                # Check if this came from Latest/Home page (has _title in cache)
                # vs Browse by Letter (no _title)
                title_key = f"{actress_id}_title"
                is_from_latest = title_key in self.cache

                # Only fetch images if it's from Latest/Home page
                # Browse by letter pages should NOT show images, only albums
                if is_from_latest:
                    # Latest/Home page - fetch images from the single gallery
                    # Find ALL images ending with t.jpg (low quality) and convert to HD
                    # Look for all img tags in the page
                    all_img_tags = soup.find_all('img')
                    seen_images = set()

                    for img_tag in all_img_tags:
                        # Try to get image URL from various attributes
                        img_src = (
                            img_tag.get('data-srcset') or
                            img_tag.get('srcset') or
                            img_tag.get('data-src') or
                            img_tag.get('src')
                        )

                        if img_src:
                            # Make absolute URL
                            if img_src.startswith('//'):
                                img_src = f"https:{img_src}"
                            elif img_src.startswith('/'):
                                img_src = f"https://www.ragalahari.com{img_src}"
                            elif not img_src.startswith('http'):
                                img_src = f"https://www.ragalahari.com/{img_src}"

                            # Convert t.jpg to .jpg for HD quality
                            # Pattern: ...1t.jpg -> ...1.jpg, ...2t.jpg -> ...2.jpg
                            if img_src.endswith('t.jpg') and not img_src.endswith('thumb.jpg'):
                                hd_src = img_src[:-5] + '.jpg'  # Remove 't.jpg' and add '.jpg'
                                if hd_src not in seen_images:
                                    images.append(hd_src)
                                    seen_images.add(hd_src)
                            # Skip thumbnail images (they're for galleries)
                            elif not img_src.endswith('thumb.jpg'):
                                # Add other high quality images directly
                                if img_src not in seen_images and 'szcdn.ragalahari.com' in img_src:
                                    images.append(img_src)
                                    seen_images.add(img_src)

                    # If no images found, try album thumbnails as fallback
                    if not images:
                        for album in albums[:5]:
                            if album.get('thumbnail'):
                                thumb = album['thumbnail']
                                # Convert thumbnail to HD image
                                if thumb.endswith('thumb.jpg'):
                                    hd_img = thumb.replace('thumb.jpg', '1.jpg')
                                    images.append(hd_img)
                                elif thumb not in seen_images:
                                    images.append(thumb)

                    # Final fallback: use placeholder
                    if not images:
                        images = [f"https://picsum.photos/seed/{actress_id}/800/1200"]

                # If from Browse by Letter, images remains empty []

                # Convert album dicts to Album objects
                album_objects = [
                    Album(
                        name=album['name'],
                        url=album['url'],
                        thumbnail=album.get('thumbnail')
                    )
                    for album in albums
                ]

                # Create detail object
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
                    known_for=[],  # Not needed for Ragalahari
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

    async def get_ragalahari_actress_albums(self, actress_id: str) -> List[dict]:
        """
        Get list of photo albums/galleries for a specific actress

        Args:
            actress_id: Actress ID (format: rh_{id})

        Returns:
            List of album dictionaries with name, url, thumbnail
        """
        # Check cache first
        cache_key = f"{actress_id}_albums"
        if cache_key in self.cache:
            return self.cache[cache_key]

        # If not in cache, fetch detail which will populate albums
        detail = await self.get_ragalahari_actress_detail(actress_id)
        if detail and cache_key in self.cache:
            return self.cache[cache_key]

        return []

    async def get_ragalahari_album_photos(self, album_url: str) -> List[str]:
        """
        Scrape all high-quality photos from a specific album/gallery

        Args:
            album_url: Full URL to the album page

        Returns:
            List of high-quality image URLs
        """
        session = await self._get_session()

        try:
            async with session.get(album_url) as response:
                if response.status != 200:
                    print(f"Error fetching album {album_url}: Status {response.status}")
                    return []

                html = await response.text()

                # Use regex to find all starzone.ragalahari.com image URLs in the HTML
                # Pattern: Find all starzone.ragalahari.com URLs ending with .jpg
                pattern = r'https://starzone\.ragalahari\.com/[^\s"\'<>]+\.jpg'
                matches = re.findall(pattern, html, re.IGNORECASE)

                photos = []
                seen = set()

                for img_url in matches:
                    # Convert low quality (with 't') to high quality first
                    # Pattern: ...1t.jpg -> ...1.jpg,
                    #          ...2t.jpg -> ...2.jpg, etc.
                    if img_url.endswith('t.jpg'):
                        img_url = img_url[:-5] + '.jpg'  # Remove 't.jpg' and add '.jpg'
                    elif img_url.endswith('thumb.jpg'):
                        # Skip thumb.jpg as it's the main thumbnail, not individual photos
                        continue

                    # Skip if already processed (check after conversion)
                    if img_url in seen:
                        continue

                    # Skip ads from Taboola CDN (images.taboola.com)
                    if 'images.taboola.com' in img_url or 'cdn.taboola.com' in img_url:
                        continue

                    # Skip logo, banner images
                    if any(
                        skip in img_url.lower()
                        for skip in ['logo', 'banner', 'icon']
                    ):
                        continue

                    seen.add(img_url)
                    photos.append(img_url)

                # Sort photos by number in filename for proper order
                def extract_number(url):
                    match = re.search(r'(\d+)\.jpg$', url)
                    return int(match.group(1)) if match else 0

                photos.sort(key=extract_number)

                print(f"Scraped {len(photos)} high-quality photos from album: {album_url}")
                return photos

        except (aiohttp.ClientError, ValueError, KeyError) as e:
            print(f"Error scraping album photos: {str(e)}")
            traceback.print_exc()
            return []
