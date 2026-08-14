def test_transfers_between_accounts(client):
    alice=client.post("/accounts", json={"name": "Alice"}).json()
    bob=client.post("/accounts", json={"name": "Bob"}).json()

    client.post(f"/accounts/{alice["id"]}/deposit", json={"amount": 10000, "idempotency_key": "dep-001"})

    response=client.post("/transfers", json={
        "from_account_id": alice['id'],
        "to_account_id": bob['id'],
        "amount": 3000,
        "idempotency_key": "tx-001",
    })
    
    assert response.status_code==200
    data=response.json()
    assert data["from_balance"]==7000
    assert data["to_balance"]==3000

def test_transfer_with_insufficient_balance(client):
    alice=client.post("/accounts", json={"name": "Alice"}).json()
    bob=client.post("/accounts", json={"name": "Bob"}).json()

    client.post(f"/accounts/{alice["id"]}/deposit", json={"amount": 1000, "idempotency_key": "dep-001"})

    response=client.post("/transfers", json={
        "from_account_id": alice['id'],
        "to_account_id": bob['id'],
        "amount": 3000,
        "idempotency_key": "tx-001",
    })
    
    assert response.status_code==400