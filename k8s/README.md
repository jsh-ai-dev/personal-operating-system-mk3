# mk3 Kubernetes (Learning-Friendly Standard)

This setup keeps `mk3` practical for learning and AWS deployment:

- local/base includes MongoDB + Qdrant + mk3 app
- AWS overlay assumes MongoDB/Qdrant are managed externally and runs only mk3 app on EKS

## Included

- `Namespace`
- `ConfigMap` + `Secret`
- `MongoDB` (Deployment + PVC + Service)
- `Qdrant` (Deployment + PVC + Service)
- `App` (Deployment + Service)
- `Ingress`

## Apply (base)

1) Create local secret file (not committed):

```bash
cp k8s/base/secret.example.yaml k8s/base/secret.yaml
```

2) Apply:

```bash
kubectl apply -k k8s/base
kubectl -n pos-mk3 get all
```

## AWS overlay

Use this when MongoDB/Qdrant are external (MongoDB Atlas or self-managed, Qdrant Cloud or external service).

1) Prepare overlay secret:

```bash
cp k8s/overlays/aws/secret.aws.example.yaml k8s/overlays/aws/secret.aws.yaml
# edit MongoDB/Qdrant/API key values
```

2) In `k8s/overlays/aws/kustomization.yaml`, replace ECR image URI.

3) Apply:

```bash
kubectl apply -k k8s/overlays/aws
kubectl -n pos-mk3 get all
```

## Build image example (ECR)

```bash
docker build -f Dockerfile.api -t personal-operating-system-mk3-app:latest .
```
