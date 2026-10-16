"""Configuration-only checks; never start containers or contact a database."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("docker"), "Docker Compose is required")
class ComposeTests(unittest.TestCase):
    def config(self, *, database_url="postgresql+psycopg://review:review@review-db/supplier"):
        values = (ROOT / ".env.example").read_text().replace(
            "SUPPLIER_DATABASE_URL=", f"SUPPLIER_DATABASE_URL={database_url}"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env") as file:
            file.write(values)
            file.flush()
            # Ignore developer shell variables and do not read service secrets.
            result = subprocess.run(
                ["docker", "compose", "--env-file", file.name, "config",
                 "--no-env-resolution", "--format", "json"],
                cwd=ROOT, env={"PATH": os.environ["PATH"]},
                text=True, capture_output=True,
            )
        return result

    def test_explicit_destinations_and_loopback_ports(self):
        result = self.config()
        self.assertEqual(result.returncode, 0, result.stderr)
        services = json.loads(result.stdout)["services"]
        supplier = services["supplier-service"]["environment"]
        self.assertEqual(supplier["DATABASE_URL"],
                         "postgresql+psycopg://review:review@review-db/supplier")
        self.assertEqual(supplier["RABBITMQ_URL"],
                         "amqp://foc:change-me-local-broker@rabbitmq:5672")
        for service in services.values():
            self.assertNotIn("container_name", service)
            for port in service.get("ports", []):
                self.assertEqual(port["host_ip"], "127.0.0.1")

    def test_database_configuration_is_required(self):
        result = self.config(database_url="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SUPPLIER_DATABASE_URL", result.stderr)


if __name__ == "__main__":
    unittest.main()
