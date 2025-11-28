"""
Production DAG for training fraud detection ML models

This DAG automates the process of retraining fraud detection models daily at 2:00 AM.
It extracts features from feedback data, trains multiple models with cross-validation,
evaluates them against a holdout set, and registers the best model in MLflow Model Registry.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import pandas as pd
from sqlalchemy import create_engine
from minio import Minio
import mlflow
import mlflow.sklearn
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import roc_auc_score, precision_recall_curve, auc
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from vault_helper import get_airflow_secrets

# Reason: Retrieve secrets from HashiCorp Vault using centralized helper
# This provides better error handling, retry logic, and caching
secrets = get_airflow_secrets()

POSTGRES_PASSWORD = secrets['postgres_password']
MINIO_ACCESS_KEY = secrets['minio_access_key']
MINIO_SECRET_KEY = secrets['minio_secret_key']

# Default arguments for the DAG
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
dag = DAG(
    'train_fraud_detector',
    default_args=default_args,
    description='Daily training of fraud detection models',
    schedule_interval='0 2 * * *',  # Daily at 2:00 AM
    catchup=False,
    tags=['ml', 'fraud_detection', 'training'],
)

def extract_features(**context):
    """
    Extract features from feedback labels and transaction data, save to MinIO
    """
    # Connect to PostgreSQL
    engine = create_engine(f"postgresql://postgres:{POSTGRES_PASSWORD}@postgres:5432/mlflow")
    
    # Query feedback labels with transaction details
    query = """
    SELECT fl.*, mr.transaction_id, mr.user_id, mr.amount, mr.device_id, 
           mr.detection_path, mr.level1_score, mr.level2_score
    FROM feedback_labels fl
    JOIN manual_reviews mr ON fl.review_id = mr.id
    """
    
    df = pd.read_sql(query, engine)
    
    # Generate features (simplified: using available numeric fields)
    # In production, this would include more sophisticated feature engineering
    df['label'] = df['verdict'].apply(lambda x: 1 if x == 'Block' else 0)
    
    # Select features for training
    features_df = df[['amount', 'level1_score', 'level2_score', 'label']].dropna()
    
    # Save to MinIO
    client = Minio("minio:9000", access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=False)
    bucket = "mlflow"
    
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    
    features_df.to_parquet('/tmp/features.parquet')
    client.fput_object(bucket, "features.parquet", '/tmp/features.parquet')
    
    context['task_instance'].xcom_push(key='features_path', value="s3://mlflow/features.parquet")
    print(f"Extracted {len(features_df)} samples with features")

def train_model(**context):
    """
    Train XGBoost and LightGBM models with cross-validation, log to MLflow
    """
    # Load features from MinIO
    client = Minio("minio:9000", access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=False)
    client.fget_object("mlflow", "features.parquet", "/tmp/features.parquet")
    
    df = pd.read_parquet("/tmp/features.parquet")
    X = df.drop('label', axis=1)
    y = df['label']
    
    # Split into train and holdout
    X_train, X_holdout, y_train, y_holdout = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Set up MLflow
    mlflow.set_tracking_uri("http://mlflow:5000")
    mlflow.set_experiment("fraud_detector_training")
    
    # Train models
    models = {
        'xgboost': XGBClassifier(random_state=42),
        'lightgbm': LGBMClassifier(random_state=42)
    }
    
    best_model_name = None
    best_score = 0
    
    for name, model in models.items():
        with mlflow.start_run(run_name=name):
            # Cross-validation
            scores = cross_val_score(model, X_train, y_train, cv=5, scoring='roc_auc')
            mean_score = scores.mean()
            
            mlflow.log_metric("cv_auc", mean_score)
            mlflow.log_param("model_type", name)
            
            # Fit model
            model.fit(X_train, y_train)
            mlflow.sklearn.log_model(model, "model")
            
            if mean_score > best_score:
                best_score = mean_score
                best_model_name = name
    
    context['task_instance'].xcom_push(key='best_model_name', value=best_model_name)
    context['task_instance'].xcom_push(key='X_holdout', value=X_holdout.to_json())
    context['task_instance'].xcom_push(key='y_holdout', value=y_holdout.to_json())
    print(f"Best model: {best_model_name} with CV AUC: {best_score}")

def evaluate_model(**context):
    """
    Evaluate best model on holdout set and compare with production model
    """
    mlflow.set_tracking_uri("http://mlflow:5000")
    
    best_model_name = context['task_instance'].xcom_pull(task_ids='train_model', key='best_model_name')
    
    # Find the latest run for the best model
    runs = mlflow.search_runs(
        experiment_names=["fraud_detector_training"], 
        filter_string=f"tags.mlflow.runName = '{best_model_name}'", 
        order_by=["start_time DESC"]
    )
    
    if runs.empty:
        raise ValueError(f"No runs found for model {best_model_name}")
    
    run_id = runs.iloc[0]['run_id']
    model = mlflow.sklearn.load_model(f"runs:/{run_id}/model")
    
    # Load holdout data
    X_holdout = pd.read_json(context['task_instance'].xcom_pull(task_ids='train_model', key='X_holdout'))
    y_holdout = pd.read_json(context['task_instance'].xcom_pull(task_ids='train_model', key='y_holdout'))
    
    # Evaluate
    y_pred_proba = model.predict_proba(X_holdout)[:, 1]
    auc_score = roc_auc_score(y_holdout, y_pred_proba)
    
    precision, recall, _ = precision_recall_curve(y_holdout, y_pred_proba)
    pr_auc = auc(recall, precision)
    
    # Compare with production model
    better_than_prod = False
    try:
        prod_model = mlflow.sklearn.load_model("models:/fraud_detector/Production")
        prod_pred_proba = prod_model.predict_proba(X_holdout)[:, 1]
        prod_auc = roc_auc_score(y_holdout, prod_pred_proba)
        better_than_prod = auc_score > prod_auc
        print(f"New model AUC: {auc_score:.4f}, Production AUC: {prod_auc:.4f}")
    except Exception as e:
        print(f"No production model found or error loading: {e}. Treating as better.")
        better_than_prod = True
    
    context['task_instance'].xcom_push(key='better_than_prod', value=better_than_prod)
    context['task_instance'].xcom_push(key='run_id', value=run_id)
    context['task_instance'].xcom_push(key='auc_score', value=auc_score)
    context['task_instance'].xcom_push(key='pr_auc', value=pr_auc)

def register_best_model(**context):
    """
    Register the best model in MLflow Model Registry and transition to Staging
    """
    mlflow.set_tracking_uri("http://mlflow:5000")
    
    better_than_prod = context['task_instance'].xcom_pull(task_ids='evaluate_model', key='better_than_prod')
    
    if better_than_prod:
        run_id = context['task_instance'].xcom_pull(task_ids='evaluate_model', key='run_id')
        auc_score = context['task_instance'].xcom_pull(task_ids='evaluate_model', key='auc_score')
        pr_auc = context['task_instance'].xcom_pull(task_ids='evaluate_model', key='pr_auc')
        
        model_uri = f"runs:/{run_id}/model"
        
        # Register model
        model_version = mlflow.register_model(model_uri, "fraud_detector")
        
        # Add description
        client = mlflow.tracking.MlflowClient()
        client.update_model_version(
            name="fraud_detector",
            version=model_version.version,
            description=f"Trained on {datetime.now().date()}. AUC: {auc_score:.4f}, PR-AUC: {pr_auc:.4f}"
        )
        
        # Transition to Staging
        client.transition_model_version_stage(
            name="fraud_detector",
            version=model_version.version,
            stage="Staging"
        )
        
        print(f"Model version {model_version.version} registered and moved to Staging")
    else:
        print("New model not better than production, skipping registration")

# Define tasks
extract_features_task = PythonOperator(
    task_id='extract_features',
    python_callable=extract_features,
    dag=dag,
)

train_model_task = PythonOperator(
    task_id='train_model',
    python_callable=train_model,
    dag=dag,
)

evaluate_model_task = PythonOperator(
    task_id='evaluate_model',
    python_callable=evaluate_model,
    dag=dag,
)

register_best_model_task = PythonOperator(
    task_id='register_best_model',
    python_callable=register_best_model,
    dag=dag,
)

# Define dependencies
extract_features_task >> train_model_task >> evaluate_model_task >> register_best_model_task