output "mlflow_app_arn" {
  description = "ARN of the SageMaker MLflow app"
  value       = aws_sagemaker_mlflow_app.mlops.arn
}

output "mlflow_tracking_uri" {
  description = "Value to export as MLFLOW_TRACKING_URI for SageMaker managed MLflow"
  value       = aws_sagemaker_mlflow_app.mlops.arn
}

output "mlflow_artifact_bucket_name" {
  description = "Name of the S3 bucket used for MLflow artifacts"
  value       = aws_s3_bucket.mlflow_artifacts.bucket
}

output "mlflow_artifact_store_uri" {
  description = "Artifact store URI configured for the SageMaker MLflow app"
  value       = local.mlflow_artifact_store_uri
}

output "sagemaker_execution_role_arn" {
  description = "Execution role ARN to export as SAGEMAKER_EXECUTION_ROLE_ARN for SageMaker training jobs"
  value       = aws_iam_role.mlops.arn
}
