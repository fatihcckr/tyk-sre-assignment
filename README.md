# Tyk SRE Tool

An internal tool for the SRE team to monitor and maintain the health of workloads running on a Kubernetes cluster. Built with Python, deployed via Helm, and automated with GitHub Actions.

## Completed Stories

1. **Deployment Health Check** - Lists all deployments across all namespaces and reports whether each has the expected number of ready replicas.
2. **K8s API Server Connectivity** - A readiness endpoint that verifies the tool can communicate with the configured Kubernetes API server.
3. **CI/CD Pipeline** - Automatically builds a container image and pushes it to GitHub Container Registry on every push to `main`.
4. **Helm Chart** - A Helm chart to deploy the tool into a Kubernetes cluster with RBAC, probes, and resource limits.

## API Endpoints

| Endpoint | Method | Description | Success | Failure |
|----------|--------|-------------|---------|---------|
| `/healthz` | GET | Liveness check | `200 ok` | - |
| `/readyz` | GET | Readiness check (K8s API connectivity) | `200 ok` | `503` + error message |
| `/api/deployments/health` | GET | Deployment health across all namespaces | `200` JSON with deployment status | - |

## Getting Started

### Prerequisites

- Python 3.12+
- Access to a Kubernetes cluster (kubeconfig)

### Setup

```bash
cd python
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
```

### Run

```bash
python3 main.py --kubeconfig '/path/to/your/kube/conf' --address ':8080'
```

## Running Tests

```bash
cd python
python3 tests.py -v
```

## Docker

### Build

```bash
docker build -t tyk-sre-tool:latest ./python
```

### Run

With a kubeconfig file:

```bash
docker run -p 8080:8080 \
  -v /path/to/kubeconfig:/home/appuser/.kube/config \
  tyk-sre-tool:latest \
  python main.py --address :8080 --kubeconfig /home/appuser/.kube/config
```

## Helm Deployment

### Install

```bash
helm install tyk-sre-tool ./helm/tyk-sre-tool
```

### Upgrade

```bash
helm upgrade tyk-sre-tool ./helm/tyk-sre-tool
```

### Uninstall

```bash
helm uninstall tyk-sre-tool
```

### Custom values

```bash
helm install tyk-sre-tool ./helm/tyk-sre-tool \
  --set image.tag=abc123 \
  --set replicaCount=3
```

## CI/CD

A GitHub Actions workflow (`.github/workflows/build.yml`) triggers on every push to `main`. It builds the Docker image from `python/Dockerfile` and pushes it to GitHub Container Registry at:

```
ghcr.io/<owner>/tyk-sre-assignment/tyk-sre-tool:<git-sha>
ghcr.io/<owner>/tyk-sre-assignment/tyk-sre-tool:latest
```
