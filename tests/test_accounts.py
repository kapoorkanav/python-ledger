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

def test_get_unknown_account_404(client):
    import uuid
    assert client.get(f"/accounts/{uuid.uuid4()}").status_code == 404


def test_new_account_starts_at_zero(client, account):
    acc = account("Alice")
    assert client.get(f"/accounts/{acc['id']}").json()["balance"] == 0

def test_list_entries_after_deposit(client, account, key):
    acc = account("Alice")
    client.post(f"/accounts/{acc['id']}/deposit", json={"amount": 5000, "idempotency_key": key("dep")})

    response = client.get(f"/accounts/{acc['id']}/entries")

    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 1
    assert entries[0]["direction"] == "credit"
    assert entries[0]["amount"] == 5000


def test_list_entries_unknown_account_404(client):
    import uuid
    assert client.get(f"/accounts/{uuid.uuid4()}/entries").status_code == 404
