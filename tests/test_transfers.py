import pytest

def _transfer(client, src, dst, amount, idem):
    return client.post("/transfers", json={
        "from_account_id": src["id"],
        "to_account_id": dst["id"],
        "amount": amount,
        "idempotency_key": idem,
    })

def test_transfer_moves_money(client, account, key):
    alice, bob = account("Alice"), account("Bob")
    client.post(f"/accounts/{alice['id']}/deposit",
                json={"amount": 10000, "idempotency_key": key("dep")})

    response = _transfer(client, alice, bob, 3000, key("tx"))

    assert response.status_code == 200
    assert response.json()["from_balance"] == 7000
    assert response.json()["to_balance"] == 3000

def test_transfer_is_idempotent(client, account, key):
    alice, bob = account("Alice"), account("Bob")
    client.post(f"/accounts/{alice['id']}/deposit",
                json={"amount": 10000, "idempotency_key": key("dep")})
    idem = key("tx")

    first = _transfer(client, alice, bob, 3000, idem)
    second = _transfer(client, alice, bob, 3000, idem)

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert client.get(f"/accounts/{alice['id']}").json()["balance"] == 7000

def test_transfer_key_reuse_with_different_amount_conflicts(client, account, key):
    alice, bob = account("Alice"), account("Bob")
    client.post(f"/accounts/{alice['id']}/deposit",
                json={"amount": 10000, "idempotency_key": key("dep")})
    idem = key("tx")

    _transfer(client, alice, bob, 3000, idem)
    response = _transfer(client, alice, bob, 4000, idem)

    assert response.status_code == 409

def test_transfer_insufficient_balance_leaves_balances_untouched(client, account, key):
    alice, bob = account("Alice"), account("Bob")
    client.post(f"/accounts/{alice['id']}/deposit",
                json={"amount": 1000, "idempotency_key": key("dep")})

    assert _transfer(client, alice, bob, 3000, key("tx")).status_code == 400
    assert client.get(f"/accounts/{alice['id']}").json()["balance"] == 1000
    assert client.get(f"/accounts/{bob['id']}").json()["balance"] == 0

def test_transfer_to_same_account_rejected(client, account, key):
    alice = account("Alice")
    assert _transfer(client, alice, alice, 100, key("tx")).status_code == 400


def test_transfer_to_unknown_account_rejected(client, account, key):
    import uuid
    alice = account("Alice")
    response = client.post("/transfers", json={
        "from_account_id": alice["id"],
        "to_account_id": str(uuid.uuid4()),
        "amount": 100,
        "idempotency_key": key("tx"),
    })
    assert response.status_code == 404

def test_transfer_across_currencies_rejected(client, account, key):
    usd, eur = account("Alice", "USD"), account("Bruno", "EUR")
    client.post(f"/accounts/{usd['id']}/deposit",
                json={"amount": 10000, "idempotency_key": key("dep")})

    assert _transfer(client, usd, eur, 1000, key("tx")).status_code == 400

def test_transfer_rejects_non_positive_amount(client, account, key):
    alice, bob = account("Alice"), account("Bob")
    assert _transfer(client, alice, bob, 0, key("tx")).status_code == 422
    assert _transfer(client, alice, bob, -100, key("tx")).status_code == 422

def test_get_transfer_by_id(client, account, key):
    alice, bob = account("Alice"), account("Bob")
    client.post(f"/accounts/{alice['id']}/deposit", json={"amount": 5000, "idempotency_key": key("dep")})
    created = _transfer(client, alice, bob, 1000, key("tx")).json()

    response = client.get(f"/transfers/{created['transfer_id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == 1000
    assert data["from_account_id"] == alice["id"]
    assert data["to_account_id"] == bob["id"]


def test_get_unknown_transfer_404(client):
    import uuid
    assert client.get(f"/transfers/{uuid.uuid4()}").status_code == 404
