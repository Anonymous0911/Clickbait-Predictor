def test_custom_user_model():
    from django.contrib.auth import get_user_model
    assert get_user_model()._meta.label == "accounts.User"

def test_admin_login_page(client):
    assert client.get("/admin/login/").status_code == 200

def test_unknown_api_route_404(client):
    response = client.get("/api/nope")
    assert response.status_code == 404
