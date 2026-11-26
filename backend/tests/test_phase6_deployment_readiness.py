import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app


REPO_ROOT = Path(__file__).resolve().parents[2]


class _ComposeSafeLoader(yaml.SafeLoader):
    """SafeLoader extension supporting Docker Compose YAML override tags (!reset, !override)."""


def _compose_tag_constructor(loader: yaml.SafeLoader, tag_suffix: str, node: yaml.Node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    return None


_ComposeSafeLoader.add_multi_constructor("!", _compose_tag_constructor)


def test_metrics_endpoint_exposes_phase6_operational_gauges():
    """
    Phase 6 Monitoring Regression:
    Verifies `/metrics` exposes DB, SQLAlchemy pool, Redis, worker heartbeat,
    and notification outbox gauges alongside HTTP request counters/histograms,
    and verifies `/health/live` and `/health/ready` contract fields.
    """
    with TestClient(app) as client:
        live = client.get("/health/live")
        assert live.status_code == 200
        assert live.json()["status"] == "UP"

        ready = client.get("/health/ready")
        assert ready.status_code in (200, 503)
        ready_json = ready.json()
        assert "ready" in ready_json
        assert "database" in ready_json.get("components", {})
        assert "redis" in ready_json.get("components", {})

        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        body = metrics.text
        expected_metrics = (
            "gobeyond_http_requests_total",
            "gobeyond_http_request_duration_seconds",
            "gobeyond_active_inventory_locks",
            "gobeyond_db_up",
            "gobeyond_db_pool_size",
            "gobeyond_db_pool_checked_out",
            "gobeyond_db_pool_checked_in",
            "gobeyond_db_pool_overflow",
            "gobeyond_redis_up",
            "gobeyond_worker_heartbeat_up",
            "gobeyond_notification_outbox_jobs",
        )
        for metric_name in expected_metrics:
            assert metric_name in body, f"Expected Prometheus metric missing from /metrics: {metric_name}"


def test_settings_rejects_angle_bracket_placeholders_in_production():
    """
    Phase 6 Secrets Guard:
    Ensures template placeholder patterns like `<GENERATE_WITH_...>` or `<REPLACE_WITH_...>`
    are rejected fail-fast for SECRET_KEY and live Razorpay credentials in production.
    """
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="<GENERATE_WITH_OPENSSL_RAND_BASE64_48>",
        )

    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="<REPLACE_WITH_STRONG_SECRET_OVER_32_CHARS>",
        )

    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 48,
            RAZORPAY_SANDBOX_MODE=False,
            RAZORPAY_KEY_ID="rzp_live_<REPLACE_WITH_LIVE_KEY_ID>",
            RAZORPAY_KEY_SECRET="<REPLACE_WITH_LIVE_KEY_SECRET>",
        )

    staging_safe = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="s" * 48,
        RAZORPAY_SANDBOX_MODE=True,
        RAZORPAY_KEY_ID="rzp_test_staging_placeholder_id",
        RAZORPAY_KEY_SECRET="staging_test_secret_123456",
    )
    assert staging_safe.ENVIRONMENT == "production"
    assert staging_safe.RAZORPAY_SANDBOX_MODE is True


