import json
from app.retrievers.stackoverflow import handle_stackoverflow_query

def run_test():
    print("=" * 60)
    print("RUNNING ISOLATED STACK OVERFLOW RETRIEVAL TEST")
    print("=" * 60)
    
    # Accept input from the user
    test_query = input("\nEnter a technical query for Stack Overflow (e.g., 'Python list comprehension'): ").strip()
    if not test_query:
        print("No query entered. Exiting.")
        return

    print(f"\nSearching Stack Exchange API for: '{test_query}'...\n")
    
    # Execute the isolated handler
    result = handle_stackoverflow_query(test_query)
    
    # Print the resulting Data Contract cleanly
    print("\n" + "=" * 60)
    print("RESULTING STANDARDIZED DATA CONTRACT:")
    print("=" * 60)
    print(json.dumps(result, indent=2))
    print("=" * 60)

if __name__ == "__main__":
    run_test()