"""
프로젝트 설정 파일
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional
from enum import Enum

# 환경 변수 로드
load_dotenv()

# 프로젝트 기본 경로
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"

# 디렉토리 생성
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


class LLMProvider(str, Enum):
    """지원하는 LLM 프로바이더"""
    QWEN = "qwen"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class CrawlerConfig(BaseModel):
    """크롤러 설정"""
    base_url: str = "https://cosmeet.cosme.net"  # 검색용
    detail_base_url: str = "https://www.cosme.net"  # 제품 상세/리뷰용
    brand_name: str = "laneige"
    max_products: int = 5
    max_reviews_per_product: int = 5
    request_delay: float = 2.0  # 요청 간 딜레이 (초)
    timeout: int = 30
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )


class DatabaseConfig(BaseModel):
    """데이터베이스 설정"""
    data_dir: Path = DATA_DIR
    products_file: str = "products.parquet"
    reviews_file: str = "reviews.parquet"
    rankings_file: str = "rankings.parquet"
    compression: str = "snappy"


class LLMConfig(BaseModel):
    """LLM 설정"""
    provider: LLMProvider = LLMProvider.QWEN
    
    # API Keys
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    google_api_key: Optional[str] = os.getenv("GOOGLE_API_KEY")
    
    # 모델 이름
    qwen_model: str = "Qwen/Qwen3-4B-Instruct-2507"
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    google_model: str = "gemini-1.5-flash"
    
    # GPU 설정 (로컬 모델용)
    gpu_ids: Optional[str] = None  # 예: "0", "0,1", "1,2,3" 또는 None (auto)
    
    # 생성 설정
    max_tokens: int = 4096
    temperature: float = 0.7


class SchedulerConfig(BaseModel):
    """스케줄러 설정"""
    crawl_interval_hours: int = 24  # 크롤링 주기 (시간)
    analysis_after_crawl: bool = True  # 크롤링 후 자동 분석


class Config(BaseModel):
    """전체 설정"""
    crawler: CrawlerConfig = CrawlerConfig()
    database: DatabaseConfig = DatabaseConfig()
    llm: LLMConfig = LLMConfig()
    scheduler: SchedulerConfig = SchedulerConfig()


# 기본 설정 인스턴스
config = Config()

