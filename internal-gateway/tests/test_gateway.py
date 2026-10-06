"""Run with: python3 -m unittest discover -s internal-gateway/tests -v."""

import json
import subprocess
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


COMPOSE_FILE = Path(__file__).with_name("compose.yaml")


def request(url, *, method="GET", body=None, headers=None):
    req = Request(url, data=body, headers=headers or {}, method=method)
    try:
        response = urlopen(req, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        return response.status, response.headers, response.read()


def wait_for(url):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            status, _, body = request(url)
            if status == 200:
                return json.loads(body)
        except (URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(0.25)
    raise AssertionError(f"Timed out waiting for {url}")


class GatewayTests(unittest.TestCase):
    @classmethod
    def compose(cls, *args):
        result = subprocess.run(
            ["docker", "compose", "-p", cls.project, "-f", str(COMPOSE_FILE), *args],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return result.stdout.strip()

    @classmethod
    def setUpClass(cls):
        cls.project = f"foc-gateway-test-{uuid4().hex[:8]}"
        cls.addClassCleanup(cls.compose, "down", "--volumes", "--remove-orphans")
        # Start proxies without peers: nginx must not require them at startup.
        cls.compose("up", "-d", "--build", "internal-gateway", "ui")
        cls.gateway_url = "http://" + cls.compose("port", "internal-gateway", "80")
        cls.ui_url = "http://" + cls.compose("port", "ui", "80")
        cls.startup_health = wait_for(cls.gateway_url + "/health")
        cls.compose("exec", "-T", "internal-gateway", "nginx", "-t")
        cls.unavailable_status = request(cls.gateway_url + "/user-api/health")[0]
        cls.compose("up", "-d", "user-service", "supplier-service")
        for prefix in ("/user-api", "/supplier-api"):
            wait_for(cls.gateway_url + prefix + "/health")
            wait_for(cls.ui_url + prefix + "/health")

    def test_gateway_starts_without_backends(self):
        self.assertEqual(
            self.startup_health,
            {"status": "healthy", "service": "internal-gateway"},
        )
        self.assertEqual(self.unavailable_status, 502)

    def test_routes_preserve_requests_through_both_proxies(self):
        for origin in (self.gateway_url, self.ui_url):
            for prefix, service in (
                ("/user-api", "user-service"),
                ("/supplier-api", "supplier-service"),
            ):
                for method in ("GET", "POST", "PATCH", "DELETE"):
                    with self.subTest(origin=origin, service=service, method=method):
                        path = "/resource/123?query=a%20b&limit=2"
                        body = b'{"name":"Test Cafe"}' if method != "GET" else None
                        status, headers, raw = request(
                            origin + prefix + path,
                            method=method,
                            body=body,
                            headers={
                                "Authorization": "Bearer test-token",
                                "Cookie": "access_token=cookie-token",
                                "Content-Type": "application/json",
                            },
                        )
                        result = json.loads(raw)
                        self.assertEqual(status, 200)
                        self.assertEqual(result["service"], service)
                        self.assertEqual(result["path"], path)
                        self.assertEqual(result["method"], method)
                        self.assertEqual(result["body"], (body or b"").decode())
                        self.assertEqual(
                            result["headers"]["authorization"], "Bearer test-token"
                        )
                        self.assertEqual(
                            result["headers"]["cookie"], "access_token=cookie-token"
                        )
                        self.assertIn("access_token=upstream-token", headers["Set-Cookie"])

    def test_upstream_status_codes_are_not_intercepted(self):
        for origin in (self.gateway_url, self.ui_url):
            for prefix in ("/user-api", "/supplier-api"):
                for expected in (401, 403, 404, 503):
                    with self.subTest(origin=origin, prefix=prefix, status=expected):
                        status, _, _ = request(f"{origin}{prefix}/status/{expected}")
                        self.assertEqual(status, expected)

    def test_unknown_gateway_routes_are_rejected(self):
        for path in ("/", "/unknown/health", "/user-api-other/health"):
            with self.subTest(path=path):
                self.assertEqual(request(self.gateway_url + path)[0], 404)

    def test_nginx_images_require_runtime_configuration(self):
        for service, variable in (
            ("internal-gateway", "USER_SERVICE_UPSTREAM"),
            ("internal-gateway", "SUPPLIER_SERVICE_UPSTREAM"),
            ("internal-gateway", "NGINX_DNS_RESOLVER"),
            ("ui", "INTERNAL_GATEWAY_URL"),
            ("ui", "NGINX_DNS_RESOLVER"),
        ):
            with self.subTest(service=service, variable=variable):
                with self.assertRaisesRegex(AssertionError, variable + " must be set"):
                    self.compose(
                        "run", "--rm", "--no-deps", "-e", variable + "=",
                        service, "nginx", "-t",
                    )

    def test_ui_keeps_spa_fallback(self):
        status, headers, body = request(self.ui_url + "/suppliers")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"<html", body)


if __name__ == "__main__":
    unittest.main()
