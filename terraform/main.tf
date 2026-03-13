provider "aws" {
  region  = var.region
  profile = "default"
}

#provider "gitlab" {
#  token = var.gitlab_token
#}

terraform {
  required_providers {
    gitlab = {
      source = "gitlabhq/gitlab"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "6.36.0"
    }
  }
}

terraform {
  backend "s3" {
    bucket = "sagemaker-mlops-kg63"
    key    = "tfstate/terraform.tfstate"
    region = "eu-west-1"
  }
}
