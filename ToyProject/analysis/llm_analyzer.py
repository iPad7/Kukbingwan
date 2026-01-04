"""
LLM을 활용한 데이터 분석 모듈
제품 인사이트, 랭킹 변화, 사용자 반응, 판매량 추이 등 분석
"""
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger

import sys
sys.path.append(str(__file__).rsplit("/", 2)[0])
from config import LLMProvider, config, OUTPUT_DIR
from models.model_factory import ModelFactory, BaseLLM
from database.storage import ParquetStorage


class LLMAnalyzer:
    """LLM 기반 데이터 분석기"""
    
    SYSTEM_PROMPT = """당신은 화장품 시장 분석 전문가입니다. 
@cosme 데이터를 기반으로 라네즈(Laneige) 제품에 대한 인사이트를 도출합니다.
분석 결과는 한국어로 작성하며, 구체적인 수치와 함께 명확한 인사이트를 제공합니다.
마케팅 담당자와 제품 기획자가 의사결정에 활용할 수 있도록 실용적인 제안을 포함합니다."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        storage: Optional[ParquetStorage] = None
    ):
        self.llm = ModelFactory.create(provider)
        self.storage = storage or ParquetStorage()
        self.output_dir = OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"LLMAnalyzer initialized with {self.llm.model_name}")
    
    def _prepare_products_summary(self, df: pd.DataFrame) -> str:
        """제품 데이터 요약 준비"""
        if df.empty:
            return "제품 데이터가 없습니다."
        
        summary_parts = ["## 제품 데이터 요약\n"]
        
        summary_parts.append(f"- 총 제품 수: {len(df)}개")
        
        if "rating" in df.columns:
            avg_rating = df["rating"].dropna().mean()
            if pd.notna(avg_rating):
                summary_parts.append(f"- 평균 별점: {avg_rating:.2f}")
        
        if "review_count" in df.columns:
            total_reviews = df["review_count"].sum()
            summary_parts.append(f"- 총 리뷰 수: {int(total_reviews):,}개")
        
        # 상위 제품: 랭킹이 있으면 랭킹 기준, 없으면 리뷰 수 기준
        summary_parts.append("\n### 인기 상위 5개 제품:")
        if "ranking" in df.columns and df["ranking"].notna().any():
            # 랭킹이 있는 경우
            ranked_df = df[df["ranking"].notna()].copy()
            ranked_df["ranking"] = pd.to_numeric(ranked_df["ranking"], errors="coerce")
            top_products = ranked_df.nsmallest(5, "ranking")
        elif "review_count" in df.columns:
            # 랭킹이 없으면 리뷰 수 기준
            top_products = df.nlargest(5, "review_count")
        else:
            top_products = df.head(5)
        
        for _, row in top_products.iterrows():
            ranking_str = f"랭킹 {int(row['ranking'])}, " if pd.notna(row.get('ranking')) else ""
            rating_str = f"{row['rating']:.1f}" if pd.notna(row.get('rating')) else "N/A"
            summary_parts.append(
                f"  - {row['product_name']}: {ranking_str}"
                f"별점 {rating_str}, 리뷰 {int(row.get('review_count', 0))}개"
            )
        
        # 전체 제품 목록
        summary_parts.append("\n### 전체 제품 목록:")
        for _, row in df.iterrows():
            ranking_str = f"{int(row['ranking'])}" if pd.notna(row.get('ranking')) else "N/A"
            rating_str = f"{row['rating']:.1f}" if pd.notna(row.get('rating')) else "N/A"
            price_str = f"{int(row['price']):,}" if pd.notna(row.get('price')) else "N/A"
            summary_parts.append(
                f"- {row['product_name']}: "
                f"랭킹 {ranking_str}, "
                f"별점 {rating_str}, "
                f"리뷰 {int(row.get('review_count', 0))}개, "
                f"가격 {price_str}엔"
            )
        
        return "\n".join(summary_parts)
    
    def _prepare_rankings_summary(self, df: pd.DataFrame) -> str:
        """랭킹 변화 데이터 요약 준비"""
        if df.empty:
            return "랭킹 히스토리 데이터가 없습니다."
        
        summary_parts = ["## 랭킹 변화 데이터\n"]
        
        df["recorded_at"] = pd.to_datetime(df["recorded_at"])
        
        # 기간 정보
        date_range = f"{df['recorded_at'].min().date()} ~ {df['recorded_at'].max().date()}"
        summary_parts.append(f"- 분석 기간: {date_range}")
        summary_parts.append(f"- 수집 횟수: {df['recorded_at'].dt.date.nunique()}회")
        
        # 제품별 랭킹 변화
        summary_parts.append("\n### 제품별 랭킹 변화:")
        
        for product_id in df["product_id"].unique():
            product_data = df[df["product_id"] == product_id].sort_values("recorded_at")
            product_name = product_data["product_name"].iloc[0]
            
            first_rank = product_data["ranking"].iloc[0]
            last_rank = product_data["ranking"].iloc[-1]
            rank_change = first_rank - last_rank  # 양수면 상승
            
            first_reviews = product_data["review_count"].iloc[0]
            last_reviews = product_data["review_count"].iloc[-1]
            review_growth = last_reviews - first_reviews
            
            direction = "↑" if rank_change > 0 else ("↓" if rank_change < 0 else "→")
            
            summary_parts.append(
                f"- {product_name}: {first_rank}위 → {last_rank}위 ({direction}{abs(rank_change)}), "
                f"리뷰 +{review_growth}개"
            )
        
        return "\n".join(summary_parts)
    
    def _prepare_reviews_summary(self, df: pd.DataFrame, max_reviews: int = 50) -> str:
        """리뷰 데이터 요약 준비"""
        if df.empty:
            return "리뷰 데이터가 없습니다."
        
        summary_parts = ["## 리뷰 데이터 요약\n"]
        
        summary_parts.append(f"- 총 리뷰 수: {len(df)}개")
        
        if "rating" in df.columns:
            avg_rating = df["rating"].mean()
            rating_dist = df["rating"].value_counts().sort_index()
            summary_parts.append(f"- 평균 별점: {avg_rating:.2f}")
            summary_parts.append("- 별점 분포:")
            for rating, count in rating_dist.items():
                summary_parts.append(f"  - {rating}점: {count}개 ({count/len(df)*100:.1f}%)")
        
        # 샘플 리뷰
        summary_parts.append(f"\n### 샘플 리뷰 ({min(max_reviews, len(df))}개):")
        
        sample_df = df.head(max_reviews)
        for _, row in sample_df.iterrows():
            content = row.get("content", "")[:200]  # 200자 제한
            summary_parts.append(
                f"- [{row.get('rating', 'N/A')}점] {content}..."
            )
        
        return "\n".join(summary_parts)
    
    def analyze_products(self) -> str:
        """제품 분석 수행"""
        logger.info("Analyzing products...")
        
        products_df = self.storage.load_products(latest_only=True)
        
        if products_df.empty:
            return "분석할 제품 데이터가 없습니다."
        
        data_summary = self._prepare_products_summary(products_df)
        
        prompt = f"""다음 라네즈(Laneige) 제품 데이터를 분석하여 인사이트를 도출해주세요.

