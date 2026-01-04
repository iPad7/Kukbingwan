"""
Parquet 기반 데이터 저장 모듈
시계열 데이터 누적 저장 지원
"""
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from loguru import logger

import sys
sys.path.append(str(__file__).rsplit("/", 2)[0])
from config import DatabaseConfig, config


class ParquetStorage:
    """Parquet 기반 데이터 저장소"""
    
    def __init__(self, db_config: Optional[DatabaseConfig] = None):
        self.config = db_config or config.database
        self.data_dir = Path(self.config.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 파일 경로 설정
        self.products_path = self.data_dir / self.config.products_file
        self.reviews_path = self.data_dir / self.config.reviews_file
        self.rankings_path = self.data_dir / self.config.rankings_file
    
    def _append_to_parquet(self, df: pd.DataFrame, file_path: Path) -> None:
        """기존 Parquet 파일에 데이터 추가 (시계열 누적)"""
        if file_path.exists():
            # 기존 데이터 로드
            existing_df = pd.read_parquet(file_path)
            # 새 데이터 추가
            combined_df = pd.concat([existing_df, df], ignore_index=True)
            logger.info(f"Appending {len(df)} rows to existing {len(existing_df)} rows")
        else:
            combined_df = df
            logger.info(f"Creating new file with {len(df)} rows")
        
        # 저장
        combined_df.to_parquet(
            file_path,
            compression=self.config.compression,
            index=False
        )
        logger.info(f"Saved to {file_path}")
    
    def save_products(self, products: list[dict]) -> None:
        """제품 데이터 저장"""
        if not products:
            logger.warning("No products to save")
            return
        
        df = pd.DataFrame(products)
        
        # 크롤링 시간 추가 (이미 있는 경우 유지)
        if "crawled_at" not in df.columns:
            df["crawled_at"] = datetime.now().isoformat()
        
        self._append_to_parquet(df, self.products_path)
        logger.info(f"Saved {len(products)} products")
    
    def save_reviews(self, reviews: list[dict]) -> None:
        """리뷰 데이터 저장"""
        if not reviews:
            logger.warning("No reviews to save")
            return
        
        df = pd.DataFrame(reviews)
        
        if "crawled_at" not in df.columns:
            df["crawled_at"] = datetime.now().isoformat()
        
        self._append_to_parquet(df, self.reviews_path)
        logger.info(f"Saved {len(reviews)} reviews")
    
    def save_rankings(self, rankings: list[dict]) -> None:
        """랭킹 히스토리 저장"""
        if not rankings:
            logger.warning("No rankings to save")
            return
        
        df = pd.DataFrame(rankings)
        
        if "recorded_at" not in df.columns:
            df["recorded_at"] = datetime.now().isoformat()
        
        self._append_to_parquet(df, self.rankings_path)
        logger.info(f"Saved {len(rankings)} ranking records")
    
    def extract_rankings_from_products(self, products: list[dict]) -> list[dict]:
        """제품 데이터에서 랭킹 히스토리 추출"""
        rankings = []
        recorded_at = datetime.now().isoformat()
        
        for product in products:
            if product.get("ranking") is not None:
                rankings.append({
                    "product_id": product["product_id"],
                    "product_name": product["product_name"],
                    "ranking": product["ranking"],
                    "rating": product.get("rating"),
                    "review_count": product.get("review_count"),
                    "sales_count": product.get("sales_count"),
                    "recorded_at": recorded_at,
                })
        
        return rankings
    
    def load_products(self, latest_only: bool = False) -> pd.DataFrame:
        """제품 데이터 로드"""
        if not self.products_path.exists():
            logger.warning("Products file not found")
            return pd.DataFrame()
        
        df = pd.read_parquet(self.products_path)
        
        if latest_only and "crawled_at" in df.columns:
            # 각 제품의 최신 데이터만 반환
            df["crawled_at"] = pd.to_datetime(df["crawled_at"])
            df = df.sort_values("crawled_at").groupby("product_id").last().reset_index()
        
        return df
    
    def load_reviews(self, product_id: Optional[str] = None) -> pd.DataFrame:
        """리뷰 데이터 로드"""
        if not self.reviews_path.exists():
            logger.warning("Reviews file not found")
            return pd.DataFrame()
        
        df = pd.read_parquet(self.reviews_path)
        
        if product_id:
            df = df[df["product_id"] == product_id]
        
        return df
    
    def load_rankings(self, product_id: Optional[str] = None) -> pd.DataFrame:
        """랭킹 히스토리 로드"""
        if not self.rankings_path.exists():
            logger.warning("Rankings file not found")
            return pd.DataFrame()
        
        df = pd.read_parquet(self.rankings_path)
        
        if product_id:
            df = df[df["product_id"] == product_id]
        
        return df
    
    def get_ranking_changes(self, product_id: str) -> pd.DataFrame:
        """특정 제품의 랭킹 변화 조회"""
        rankings = self.load_rankings(product_id)
        
        if rankings.empty:
            return rankings
        
        rankings["recorded_at"] = pd.to_datetime(rankings["recorded_at"])
        rankings = rankings.sort_values("recorded_at")
        
        # 변화량 계산
        rankings["ranking_change"] = rankings["ranking"].diff()
        rankings["rating_change"] = rankings["rating"].diff()
        rankings["review_count_change"] = rankings["review_count"].diff()
        
        return rankings
    
    def get_all_ranking_trends(self) -> pd.DataFrame:
        """모든 제품의 랭킹 트렌드 요약"""
        rankings = self.load_rankings()
        
        if rankings.empty:
            return rankings
        
        rankings["recorded_at"] = pd.to_datetime(rankings["recorded_at"])
        
        # 제품별 첫 랭킹과 마지막 랭킹
        summary = rankings.groupby("product_id").agg({
            "product_name": "first",
            "ranking": ["first", "last", "min", "max", "mean"],
            "rating": ["first", "last"],
            "review_count": ["first", "last"],
            "recorded_at": ["min", "max"],
        })
        
        # 컬럼명 평탄화
        summary.columns = ["_".join(col).strip() for col in summary.columns.values]
        summary = summary.reset_index()
        
        # 변화량 계산
        summary["ranking_change"] = summary["ranking_last"] - summary["ranking_first"]
        summary["review_growth"] = summary["review_count_last"] - summary["review_count_first"]
        
        return summary
    
    def get_statistics(self) -> dict:
        """저장된 데이터 통계"""
        stats = {
            "products_file_exists": self.products_path.exists(),
            "reviews_file_exists": self.reviews_path.exists(),
            "rankings_file_exists": self.rankings_path.exists(),
        }
        
        if stats["products_file_exists"]:
            products_df = pd.read_parquet(self.products_path)
            stats["total_product_records"] = len(products_df)
            stats["unique_products"] = products_df["product_id"].nunique()
            
            if "crawled_at" in products_df.columns:
                products_df["crawled_at"] = pd.to_datetime(products_df["crawled_at"])
                stats["first_crawl"] = products_df["crawled_at"].min().isoformat()
                stats["last_crawl"] = products_df["crawled_at"].max().isoformat()
                stats["crawl_count"] = products_df["crawled_at"].dt.date.nunique()
        
        if stats["reviews_file_exists"]:
            reviews_df = pd.read_parquet(self.reviews_path)
            stats["total_reviews"] = len(reviews_df)
            stats["unique_reviews"] = reviews_df["review_id"].nunique() if "review_id" in reviews_df.columns else len(reviews_df)
        
        if stats["rankings_file_exists"]:
            rankings_df = pd.read_parquet(self.rankings_path)
            stats["total_ranking_records"] = len(rankings_df)
        
        return stats
    
    def export_to_csv(self, output_dir: Optional[Path] = None) -> None:
        """CSV로 내보내기 (백업용)"""
        output_dir = output_dir or self.data_dir / "csv_export"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if self.products_path.exists():
            df = pd.read_parquet(self.products_path)
            df.to_csv(output_dir / f"products_{timestamp}.csv", index=False)
            logger.info(f"Exported products to CSV")
        
        if self.reviews_path.exists():
            df = pd.read_parquet(self.reviews_path)
            df.to_csv(output_dir / f"reviews_{timestamp}.csv", index=False)
            logger.info(f"Exported reviews to CSV")
        
        if self.rankings_path.exists():
            df = pd.read_parquet(self.rankings_path)
            df.to_csv(output_dir / f"rankings_{timestamp}.csv", index=False)
            logger.info(f"Exported rankings to CSV")


if __name__ == "__main__":
    # 테스트
    storage = ParquetStorage()
    
    # 테스트 데이터
    test_products = [
        {
            "product_id": "12345",
            "product_name": "라네즈 워터 슬리핑 마스크",
            "brand_name": "laneige",
            "category": "마스크팩",
            "price": 3000,
            "ranking": 1,
            "rating": 4.5,
            "review_count": 1000,
            "sales_count": 5000,
            "product_url": "https://example.com/product/12345",
            "image_url": None,
        }
    ]
    
    storage.save_products(test_products)
    rankings = storage.extract_rankings_from_products(test_products)
    storage.save_rankings(rankings)
    
    print("Statistics:", storage.get_statistics())

