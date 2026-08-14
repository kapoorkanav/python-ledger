def test_create_account(client):
    response=client.post("/accounts", json={"name": "Alice", "currency": "USD"})

    assert response.status_code==201
    data=response.json()
    assert data["name"]=="Alice"
    assert data["currency"]=="USD"
    assert "id" in data

def test_create_account_requires_name(client):
    response=client.post("/accounts", json={"currency": "USD"})
    assert response.status_code==422

def test_get_account(client):
    response_initial=client.post("/accounts", json={"name": "Alice", "currency": "USD"})
    account_id = response_initial.json()["id"]
    response=client.get(f"/accounts/{account_id}")
    data=response.json()
    assert data["name"]=="Alice"
    assert data["currency"]=="USD"
    assert data["id"]==account_id