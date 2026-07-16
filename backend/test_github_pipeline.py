import json
from app.retrievers.github import handle_github_query

def run_test():
    print("=" * 60)
    print("RUNNING ISOLATED GITHUB RETRIEVAL TEST")
    print("=" * 60)
    
    # Accept input from the user
    test_query = input("\nEnter a technical issue to search on GitHub (e.g., 'FastAPI CORS missing allow_credentials'): ").strip()
    if not test_query:
        print("No query entered. Exiting.")
        return

    print(f"\nSearching GitHub Issues API for: '{test_query}'...\n")
    
    # Execute the isolated handler
    result = handle_github_query(test_query)
    
    # Print the resulting Data Contract cleanly
    print("\n" + "=" * 60)
    print("RESULTING STANDARDIZED DATA CONTRACT:")
    print("=" * 60)
    print(json.dumps(result, indent=2))
    print("=" * 60)

if __name__ == "__main__":
    run_test()