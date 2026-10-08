from app.core.llm import MockLLMClient
import pytest
def test_mock_feedback_candidate_is_deterministic():
    c={"task":"feedback-candidate","raw_feedback":"We already support account deletion.","facts":[{"fact_id":7,"name":"account_deletion"}]}
    client=MockLLMClient(); assert client.chat_json("","",context=c)==client.chat_json("","",context=c)
    assert client.chat_json("","",context=c)["proposed_status"]=="PRESENT"
def test_mock_ambiguous_feedback_asks_one_question():
    c={"task":"feedback-candidate","raw_feedback":"We plan this maybe.","facts":[{"fact_id":7,"name":"account_deletion"}]}
    result=MockLLMClient().chat_json("","",context=c)
    assert result["needs_clarification"] and result["clarification_question"]

@pytest.mark.parametrize("text,status,value", [
    ("我们已经支持账号删除。", "PRESENT", True),
    ("我们没有账号删除功能。", "ABSENT", False),
    ("账号删除功能目前未知。", "UNKNOWN", None),
    ("代码中未检测到账号删除。", "NOT_DETECTED", None),
    ("代码中没有检测到账号删除。", "NOT_DETECTED", None),
])
def test_chinese_mock_preserves_distinct_observation_states(text, status, value):
    result = MockLLMClient().chat_json("", "", context={"task": "feedback-candidate", "raw_feedback": text, "facts": [{"fact_id": 7, "name": "account_deletion"}]})
    assert result["target_fact_id"] == 7
    assert result["proposed_status"] == status
    assert result["proposed_value"] is value
    assert not result["needs_clarification"]

def test_mock_never_guesses_first_fact_when_feedback_has_no_target():
    result = MockLLMClient().chat_json("", "", context={"task": "feedback-candidate", "raw_feedback": "这个发现不准确。", "facts": [{"fact_id": 7, "name": "account_deletion"}]})
    assert result["needs_clarification"]
    assert result["target_fact_id"] is None
    assert result["proposed_status"] is None

def test_chinese_clarification_retains_original_fact_target():
    result = MockLLMClient().chat_json("", "", context={"task": "feedback-candidate", "raw_feedback": "账号删除可能已经实现。", "clarification_answer": "我们已经支持。", "facts": [{"fact_id": 7, "name": "account_deletion"}]})
    assert result["target_fact_id"] == 7
    assert result["proposed_status"] == "PRESENT"
    assert not result["needs_clarification"]

def test_short_market_name_does_not_match_users_in_a_control_correction():
    result = MockLLMClient().chat_json("", "", context={"task": "feedback-candidate", "raw_feedback": "We already disclose AI use to users.", "facts": [{"fact_id": 2, "name": "US"}, {"fact_id": 7, "name": "ai_disclosure"}]})
    assert result["target_fact_id"] == 7
    assert result["proposed_status"] == "PRESENT"
