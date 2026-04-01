locals {
  resolved_mlflow_artifact_bucket_name = var.mlflow_artifact_bucket_name != "" ? var.mlflow_artifact_bucket_name : "mlflow-artifacts-${data.aws_caller_identity.current.account_id}-${data.aws_region.current.region}"
  mlflow_artifact_store_uri            = "s3://${aws_s3_bucket.mlflow_artifacts.bucket}/${trim(var.mlflow_artifact_prefix, "/")}"
}

resource "aws_s3_bucket" "mlflow_artifacts" {
  bucket = local.resolved_mlflow_artifact_bucket_name
  tags   = var.tags
}

resource "aws_s3_bucket_public_access_block" "mlflow_artifacts" {
  bucket = aws_s3_bucket.mlflow_artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "mlflow_artifacts" {
  bucket = aws_s3_bucket.mlflow_artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

data "aws_iam_policy_document" "mlflow_app_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["sagemaker.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "mlflow_app" {
  name               = "${var.role_name}-mlflow-app"
  assume_role_policy = data.aws_iam_policy_document.mlflow_app_trust.json
  tags               = var.tags
}

data "aws_iam_policy_document" "mlflow_app_s3_access" {
  statement {
    sid = "ListMlflowArtifactBucket"

    actions = [
      "s3:GetBucketLocation",
      "s3:ListBucket",
    ]

    resources = [aws_s3_bucket.mlflow_artifacts.arn]
  }

  statement {
    sid = "ReadWriteMlflowArtifacts"

    actions = [
      "s3:AbortMultipartUpload",
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:ListBucketMultipartUploads",
      "s3:ListMultipartUploadParts",
      "s3:PutObject",
    ]

    resources = ["${aws_s3_bucket.mlflow_artifacts.arn}/*"]
  }
}

resource "aws_iam_role_policy" "mlflow_app_s3_access" {
  name   = "${var.role_name}-mlflow-app-s3-access"
  role   = aws_iam_role.mlflow_app.id
  policy = data.aws_iam_policy_document.mlflow_app_s3_access.json
}

resource "aws_sagemaker_mlflow_app" "mlops" {
  name                    = var.mlflow_app_name
  role_arn                = aws_iam_role.mlflow_app.arn
  artifact_store_uri      = local.mlflow_artifact_store_uri
  model_registration_mode = var.mlflow_model_registration_mode
  tags                    = var.tags

  depends_on = [
    aws_s3_bucket_server_side_encryption_configuration.mlflow_artifacts,
    aws_s3_bucket_public_access_block.mlflow_artifacts,
    aws_iam_role_policy.mlflow_app_s3_access,
  ]
}
