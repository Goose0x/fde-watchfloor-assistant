# Security

This is a demonstration scoping and retrieval tool, not a production or accredited system.

## Data policy

- Use **fictional, unclassified** documents only.
- Do not paste real personal data, real customer documents, real unit or organization identifiers, or anything that is or might be classified, CUI, or otherwise restricted.
- Sample documents and planted identifiers in this repository are invented. They are not based on a real program, company, person, or engagement.
- Planted SSN-like, card-like, and email-like values exist only so the masking proxy can be tested. They are not real identifiers.

## Secrets

- API keys and cloud credentials live in environment variables or a local `.env` file that is not committed.
- `.env.example` lists names only. Never put a live key in source, tests, compose files, or Helm values committed to the repo.

## What this tool does not claim

- It is not an authority to operate, a real threat assessment, or a cross-domain solution.
- Role and compartment labels in the fixture set (`ops`, `finance`, `shared`) are demo access tags. They are not government classification markings.
- The Terraform and Helm packs show a zero-public-egress pattern on a private VPC. They are a starting point, not a hardened production baseline.
- Human approval in this MVP is a durable workflow with a local approve endpoint. It is not a substitute for a real change-control process.

## Reporting issues

If you find a defect in the masking, retrieval filter, audit chain, or deploy pack, open an issue on the repository. Do not include real personal data or restricted documents in the report.
