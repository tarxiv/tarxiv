def test_openapi_json_served(mock_api):
    client = mock_api.app.test_client()

    response = client.get("/openapi.json")

    assert response.status_code == 200
    # This is we get back valid semver
    assert len(response.json["openapi"].split(".")) == 3
    assert response.json["info"]["title"] == "TarXiv API"
    assert "/tags" in response.json["paths"]
    assert "/users/search" in response.json["paths"]
    assert "/teams/search" in response.json["paths"]
    assert "/teams/{team_id}/join" in response.json["paths"]
    assert "/user/teams/{team_id}" in response.json["paths"]
    assert "/tags/{tag_id}/objects" in response.json["paths"]
    assert "/auth/{provider}/login" in response.json["paths"]
    assert "/auth/{provider}/callback" in response.json["paths"]
    assert "/docs" not in response.json["paths"]


def test_swagger_docs_page_served(mock_api):
    client = mock_api.app.test_client()

    response = client.get("/docs")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "SwaggerUIBundle" in response.text
    assert "/openapi.json" in response.text
