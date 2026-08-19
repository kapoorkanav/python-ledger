import uuid

from hypothesis import HealthCheck, given, settings, strategies as st
from sqlalchemy import case, func

from app import models

operation=st.fixed_dictionaries({
    "kind": st.sampled_from(["deposit", "withdraw"]),
    "amount": st.integers(min_value=1, max_value=500),
})

@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    operations=st.lists(operation, min_size=1, max_size=20)
)
def test_balance_matches_accepted_operations(client, db_session, operations):
    acc=client.post("/accounts", json={"name": f"prop-{uuid.uuid4()}"}).json()
    expected=0

    for op in operations:
        response=client.post(
            f"/accounts/{acc['id']}/{op['kind']}",
            json={"amount": op["amount"], "idempotency_key": f"prop-{uuid.uuid4()}"},
        )
        if op['kind']=="deposit":
            assert response.status_code==200
            expected+=op["amount"]
            assert response.json()["balance"] == expected
        elif response.status_code==200:
            expected-=op["amount"]
            assert response.json()["balance"] == expected
        else:
            assert response.status_code==400
        
        assert expected>=0, "a withdrawal was accepted which should not have been"

    assert client.get(f"/accounts/{acc['id']}").json()["balance"] == expected

    net = db_session.query(
        func.coalesce(func.sum(case(
            (models.LedgerEntry.direction == "credit", models.LedgerEntry.amount),
            else_=-models.LedgerEntry.amount,
        )), 0)
    ).scalar()

    assert net == 0, "every entry must have an equal and opposite counterpart"