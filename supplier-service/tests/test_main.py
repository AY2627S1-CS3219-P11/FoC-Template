from uuid import UUID

import httpx
import pytest
from fastapi import status

import main


SUPPLIER = {
    "name": "Test Cafe",
    "category": "Food",
    "building": "COM1",
    "floor": 1,
    "description": "Near the entrance",
    "lattitude": 1.2966,
    "longitude": 103.7764,
    "startingTime": "09:00:00",
    "closingTime": "17:00:00",
}


async def create_supplier(client, **changes):
    """Create a supplier and return the response JSON for tests that need one."""
    payload = SUPPLIER | changes
    response = await client.post("/suppliers", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


@pytest.mark.anyio
async def test_health(client):
    response = await client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "status": "healthy",
        "service": "supplier-service",
    }


@pytest.mark.anyio
async def test_create_supplier(client):
    supplier = await create_supplier(client)

    assert supplier["name"] == "Test Cafe"
    assert supplier["category"] == "Food"
    assert supplier["imageUrl"] is None
    assert "id" in supplier

    response = await client.get("/suppliers")

    assert response.status_code == status.HTTP_200_OK
    assert [item["id"] for item in response.json()] == [supplier["id"]]


@pytest.mark.anyio
async def test_patch_supplier_changes_only_sent_fields(client):
    supplier = await create_supplier(client)

    response = await client.patch(
        f"/suppliers/{supplier['id']}",
        json={"name": "Renamed Cafe", "floor": 2},
    )

    assert response.status_code == status.HTTP_200_OK
    updated = response.json()
    assert updated["id"] == supplier["id"]
    assert updated["name"] == "Renamed Cafe"
    assert updated["floor"] == 2
    assert updated["building"] == "COM1"


@pytest.mark.anyio
async def test_patch_unknown_supplier_returns_404(client):
    response = await client.patch(
        "/suppliers/00000000-0000-0000-0000-000000000000",
        json={"name": "Does not exist"},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Supplier not found"


@pytest.mark.anyio
async def test_delete_supplier_hides_it_from_list(client):
    supplier = await create_supplier(client)

    response = await client.delete(f"/suppliers/{supplier['id']}")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.content == b""

    list_response = await client.get("/suppliers")
    assert list_response.status_code == status.HTTP_200_OK
    assert list_response.json() == []


@pytest.mark.anyio
async def test_non_admin_cannot_create_supplier(client):
    main.app.dependency_overrides[main.get_user] = lambda: main.AuthenticatedUser(
        user_id=UUID("00000000-0000-0000-0000-000000000002"),
        role="user",
    )

    response = await client.post("/suppliers", json=SUPPLIER)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Admin access required"


@pytest.mark.anyio
async def test_admin_manager_can_create_supplier(client):
    main.app.dependency_overrides[main.get_user] = lambda: main.AuthenticatedUser(
        user_id=UUID("00000000-0000-0000-0000-000000000003"),
        role="admin_manager",
    )

    response = await client.post("/suppliers", json=SUPPLIER)

    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.anyio
async def test_authentication_forwards_access_token_cookie(client):
    main.app.dependency_overrides.pop(main.get_user)

    def authenticate(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/authentication/sessions/current"
        assert request.headers["cookie"] == "access_token=test-token"
        return httpx.Response(
            status.HTTP_200_OK,
            json={
                "user_id": "00000000-0000-0000-0000-000000000004",
                "role": "admin",
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(authenticate),
        base_url="http://user-service",
    ) as user_service_client:
        async def override_user_service_client():
            yield user_service_client

        main.app.dependency_overrides[main.get_user_service_client] = (
            override_user_service_client
        )
        client.cookies.set("access_token", "test-token")
        response = await client.post("/suppliers", json=SUPPLIER)

    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.anyio
async def test_missing_access_token_is_unauthorized(client):
    main.app.dependency_overrides.pop(main.get_user)

    response = await client.post("/suppliers", json=SUPPLIER)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "No authentication token found. Please sign in."


@pytest.mark.anyio
async def test_rejected_access_token_is_unauthorized(client):
    main.app.dependency_overrides.pop(main.get_user)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(status.HTTP_401_UNAUTHORIZED)
        ),
        base_url="http://user-service",
    ) as user_service_client:
        async def override_user_service_client():
            yield user_service_client

        main.app.dependency_overrides[main.get_user_service_client] = (
            override_user_service_client
        )
        client.cookies.set("access_token", "expired-token")
        response = await client.post("/suppliers", json=SUPPLIER)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid or expired token. Please sign in."


@pytest.mark.anyio
async def test_unavailable_user_service_returns_503(client):
    main.app.dependency_overrides.pop(main.get_user)

    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(unavailable),
        base_url="http://user-service",
    ) as user_service_client:
        async def override_user_service_client():
            yield user_service_client

        main.app.dependency_overrides[main.get_user_service_client] = (
            override_user_service_client
        )
        client.cookies.set("access_token", "test-token")
        response = await client.post("/suppliers", json=SUPPLIER)

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["detail"] == "Authentication is temporarily unavailable."
