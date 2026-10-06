from app.api.feedback import router
def test_feedback_routes_are_registered():
    paths={route.path for route in router.routes if hasattr(route,"path")}
    assert "/v1/feedback" in paths
    assert "/v1/feedback-candidates/{candidate_id}/apply" in paths
    assert "/v1/products/{product_id}/feedback" in paths
