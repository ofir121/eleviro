def test_read_root(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_strip_placeholder_publications():
    from app.services.ai_service import _strip_placeholder_publications
    # Placeholder content should be removed
    md = """# Jane Doe
City · 555-1234 · jane@example.com

## Experience
Some job here.

## Publications
Title of Publication, Author Name
Title of Publication, Author Name

## Professional Summary
A summary.
"""
    out = _strip_placeholder_publications(md)
    assert "## Publications" not in out
    assert "Title of Publication" not in out
    assert "## Experience" in out
    assert "## Professional Summary" in out
    # Real publication should be kept
    real = """# Jane
## Publications
**Real Paper Title**, Jane Doe. Journal of X, 2023.
"""
    assert _strip_placeholder_publications(real) == real
