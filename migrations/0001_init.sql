-- Initial schema based on ERD (SoT)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS platforms (
    platform_id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    category_id SERIAL PRIMARY KEY,
    platform_id INT NOT NULL REFERENCES platforms(platform_id),
    name VARCHAR(150) NOT NULL,
    source_url TEXT
);

CREATE TABLE IF NOT EXISTS products (
    product_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    brand VARCHAR(150),
    name VARCHAR(255),
    canonical_name VARCHAR(255),
    global_sku VARCHAR(150),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS product_listings (
    listing_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID REFERENCES products(product_id),
    platform_id INT NOT NULL REFERENCES platforms(platform_id),
    product_url TEXT,
    external_id VARCHAR(150),
    title_raw TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ranking_daily (
    dt DATE NOT NULL,
    platform_id INT NOT NULL REFERENCES platforms(platform_id),
    category_id INT NOT NULL REFERENCES categories(category_id),
    rank INT NOT NULL,
    listing_id UUID REFERENCES product_listings(listing_id),
    product_title_raw TEXT,
    product_url TEXT,
    captured_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (dt, platform_id, category_id, rank)
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    listing_id UUID REFERENCES product_listings(listing_id),
    platform_id INT NOT NULL REFERENCES platforms(platform_id),
    external_review_id VARCHAR(255),
    rating REAL,
    title TEXT,
    body TEXT,
    author TEXT,
    reviewed_at TIMESTAMPTZ,
    language VARCHAR(10),
    crawled_at TIMESTAMPTZ DEFAULT NOW(),
    hash VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS review_embeddings (
    review_id UUID PRIMARY KEY REFERENCES reviews(review_id),
    vector_store VARCHAR(50),
    collection VARCHAR(100),
    point_id VARCHAR(255),
    embedding_model VARCHAR(150),
    embedded_at TIMESTAMPTZ,
    status VARCHAR(50),
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS reports (
    report_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    period_start DATE,
    period_end DATE,
    platform_scope VARCHAR(50),
    category_scope TEXT,
    notion_url TEXT,
    summary TEXT,
    content_markdown TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS job_runs (
    run_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dag_id VARCHAR(200),
    task_id VARCHAR(200),
    logical_date TIMESTAMPTZ,
    status VARCHAR(50),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    stats_json TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_reviews_listing_id ON reviews(listing_id);
CREATE INDEX IF NOT EXISTS idx_reviews_platform_id ON reviews(platform_id);
CREATE INDEX IF NOT EXISTS idx_ranking_daily_dt ON ranking_daily(dt);
CREATE INDEX IF NOT EXISTS idx_job_runs_dag_id ON job_runs(dag_id);
