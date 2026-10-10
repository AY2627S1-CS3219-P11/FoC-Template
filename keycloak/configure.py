"""Apply FoC clients and profile settings to an existing realm without deleting users."""

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def load_env(path: Path):
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    return values | dict(os.environ)


def configure(url: str, values: dict):
    def request(method, path, data=None, token=None, missing_ok=False):
        headers = {}
        if isinstance(data, (dict, list)):
            data = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            with urlopen(Request(url.rstrip("/") + path, data=data, headers=headers, method=method), timeout=15) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except HTTPError as error:
            status = error.code
            error.close()
            if status == 404 and missing_ok:
                return None
            raise RuntimeError(f"Keycloak returned {status} for {method} {path}") from None

    secrets = {
        "foc-backend": values.get("KEYCLOAK_BACKEND_CLIENT_SECRET"),
        "foc-api": values.get("KEYCLOAK_API_CLIENT_SECRET"),
    }
    if not all(secrets.values()):
        raise ValueError("KEYCLOAK_BACKEND_CLIENT_SECRET and KEYCLOAK_API_CLIENT_SECRET must be set")
    admin = request("POST", "/realms/master/protocol/openid-connect/token", urlencode({
        "grant_type": "password", "client_id": "admin-cli",
        "username": values["KEYCLOAK_ADMIN_USERNAME"], "password": values["KEYCLOAK_ADMIN_PASSWORD"],
    }).encode())["access_token"]
    template = json.loads((Path(__file__).parent / "realms/foc-realm.json").read_text())
    for client in template["clients"]:
        if client["clientId"] in secrets:
            client["secret"] = secrets[client["clientId"]]
    realm = template["realm"]
    root = f"/admin/realms/{realm}"
    if request("GET", root, token=admin, missing_ok=True) is None:
        request("POST", "/admin/realms", template, admin)
    else:
        request("PUT", root, {"editUsernameAllowed": True,
            "passwordPolicy": template["passwordPolicy"]}, admin)
        for role in template["roles"]["realm"]:
            if request("GET", root + f"/roles/{role['name']}", token=admin, missing_ok=True) is None:
                request("POST", root + "/roles", role, admin)
        for client in template["clients"]:
            found = request("GET", root + "/clients?" + urlencode({"clientId": client["clientId"]}), token=admin)
            if found:
                request("PUT", root + f"/clients/{found[0]['id']}", client, admin)
            else:
                request("POST", root + "/clients", client, admin)
    backend = request("GET", root + "/clients?clientId=foc-backend", token=admin)[0]
    account = request("GET", root + f"/clients/{backend['id']}/service-account-user", token=admin)
    management = request("GET", root + "/clients?clientId=realm-management", token=admin)[0]
    roles = request("GET", root + f"/clients/{management['id']}/roles", token=admin)
    required = {"manage-users", "view-users", "query-users", "view-realm"}
    request("POST", root + f"/users/{account['id']}/role-mappings/clients/{management['id']}",
        [r for r in roles if r["name"] in required], admin)
    component = template["components"]["org.keycloak.userprofile.UserProfileProvider"][0]
    profile = json.loads(component["config"]["kc.user.profile.config"][0])
    request("PUT", root + "/users/profile", profile, admin)
    print("FoC realm configuration applied. Existing application users preserved.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--url", default="http://localhost:8080")
    args = parser.parse_args()
    configure(args.url, load_env(args.env_file))