{data_summary}

다음 항목에 대해 분석해주세요:
1. **제품 포트폴리오 분석**: 카테고리별 제품 구성과 강점/약점
2. **인기 제품 분석**: 상위 랭킹 제품의 공통점과 성공 요인
3. **가격 전략 분석**: 가격대별 제품 분포와 경쟁력
4. **고객 반응 분석**: 별점과 리뷰 수 기반 고객 만족도
5. **개선 제안**: 제품 라인업 강화를 위한 제안

각 항목에 대해 구체적인 수치와 함께 인사이트를 제공해주세요."""

        response = self.llm.generate(prompt, self.SYSTEM_PROMPT)
        return response
    
    def analyze_rankings(self) -> str:
        """랭킹 변화 분석"""
        logger.info("Analyzing ranking changes...")
        
        rankings_df = self.storage.load_rankings()
        
        if rankings_df.empty:
            return "분석할 랭킹 히스토리 데이터가 없습니다."
        
        data_summary = self._prepare_rankings_summary(rankings_df)
        
        prompt = f"""다음 라네즈(Laneige) 제품의 랭킹 변화 데이터를 분석해주세요.

{data_summary}

다음 항목에 대해 분석해주세요:
1. **랭킹 트렌드 분석**: 전체적인 랭킹 변화 추세
2. **상승 제품 분석**: 랭킹이 상승한 제품과 그 요인 분석
3. **하락 제품 분석**: 랭킹이 하락한 제품과 원인 추정
4. **리뷰 성장 분석**: 리뷰 증가와 랭킹 변화의 상관관계
5. **예측 및 제안**: 향후 랭킹 변화 예측과 개선 전략

