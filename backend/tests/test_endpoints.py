import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def validate_contract(response):
    """Helper to validate the standardized data contract."""
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "intent" in data
    assert "display_payload" in data
    return data

def test_oracle_endpoint():
    response = client.get("/api/retriever/oracle?q=ORA-00942")
    validate_contract(response)

def test_weather_endpoint():
    response = client.get("/api/retriever/weather?q=Delhi")
    validate_contract(response)

def test_github_endpoint():
    response = client.get("/api/retriever/github?q=fastapi server")
    validate_contract(response)

def test_stackoverflow_endpoint():
    response = client.get("/api/retriever/stackoverflow?q=python list comprehension")
    validate_contract(response)

def test_reddit_endpoint():
    response = client.get("/api/retriever/reddit?q=programming")
    validate_contract(response)

def test_wiki_endpoint():
    response = client.get("/api/retriever/wiki?q=Python (programming language)")
    validate_contract(response)

def test_news_endpoint():
    response = client.get("/api/retriever/news?q=covid 19")
    validate_contract(response)