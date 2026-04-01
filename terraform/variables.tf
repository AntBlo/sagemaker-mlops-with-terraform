variable "domain_name" {
  description = "SageMaker Domain name"
  type        = string
  default     = "mlops"
}

variable "space_name" {
  description = "SageMaker Space name"
  type        = string
  default     = "mlops-space"
}

variable "lifecycle_config_name" {
  description = "Studio lifecycle config name"
  type        = string
  default     = "mlops-lifecycle-config"
}

variable "instance_type" {
  description = "Default instance type for Jupyter server apps"
  type        = string
  default     = "system"
}

variable "role_name" {
  description = "Name for the execution IAM role"
  type        = string
  default     = "mlops"
}

variable "tags" {
  description = "Map of tags applied to resources"
  type        = map(string)
  default = {
    Project     = "mlops"
    Environment = "dev"
  }
}
variable "env" {
  description = "Depolyment environment"
  default     = "stage"
}

variable "AWS_ID" {
  description = "AWS ID"
  default     = "417153931970"
}

variable "region" {
  description = "AWS region"
  default     = "eu-west-1"
}

variable "mlflow_app_name" {
  description = "Name of the SageMaker MLflow app"
  type        = string
  default     = "mlops-mlflow"
}

variable "mlflow_artifact_bucket_name" {
  description = "Optional explicit S3 bucket name for MLflow artifacts"
  type        = string
  default     = ""
}

variable "mlflow_artifact_prefix" {
  description = "Prefix path under the artifact bucket for MLflow artifacts"
  type        = string
  default     = "artifacts"
}

variable "mlflow_account_default_status" {
  description = "Whether the MLflow app should be account default"
  type        = string
  default     = "DISABLED"
}

variable "mlflow_model_registration_mode" {
  description = "Automatic model registration mode for MLflow"
  type        = string
  default     = "AutoModelRegistrationDisabled"
}
