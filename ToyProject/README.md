# 🧴 @cosme 라네즈(Laneige) 제품 분석 프로젝트

@cosme 사이트에서 라네즈 화장품 정보를 수집하고, LLM을 활용하여 인사이트를 도출하는 파이프라인입니다.

## 📁 프로젝트 구조

```
SideProject/
├── config.py                 # 설정 파일
├── crawler/
│   ├── __init__.py
│   └── cosme_crawler.py      # @cosme 크롤러
├── database/
│   ├── __init__.py
│   └── storage.py            # Parquet 저장소 관리
├── models/
│   ├── __init__.py
│   └── model_factory.py      # 다양한 LLM 모델 지원
├── analysis/
│   ├── __init__.py
│   └── llm_analyzer.py       # LLM 분석기
├── data/                     # Parquet 데이터 저장소
├── output/                   # 분석 결과 (txt)
├── scheduler.py              # 주기적 크롤링 스케줄러
└── main.py                   # 메인 실행 파일
```

## 🚀 설치 및 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 단일 실행
python main.py

# 스케줄러 실행 (주기적 크롤링)
python scheduler.py
```

## ⚙️ 설정

`.env` 파일을 생성하고 API 키를 설정하세요:

```env
# LLM API Keys
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key

# 로컬 모델 설정
LOCAL_MODEL_PATH=/path/to/local/model
```

## 📊 기능

1. **크롤링**: @cosme에서 라네즈 제품 정보 수집
   - 상품명, 가격, 랭킹, 판매량, 별점, 리뷰 수, 리뷰

2. **데이터 저장**: Parquet 형식으로 시계열 데이터 누적 저장
   - 덮어쓰기가 아닌 시계열 누적으로 변화 추적 가능

3. **LLM 분석**: 다양한 모델 지원
   - Qwen3 (기본)
   - GPT, Claude, Gemini 지원

4. **결과 출력**: 분석 결과를 txt 파일로 깔끔하게 저장


# 추가 정보
모델의 저장 경로 지정하는 cache_dir은 model_factory.py 에 있음