from twilio_observe.csat import CsatScorer


def test_initial_score():
    scorer = CsatScorer()
    scorer.init_call("CA1")
    assert scorer.get_score("CA1") == 7


def test_negative_customer_message_drops_score():
    scorer = CsatScorer()
    scorer.init_call("CA1")
    scorer.score_customer_message("CA1", "That's ridiculous, I already told you!")
    assert scorer.get_score("CA1") == 5


def test_positive_customer_message_raises_score():
    scorer = CsatScorer()
    scorer.init_call("CA1")
    scorer.score_customer_message("CA1", "That sounds great, thank you!")
    assert scorer.get_score("CA1") == 8


def test_deflection_response_drops_score():
    scorer = CsatScorer()
    scorer.init_call("CA1")
    scorer.score_ai_response("CA1", "Our team will reach out in 3 to 5 business days.")
    assert scorer.get_score("CA1") == 6


def test_score_clamps_to_1_10():
    scorer = CsatScorer()
    scorer.init_call("CA1", initial_score=2)
    scorer.score_customer_message("CA1", "This is ridiculous")
    assert scorer.get_score("CA1") == 1


def test_unknown_call_returns_default():
    scorer = CsatScorer()
    assert scorer.get_score("unknown") == 7
