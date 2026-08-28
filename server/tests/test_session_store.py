from twilio_observe.session_store import SessionStore


def test_create_session():
    store = SessionStore()
    session = store.create("CA123", "+15551234567")
    assert session.call_sid == "CA123"
    assert session.caller_number == "+15551234567"
    assert session.status == "active"
    assert session.csat == 7
    assert session.transcript == []


def test_get_session():
    store = SessionStore()
    store.create("CA123", "+15551234567")
    session = store.get("CA123")
    assert session is not None
    assert session.call_sid == "CA123"


def test_get_all_active():
    store = SessionStore()
    store.create("CA1", "+1111")
    store.create("CA2", "+2222")
    s = store.get("CA1")
    s.status = "completed"
    active = store.get_all_active()
    assert len(active) == 1
    assert active[0].call_sid == "CA2"


def test_add_transcript_turn():
    store = SessionStore()
    store.create("CA123", "+15551234567")
    store.add_turn("CA123", "customer", "Hello")
    session = store.get("CA123")
    assert len(session.transcript) == 1
    assert session.transcript[0]["role"] == "customer"
    assert session.transcript[0]["content"] == "Hello"
