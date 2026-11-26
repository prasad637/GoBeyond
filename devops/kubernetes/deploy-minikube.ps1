# ==========================================
# GO BEYOND - Minikube Deployment Script (PowerShell)
# ==========================================
Write-Host "Starting GO BEYOND Deployment to Minikube..." -ForegroundColor Cyan

# Check if Minikube is running
$status = minikube status --format "{{.Host}}" 2>$null
if ($status -ne "Running") {
    Write-Host "Starting Minikube..." -ForegroundColor Yellow
    minikube start --driver=docker --cpus=4 --memory=8192
}

Write-Host "Enabling Ingress and Metrics Server addons..." -ForegroundColor Cyan
minikube addons enable ingress
minikube addons enable metrics-server

Write-Host "Configuring Minikube Docker environment..." -ForegroundColor Cyan
& minikube -p minikube docker-env --shell powershell | Invoke-Expression

Write-Host "Building Docker images inside Minikube..." -ForegroundColor Cyan
docker build -t gobeyond/backend:latest ./backend
docker build -t gobeyond/frontend:latest --build-arg NEXT_PUBLIC_API_URL="" ./frontend

Write-Host "Applying Kubernetes Namespace and ConfigMap..." -ForegroundColor Cyan
kubectl apply -f devops/kubernetes/00-namespace.yaml
kubectl apply -f devops/kubernetes/01-configmap.yaml

# Guard against deploying placeholder secrets from template 02-secrets.yaml
$secretExists = $false
kubectl get secret gobeyond-secrets -n gobeyond *> $null
if ($LASTEXITCODE -eq 0) { $secretExists = $true }

if (-not $secretExists) {
    $secretsRaw = Get-Content devops/kubernetes/02-secrets.yaml -Raw
    if ($secretsRaw -match '<REPLACE_WITH_') {
        Write-Error "Kubernetes Secret 'gobeyond-secrets' is not created and devops/kubernetes/02-secrets.yaml contains placeholders. Create it out-of-band with 'kubectl create secret generic gobeyond-secrets -n gobeyond --from-env-file=.env' before running this script."
        exit 1
    }
    kubectl apply -f devops/kubernetes/02-secrets.yaml
}

kubectl apply -f devops/kubernetes/03-postgres.yaml
kubectl apply -f devops/kubernetes/04-redis.yaml

Write-Host "Waiting for Database and Redis to become ready..." -ForegroundColor Yellow
kubectl wait --namespace gobeyond --for=condition=ready pod -l app=gobeyond-postgres --timeout=120s
kubectl wait --namespace gobeyond --for=condition=ready pod -l app=gobeyond-redis --timeout=120s

kubectl apply -f devops/kubernetes/05-backend.yaml
kubectl apply -f devops/kubernetes/06-frontend.yaml
kubectl apply -f devops/kubernetes/07-ingress.yaml
kubectl apply -f devops/kubernetes/08-worker.yaml

Write-Host "Waiting for Backend, Worker, and Frontend rollouts..." -ForegroundColor Yellow
kubectl rollout status deployment/gobeyond-backend -n gobeyond --timeout=180s
kubectl rollout status deployment/gobeyond-worker -n gobeyond --timeout=180s
kubectl rollout status deployment/gobeyond-frontend -n gobeyond --timeout=180s

$minikubeIp = minikube ip
Write-Host "GO BEYOND Successfully Deployed to Kubernetes!" -ForegroundColor Green
Write-Host "Add to hosts file: $minikubeIp gobeyond.local" -ForegroundColor Magenta
