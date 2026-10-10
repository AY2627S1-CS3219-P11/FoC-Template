# FoC authentication

Shared RS256 Keycloak access-token validation for user-service and supplier-service.
Both services install this package through their `uv` path dependency. Future
services can use the same package without importing another service's code.

`KeycloakTokenValidator` checks signature, issuer, audience, required claims,
expiry, token type and UUID subject, then selects an application realm role.
Built-in Keycloak roles alone grant no application access. Signing keys are
cached for five minutes. Unknown key IDs can trigger a refresh after the
library's 30-second cooldown, which limits requests from invalid tokens. A signing-key
retrieval failure raises `AuthenticationUnavailableError`; an invalid token
raises `jwt.InvalidTokenError`; a valid token without an application role raises
`ApplicationRoleRequiredError`. Service dependencies translate these to HTTP
503, 401 and 403 respectively. JWKS fetching runs in a worker thread.

Run the cryptographic and key-rotation tests from the repository root:

```sh
uv run --project supplier-service --locked pytest packages/foc-auth/tests -q
```

Backend Dockerfiles now use the repository root as their build context to include
this package. Use root Compose, or `docker build -f user-service/Dockerfile .`
and `docker build -f supplier-service/Dockerfile .` from the repository root.
