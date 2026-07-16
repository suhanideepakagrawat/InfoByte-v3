"""
test_backend.py
Integration testing suite for InfoByte v3 API Engine.
"""
import requests

BASE_URL = "http://127.0.0.1:8000"

def test_api_health():
    """Verifies that the FastAPI server is responsive."""
    response = requests.get(f"{BASE_URL}/docs")
    assert response.status_code == 200, "Server is not reachable."

def test_empty_query_handling():
    """Tests the edge case of an empty query string."""
    payload = {"query": "   "}
    response = requests.post(f"{BASE_URL}/api/query", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "error" in data, "Router failed to catch empty query."
    assert data["error"] == "Empty or invalid query received."

def test_technical_code_routing():
    """Verifies standard routing using a dataset sample."""
    payload = {"query": "react router redirects to 404 after refresh"}
    response = requests.post(f"{BASE_URL}/api/query", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "technical_code" in data["intents_detected"]
    
    # Verify the correct scrapers were spun up
    payload_keys = data["payload"].keys()
    assert "stackoverflow" in payload_keys
    assert "github" in payload_keys
    assert "reddit" in payload_keys

def test_technical_oracle_routing():
    """Verifies Oracle-specific routing pathways."""
    payload = {"query": "how to resolve ORA-00001 unique constraint violated"}
    response = requests.post(f"{BASE_URL}/api/query", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "technical_oracle" in data["intents_detected"]
    assert "oracle" in data["payload"], "Oracle scraper was not triggered."

def test_weather_routing():
    """Verifies simple non-technical routing."""
    payload = {"query": "snow expected in manali"}
    response = requests.post(f"{BASE_URL}/api/query", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "weather" in data["intents_detected"]
    assert "weather" in data["payload"]

def test_diagnostic_endpoints():
    """Verifies the isolated diagnostic endpoints maintain intent injection."""
    response = requests.get(f"{BASE_URL}/api/retriever/news?q=technology")
    assert response.status_code == 200
    
    data = response.json()
    assert "intent" in data, "_inject_intent failed on diagnostic endpoint."
    assert data["intent"] == "discussion_social"

def test_gibberish_edge_case():
    """
    Tests how the system handles completely out-of-distribution data.
    Note: If this fails by returning successful payloads, you need to implement 
    a minimum threshold for top_score in router.py.
    """
    payload = {"query": "xxxxxxxxxxxxxx yyyyyyy zzzzzzz"}
    response = requests.post(f"{BASE_URL}/api/query", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    # Ideally, the system should catch this. We check the top score to see how the model reacted.
    scores = data.get("confidence_scores", {})
    if scores:
        top_score_str = list(scores.values())[0]
        top_score_float = float(top_score_str.strip('%')) / 100
        print(f"\n[Diagnostic] Gibberish confidence score: {top_score_float}")