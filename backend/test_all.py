"""
test_all.py
Unified test harness to verify all new retrieval pipelines.
"""
import json
from app.retrievers.news import handle_news_query

from app.retrievers.weather import handle_weather_query
from app.retrievers.github import handle_github_query

def main():
    print("--- INFOBYTE V3: RETRIEVAL SYSTEM TEST ---")
    print("Select a test:")
    print("1. News (discussion_social)")
    print("2. Movies")
    print("3. Weather (Global/OpenWeather)")
    print("4. GitHub Issues (general_code)")
    
    choice = input("\nEnter choice (1-4): ")
    query = input("Enter search query: ")
    
    if choice == "1":
        result = handle_news_query(query)
    elif choice == "3":
        result = handle_weather_query(query)
    elif choice == "4":
        result = handle_github_query(query)
    else:
        print("Invalid choice.")
        return

    print("\nRESULTING DATA CONTRACT:")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()