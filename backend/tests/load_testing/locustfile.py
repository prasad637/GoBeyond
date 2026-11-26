"""
Locust load testing scenario for GO BEYOND platform.
Simulates realistic concurrent user browsing across discovery, search, and catalog endpoints.
Run via: locust -f backend/tests/load_testing/locustfile.py --host=http://localhost:8000
"""
from locust import HttpUser, task, between


class GoBeyondCustomerUser(HttpUser):
    wait_time = between(1, 3)

    @task(5)
    def view_home_discovery_feed(self):
        """High-traffic homepage discovery feed with city filtering."""
        self.client.get(
            "/api/v1/discovery/home?city_slug=hyderabad",
            headers={"X-Correlation-ID": "locust-home-feed"}
        )

    @task(3)
    def search_all_verticals(self):
        """Unified catalog search across all 5 lifestyle verticals."""
        self.client.get(
            "/api/v1/discovery/search?q=biryani&category=ALL",
            headers={"X-Correlation-ID": "locust-search"}
        )

    @task(2)
    def get_supported_cities(self):
        """Fetch list of supported launch cities."""
        self.client.get(
            "/api/v1/locations/cities",
            headers={"X-Correlation-ID": "locust-cities"}
        )

    @task(2)
    def get_hyderabad_localities(self):
        """Fetch localities within Hyderabad."""
        self.client.get(
            "/api/v1/locations/localities?city_slug=hyderabad",
            headers={"X-Correlation-ID": "locust-localities"}
        )

    @task(1)
    def health_check(self):
        """Liveness and readiness probes."""
        self.client.get("/health/ready")

