
############################
# VPC
############################

data "aws_vpc" "mlops" {
  id = "vpc-090ce51e3e0f7120f"
}

data "aws_availability_zones" "available" {}

data "aws_subnets" "mlops" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.mlops.id]
  }
}


# ############################
# # Internet Gateway
# ############################

# resource "aws_internet_gateway" "igw" {
#   vpc_id = data.aws_vpc.mlops.id
# }

# ############################
# # Availability Zones
# ############################

# ############################
# # Public Subnets
# ############################

# resource "aws_subnet" "public_a" {
#   vpc_id                  = data.aws_vpc.mlops.id
#   cidr_block              = "10.0.1.0/24"
#   availability_zone       = data.aws_availability_zones.available.names[0]
#   map_public_ip_on_launch = true
# }

# ############################
# # Private Subnets
# ############################

# resource "aws_subnet" "private_a" {
#   vpc_id            = data.aws_vpc.mlops.id
#   cidr_block        = "10.0.11.0/24"
#   availability_zone = data.aws_availability_zones.available.names[0]
# }

# ############################
# # Elastic IP for NAT
# ############################

# resource "aws_eip" "nat" {
#   depends_on = [aws_internet_gateway.igw]
# }

# ############################
# # NAT Gateway
# ############################

# resource "aws_nat_gateway" "nat" {
#   allocation_id = aws_eip.nat.id
#   subnet_id     = aws_subnet.public_a.id
#   depends_on    = [aws_internet_gateway.igw]
# }

# ############################
# # Public Route Table
# ############################

# resource "aws_route_table" "public" {
#   vpc_id = data.aws_vpc.mlops.id
# }

# resource "aws_route" "public_internet" {
#   route_table_id         = aws_route_table.public.id
#   destination_cidr_block = "0.0.0.0/0"
#   gateway_id             = aws_internet_gateway.igw.id
# }

# ############################
# # Private Route Table
# ############################

# resource "aws_route_table" "private" {
#   vpc_id = data.aws_vpc.mlops.id
# }

# resource "aws_route" "private_nat" {
#   route_table_id         = aws_route_table.private.id
#   destination_cidr_block = "0.0.0.0/0"
#   nat_gateway_id         = aws_nat_gateway.nat.id

#   depends_on = [aws_nat_gateway.nat]
# }

# ############################
# # Route Table Associations
# ############################

# resource "aws_route_table_association" "public_a" {
#   subnet_id      = aws_subnet.public_a.id
#   route_table_id = aws_route_table.public.id
# }

# resource "aws_route_table_association" "private_a" {
#   subnet_id      = aws_subnet.private_a.id
#   route_table_id = aws_route_table.private.id
# }
