import uuid

def test_deposit_increases_balance(client, account, key):
    acc = account("Alice")
    response = client.post(f"/accounts/{acc['id']}/deposit",
                           json={"amount": 5000, "idempotency_key": key("dep")})
    assert response.status_code == 200
    assert response.json()["balance"] == 5000

def test_deposit_is_idempotent(client, account, key):
    acc = account("Alice")
    idem = key("dep")

    first = client.post(f"/accounts/{acc['id']}/deposit",
                        json={"amount": 5000, "idempotency_key": idem})
    second = client.post(f"/accounts/{acc['id']}/deposit",
                         json={"amount": 5000, "idempotency_key": idem})

    assert first.status_code == second.status_code == 200
    assert first.json()["balance"] == second.json()["balance"] == 5000

def test_deposit_key_reuse_with_different_amount_conflicts(client, account, key):
    acc = account("Alice")
    idem = key("dep")
    client.post(f"/accounts/{acc['id']}/deposit", json={"amount": 5000, "idempotency_key": idem})

    response = client.post(f"/accounts/{acc['id']}/deposit",
                           json={"amount": 9000, "idempotency_key": idem})
    assert response.status_code == 409

def test_deposit_and_withdraw_keys_are_independent(client, account, key):
    """Regression: a deposit key must not make a withdrawal a silent no-op."""
    acc = account("Alice")
    shared = key("op")

    client.post(f"/accounts/{acc['id']}/deposit",
                json={"amount": 5000, "idempotency_key": shared})
    response = client.post(f"/accounts/{acc['id']}/withdraw",
                           json={"amount": 2000, "idempotency_key": shared})

    assert response.status_code == 200
    assert response.json()["balance"] == 3000

def test_deposit_to_unknown_account_404(client, key):
    response = client.post(f"/accounts/{uuid.uuid4()}/deposit",
                           json={"amount": 100, "idempotency_key": key("dep")})
    assert response.status_code == 404

def test_deposit_rejects_non_positive_amount(client, account, key):
    acc = account("Alice")
    for amount in (0, -1):
        response = client.post(f"/accounts/{acc['id']}/deposit",
                               json={"amount": amount, "idempotency_key": key("dep")})
        assert response.status_code == 422