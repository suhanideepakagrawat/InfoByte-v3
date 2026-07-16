import json
from app.retrievers.documentation import handle_documentation_query

def run_test():
    print("=" * 60)
    print("RUNNING ISOLATED DOCUMENTATION RETRIEVAL TEST")
    print("=" * 60)
    
    test_query = input("\nEnter a technical query (e.g., 'FastAPI dependency injection' or 'React useEffect'): ").strip()
    if not test_query:
        print("No query entered. Exiting.")
        return

    print(f"\nSearching and scoring official documentation for: '{test_query}'...\n")
    
    result = handle_documentation_query(test_query)
    
    print("\n" + "=" * 60)
    print("RESULTING STANDARDIZED DATA CONTRACT:")
    print("=" * 60)
    print(json.dumps(result, indent=2))
    print("=" * 60)

if __name__ == "__main__":
    run_test()