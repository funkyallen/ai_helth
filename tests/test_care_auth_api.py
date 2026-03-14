from fastapi.testclient import TestClient

from backend.main import app


def test_care_directory_contains_community_elders_and_families() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/care/directory")
    assert response.status_code == 200
    payload = response.json()
    assert payload["community"]["id"]
    assert payload["elders"]
    assert payload["families"]


def test_family_directory_is_scoped() -> None:
    client = TestClient(app)
    full = client.get("/api/v1/care/directory").json()
    first_family_id = full["families"][0]["id"]
    family_directory = client.get(f"/api/v1/care/directory/family/{first_family_id}")
    assert family_directory.status_code == 200
    payload = family_directory.json()
    assert len(payload["families"]) == 1
    assert payload["families"][0]["id"] == first_family_id
    scoped_elder_ids = set(payload["families"][0]["elder_ids"])
    assert scoped_elder_ids == {elder["id"] for elder in payload["elders"]}


def test_mock_login_and_me_flow() -> None:
    client = TestClient(app)
    accounts = client.get("/api/v1/auth/mock-accounts")
    assert accounts.status_code == 200
    assert accounts.json()
    username = accounts.json()[0]["username"]

    login = client.post(
        "/api/v1/auth/mock-login",
        json={"username": username, "password": "123456"},
    )
    assert login.status_code == 200
    token = login.json()["token"]
    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    assert me.json()["username"] == username
