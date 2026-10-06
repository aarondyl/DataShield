from app.tenant.findings.schemas import TenantTriggerType

def test_feedback_reanalysis_trigger_is_supported_contract():
    assert TenantTriggerType.FEEDBACK_REANALYSIS.value == "FEEDBACK_REANALYSIS"
