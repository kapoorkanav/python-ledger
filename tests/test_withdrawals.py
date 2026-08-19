import uuid

def _fund(client, key, acc, amount=5000):
    client.post(f"/accounts/{acc['id']}/deposit",
                json={"amount": amount, "idempotency_key": key("dep")})

def test_withdrawal_decreases_balance(client, account, key):
    acc = account("Alice")
    _fund(client, key, acc)

    response = client.post(f"/accounts/{acc['id']}/withdraw",
                           json={"amount": 4500, "idempotency_key": key("wd")})
    assert response.status_code == 200
    assert response.json()["balance"] == 500

def test_withdrawal_is_idempotent(client, account, key):
    acc = account("Alice")
    _fund(client, key, acc)
    idem = key("wd")

    first = client.post(f"/accounts/{acc['id']}/withdraw",
                        json={"amount": 2000, "idempotency_key": idem})
    second = client.post(f"/accounts/{acc['id']}/withdraw",
                         json={"amount": 2000, "idempotency_key": idem})

    assert first.json()["balance"] == second.json()["balance"] == 3000

def test_insufficient_balance_leaves_balance_untouched(client, account, key):
    acc = account("Alice")
    _fund(client, key, acc)

    response = client.post(f"/accounts/{acc['id']}/withdraw",
                           json={"amount": 6000, "idempotency_key": key("wd")})

    assert response.status_code == 400
    assert client.get(f"/accounts/{acc['id']}").json()["balance"] == 5000

def test_withdraw_from_unknown_account_404(client, key):
    response = client.post(f"/accounts/{uuid.uuid4()}/withdraw",
                           json={"amount": 100, "idempotency_key": key("wd")})
    assert response.status_code == 404