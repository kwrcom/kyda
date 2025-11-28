"""
Example Airflow DAG for testing the MLOps infrastructure

Reason: This DAG demonstrates basic Airflow functionality and verifies
that the scheduler, worker, and webserver are properly configured.
It includes tasks for printing environment info and simulating a simple
ML workflow step.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

# Default arguments for the DAG
# Reason: Defines retry behavior and owner information
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Create the DAG
# Reason: Defines the workflow schedule and configuration
dag = DAG(
    'example_mlops_test',
    default_args=default_args,
    description='Test DAG for MLOps infrastructure',
    schedule_interval=None,  # Manual trigger only
    catchup=False,
    tags=['example', 'test'],
)

# Task 1: Print environment information
# Reason: Verifies that the worker environment is properly set up
print_date = BashOperator(
    task_id='print_date',
    bash_command='echo "Current date: $(date)"',
    dag=dag,
)

# Task 2: Check Python environment
# Reason: Confirms Python is available and shows installed packages
check_python = BashOperator(
    task_id='check_python',
    bash_command='python --version && echo "Python is available"',
    dag=dag,
)

# Task 3: Simulate ML task
# Reason: Demonstrates using Python operator for ML workflow steps
def simulate_ml_task(**context):
    """
    Simulates a simple ML task
    
    Reason: This would normally include data loading, preprocessing,
    model training, or evaluation steps
    """
    import random
    
    # Simulate some computation
    accuracy = random.uniform(0.80, 0.95)
    
    print(f"Simulated model training completed")
    print(f"Model accuracy: {accuracy:.4f}")
    
    # Push result to XCom for downstream tasks
    # Reason: XCom allows task-to-task communication in Airflow
    context['task_instance'].xcom_push(key='accuracy', value=accuracy)
    
    return f"Training completed with accuracy: {accuracy:.4f}"

ml_task = PythonOperator(
    task_id='simulate_ml_training',
    python_callable=simulate_ml_task,
    dag=dag,
)

# Task 4: Print results
# Reason: Demonstrates retrieving XCom values from previous tasks
print_results = BashOperator(
    task_id='print_results',
    bash_command='echo "ML pipeline test completed successfully"',
    dag=dag,
)

# Define task dependencies
# Reason: Creates a linear workflow: date → python check → ML task → results
print_date >> check_python >> ml_task >> print_results
