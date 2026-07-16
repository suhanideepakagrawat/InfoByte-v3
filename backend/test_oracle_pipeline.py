import json
from app.retrievers.oracle import handle_oracle_query

def run_test():
    print("=" * 60)
    print("RUNNING ISOLATED ORACLE RETRIEVAL PIPELINE TEST")
    print("=" * 60)
    
    # Updated prompt to reflect both error codes and general topics
    target_query = input("Enter an Oracle error signature or general topic (e.g., ORA-00001 or Data Pump): ").strip()
    if not target_query:
        print("Invalid target input.")
        return

    result = handle_oracle_query(target_query)
    
    print("\n" + "=" * 60)
    print("RESULTING STANDARDIZED DATA CONTRACT:")
    print("=" * 60)
    print(json.dumps(result, indent=2))
    print("=" * 60)

if __name__ == "__main__":
    run_test()