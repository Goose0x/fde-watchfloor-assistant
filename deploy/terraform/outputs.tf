output "vpc_name" {
  value       = google_compute_network.private.name
  description = "Private VPC name."
}

output "subnet_name" {
  value       = google_compute_subnetwork.private.name
  description = "Private subnet with Private Google Access enabled."
}

output "cloud_run_uri" {
  value       = google_cloud_run_v2_service.api.uri
  description = "Internal Cloud Run URI. Not reachable from the public internet."
}

output "vpc_sc_notes" {
  value       = "Add this project to a VPC Service Controls perimeter covering Cloud Run, Artifact Registry, Logging, and optional Vertex AI. Use restricted.googleapis.com (199.36.153.4/30) rather than public internet egress."
  description = "Operator reminder for the organization-level perimeter."
}
