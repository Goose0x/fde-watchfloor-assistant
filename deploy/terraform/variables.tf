variable "project_id" {
  type        = string
  description = "Google Cloud project that will host the private VPC and Cloud Run service."
}

variable "region" {
  type        = string
  description = "Region for the subnet, VPC connector, and Cloud Run service."
  default     = "us-central1"
}

variable "name" {
  type        = string
  description = "Name prefix for network and service resources."
  default     = "watchfloor"
}

variable "image" {
  type        = string
  description = "Container image for the API (Artifact Registry path recommended)."
  default     = "us-central1-docker.pkg.dev/example/watchfloor/watchfloor:latest"
}

variable "vpc_cidr" {
  type        = string
  default     = "10.40.0.0/20"
  description = "Primary CIDR for the private subnet."
}

variable "connector_cidr" {
  type        = string
  default     = "10.40.16.0/28"
  description = "Unused /28 for the Serverless VPC Access connector."
}
