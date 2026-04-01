resource "aws_iam_user" "mlops_user" {
  name = "mlops-user"
}

resource "aws_iam_user_login_profile" "mlops_user_password" {
  user                    = aws_iam_user.mlops_user.name
  password_reset_required = false
}

resource "aws_iam_user_policy_attachment" "mlops_attach_sagemaker_full" {
  user       = aws_iam_user.mlops_user.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

resource "aws_iam_user_policy" "mlops_mlflow_access" {
  name = "mlops-mlflow-access"
  user = aws_iam_user.mlops_user.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sagemaker:*Mlflow*",
          "sagemaker-mlflow:*",
        ]
        Resource = "*"
      }
    ]
  })
}
