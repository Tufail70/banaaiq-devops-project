terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.92"
    }
  }
}

# Tell Terraform to build this in the US East region
provider "aws" {
  region = "ap-south-1" 
}

# 1. Give AWS our Public SSH Key so we can log in later
resource "aws_key_pair" "deployer" {
  key_name   = "banaaiq-deployer-key"
  public_key = file("~/.ssh/banaaiq_key.pub")
}

# 2. Security Group: This is our server's Firewall.
resource "aws_security_group" "web_sg" {
  name        = "banaaiq_web_sg"
  description = "Allow SSH and HTTP/HTTPS inbound traffic"

  # Allow SSH (Port 22) for us to log in
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow standard web traffic (Port 80 for HTTP)
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow secure web traffic (Port 443 for HTTPS)
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow the server to access the outside internet (to download packages)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 3. Data Block: Automatically find the latest Ubuntu 22.04 Operating System
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical's official AWS Account ID

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# 4. EC2 Instance: The actual virtual server
resource "aws_instance" "web" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.small" # This type is eligible for the AWS Free Tier!
  key_name               = aws_key_pair.deployer.key_name
  vpc_security_group_ids = [aws_security_group.web_sg.id]

  tags = {
    Name = "BanaaIQ-Production-Server"
  }
}

# 5. Output: After creation, print out the public IP address so we know where it lives
output "server_public_ip" {
  description = "The public IP address of our new server"
  value       = aws_instance.web.public_ip
}
