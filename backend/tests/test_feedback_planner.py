from app.core.llm import MockLLMClient
def test_mock_feedback_candidate_is_deterministic():
    c={"task":"feedback-candidate","raw_feedback":"We already support account deletion.","facts":[{"fact_id":7,"name":"account_deletion"}]}
    client=MockLLMClient(); assert client.chat_json("","",context=c)==client.chat_json("","",context=c)
    assert client.chat_json("","",context=c)["proposed_status"]=="PRESENT"
def test_mock_ambiguous_feedback_asks_one_question():
    c={"task":"feedback-candidate","raw_feedback":"We plan this maybe.","facts":[{"fact_id":7,"name":"account_deletion"}]}
    result=MockLLMClient().chat_json("","",context=c)
    assert result["needs_clarification"] and result["clarification_question"]
