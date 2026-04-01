resource "aws_sagemaker_domain" "mlops" {
  domain_name = var.domain_name
  auth_mode   = "IAM"
  vpc_id      = data.aws_vpc.mlops.id
  subnet_ids  = [data.aws_subnets.mlops.ids[0]]

  default_user_settings {
    execution_role = aws_iam_role.mlops.arn

    jupyter_server_app_settings {
      default_resource_spec {
        instance_type        = var.instance_type
        lifecycle_config_arn = aws_sagemaker_studio_lifecycle_config.mlops.arn
      }
    }
  }

  default_space_settings {
    execution_role = aws_iam_role.mlops.arn

    jupyter_server_app_settings {
      default_resource_spec {
        instance_type        = var.instance_type
        lifecycle_config_arn = aws_sagemaker_studio_lifecycle_config.mlops.arn
      }
    }
  }
}

resource "aws_iam_role_policy_attachment" "sagemaker_execution" {
  role       = aws_iam_role.mlops.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

resource "aws_sagemaker_studio_lifecycle_config" "mlops" {
  studio_lifecycle_config_name     = var.lifecycle_config_name
  studio_lifecycle_config_app_type = "JupyterServer"
  studio_lifecycle_config_content  = base64encode("echo hello")

}

resource "aws_sagemaker_space" "mlops" {
  domain_id  = aws_sagemaker_domain.mlops.id
  space_name = var.space_name

  ownership_settings {
    owner_user_profile_name = aws_sagemaker_user_profile.mlops_user.user_profile_name
  }

  space_settings {
    app_type = "JupyterLab"

    jupyter_server_app_settings {
      default_resource_spec {
        instance_type        = var.instance_type
        lifecycle_config_arn = aws_sagemaker_studio_lifecycle_config.mlops.arn
      }
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
      ]
    }
  }
}

resource "aws_iam_role" "mlops" {
  name               = var.role_name
  assume_role_policy = data.aws_iam_policy_document.mlops_trust.json
}


# SageMaker User Profile
resource "aws_sagemaker_user_profile" "mlops_user" {
  domain_id         = aws_sagemaker_domain.mlops.id
  user_profile_name = aws_iam_user.mlops_user.name

  user_settings {
    execution_role = aws_iam_role.mlops.arn

    jupyter_server_app_settings {
      default_resource_spec {
        instance_type        = var.instance_type
        lifecycle_config_arn = aws_sagemaker_studio_lifecycle_config.mlops.arn
      }
    }
  }
}
