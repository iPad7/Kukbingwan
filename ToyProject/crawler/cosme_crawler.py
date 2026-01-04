"""
@cosme 사이트에서 라네즈(Laneige) 제품 정보를 크롤링하는 모듈

@cosme URL 구조:
- 검색 1페이지: https://cosmeet.cosme.net/product/search?fw=laneige
- 검색 2페이지+: https://cosmeet.cosme.net/product/search/page/{page}/srt/4/fw/laneige
- 제품 상세: https://www.cosme.net/products/{product_id}
- 제품 리뷰: https://www.cosme.net/products/{product_id}/review
"""
import time
import re
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field, asdict

import requests
from bs4 import BeautifulSoup
from loguru import logger
from tqdm import tqdm

import sys
sys.path.append(str(__file__).rsplit("/", 2)[0])
from config import CrawlerConfig, config


@dataclass
class ProductInfo:
    """제품 정보 데이터 클래스"""
    product_id: str
    product_name: str
    brand_name: str
    category: str
    price: Optional[int]
    ranking: Optional[int]
    rating: Optional[float]
    review_count: int
    sales_count: Optional[int]
    product_url: str
    image_url: Optional[str]
    crawled_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ReviewInfo:
    """리뷰 정보 데이터 클래스"""
    review_id: str
    product_id: str
    user_id: str
    rating: float
    title: Optional[str]
    content: str
    helpful_count: int
    posted_at: Optional[str]
    crawled_at: str = field(default_factory=lambda: datetime.now().isoformat())


