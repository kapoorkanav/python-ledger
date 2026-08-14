def test_transfer_completed_event_published(client, monkeypatch):
    published_events=[]

    def fake_publish(**kwargs):
        published_events.append(kwargs)
    
    monkeypatch.setattr("app.routers.transfers.events.publish_transfer_completed", fake_publish)

    alice = client.post("/accounts", json={"name": "Alice"}).json()
    bob = client.post("/accounts", json={"name": "Bob"}).json()
    client.post(f"/accounts/{alice['id']}/deposit", json={"amount": 5000, "idempotency_key": "d1"})

    client.post("/transfers", json={
        "from_account_id": alice["id"], "to_account_id": bob["id"],
        "amount": 1000, "idempotency_key": "t1",
    })

    assert len(published_events)==1
    assert published_events[0]["amount"]==1000