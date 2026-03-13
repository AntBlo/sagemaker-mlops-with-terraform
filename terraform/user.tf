resource "aws_iam_user" "mlops_user" {
  name = "mlops-studio-user"
}

resource "aws_iam_user_login_profile" "mlops_user_password" {
  user                    = aws_iam_user.mlops_user.name
  password_reset_required = false
}

resource "aws_iam_user_policy" "mlops_studio_policy" {
  name = "mlops-studio-user-policy"
  user = aws_iam_user.mlops_user.name

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          # Domain & Studio login
          "sagemaker:ListDomains",
          "sagemaker:DescribeDomain",
          "sagemaker:CreatePresignedDomainUrl",
          "sagemaker:ListUserProfiles",
          "sagemaker:StartSpace",
          "sagemaker:StopSpace",
          "sagemaker:CreateApp",
          "sagemaker:ListSpaces",
          "sagemaker:CreateSpace",
          "sagemaker:UpdateSpace",
          "sagemaker:DescribeSpace",
          "sagemaker:DescribeApp",
          "sagemaker:DeleteApp",
          "sagemaker:ListApps",
          "sagemaker:StartSession",
          "sts:GetSessionToken",
        ],
        Resource = [
          "*",
        ]
      },
      {
        "Effect" : "Allow",
        "Action" : [
          "sagemaker:DescribeUserProfile",
          "sagemaker:UpdateUserProfile"
        ],
        "Resource" : "arn:aws:sagemaker:eu-west-1:417153931970:user-profile/d-8nj1vy8xdefj/mlops-studio-user"
      },
      {
        "Effect" : "Allow",
        "Action" : [
          "sagemaker:DescribeDomain",
          "sagemaker:UpdateDomain"
        ],
        "Resource" : "arn:aws:sagemaker:eu-west-1:417153931970:domain/d-8nj1vy8xdefj"
      },
      {
        Effect = "Allow",
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ],
        Resource = ["arn:aws:s3:::*"]
      },
      {
        Effect = "Allow",
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "cloudwatch:PutMetricData"
        ],
        Resource = "*"
      }
    ]
  })
}
