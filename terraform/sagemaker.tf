resource "aws_sagemaker_domain" "mlops" {
  domain_name = "mlops"
  auth_mode   = "IAM"
  vpc_id      = aws_vpc.mlops.id
  subnet_ids  = [aws_subnet.private_a.id]

  default_user_settings {
    execution_role = aws_iam_role.mlops.arn

    jupyter_server_app_settings {
      default_resource_spec {
        instance_type        = "system"
        lifecycle_config_arn = aws_sagemaker_studio_lifecycle_config.mlops.arn
      }
      lifecycle_config_arns = [
        aws_sagemaker_studio_lifecycle_config.mlops.arn
      ]
    }
  }

  default_space_settings {
    execution_role = aws_iam_role.mlops.arn

    jupyter_server_app_settings {
      default_resource_spec {
        instance_type        = "system"
        lifecycle_config_arn = aws_sagemaker_studio_lifecycle_config.mlops.arn
      }

      lifecycle_config_arns = [
        aws_sagemaker_studio_lifecycle_config.mlops.arn
      ]
    }
  }

}

resource "aws_iam_role_policy_attachment" "sagemaker_execution" {
  role       = aws_iam_role.mlops.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

resource "aws_sagemaker_studio_lifecycle_config" "mlops" {
  studio_lifecycle_config_name     = "mlops-lifecycle-config"
  studio_lifecycle_config_app_type = "JupyterServer"
  studio_lifecycle_config_content  = base64encode("echo hello")
}

resource "aws_sagemaker_space" "mlops" {
  domain_id  = aws_sagemaker_domain.mlops.id
  space_name = "mlops-space"

  ownership_settings {
    owner_user_profile_name = aws_sagemaker_user_profile.mlops_user.user_profile_name
  }

  space_settings {
    app_type = "JupyterLab"

    jupyter_server_app_settings {
      default_resource_spec {
        instance_type        = "system"
        lifecycle_config_arn = aws_sagemaker_studio_lifecycle_config.mlops.arn
      }
      lifecycle_config_arns = [aws_sagemaker_studio_lifecycle_config.mlops.arn]
    }
  }

  space_sharing_settings {
    sharing_type = "Shared"
  }

  depends_on = [
    aws_sagemaker_user_profile.mlops_user,
    aws_sagemaker_domain.mlops,
  ]
}

data "aws_iam_policy_document" "mlops_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type = "Service"
      identifiers = [
        "sagemaker.amazonaws.com",
        "sagemaker-geospatial.amazonaws.com"
      ]
    }
  }
}

resource "aws_iam_role" "mlops" {
  name               = "mlops"
  assume_role_policy = data.aws_iam_policy_document.mlops_trust.json
}

data "aws_iam_policy_document" "mlops_permissions" {
  statement {
    effect = "Allow"

    actions = [
      # Domain actions
      "sagemaker:ListDomains",
      "sagemaker:DescribeDomain",
      # Space actions
      "sagemaker:ListSpaces",
      "sagemaker:CreateSpace",
      "sagemaker:UpdateSpace",
      "sagemaker:DescribeSpace",
      "sagemaker:StartSpace",
      "sagemaker:StopSpace",
      "sagemaker:StartSession",
      # App actions
      "sagemaker:CreateApp",
      "sagemaker:ListApps",
      "sagemaker:DeleteApp",
      "sagemaker:DescribeApp",
      "sagemaker:CreatePresignedDomainUrl",
      "sagemaker:AddTags",
      # UserProfile actions
      "sagemaker:ListUserProfiles",
      "sagemaker:DescribeUserProfile",
      # Logging & monitoring
      "cloudwatch:PutMetricData",
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = ["*"]
  }

  statement {
    effect = "Allow"
    actions = [
      "sagemaker:CreateApp",
      "sagemaker:ListSpaces",
      "sagemaker:CreateSpace",
      "sagemaker:UpdateSpace",
      "sagemaker:DescribeSpace",
      "sagemaker:StartSpace",
      "sagemaker:StopSpace",
      "sagemaker:StartApp",
      "sagemaker:StopApp",
      "sagemaker:DeleteSpace",
      "sagemaker:CreateUserProfile",
      "sagemaker:DescribeApp",
    ]
    resources = [
      "arn:aws:sagemaker:${var.region}:${data.aws_caller_identity.current.account_id}:app/${aws_sagemaker_domain.mlops.id}/*"
    ]
  }
}

resource "aws_iam_role_policy" "mlops_permissions" {
  name   = "mlops-sagemaker-execution-policy"
  role   = aws_iam_role.mlops.id
  policy = data.aws_iam_policy_document.mlops_permissions.json
}

# SageMaker User Profile
resource "aws_sagemaker_user_profile" "mlops_user" {
  domain_id         = aws_sagemaker_domain.mlops.id
  user_profile_name = aws_iam_user.mlops_user.name

  user_settings {
    execution_role = aws_iam_role.mlops.arn

    jupyter_server_app_settings {
      default_resource_spec {
        instance_type        = "system"
        lifecycle_config_arn = aws_sagemaker_studio_lifecycle_config.mlops.arn
      }
      lifecycle_config_arns = [
        aws_sagemaker_studio_lifecycle_config.mlops.arn
      ]
    }
  }
}
