from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "kukbingwan",
    "depends_on_past": False,
    "retries": 0,
}

with DAG(
    dag_id="report_weekly",
    default_args=default_args,
    description="Dummy report generation",
    schedule_interval="@weekly",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
) as dag:
    generate_report = BashOperator(
        task_id="report_gen",
        bash_command='echo "TODO: docker exec agent-batch python -m app report_gen --period weekly --end_date {{ ds }}"',
    )
