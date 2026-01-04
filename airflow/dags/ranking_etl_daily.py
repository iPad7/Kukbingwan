from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "kukbingwan",
    "depends_on_past": False,
    "retries": 0,
}

with DAG(
    dag_id="ranking_etl_daily",
    default_args=default_args,
    description="Dummy ranking ETL",
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
) as dag:
    run_ranking = BashOperator(
        task_id="ranking_etl",
        bash_command='echo "TODO: docker exec agent-batch python -m app ranking_etl --date {{ ds }}"',
    )
