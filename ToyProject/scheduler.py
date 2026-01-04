"""
주기적 크롤링 및 분석 스케줄러
"""
import sys
import signal
import argparse
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from config import config, SchedulerConfig
from crawler.cosme_crawler import CosmeCrawler
from database.storage import ParquetStorage
from analysis.llm_analyzer import LLMAnalyzer


# 로깅 설정
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add(
    LOG_DIR / "scheduler_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="DEBUG"
)


def run_crawl_job(include_reviews: bool = True, run_analysis: bool = True):
    """크롤링 작업 실행"""
    logger.info("=" * 60)
    logger.info(f"Starting scheduled crawl job at {datetime.now()}")
    logger.info("=" * 60)
    
    try:
        # 크롤링
        crawler = CosmeCrawler()
        products, reviews = crawler.crawl_all(include_reviews=include_reviews)
        
        if not products:
            logger.warning("No products crawled")
            return
        
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
        
        logger.info(f"Crawl complete: {len(products)} products, {len(reviews)} reviews")
        
        # 분석 실행 (설정에 따라)
        if run_analysis and config.scheduler.analysis_after_crawl:
            logger.info("Running post-crawl analysis...")
            try:
                analyzer = LLMAnalyzer()
                report_path = analyzer.run_full_analysis()
                logger.info(f"Analysis report saved to: {report_path}")
            except Exception as e:
                logger.error(f"Analysis failed: {e}")
        
        logger.info("=" * 60)
        logger.info("Scheduled job completed successfully")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Crawl job failed: {e}")
        raise


def run_analysis_job():
    """분석 작업만 실행"""
    logger.info("=" * 60)
    logger.info(f"Starting scheduled analysis job at {datetime.now()}")
    logger.info("=" * 60)
    
    try:
        analyzer = LLMAnalyzer()
        report_path = analyzer.run_full_analysis()
        logger.info(f"Analysis report saved to: {report_path}")
        
    except Exception as e:
        logger.error(f"Analysis job failed: {e}")
        raise


class CosmeScheduler:
    """크롤링 및 분석 스케줄러"""
    
    def __init__(self, scheduler_config: SchedulerConfig = None):
        self.config = scheduler_config or config.scheduler
        self.scheduler = BlockingScheduler()
        
        # 시그널 핸들러 설정
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)
    
    def _shutdown(self, signum, frame):
        """그레이스풀 셧다운"""
        logger.info("Received shutdown signal, stopping scheduler...")
        self.scheduler.shutdown(wait=False)
        sys.exit(0)
    
    def add_crawl_job(
        self,
        interval_hours: int = None,
        include_reviews: bool = True,
        run_analysis: bool = True
    ):
        """크롤링 작업 추가"""
        interval = interval_hours or self.config.crawl_interval_hours
        
        self.scheduler.add_job(
            run_crawl_job,
            trigger=IntervalTrigger(hours=interval),
            kwargs={
                "include_reviews": include_reviews,
                "run_analysis": run_analysis,
            },
            id="crawl_job",
            name="@cosme Crawling Job",
            replace_existing=True,
        )
        
        logger.info(f"Added crawl job: every {interval} hours")
    
    def add_daily_crawl_job(
        self,
        hour: int = 9,
        minute: int = 0,
        include_reviews: bool = True,
        run_analysis: bool = True
    ):
        """매일 정해진 시간에 크롤링 작업 추가"""
        self.scheduler.add_job(
            run_crawl_job,
            trigger=CronTrigger(hour=hour, minute=minute),
            kwargs={
                "include_reviews": include_reviews,
                "run_analysis": run_analysis,
            },
            id="daily_crawl_job",
            name="Daily @cosme Crawling Job",
            replace_existing=True,
        )
        
        logger.info(f"Added daily crawl job: every day at {hour:02d}:{minute:02d}")
    
    def add_weekly_analysis_job(self, day_of_week: str = "mon", hour: int = 10):
        """주간 분석 작업 추가"""
        self.scheduler.add_job(
            run_analysis_job,
            trigger=CronTrigger(day_of_week=day_of_week, hour=hour),
            id="weekly_analysis_job",
            name="Weekly Analysis Job",
            replace_existing=True,
        )
        
        logger.info(f"Added weekly analysis job: every {day_of_week} at {hour:02d}:00")
    
    def run_now(self, include_reviews: bool = True, run_analysis: bool = True):
        """즉시 실행"""
        run_crawl_job(include_reviews=include_reviews, run_analysis=run_analysis)
    
    def start(self):
        """스케줄러 시작"""
        logger.info("=" * 60)
        logger.info("Starting @cosme Crawler Scheduler")
        logger.info(f"Scheduled jobs: {len(self.scheduler.get_jobs())}")
        for job in self.scheduler.get_jobs():
            logger.info(f"  - {job.name}: {job.trigger}")
        logger.info("=" * 60)
        logger.info("Press Ctrl+C to stop")
        
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="@cosme Crawler Scheduler")
    parser.add_argument(
        "--mode",
        choices=["interval", "daily", "now"],
        default="interval",
        help="Scheduling mode: interval (default), daily, or now (run once immediately)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=24,
        help="Crawl interval in hours (for interval mode, default: 24)"
    )
    parser.add_argument(
        "--hour",
        type=int,
        default=9,
        help="Hour to run (for daily mode, default: 9)"
    )
    parser.add_argument(
        "--no-reviews",
        action="store_true",
        help="Skip review crawling"
    )
    parser.add_argument(
        "--no-analysis",
        action="store_true",
        help="Skip LLM analysis after crawling"
    )
    
    args = parser.parse_args()
    
    scheduler = CosmeScheduler()
    
    include_reviews = not args.no_reviews
    run_analysis = not args.no_analysis
    
    if args.mode == "now":
        # 즉시 실행
        logger.info("Running crawl job immediately...")
        scheduler.run_now(include_reviews=include_reviews, run_analysis=run_analysis)
    
    elif args.mode == "daily":
        # 매일 정해진 시간
        scheduler.add_daily_crawl_job(
            hour=args.hour,
            include_reviews=include_reviews,
            run_analysis=run_analysis
        )
        scheduler.start()
    
    else:
        # 주기적 실행
        scheduler.add_crawl_job(
            interval_hours=args.interval,
            include_reviews=include_reviews,
            run_analysis=run_analysis
        )
        scheduler.start()


if __name__ == "__main__":
    main()

