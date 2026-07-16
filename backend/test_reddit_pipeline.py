import json
from app.retrievers.reddit import handle_reddit_query

def run_test():
    print("=" * 60)
    print("RUNNING ISOLATED REDDIT RETRIEVAL TEST")
    print("=" * 60)
    
    # Accept input from the user
    test_query = input("\nEnter a topic to search on Reddit (e.g., 'best IDE for fastAPI'): ").strip()
    if not test_query:
        print("No query entered. Exiting.")
        return

    print(f"\nSearching SerpAPI and crawling old.reddit.com for: '{test_query}'...\n")
    
    # Execute the isolated handler (passing 'general_code' as the mock intent)
    result = handle_reddit_query(test_query, detected_intent="general_code")
    
    # Print the resulting Data Contract cleanly
    print("\n" + "=" * 60)
    print("RESULTING STANDARDIZED DATA CONTRACT:")
    print("=" * 60)
    print(json.dumps(result, indent=2))
    print("=" * 60)

if __name__ == "__main__":
    run_test()