def test_validate_env_script_profiles_and_pool_budget():
    """
    Verifies scripts/validate_env.py validates template structure cleanly while rejecting
    unmodified production placeholder templates and oversized PostgreSQL connection budgets.
    """
    script = REPO_ROOT / "scripts" / "validate_env.py"
    if not script.is_file():
        pytest.skip("Repository root scripts/ not present inside container test context.")

    for tpl, mode in (
        (".env.example", "local"),
        (".env.staging.example", "staging"),
        (".env.production.example", "production"),
    ):
        proc = subprocess.run(
            [sys.executable, str(script), "--env-file", str(REPO_ROOT / tpl), "--mode", mode, "--template"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"{tpl} failed template validation:\n{proc.stdout}\n{proc.stderr}"
        assert "ENV_VALIDATION_RESULT=PASS" in proc.stdout

    # Without --template, .env.production.example MUST fail due to <...> placeholder markers
    fail_proc = subprocess.run(
        [sys.executable, str(script), "--env-file", str(REPO_ROOT / ".env.production.example"), "--mode", "production"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert fail_proc.returncode == 1
    assert "ENV_VALIDATION_RESULT=FAILED" in fail_proc.stderr

    # Pool connection budget guard: 4 workers * (30+20) + (10+5) = 215 > 97
    scripts_dir = str(REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import validate_env as ve

    env_map = ve.parse_env_file(REPO_ROOT / ".env.staging.example")
    env_map.update(
        {
            "POSTGRES_PASSWORD": "StrongTestPassword#2026",
            "SECRET_KEY": "k" * 48,
            "RAZORPAY_KEY_ID": "rzp_test_1234567890abcd",
            "RAZORPAY_KEY_SECRET": "test_secret_1234567890",
            "GRAFANA_ADMIN_PASSWORD": "StrongGrafanaPassword#2026",
            "UVICORN_WORKERS": "4",
            "DB_POOL_SIZE": "30",
            "DB_MAX_OVERFLOW": "20",
        }
    )
    errors, _warnings = ve.validate_env(env_map, mode="staging", template_check=False)
    assert any("exceeds default PostgreSQL usable connections (97)" in err for err in errors), errors


def test_prometheus_rules_and_grafana_dashboard_integrity():
    """
    Verifies Prometheus config references prometheus_rules.yml, all 10 required alert rules exist,
    and Grafana dashboard panels align cleanly to actual metrics emitted by `/metrics`.
    """
    mon_dir = REPO_ROOT / "devops" / "monitoring"
    if not mon_dir.is_dir():
        pytest.skip("devops/monitoring directory not present.")

    prom_cfg = yaml.safe_load((mon_dir / "prometheus.yml").read_text(encoding="utf-8"))
    assert "/etc/prometheus/prometheus_rules.yml" in prom_cfg.get("rule_files", [])
    scrape_jobs = {j["job_name"]: j for j in prom_cfg.get("scrape_configs", [])}
    assert "gobeyond-backend" in scrape_jobs
    assert scrape_jobs["gobeyond-backend"]["metrics_path"] == "/metrics"

    rules_doc = yaml.safe_load((mon_dir / "prometheus_rules.yml").read_text(encoding="utf-8"))
    groups = rules_doc.get("groups", [])
    assert groups, "Expected alert rule group in prometheus_rules.yml"
    rule_names = {rule["alert"] for group in groups for rule in group.get("rules", [])}
    expected_alerts = {
        "BackendUnavailable",
        "DatabaseUnavailable",
        "RedisUnavailable",
        "WorkerHeartbeatMissing",
        "HighHttp5xxRate",
        "HighApiLatencyP95",
        "PaymentWebhookFailures",
        "BackgroundJobBacklog",
        "DatabaseConnectionExhaustion",
        "HostDiskSpaceShortage",
    }
    assert expected_alerts.issubset(rule_names)

    dash = json.loads((mon_dir / "grafana" / "dashboards" / "gobeyond-dashboard.json").read_text(encoding="utf-8"))
    assert dash["uid"] == "gobeyond-metrics-v1"
    assert len(dash["panels"]) == 7

    dash_prov = yaml.safe_load(
        (mon_dir / "grafana" / "provisioning" / "dashboards" / "dashboards.yml").read_text(encoding="utf-8")
    )
    assert dash_prov["providers"][0]["options"]["path"] == "/etc/grafana/dashboards"
    rendered_exprs = "\n".join(
        t.get("expr", "")
        for p in dash["panels"]
        for t in p.get("targets", [])
    )
    for expected_metric in (
        "gobeyond_http_requests_total",
        "gobeyond_http_request_duration_seconds_bucket",
        "gobeyond_db_pool_checked_out",
        "gobeyond_db_up",
        "gobeyond_redis_up",
        "gobeyond_worker_heartbeat_up",
        "gobeyond_active_inventory_locks",
        "gobeyond_notification_outbox_jobs",
    ):
        assert expected_metric in rendered_exprs


def test_docker_compose_and_kubernetes_manifests_valid_yaml_and_safe_defaults():
    """
    Validates syntax and architectural invariants across Docker Compose base/prod files
    and Kubernetes manifests without requiring a local Minikube daemon.
    """
    compose_path = REPO_ROOT / "docker-compose.yml"
    prod_compose_path = REPO_ROOT / "docker-compose.prod.yml"
    k8s_dir = REPO_ROOT / "devops" / "kubernetes"
    if not compose_path.is_file() or not k8s_dir.is_dir():
        pytest.skip("Repository manifests not present.")

    compose = yaml.load(compose_path.read_text(encoding="utf-8"), Loader=_ComposeSafeLoader)
    prod_compose = yaml.load(prod_compose_path.read_text(encoding="utf-8"), Loader=_ComposeSafeLoader)

    services = set(compose["services"].keys())
    assert services == {"postgres", "redis", "backend", "worker", "frontend", "nginx", "prometheus", "grafana"}
    for svc_name, svc in compose["services"].items():
        assert "healthcheck" in svc, f"{svc_name} missing Docker healthcheck"
        assert "deploy" in svc and "resources" in svc["deploy"], f"{svc_name} missing resource limits"
        assert "logging" in svc, f"{svc_name} missing log rotation policy"

    # Production Compose overlay strips internal service ports and locks monitoring to loopback
    for internal_svc in ("postgres", "redis", "backend", "frontend"):
        assert prod_compose["services"][internal_svc]["ports"] == []
    assert prod_compose["services"]["prometheus"]["ports"] == ["127.0.0.1:9090:9090"]
    assert prod_compose["services"]["grafana"]["ports"] == ["127.0.0.1:3001:3000"]

    # Validate all Kubernetes manifests parse cleanly and honor connection & RWO constraints
    docs = []
    for manifest in sorted(k8s_dir.glob("*.yaml")):
        loaded = [d for d in yaml.safe_load_all(manifest.read_text(encoding="utf-8")) if d]
        assert loaded, f"Empty K8s YAML: {manifest.name}"
        docs.extend(loaded)

    by_kind_name = {(d["kind"], d["metadata"]["name"]): d for d in docs}

    pg_deploy = by_kind_name[("Deployment", "gobeyond-postgres")]
    redis_deploy = by_kind_name[("Deployment", "gobeyond-redis")]
    assert pg_deploy["spec"]["strategy"]["type"] == "Recreate"
    assert redis_deploy["spec"]["strategy"]["type"] == "Recreate"
    assert "postgres-init-script" in str(pg_deploy)
    assert "btree_gist" in by_kind_name[("ConfigMap", "postgres-init-script")]["data"]["init-db.sql"]

    # Secrets manifest must remain a sanitized template without real credentials
    secrets_raw = (k8s_dir / "02-secrets.yaml").read_text(encoding="utf-8")
    assert "<REPLACE_WITH_" in secrets_raw

    # Backend + Worker HPA DB connection math <= 97 default PostgreSQL usable connections
    cm_data = by_kind_name[("ConfigMap", "gobeyond-config")]["data"]
    assert cm_data["REDIS_REQUIRED_IN_PRODUCTION"] == "true"
    assert cm_data["USE_MEMORY_LOCK_FALLBACK"] == "false"

    hpa_max = by_kind_name[("HorizontalPodAutoscaler", "gobeyond-backend-hpa")]["spec"]["maxReplicas"]
    api_conns_per_pod = int(cm_data["DB_POOL_SIZE"]) + int(cm_data["DB_MAX_OVERFLOW"])
    worker_conns = int(cm_data["WORKER_DB_POOL_SIZE"]) + int(cm_data["WORKER_DB_MAX_OVERFLOW"])
    assert (hpa_max * api_conns_per_pod + worker_conns) <= 97

    worker_deploy = by_kind_name[("Deployment", "gobeyond-worker")]
    assert "initContainers" in worker_deploy["spec"]["template"]["spec"]
    assert "livenessProbe" in worker_deploy["spec"]["template"]["spec"]["containers"][0]

    ingress = by_kind_name[("Ingress", "gobeyond-ingress")]
    paths = [p["path"] for p in ingress["spec"]["rules"][0]["http"]["paths"]]
    assert "/metrics" not in paths
    assert "proxy_ignore_client_abort on;" in ingress["metadata"]["annotations"].get(
        "nginx.ingress.kubernetes.io/configuration-snippet", ""
    )

