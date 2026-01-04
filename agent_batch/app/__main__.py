import argparse
import json
import os
import sys
import uuid
from datetime import datetime

import psycopg2
from psycopg2.extras import Json


def get_db_conn():
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://sot:sot@localhost:5433/sot",
    )
    try:
        return psycopg2.connect(db_url)
    except Exception as exc:  # pragma: no cover - best effort logging only
        print(f"[agent-batch] Failed to connect DB: {exc}", file=sys.stderr)
        return None


def record_job(dag_id: str, task_id: str, status: str, stats: dict | None = None, error: str | None = None):
    conn = get_db_conn()
    if conn is None:
        return

    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO job_runs (run_id, dag_id, task_id, logical_date, status, started_at, ended_at, stats_json, error_message)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW(), %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    dag_id,
                    task_id,
                    datetime.utcnow(),
                    status,
                    Json(stats) if stats else None,
                    error,
                ),
            )
    except Exception as exc:  # pragma: no cover
        print(f"[agent-batch] Failed to record job: {exc}", file=sys.stderr)
    finally:
        conn.close()


def ranking_etl(args):
    print(f"[ranking_etl] stub run for date={args.date}")
    record_job("ranking_etl_daily", "ranking_etl", "success", {"date": args.date, "rows_upserted": 0})


def review_etl(args):
    print(f"[review_etl] stub run for date={args.date}, topn={args.topn}")
    record_job("review_etl_daily", "review_etl", "success", {"date": args.date, "topn": args.topn})


def embed_reviews(args):
    print(f"[embed_reviews] stub run with batch_size={args.batch_size}")
    record_job("review_embed_daily", "embed_reviews", "success", {"batch_size": args.batch_size})


def report_gen(args):
    print(f"[report_gen] stub run for period={args.period}, end_date={args.end_date}")
    record_job("report_weekly", "report_gen", "success", {"period": args.period, "end_date": args.end_date})


def build_parser():
    parser = argparse.ArgumentParser(description="Agent batch CLI (dummy stub).")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_rank = subparsers.add_parser("ranking_etl", help="Run ranking ETL (stub).")
    p_rank.add_argument("--date", required=True, help="Date in YYYY-MM-DD")
    p_rank.set_defaults(func=ranking_etl)

    p_review = subparsers.add_parser("review_etl", help="Run review ETL (stub).")
    p_review.add_argument("--date", required=True, help="Date in YYYY-MM-DD")
    p_review.add_argument("--topn", type=int, default=100, help="TopN reviews per listing")
    p_review.set_defaults(func=review_etl)

    p_embed = subparsers.add_parser("embed_reviews", help="Run review embedding (stub).")
    p_embed.add_argument("--batch_size", type=int, default=200)
    p_embed.set_defaults(func=embed_reviews)

    p_report = subparsers.add_parser("report_gen", help="Generate report (stub).")
    p_report.add_argument("--period", default="weekly", choices=["weekly", "daily"])
    p_report.add_argument("--end_date", required=True, help="Period end date in YYYY-MM-DD")
    p_report.set_defaults(func=report_gen)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
