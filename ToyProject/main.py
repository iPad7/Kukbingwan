"""
라네즈(Laneige) @cosme 분석 파이프라인 메인 실행 파일

사용법:
    # 전체 파이프라인 실행 (크롤링 + 저장 + 분석)
    python main.py

    # 크롤링만 실행
    python main.py --crawl-only

    # 분석만 실행 (기존 데이터 사용)
    python main.py --analyze-only

    # 특정 LLM 프로바이더 사용
    python main.py --provider openai
    python main.py --provider anthropic
    python main.py --provider google
"""
import sys
import argparse
from datetime import datetime
from pathlib import Path

from loguru import logger

from config import config, LLMProvider, OUTPUT_DIR
from crawler.cosme_crawler import CosmeCrawler
from database.storage import ParquetStorage
from models.model_factory import ModelFactory
from analysis.llm_analyzer import LLMAnalyzer


# 로깅 설정
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")
logger.add(
    LOG_DIR / "main_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="DEBUG"
)


def run_crawl(include_reviews: bool = True) -> tuple[list, list]:
    """크롤링 실행"""
    logger.info("=" * 60)
    logger.info("🕷️  Starting @cosme Crawling")
    logger.info("=" * 60)
    
    crawler = CosmeCrawler()
    products, reviews = crawler.crawl_all(include_reviews=include_reviews)
    
    if not products:
        logger.warning("No products were crawled")
        return [], []
    
    # 저장
    storage = ParquetStorage()
    
    products_dict = crawler.to_dict_list(products)
    storage.save_products(products_dict)
    
    # 랭킹 히스토리 저장
    rankings = storage.extract_rankings_from_products(products_dict)
    storage.save_rankings(rankings)
    
    if reviews:
        reviews_dict = crawler.to_dict_list(reviews)
        storage.save_reviews(reviews_dict)
    
    logger.info(f"✅ Crawling complete: {len(products)} products, {len(reviews)} reviews")
    
    return products_dict, reviews if reviews else []


def run_analysis(provider: LLMProvider = None) -> Path:
    """LLM 분석 실행"""
    logger.info("=" * 60)
    logger.info("🤖 Starting LLM Analysis")
    logger.info("=" * 60)
    
    analyzer = LLMAnalyzer(provider=provider)
    
    # 데이터 통계 확인
    stats = analyzer.storage.get_statistics()
    logger.info(f"Data statistics: {stats}")
    
    if not stats.get("products_file_exists"):
        logger.error("No product data found. Run crawling first.")
        return None
    
    # 분석 실행
    report_path = analyzer.run_full_analysis()
    
    logger.info(f"✅ Analysis complete. Report saved to: {report_path}")
    
    return report_path


def show_statistics():
    """저장된 데이터 통계 표시"""
    storage = ParquetStorage()
    stats = storage.get_statistics()
    
    print("\n" + "=" * 60)
    print("📊 Data Statistics")
    print("=" * 60)
    
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("=" * 60 + "\n")


def list_reports():
    """저장된 리포트 목록 표시"""
    print("\n" + "=" * 60)
    print("📄 Saved Reports")
    print("=" * 60)
    
    report_files = sorted(OUTPUT_DIR.glob("*.txt"), reverse=True)
    
    if not report_files:
        print("  No reports found")
    else:
        for f in report_files[:20]:  # 최근 20개만
            size = f.stat().st_size / 1024
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            print(f"  {f.name} ({size:.1f} KB, {mtime})")
    
    print("=" * 60 + "\n")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="라네즈(Laneige) @cosme 분석 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python main.py                    # 전체 파이프라인 실행
  python main.py --crawl-only       # 크롤링만 실행
  python main.py --analyze-only     # 분석만 실행
  python main.py --provider openai  # OpenAI GPT로 분석
  python main.py --gpu 0            # GPU 0번 사용 (로컬 모델)
  python main.py --gpu 0,1          # GPU 0,1번 사용 (다중 GPU)
  python main.py --stats            # 데이터 통계 확인
  python main.py --list-reports     # 저장된 리포트 목록
        """
    )
    
    parser.add_argument(
        "--crawl-only",
        action="store_true",
        help="크롤링만 실행 (분석 생략)"
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="분석만 실행 (기존 데이터 사용)"
    )
    parser.add_argument(
        "--no-reviews",
        action="store_true",
        help="리뷰 크롤링 생략"
    )
    parser.add_argument(
        "--provider",
        choices=["qwen", "openai", "anthropic", "google"],
        default="qwen",
        help="LLM 프로바이더 선택 (기본: qwen)"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="저장된 데이터 통계 표시"
    )
    parser.add_argument(
        "--list-reports",
        action="store_true",
        help="저장된 리포트 목록 표시"
    )
    parser.add_argument(
        "--list-providers",
        action="store_true",
        help="사용 가능한 LLM 프로바이더 목록"
    )
    parser.add_argument(
        "--gpu",
        type=str,
        default=None,
        help="사용할 GPU ID (예: '0', '0,1', '1,2,3'). 로컬 모델(qwen)에만 적용"
    )
    
    args = parser.parse_args()
    
    # 정보 표시 옵션
    if args.stats:
        show_statistics()
        return
    
    if args.list_reports:
        list_reports()
        return
    
    if args.list_providers:
        print("\n사용 가능한 LLM 프로바이더:")
        for p in ModelFactory.list_providers():
            print(f"  - {p}")
        return
    
    # LLM 프로바이더 설정
    provider = LLMProvider(args.provider)
    
    # GPU 설정 (로컬 모델용)
    if args.gpu is not None:
        config.llm.gpu_ids = args.gpu
        logger.info(f"GPU setting: {args.gpu}")
    
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║   🧴 라네즈(Laneige) @cosme 분석 파이프라인              ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    start_time = datetime.now()
    logger.info(f"Pipeline started at {start_time}")
    
    try:
        if args.analyze_only:
            # 분석만 실행
            report_path = run_analysis(provider)
        
        elif args.crawl_only:
            # 크롤링만 실행
            run_crawl(include_reviews=not args.no_reviews)
        
        else:
            # 전체 파이프라인 실행
            products, reviews = run_crawl(include_reviews=not args.no_reviews)
            
            if products:
                report_path = run_analysis(provider)
            else:
                logger.warning("Skipping analysis due to no data")
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        logger.info("=" * 60)
        logger.info(f"🎉 Pipeline completed successfully!")
        logger.info(f"   Duration: {duration}")
        logger.info("=" * 60)
        
    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user")
        sys.exit(1)
    
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise


if __name__ == "__main__":
    main()