구체적인 수치를 포함하여 분석해주세요."""

        response = self.llm.generate(prompt, self.SYSTEM_PROMPT)
        return response
    
    def analyze_reviews(self, product_id: Optional[str] = None) -> str:
        """리뷰 감성 분석"""
        logger.info("Analyzing reviews...")
        
        reviews_df = self.storage.load_reviews(product_id)
        
        if reviews_df.empty:
            return "분석할 리뷰 데이터가 없습니다."
        
        data_summary = self._prepare_reviews_summary(reviews_df)
        
        prompt = f"""다음 라네즈(Laneige) 제품 리뷰를 분석해주세요.

{data_summary}

다음 항목에 대해 분석해주세요:
1. **감성 분석**: 긍정/부정 리뷰 비율과 주요 감성 키워드
2. **주요 장점**: 고객들이 자주 언급하는 장점
3. **주요 불만**: 고객들이 자주 언급하는 단점이나 불만
4. **제품별 특성**: 제품별로 두드러지는 리뷰 특성
5. **개선 제안**: 리뷰 기반 제품 개선 방향

고객의 목소리를 바탕으로 실용적인 인사이트를 제공해주세요."""

        response = self.llm.generate(prompt, self.SYSTEM_PROMPT)
        return response
    
    def generate_full_report(self) -> str:
        """전체 분석 리포트 생성"""
        logger.info("Generating full analysis report...")
        
        # 데이터 수집
        products_df = self.storage.load_products(latest_only=True)
        rankings_df = self.storage.load_rankings()
        reviews_df = self.storage.load_reviews()
        
        # 데이터 요약 준비
        products_summary = self._prepare_products_summary(products_df)
        rankings_summary = self._prepare_rankings_summary(rankings_df)
        reviews_summary = self._prepare_reviews_summary(reviews_df, max_reviews=30)
        
        prompt = f"""다음 라네즈(Laneige) 데이터를 종합 분석하여 경영진 보고서를 작성해주세요.

{products_summary}

{rankings_summary}

{reviews_summary}

---

다음 구조로 종합 보고서를 작성해주세요:

# 라네즈(Laneige) @cosme 시장 분석 보고서

## 1. Executive Summary
- 핵심 인사이트 3-5개 요약

## 2. 제품 포트폴리오 현황
- 현재 제품 라인업 분석
- 카테고리별 성과

## 3. 시장 경쟁력 분석
- @cosme 내 랭킹 현황
- 랭킹 변화 트렌드
- 경쟁 우위 요소

## 4. 고객 반응 분석
- 별점 및 리뷰 현황
- 고객 만족/불만 요인
- 주요 키워드 분석

## 5. 기회와 위협
- 성장 기회 요인
- 잠재적 위협 요인

## 6. 전략적 제안
- 단기 개선 과제 (1-3개월)
- 중장기 전략 방향 (6개월-1년)

구체적인 수치와 데이터를 근거로 분석해주세요."""

        response = self.llm.generate(prompt, self.SYSTEM_PROMPT)
        return response
    
    def save_report(self, report: str, report_type: str = "full") -> Path:
        """분석 결과를 txt 파일로 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"laneige_analysis_{report_type}_{timestamp}.txt"
        filepath = self.output_dir / filename
        
        # 헤더 추가
        header = f"""{'='*60}
라네즈(Laneige) @cosme 분석 리포트
{'='*60}
생성 일시: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
분석 유형: {report_type}
사용 모델: {self.llm.model_name}
{'='*60}

"""
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(header)
            f.write(report)
            f.write(f"\n\n{'='*60}\n리포트 끝\n{'='*60}")
        
        logger.info(f"Report saved to {filepath}")
        return filepath
    
    def run_full_analysis(self) -> Path:
        """전체 분석 파이프라인 실행 및 결과 저장"""
        logger.info("=" * 50)
        logger.info("Starting full analysis pipeline")
        logger.info("=" * 50)
        
        # 전체 리포트 생성
        report = self.generate_full_report()
        
        # 저장
        filepath = self.save_report(report, "full")
        
        logger.info("=" * 50)
        logger.info(f"Analysis complete. Report saved to: {filepath}")
        logger.info("=" * 50)
        
        return filepath


if __name__ == "__main__":
    # 테스트 실행
    from loguru import logger
    import sys
    
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    # 분석기 생성 (기본 Qwen 사용)
    try:
        analyzer = LLMAnalyzer()
        
        # 데이터 통계 확인
        stats = analyzer.storage.get_statistics()
        print("Data Statistics:", stats)
        
        # 데이터가 있으면 분석 실행
        if stats.get("products_file_exists"):
            report_path = analyzer.run_full_analysis()
            print(f"Report saved to: {report_path}")
        else:
            print("No data available for analysis. Run crawler first.")
            
    except Exception as e:
        print(f"Analysis failed: {e}")

