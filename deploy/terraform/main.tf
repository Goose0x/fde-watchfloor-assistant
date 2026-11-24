terraform {
  required_version = ">= 1.6.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_compute_network" "private" {
  name                    = "${var.name}-vpc"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

resource "google_compute_subnetwork" "private" {
  name                     = "${var.name}-subnet"
  ip_cidr_range            = var.vpc_cidr
  region                   = var.region
  network                  = google_compute_network.private.id
  private_ip_google_access = true
}

# Default deny all egress. Workloads should not reach the public internet.
resource "google_compute_firewall" "deny_all_egress" {
  name      = "${var.name}-deny-egress"
  network   = google_compute_network.private.name
  direction = "EGRESS"
  priority  = 65534

  deny {
    protocol = "all"
  }

  destination_ranges = ["0.0.0.0/0"]
}

# Narrow allow for restricted Google APIs (Private Google Access / VPC-SC).
resource "google_compute_firewall" "allow_restricted_googleapis" {
  name      = "${var.name}-allow-restricted-apis"
  network   = google_compute_network.private.name
  direction = "EGRESS"
  priority  = 1000

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  destination_ranges = ["199.36.153.4/30"]
}

resource "google_vpc_access_connector" "connector" {
  name          = "${var.name}-cx"
  region        = var.region
  network       = google_compute_network.private.name
  ip_cidr_range = var.connector_cidr
}

resource "google_cloud_run_v2_service" "api" {
  name     = "${var.name}-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "ALL_TRAFFIC"
    }

    containers {
      image = var.image

      env {
        name  = "WATCHFLOOR_LLM_PROVIDER"
        value = "stub"
      }

      env {
        name  = "WATCHFLOOR_WORKFLOW_BACKEND"
        value = "inprocess"
      }

      ports {
        container_port = 8080
      }
    }
  }
}

# Intentionally no allUsers or allAuthenticatedUsers IAM binding.
# Grant Cloud Run Invoker to a specific service account or group outside this demo pack.
