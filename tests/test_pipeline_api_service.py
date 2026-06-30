from backend.services.translation_api_service import app


def test_translation_api_routes_are_specific_and_not_job_based():
    routes = {route.path for route in app.routes}

    assert "/api/translate" in routes
    assert "/api/translate/upload" in routes
    assert "/api/translations" in routes
    assert "/api/translate/{translation_id}" in routes
    assert "/api/translate/{translation_id}/logs" in routes
    assert "/jobs/vi" not in routes
    assert "/jobs" not in routes
    assert "/api/jobs/vi" not in routes
