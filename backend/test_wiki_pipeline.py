import json
import urllib.parse
from app.retrievers.wikipedia import handle_wiki_query

def run_test():
    print("=" * 60)
    print("RUNNING ISOLATED WIKIPEDIA RETRIEVAL PIPELINE TEST")
    print("=" * 60)
    
    # Accept input from the user
    test_query = input("\nEnter a Wikipedia topic to scrape: ").strip()
    if not test_query:
        print("No query entered. Exiting.")
        return

    # Format the query for the Wikipedia URL (e.g., "artificial intelligence" -> "Artificial_intelligence")
    formatted_topic = urllib.parse.quote(test_query.replace(" ", "_").capitalize())
    test_url = f"https://en.wikipedia.org/wiki/{formatted_topic}"
    
    print(f"\nTarget Query: '{test_query}'")
    print(f"Target URL:   '{test_url}'\n")
    
    # Execute the isolated handler
    result = handle_wiki_query(test_query, test_url)
    
    # Print the resulting Data Contract cleanly
    print("\n" + "=" * 60)
    print("RESULTING STANDARDIZED DATA CONTRACT:")
    print("=" * 60)
    print(json.dumps(result, indent=2))
    print("=" * 60)

if __name__ == "__main__":
    run_test()