class CosmeCrawler:
    """@cosme 크롤러"""
    
    def __init__(self, crawler_config: Optional[CrawlerConfig] = None):
        self.config = crawler_config or config.crawler
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        
    def _request(self, url: str) -> Optional[BeautifulSoup]:
        """HTTP 요청을 수행하고 BeautifulSoup 객체 반환"""
        try:
            logger.debug(f"Requesting: {url}")
            response = self.session.get(url, timeout=self.config.timeout)
            response.raise_for_status()
            time.sleep(self.config.request_delay)
            return BeautifulSoup(response.text, "lxml")
        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return None
    
    def _extract_number(self, text: str) -> Optional[int]:
        """텍스트에서 숫자 추출"""
        if not text:
            return None
        # 쉼표 제거 후 숫자 추출
        cleaned = text.replace(",", "").replace("，", "")
        numbers = re.findall(r"\d+", cleaned)
        return int(numbers[0]) if numbers else None
    
    def _extract_float(self, text: str) -> Optional[float]:
        """텍스트에서 소수 추출"""
        if not text:
            return None
        numbers = re.findall(r"[\d.]+", text)
        return float(numbers[0]) if numbers else None

    def get_product_search_url(self, keyword: str, page: int = 1) -> str:
        """제품 검색 URL 생성
        
        @cosme URL 패턴:
        - 1페이지: https://cosmeet.cosme.net/product/search?fw=laneige
        - 2페이지+: https://cosmeet.cosme.net/product/search/page/{page-1}/srt/4/fw/laneige
        """
        if page == 1:
            return f"{self.config.base_url}/product/search?fw={keyword}"
        else:
            # 2페이지는 page/1, 3페이지는 page/2 ... (0-indexed)
            return f"{self.config.base_url}/product/search/page/{page-1}/srt/4/fw/{keyword}"
    
    def get_product_detail_url(self, product_id: str) -> str:
        """제품 상세 페이지 URL 생성"""
        return f"{self.config.detail_base_url}/products/{product_id}"
    
    def get_reviews_url(self, product_id: str, page: int = 1) -> str:
        """제품 리뷰 페이지 URL 생성"""
        if page == 1:
            return f"{self.config.detail_base_url}/products/{product_id}/review"
        else:
            return f"{self.config.detail_base_url}/products/{product_id}/review/page/{page}"
    
    def crawl_product_list(self) -> list[ProductInfo]:
        """브랜드의 제품 목록을 크롤링"""
        products = []
        seen_product_ids = set()  # 중복 제거용
        page = 1
        
        logger.info(f"Starting to crawl {self.config.brand_name} products...")
        
        while len(products) < self.config.max_products:
            url = self.get_product_search_url(self.config.brand_name, page)
            soup = self._request(url)
            
            if not soup:
                break
            
            # cosmeet.cosme.net 검색 결과 페이지의 제품 카드 선택자
            # 실제 사이트 구조에 맞게 여러 선택자 시도
            product_cards = soup.select("article.product-card")
            
            if not product_cards:
                product_cards = soup.select("[class*='product-card']")
            
            if not product_cards:
                product_cards = soup.select(".search-result-item, .item-card")
            
            if not product_cards:
                # 링크 기반으로 제품 찾기
                product_cards = soup.select("a[href*='/products/']")
                if product_cards:
                    # 부모 요소를 카드로 사용
                    product_cards = [link.find_parent() for link in product_cards if link.find_parent()]
                    product_cards = [p for p in product_cards if p]  # None 제거
            
            if not product_cards:
                logger.warning(f"No products found on page {page}. Trying alternative parsing...")
                # HTML에서 직접 제품 정보 추출 시도
                products_from_html = self._extract_products_from_html(soup)
                for p in products_from_html:
                    if p.product_id not in seen_product_ids:
                        seen_product_ids.add(p.product_id)
                        products.append(p)
                        if len(products) >= self.config.max_products:
                            break
                break
            
            parsed_count = 0
            for card in product_cards:
                if len(products) >= self.config.max_products:
                    break
                
                try:
                    product = self._parse_product_card(card)
                    if product and product.product_id not in seen_product_ids:
                        # 잘못된 제품명 필터링
                        if self._is_valid_product(product):
                            seen_product_ids.add(product.product_id)
                            products.append(product)
                            parsed_count += 1
                except Exception as e:
                    logger.error(f"Failed to parse product card: {e}")
                    continue
            
            logger.info(f"Page {page}: parsed {parsed_count} products (total: {len(products)})")
            
            if parsed_count == 0:
                logger.warning(f"No new products parsed on page {page}, stopping")
                break
            
            page += 1
            
            # 최대 10페이지까지
            if page > 10:
                break
        
        logger.info(f"Crawled {len(products)} unique products")
        return products
    
    def _is_valid_product(self, product: ProductInfo) -> bool:
        """유효한 제품인지 확인"""
        # 잘못된 제품명 패턴 필터링
        invalid_patterns = [
            "取り扱い店舗",  # 매장 정보
            "購入サイト",    # 구매 사이트
            "もっと見る",    # 더보기
            "ランキング",    # 랭킹
        ]
        for pattern in invalid_patterns:
            if pattern in product.product_name:
                return False
        
        # 너무 짧은 제품명
        if len(product.product_name) < 3:
            return False
        
        return True
    
    def _extract_products_from_html(self, soup: BeautifulSoup) -> list[ProductInfo]:
        """HTML에서 직접 제품 정보 추출 (대체 방법)"""
        products = []
        
        # 제품 링크 패턴으로 찾기
        product_links = soup.find_all("a", href=re.compile(r"/products?/\d+"))
        
        seen_ids = set()
        for link in product_links:
            href = link.get("href", "")
            match = re.search(r"/products?/(\d+)", href)
            if not match:
                continue
            
            product_id = match.group(1)
            if product_id in seen_ids:
                continue
            seen_ids.add(product_id)
            
            # 링크 주변에서 제품명 찾기
            parent = link.find_parent()
            if parent:
                product_name = link.get_text(strip=True)
                if not product_name or len(product_name) < 2:
                    # 이미지의 alt 텍스트에서 찾기
                    img = parent.find("img")
                    if img:
                        product_name = img.get("alt", "Unknown")
                
                # 별점 찾기
                rating = None
                rating_elem = parent.find(string=re.compile(r"\d+\.\d+"))
                if rating_elem:
                    rating = self._extract_float(str(rating_elem))
                
                # 리뷰 수 찾기
                review_count = 0
                review_elem = parent.find(string=re.compile(r"クチコミ|件|review?", re.I))
                if review_elem:
                    review_count = self._extract_number(str(review_elem)) or 0
                
                # 가격 찾기
                price = None
                price_elem = parent.find(string=re.compile(r"[¥￥円]|\d+円"))
                if price_elem:
                    price = self._extract_number(str(price_elem))
                
                product_url = href if href.startswith("http") else f"{self.config.detail_base_url}{href}"
                
                products.append(ProductInfo(
                    product_id=product_id,
                    product_name=product_name[:100] if product_name else "Unknown",
                    brand_name=self.config.brand_name,
                    category="기타",
                    price=price,
                    ranking=None,
                    rating=rating,
                    review_count=review_count,
                    sales_count=None,
                    product_url=product_url,
                    image_url=None,
                ))
        
        return products
    
    def _parse_product_card(self, card: BeautifulSoup) -> Optional[ProductInfo]:
        """제품 카드에서 정보 추출"""
        try:
            # 제품 링크 및 ID
            link = card.select_one("a[href*='/products/']")
            if not link:
                link = card.select_one("a[href*='/product/']")
            if not link:
                link = card if card.name == "a" else card.select_one("a")
            
            if not link:
                return None
            
            href = link.get("href", "")
            product_id_match = re.search(r"/products?/(\d+)", href)
            if not product_id_match:
                return None
            
            product_id = product_id_match.group(1)
            
            # 제품명 - 여러 선택자 시도
            product_name = None
            name_selectors = [
                "h2", "h3", "h4",
                ".product-name", ".item-name", ".title",
                "[class*='name']", "[class*='title']",
            ]
            for selector in name_selectors:
                name_elem = card.select_one(selector)
                if name_elem:
                    product_name = name_elem.get_text(strip=True)
                    if product_name:
                        break
            
            if not product_name:
                # 링크 텍스트 사용
                product_name = link.get_text(strip=True)
            
            if not product_name or len(product_name) < 2:
                # 이미지 alt 텍스트
                img = card.select_one("img")
                if img:
                    product_name = img.get("alt", "Unknown")
            
            # 가격 추출
            price = None
            price_selectors = [".price", "[class*='price']", "span:contains('円')"]
            for selector in price_selectors:
                try:
                    price_elem = card.select_one(selector)
                    if price_elem:
                        price_text = price_elem.get_text()
                        price = self._extract_number(price_text)
                        if price:
                            break
                except:
                    continue
            
            # 별점 추출 (예: "5.3")
            rating = None
            rating_text = card.get_text()
            rating_match = re.search(r"(\d+\.\d+)", rating_text)
            if rating_match:
                rating = float(rating_match.group(1))
            
            # 리뷰 수 추출 (예: "クチコミ3838件" or "3838件")
            review_count = 0
            review_match = re.search(r"クチコミ(\d+)|(\d+)件", rating_text)
            if review_match:
                review_count = int(review_match.group(1) or review_match.group(2))
            
            # 카테고리 추출
            category = "기타"
            category_elem = card.select_one("[class*='category'], .tag")
            if category_elem:
                category = category_elem.get_text(strip=True)
            
            # 랭킹 추출
            ranking = None
            rank_elem = card.select_one("[class*='rank'], .ranking")
            if rank_elem:
                ranking = self._extract_number(rank_elem.get_text())
            
            # 이미지 URL
            image_url = None
            img_elem = card.select_one("img")
            if img_elem:
                image_url = img_elem.get("src") or img_elem.get("data-src")
            
            # 제품 상세 URL 생성
            product_url = self.get_product_detail_url(product_id)
            
            return ProductInfo(
                product_id=product_id,
                product_name=product_name[:200] if product_name else "Unknown",
                brand_name=self.config.brand_name,
                category=category,
                price=price,
                ranking=ranking,
                rating=rating,
                review_count=review_count,
                sales_count=None,
                product_url=product_url,
                image_url=image_url,
            )
        except Exception as e:
            logger.error(f"Error parsing product card: {e}")
            return None
    
    def crawl_product_detail(self, product: ProductInfo) -> ProductInfo:
        """제품 상세 페이지에서 추가 정보 크롤링"""
        soup = self._request(product.product_url)
        
        if not soup:
            return product
        
        try:
            page_text = soup.get_text()
            
            # 별점 추출 (예: "5.3" - @cosme는 7점 만점)
            # 별점은 항상 1자리.1자리 형식 (예: 5.3, 4.8)
            # "5.3292.1pt" 같은 경우를 피하기 위해 경계 조건 추가
            rating_patterns = [
                r"(?<!\d)([0-6]\.\d)(?!\d)",  # 0.x ~ 6.x (7점 만점이므로)
                r"評価[：:\s]*(\d\.\d)",  # "評価: 5.3" 형식
            ]
            for pattern in rating_patterns:
                match = re.search(pattern, page_text)
                if match:
                    try:
                        rating = float(match.group(1))
                        if 0 <= rating <= 7:
                            product.rating = rating
                            break
                    except ValueError:
                        continue
            
            # 별점이 아직 없으면 요소에서 시도
            if not product.rating:
                # 별점 관련 요소 찾기
                for selector in ["[class*='rating']", "[class*='score']", "[class*='average']"]:
                    rating_elem = soup.select_one(selector)
                    if rating_elem:
                        elem_text = rating_elem.get_text()
                        # 숫자.숫자 패턴만 추출
                        match = re.search(r"(?<!\d)(\d\.\d)(?!\d)", elem_text)
                        if match:
                            try:
                                rating = float(match.group(1))
                                if 0 <= rating <= 7:
                                    product.rating = rating
                                    break
                            except ValueError:
                                continue
            
            # 리뷰 수 추출 (예: "クチコミ3838件" 또는 "3838件")
            review_patterns = [
                r"クチコミ\s*(\d+)",  # "クチコミ3838"
                r"(\d+)\s*件",  # "3838件"
                r"レビュー\s*(\d+)",  # "レビュー3838"
            ]
            for pattern in review_patterns:
                match = re.search(pattern, page_text)
                if match:
                    product.review_count = int(match.group(1))
                    break
            
            # 카테고리 추출 (breadcrumb에서)
            breadcrumb = soup.select(".breadcrumb a, nav a")
            if breadcrumb and len(breadcrumb) > 1:
                # 마지막에서 두 번째가 보통 카테고리
                category = breadcrumb[-2].get_text(strip=True) if len(breadcrumb) >= 2 else None
                if category and len(category) > 1 and "LANEIGE" not in category.upper():
                    product.category = category
            
            # 가격 추출
            if not product.price:
                price_match = re.search(r"(\d{1,3}(?:,\d{3})*)\s*円", page_text)
                if price_match:
                    product.price = int(price_match.group(1).replace(",", ""))
            
            # 제품명 업데이트 (더 정확한 이름)
            title_elem = soup.select_one("h1, [class*='product-name'], [class*='title']")
            if title_elem:
                full_name = title_elem.get_text(strip=True)
                # 더 정확한 이름인지 확인 (불필요한 텍스트 제외)
                if full_name and "商品情報" not in full_name:
                    if len(full_name) > 3 and len(full_name) < 100:
                        product.product_name = full_name
                    
        except Exception as e:
            logger.error(f"Error parsing product detail for {product.product_id}: {e}")
        
        return product
    
    def crawl_reviews(self, product: ProductInfo) -> list[ReviewInfo]:
        """제품의 리뷰 크롤링"""
        reviews = []
        page = 1
        
        logger.info(f"Crawling reviews for: {product.product_name}")
        
        while len(reviews) < self.config.max_reviews_per_product:
            review_url = self.get_reviews_url(product.product_id, page)
            soup = self._request(review_url)
            
            if not soup:
                break
            
            # @cosme 리뷰 페이지 구조: div.review-sec
            review_cards = soup.select("div.review-sec")
            
            if not review_cards:
                logger.debug(f"No reviews found on page {page}")
                break
            
            parsed_count = 0
            for card in review_cards:
                if len(reviews) >= self.config.max_reviews_per_product:
                    break
                
                try:
                    review = self._parse_review_card(card, product.product_id)
                    if review:
                        reviews.append(review)
                        parsed_count += 1
                except Exception as e:
                    logger.error(f"Failed to parse review: {e}")
                    continue
            
            if parsed_count == 0:
                break
            
            page += 1
            
            # 다음 페이지 확인
            next_page = soup.select_one("a[rel='next'], .pagination .next, a.next")
            if not next_page:
                break
        
        logger.info(f"Crawled {len(reviews)} reviews for {product.product_name}")
        return reviews
    
    def _parse_review_card(self, card: BeautifulSoup, product_id: str) -> Optional[ReviewInfo]:
        """리뷰 카드에서 정보 추출 (@cosme 구조에 맞춤)"""
        try:
            # 리뷰 내용 먼저 확인 (p.read)
            content_elem = card.select_one("p.read")
            content = content_elem.get_text(strip=True) if content_elem else ""
            
            # "続きを読む" 제거
            if "続きを読む" in content:
                content = content.replace("続きを読む", "").strip()
            
            if not content or len(content) < 5:
                return None
            
            # 리뷰 ID (내용 해시)
            review_id = str(abs(hash(content[:50])))
            
            # 사용자 이름 (span.reviewer-name)
            user_elem = card.select_one("span.reviewer-name")
            user_id = user_elem.get_text(strip=True) if user_elem else "anonymous"
            
            # 별점 (p.reviewer-rating에서 첫 번째 숫자)
            rating = 0.0
            rating_elem = card.select_one("p.reviewer-rating")
            if rating_elem:
                rating_text = rating_elem.get_text(strip=True)
                # 첫 번째 숫자가 별점 (예: "7購入品リピート" -> 7)
                match = re.match(r"(\d+)", rating_text)
                if match:
                    rating = float(match.group(1))
            
            # 리뷰 제목은 @cosme에서 보통 없음
            title = None
            
            # 도움됨 수 (いいね 등)
            helpful_count = 0
            helpful_elem = card.select_one("[class*='like'], [class*='good'], [class*='helpful']")
            if helpful_elem:
                helpful_count = self._extract_number(helpful_elem.get_text()) or 0
            
            # 작성일 (p.mobile-date)
            posted_at = None
            date_elem = card.select_one("p.mobile-date, [class*='date'], time")
            if date_elem:
                posted_at = date_elem.get_text(strip=True)
            
            return ReviewInfo(
                review_id=str(review_id),
                product_id=product_id,
                user_id=user_id[:50] if user_id else "anonymous",
                rating=rating,
                title=title,
                content=content[:2000],  # 리뷰 내용 길이 제한
                helpful_count=helpful_count,
                posted_at=posted_at,
            )
        except Exception as e:
            logger.error(f"Error parsing review card: {e}")
            return None
    
    def crawl_all(self, include_reviews: bool = True) -> tuple[list[ProductInfo], list[ReviewInfo]]:
        """전체 크롤링 실행"""
        logger.info("=" * 50)
        logger.info(f"Starting full crawl for {self.config.brand_name}")
        logger.info("=" * 50)
        
        # 제품 목록 크롤링
        products = self.crawl_product_list()
        
        if not products:
            logger.warning("No products found. Check if URL structure has changed.")
            return [], []
        
        # 상세 정보 크롤링
        logger.info("Crawling product details...")
        for i, product in enumerate(tqdm(products, desc="Product details")):
            products[i] = self.crawl_product_detail(product)
        
        # 리뷰 크롤링
        all_reviews = []
        if include_reviews:
            for product in tqdm(products, desc="Reviews"):
                reviews = self.crawl_reviews(product)
                all_reviews.extend(reviews)
        
        logger.info("=" * 50)
        logger.info(f"Crawl complete: {len(products)} products, {len(all_reviews)} reviews")
        logger.info("=" * 50)
        
        return products, all_reviews
    
    def to_dict_list(self, items: list) -> list[dict]:
        """데이터 클래스 리스트를 딕셔너리 리스트로 변환"""
        return [asdict(item) for item in items]


if __name__ == "__main__":
    # 테스트 실행
    from loguru import logger
    import sys
    
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")
    
    crawler = CosmeCrawler()
    
    # URL 테스트
    print("=== URL 테스트 ===")
    print(f"검색 1페이지: {crawler.get_product_search_url('laneige', 1)}")
    print(f"검색 2페이지: {crawler.get_product_search_url('laneige', 2)}")
    print(f"검색 3페이지: {crawler.get_product_search_url('laneige', 3)}")
    print(f"제품 상세: {crawler.get_product_detail_url('10220558')}")
    print(f"리뷰 1페이지: {crawler.get_reviews_url('10220558', 1)}")
    print(f"리뷰 2페이지: {crawler.get_reviews_url('10220558', 2)}")
    print()
    
    # 크롤링 테스트
    products, reviews = crawler.crawl_all(include_reviews=False)  # 빠른 테스트를 위해 리뷰 제외
    
    print(f"\n총 {len(products)}개 제품, {len(reviews)}개 리뷰 수집 완료")
    
    if products:
        print("\n첫 번째 제품:")
        for key, value in asdict(products[0]).items():
            print(f"  {key}: {value}")
