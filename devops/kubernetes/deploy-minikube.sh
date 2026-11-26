#!/usr/bin/env bash
# ==========================================
# GO BEYOND - Minikube Deployment Script
# ==========================================
set -e

echo "Starting GO BEYOND Deployment to Minikube..."

if ! minikube status >/dev/null 2>&1; then
    echo "Starting Minikube..."
    minikube start --driver=docker --cpus=4 --memory=8192
fi

echo "Enabling Ingress and Metrics Server addons..."
minikube addons enable ingress
minikube addons enable metrics-server

echo "Pointing Docker CLI to Minikube daemon..."
eval "$(minikube docker-env)"

echo "Building Docker images inside Minikube..."
docker build -t gobeyond/backend:latest ./backend
docker build -t gobeyond/frontend:latest --build-arg NEXT_PUBLIC_API_URL="" ./frontend

echo "Applying Kubernetes Namespace and ConfigMap..."
kubectl apply -f devops/kubernetes/00-namespace.yaml
kubectl apply -f devops/kubernetes/01-configmap.yaml

if ! kubectl get secret gobeyond-secrets -n gobeyond >/dev/null 2>&1; then
    if grep -q "<REPLACE_WITH_" devops/kubernetes/02-secrets.yaml; then
        echo "ERROR: Kubernetes Secret 'gobeyond-secrets' is missing and 02-secrets.yaml still contains placeholder markers." >&2
        echo "Create it out-of-band first: kubectl create secret generic gobeyond-secrets -n gobeyond --from-env-file=.env" >&2
        exit 1
    fi
    kubectl apply -f devops/kubernetes/02-secrets.yaml
fi

kubectl apply -f devops/kubernetes/03-postgres.yaml
kubectl apply -f devops/kubernetes/04-redis.yaml

echo "Waiting for PostgreSQL and Redis to be ready..."
kubectl wait --namespace gobeyond --for=condition=ready pod -l app=gobeyond-postgres --timeout=120s
kubectl wait --namespace gobeyond --for=condition=ready pod -l app=gobeyond-redis --timeout=120s

kubectl apply -f devops/kubernetes/05-backend.yaml
kubectl apply -f devops/kubernetes/06-frontend.yaml
kubectl apply -f devops/kubernetes/07-ingress.yaml
kubectl apply -f devops/kubernetes/08-worker.yaml

echo "Waiting for Backend, Worker, and Frontend rollouts..."
kubectl rollout status deployment/gobeyond-backend -n gobeyond --timeout=180s
kubectl rollout status deployment/gobeyond-worker -n gobeyond --timeout=180s
kubectl rollout status deployment/gobeyond-frontend -n gobeyond --timeout=180s

MINIKUBE_IP=$(minikube ip)
echo "GO BEYOND Successfully Deployed!"
echo "Add to /etc/hosts: $MINIKUBE_IP gobeyond.local"
