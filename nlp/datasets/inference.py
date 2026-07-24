import pandas as pd

# Load dataset
file_path = "/Users/guddu/Desktop/InfoByte-v3/nlp/datasets/intent_dataset_augmented.csv"
df = pd.read_csv(file_path)

# Basic dataset information
print("Total queries:", len(df))
print("\nColumns:", df.columns.tolist())

# Count queries for each intent
intent_counts = df["intent"].value_counts()

print("\nQueries per intent:")
print("=" * 40)

for intent, count in intent_counts.items():
    print(f"{intent:<25} : {count}")

print("=" * 40)
print(f"{'TOTAL':<25} : {intent_counts.sum()}")