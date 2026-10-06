from app.api.today import AttentionItem,TodayResponse
def test_today_contract_has_three_action_groups():
    result=TodayResponse(); assert result.needs_review==[] and result.waiting_for_you==[] and result.recently_completed==[]
def test_attention_target_is_explicit():
    item=AttentionItem(id="finding:1",type="FINDING",title="Review",summary="Evidence found",status="OPEN",product_id=1,target_route="/app/findings/1"); assert item.target_route=="/app/findings/1"
