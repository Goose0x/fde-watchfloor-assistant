# Google Cloud private VPC deploy pack

This pack sketches a zero-public-egress substrate for Watchfloor on Google Cloud:

- A custom VPC and private subnet with **Private Google Access** enabled.
- Default-deny egress firewall, with a narrow allow for the restricted Google APIs range (`restricted.googleapis.com` / `199.36.153.4/30`) so the platform can reach Vertex or Artifact Registry without general internet.
- A **Serverless VPC Access** connector and a **Cloud Run** service with internal ingress only and all egress forced through the VPC.
- Notes on wrapping the project in a **VPC Service Controls** perimeter.

This is a starting point, not a production baseline. Apply it only in a project you control, with fictional / unclassified data.

## What you need

- A Google Cloud project, billing, and the `roles/owner` or equivalent to create networking, Cloud Run, and IAM.
- Terraform >= 1.6 and the `hashicorp/google` provider.
- Container image pushed to Artifact Registry in the same project (or a private repo reachable via Private Google Access).

## Apply

```bash
terraform init
terraform plan -var="project_id=YOUR_PROJECT" -var="region=us-central1" -var="image=REGION-docker.pkg.dev/PROJECT/REPO/watchfloor:tag"
terraform apply -var="project_id=YOUR_PROJECT" -var="region=us-central1" -var="image=REGION-docker.pkg.dev/PROJECT/REPO/watchfloor:tag"
```

## Private Google Access and VPC Service Controls

- `private_ip_google_access = true` on the subnet lets instances and the VPC connector reach Google APIs without a public IP.
- Prefer `restricted.googleapis.com` over `private.googleapis.com` when the project sits inside a VPC-SC perimeter. Point `*.googleapis.com` at `199.36.153.4/30` with a private DNS zone (not created here; add it when you stand up the perimeter).
- VPC Service Controls themselves are organization-level. Create a perimeter that includes this project and the APIs you actually use (Cloud Run, Artifact Registry, Logging, and optionally Vertex AI). Do not add unrestricted public egress or a broad access level that bypasses the perimeter for the demo service.
- The Cloud Run service is `INGRESS_TRAFFIC_INTERNAL_ONLY`. Reach it from inside the VPC (or an IAP / Identity-Aware Proxy path you add later), not from the public internet.

## GKE alternative

A private GKE Autopilot or standard private cluster can replace Cloud Run. Keep the same VPC, disable public node IPs, and install the Helm chart under `deploy/helm/watchfloor` with the provided NetworkPolicy (default-deny egress except DNS, Postgres, and the restricted Google APIs range). The chart is the workload pack; this Terraform is the network pack.

## Egress smoke test

From a workload Pod or a Cloud Run job attached to the connector:

```bash
deploy/scripts/egress-smoke.sh
```

The script must fail to reach a public URL. If it succeeds, the perimeter is open and should be closed before any demo that claims zero public egress.
