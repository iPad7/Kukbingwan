from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "kukbingwan",
    "depends_on_past": False,
    "retries": 0,
}

with DAG(
    dag_id="review_etl_daily",
    default_args=default_args,
    description="Dummy review ETL",
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
) as dag:
    run_reviews = BashOperator(
        task_id="review_etl",
        bash_command='echo "TODO: docker exec agent-batch python -m app review_etl --date {{ ds }} --topn 100"',
    )
