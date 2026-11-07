# DevSecOps-Based Secure CI/CD Pipeline

A DevOps mini-project that shows how security is built into every stage of a CI/CD pipeline ("shift-left security") instead of being bolted on at the end. A small Flask REST API is used as the protected application; the focus is the **pipeline**.

## Architecture

```
 git push / PR
      │
      ▼
┌───────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐
│ 1 Secret scan │   │ 2 SAST     │   │ 3 SCA      │   │ 4 Unit     │   run in
│   Gitleaks    │   │ Bandit +   │   │ pip-audit  │   │ tests +    │   parallel
│               │   │ Semgrep    │   │            │   │ coverage   │
└──────┬────────┘   └─────┬──────┘   └─────┬──────┘   └─────┬──────┘
       └──────────────────┴────────┬───────┴────────────────┘
                                   ▼  (all must pass)
                        ┌─────────────────────┐
                        │ 5 Hadolint + Build  │
                        └──────────┬──────────┘
                     ┌─────────────┴─────────────┐
                     ▼                           ▼
          ┌────────────────────┐      ┌────────────────────┐
          │ 6 Trivy image scan │      │ 7 DAST             │
          │   + SBOM           │      │   OWASP ZAP        │
          └─────────┬──────────┘      └─────────┬──────────┘
                    └─────────────┬─────────────┘
                                  ▼  (main branch only)
                        ┌─────────────────────┐
                        │ 8 Push to GHCR      │
                        │   + Cosign signing  │
                        └─────────────────────┘
```

## What each stage does

| # | Stage | Tool | What it catches | Fails the build when |
|---|-------|------|-----------------|----------------------|
| 1 | Secret scanning | Gitleaks | API keys, passwords, tokens committed to git (including history) | any secret is found |
| 2 | SAST | Bandit, Semgrep | insecure code: injection, `eval`, weak crypto, debug mode, OWASP Top 10 patterns | medium+ severity finding |
| 3 | SCA | pip-audit | known CVEs in third-party dependencies | any known vulnerability |
| 4 | Testing | pytest + coverage | functional bugs and missing input validation | test fails or coverage < 85% |
| 5 | Build hygiene | Hadolint | Dockerfile anti-patterns (root user, unpinned tags, etc.) | warning or worse |
| 6 | Container scan | Trivy | OS-package and library CVEs inside the image | HIGH/CRITICAL with a fix available |
| 6 | SBOM | Syft (anchore/sbom-action) | produces a CycloneDX software bill of materials | n/a (artifact) |
| 7 | DAST | OWASP ZAP baseline | runtime issues: missing headers, info leaks, reflected input | any HIGH-risk alert |
| 8 | Publish and sign | GHCR + Cosign | tampering - image is signed keylessly with Sigstore | only runs on `main` after all gates pass |

### Other security measures in the repo

- **Least-privilege workflow permissions**: `contents: read` by default; jobs elevate only what they need.
- **Hardened container**: multi-stage build, slim base, non-root UID 10001, no shell for the user, healthcheck, read-only filesystem and dropped capabilities in `docker-compose.yml`.
- **Hardened app**: strict input validation (regex allow-list), request size limit, security headers (CSP, X-Frame-Options, nosniff, ...), no debug mode.
- **Dependabot** keeps pip, Docker and GitHub Actions dependencies fresh.
- **Weekly scheduled run** re-scans so newly disclosed CVEs are caught even without a code change.
- **Results in the Security tab**: Semgrep and Trivy upload SARIF to GitHub code scanning (needs a public repo or GitHub Advanced Security).

## Project structure

```
.
├── app/
│   ├── app.py                 # Flask API with validation + security headers
│   └── requirements.txt       # pinned runtime dependencies
├── tests/test_app.py          # pytest suite (16 tests, ~98% coverage)
├── Dockerfile                 # multi-stage, non-root
├── docker-compose.yml         # hardened local run
├── requirements-dev.txt       # pytest, bandit, pip-audit
├── scripts/local-scan.sh      # run the same gates locally
├── .zap/rules.tsv             # ZAP rule tuning
└── .github/
    ├── workflows/devsecops.yml   # the pipeline
    └── dependabot.yml
```

## How to run it

### 1. On GitHub (the real pipeline)

```bash
git init
git add .
git commit -m "Initial DevSecOps pipeline"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

Open the **Actions** tab to watch the 8 stages run. For the publish stage, make sure
*Settings → Actions → General → Workflow permissions* allows read and write (needed to push to GHCR).

### 2. Locally

```bash
./scripts/local-scan.sh          # bandit + pip-audit + pytest (+ trivy if installed)

# run the app
docker compose up --build
curl localhost:5000/health
curl "localhost:5000/api/greet?name=Arif"
curl -X POST localhost:5000/api/echo -H 'Content-Type: application/json' -d '{"text":"hello"}'
```

## Demo script: make the pipeline fail on purpose

Show your examiner that the gates really work. Each experiment on a branch should turn a stage red.

| Experiment | Add this | Stage that fails |
|------------|----------|------------------|
| Leak a secret | commit a file containing `AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"` | 1 Gitleaks |
| Insecure code | `import subprocess; subprocess.call(user_input, shell=True)` in `app.py` | 2 Bandit/Semgrep |
| Debug mode | `app.run(host="0.0.0.0", debug=True)` | 2 Bandit |
| Vulnerable dependency | change `flask==3.1.3` to `flask==2.0.1` | 3 pip-audit |
| Run as root | remove the `USER 10001:10001` line | 5 Hadolint |
| Vulnerable base image | change base to `python:3.8-slim-buster` | 6 Trivy |
| Remove validation | return `request.args["name"]` unchecked as HTML | 7 ZAP / 4 tests |

## Results observed while building this project

- The **SCA stage found real CVEs** (two advisories) in Flask 3.1.0 during local verification; fixed by upgrading to 3.1.3, after which `pip-audit` reports no known vulnerabilities.
- Bandit: 0 findings. pytest: 16 passed, ~98% coverage.

## Tools and why they were chosen

- **GitHub Actions**: free, YAML-based, no server to maintain.
- **Gitleaks / Bandit / Semgrep / pip-audit / Hadolint / Trivy / ZAP / Syft / Cosign**: all open source, each covering a different layer (secrets, code, dependencies, config, image, running app, supply chain).

## Possible extensions

- Deploy to Kubernetes or a VM after the publish stage, with a manual approval gate.
- Add Kyverno or cosign verification to only admit signed images.
- Add Infrastructure-as-Code scanning (Checkov, tfsec) if you add Terraform.
- Send Slack or email notifications on failure.
