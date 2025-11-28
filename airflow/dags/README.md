# Airflow DAGs Directory

## Reason
This directory contains Airflow Directed Acyclic Graphs (DAGs) that define ML pipelines and workflows.

## Usage
Place your DAG Python files here. Example structure:
```
dags/
├── example_ml_pipeline.py
├── data_ingestion_dag.py
└── model_training_dag.py
```

## Getting Started
Create a simple DAG to test the setup:

```python
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'hello_world',
    default_args=default_args,
    description='A simple test DAG',
    schedule_interval=timedelta(days=1),
)

task = BashOperator(
    task_id='print_hello',
    bash_command='echo "Hello from Airflow!"',
    dag=dag,
)
```
