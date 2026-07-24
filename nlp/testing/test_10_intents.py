import os
import json
import torch
import pandas as pd

from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)
MODEL_PATH = "nlp/exports/best_model"

MAX_LENGTH = 128


# ============================================================
# TEST QUERIES
# 90 TOTAL = 9 QUERIES × 10 INTENTS
# ============================================================

TEST_CASES = [

    # ========================================================
    # 1. GENERAL WIKI
    # ========================================================

    (
        "Who was Alan Turing and why is he important?",
        "general_wiki",
    ),
    (
        "Explain how the French Revolution started",
        "general_wiki",
    ),
    (
        "What is quantum entanglement?",
        "general_wiki",
    ),
    (
        "Tell me about the history of the Taj Mahal",
        "general_wiki",
    ),
    (
        "How does photosynthesis work in plants?",
        "general_wiki",
    ),
    (
        "What is the difference between a republic and a democracy?",
        "general_wiki",
    ),
    (
        "Who invented the World Wide Web?",
        "general_wiki",
    ),
    (
        "Explain the concept of black holes in simple terms",
        "general_wiki",
    ),
    (
        "What caused the fall of the Roman Empire?",
        "general_wiki",
    ),


    # ========================================================
    # 2. TECHNICAL CODE
    # ========================================================

    (
        "Why am I getting a segmentation fault in my C program?",
        "technical_code",
    ),
    (
        "How do I reverse a linked list in Python?",
        "technical_code",
    ),
    (
        "My React useEffect keeps running infinitely, how do I fix it?",
        "technical_code",
    ),
    (
        "How can I implement binary search recursively in Java?",
        "technical_code",
    ),
    (
        "What does the async await syntax do in JavaScript?",
        "technical_code",
    ),
    (
        "How do I center a div using CSS flexbox?",
        "technical_code",
    ),
    (
        "Why does my FastAPI endpoint return a 422 validation error?",
        "technical_code",
    ),
    (
        "Write an SQL query to find the second highest salary",
        "technical_code",
    ),
    (
        "How can I remove duplicate elements from a C++ vector?",
        "technical_code",
    ),


    # ========================================================
    # 3. TECHNICAL ORACLE
    # ========================================================

    (
        "How do I fix ORA-00001 unique constraint violated?",
        "technical_oracle",
    ),
    (
        "Why does Oracle throw ORA-00942 table or view does not exist?",
        "technical_oracle",
    ),
    (
        "How can I create a sequence in Oracle Database?",
        "technical_oracle",
    ),
    (
        "What causes ORA-12154 TNS could not resolve the connect identifier?",
        "technical_oracle",
    ),
    (
        "How do I write a stored procedure in PL SQL?",
        "technical_oracle",
    ),
    (
        "How can I improve the performance of an Oracle SQL query?",
        "technical_oracle",
    ),
    (
        "What is the difference between NVL and COALESCE in Oracle?",
        "technical_oracle",
    ),
    (
        "How do I resolve ORA-01555 snapshot too old?",
        "technical_oracle",
    ),
    (
        "How can I view the execution plan of a query in Oracle?",
        "technical_oracle",
    ),


    # ========================================================
    # 4. DISCUSSION SOCIAL
    # ========================================================

    (
        "What do people think about working from home permanently?",
        "discussion_social",
    ),
    (
        "Is the latest iPhone actually worth upgrading to according to users?",
        "discussion_social",
    ),
    (
        "What are people's experiences with learning programming through bootcamps?",
        "discussion_social",
    ),
    (
        "Why are people divided over the ending of Game of Thrones?",
        "discussion_social",
    ),
    (
        "What do students think about using AI tools for assignments?",
        "discussion_social",
    ),
    (
        "What are users saying about switching from Android to iPhone?",
        "discussion_social",
    ),
    (
        "Do developers actually enjoy working with Java compared to Python?",
        "discussion_social",
    ),
    (
        "What is the public discussion around four day work weeks?",
        "discussion_social",
    ),
    (
        "What are people's experiences with remote internships?",
        "discussion_social",
    ),


    # ========================================================
    # 5. MOVIES
    # ========================================================

    (
        "Suggest some good psychological thriller movies",
        "movies",
    ),
    (
        "Who acted in the movie Interstellar?",
        "movies",
    ),
    (
        "Recommend Hindi suspense movies similar to Drishyam",
        "movies",
    ),
    (
        "What are some highly rated Christopher Nolan films?",
        "movies",
    ),
    (
        "I want a scary movie to watch tonight",
        "movies",
    ),
    (
        "Suggest a good murder mystery film",
        "movies",
    ),
    (
        "What is the movie Shutter Island about?",
        "movies",
    ),
    (
        "Give me some family friendly comedy movie recommendations",
        "movies",
    ),
    (
        "Which movies are similar to Gone Girl?",
        "movies",
    ),


    # ========================================================
    # 6. WEATHER
    # ========================================================

    (
        "What is the weather like in Delhi today?",
        "weather",
    ),
    (
        "Will it rain in Mumbai tomorrow?",
        "weather",
    ),
    (
        "What will the temperature be in Bangalore this evening?",
        "weather",
    ),
    (
        "Do I need an umbrella in Noida today?",
        "weather",
    ),
    (
        "What is the weather forecast for Jaipur this weekend?",
        "weather",
    ),
    (
        "Is it going to be windy in Chennai tomorrow?",
        "weather",
    ),
    (
        "How hot will Hyderabad get this afternoon?",
        "weather",
    ),
    (
        "Will there be thunderstorms in Kolkata tonight?",
        "weather",
    ),
    (
        "Give me the five day weather forecast for Pune",
        "weather",
    ),


    # ========================================================
    # 7. ACADEMIC RESEARCH
    # ========================================================

    (
        "Find recent research papers on retrieval augmented generation",
        "academic_research",
    ),
    (
        "I need scholarly articles about browser extension security",
        "academic_research",
    ),
    (
        "Show me highly cited papers on federated learning",
        "academic_research",
    ),
    (
        "Find academic studies comparing graph neural network architectures",
        "academic_research",
    ),
    (
        "I am doing a literature review on post quantum cryptography",
        "academic_research",
    ),
    (
        "What research has been published on hyperlocal air quality forecasting?",
        "academic_research",
    ),
    (
        "Find conference papers about automated program repair",
        "academic_research",
    ),
    (
        "Show recent scholarly work on detecting hallucinations in large language models",
        "academic_research",
    ),
    (
        "I need research publications about privacy preserving machine learning",
        "academic_research",
    ),


    # ========================================================
    # 8. MEDICAL RESEARCH
    # ========================================================

    (
        "Find recent clinical studies on Alzheimer's disease treatment",
        "medical_research",
    ),
    (
        "What do randomized controlled trials say about semaglutide for weight loss?",
        "medical_research",
    ),
    (
        "Show me medical research on long term proton pump inhibitor safety",
        "medical_research",
    ),
    (
        "Are there clinical trials studying new treatments for Parkinson's disease?",
        "medical_research",
    ),
    (
        "Find systematic reviews on metformin effectiveness in type 2 diabetes",
        "medical_research",
    ),
    (
        "What does recent medical evidence say about long COVID treatment?",
        "medical_research",
    ),
    (
        "Show clinical research comparing therapies for rheumatoid arthritis",
        "medical_research",
    ),
    (
        "Find studies evaluating AI assisted diagnosis of breast cancer",
        "medical_research",
    ),
    (
        "I need peer reviewed medical literature on antimicrobial resistance",
        "medical_research",
    ),


    # ========================================================
    # 9. MEDICINE
    # ========================================================

    (
        "What is Montair LC used for?",
        "medicine",
    ),
    (
        "What are the active ingredients in Zerodol SP?",
        "medicine",
    ),
    (
        "Tell me the side effects of metformin",
        "medicine",
    ),
    (
        "What is the recommended dosage of pantoprazole?",
        "medicine",
    ),
    (
        "Can I take ibuprofen during pregnancy?",
        "medicine",
    ),
    (
        "What warnings are listed for azithromycin?",
        "medicine",
    ),
    (
        "What is the composition of Pan D?",
        "medicine",
    ),
    (
        "Does amoxicillin interact with other medicines?",
        "medicine",
    ),
    (
        "What precautions should I know before taking Dolo 650?",
        "medicine",
    ),


    # ========================================================
    # 10. FOOD NUTRITION
    # ========================================================

    (
        "How many calories are in 200 grams of paneer?",
        "food_nutrition",
    ),
    (
        "How much protein is present in 250 grams of chicken breast?",
        "food_nutrition",
    ),
    (
        "What is the nutritional value of one banana?",
        "food_nutrition",
    ),
    (
        "Give me the macros for 100 grams of cooked rice",
        "food_nutrition",
    ),
    (
        "How much carbohydrate is there in one cup of oats?",
        "food_nutrition",
    ),
    (
        "What are the calories protein fat and carbs in two boiled eggs?",
        "food_nutrition",
    ),
    (
        "Show the nutrition facts for palak paneer",
        "food_nutrition",
    ),
    (
        "How much fiber is present in 150 grams of apple?",
        "food_nutrition",
    ),
    (
        "What nutrients are found in Greek yogurt?",
        "food_nutrition",
    ),
]


# ============================================================
# LOAD MODEL
# ============================================================

def load_model():

    print("=" * 70)
    print("LOADING INTENT CLASSIFIER")
    print("=" * 70)

    print(f"\nModel path: {MODEL_PATH}")

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_PATH
    )

    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_PATH
    )

    device = torch.device(
        "mps"
        if torch.backends.mps.is_available()
        else "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    model.to(device)
    model.eval()

    print(f"Device: {device}")

    # Get label mapping directly from trained model
    id2label = {
        int(k): v
        for k, v in model.config.id2label.items()
    }

    print("\nModel label mapping:")

    for label_id, intent in sorted(
        id2label.items()
    ):
        print(
            f"  {label_id} -> {intent}"
        )

    return (
        tokenizer,
        model,
        device,
        id2label,
    )


# ============================================================
# PREDICTION
# ============================================================

def predict(
    query,
    tokenizer,
    model,
    device,
    id2label,
):

    inputs = tokenizer(
        query,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=MAX_LENGTH,
    )

    inputs = {
        key: value.to(device)
        for key, value in inputs.items()
    }

    with torch.no_grad():

        outputs = model(
            **inputs
        )

        probabilities = torch.softmax(
            outputs.logits,
            dim=-1,
        )[0]

    predicted_id = int(
        torch.argmax(
            probabilities
        ).item()
    )

    predicted_intent = id2label[
        predicted_id
    ]

    confidence = float(
        probabilities[
            predicted_id
        ].item()
    )

    # Top 3 predictions
    top_values, top_indices = torch.topk(
        probabilities,
        k=min(
            3,
            len(
                probabilities
            ),
        ),
    )

    top_predictions = []

    for score, index in zip(
        top_values.tolist(),
        top_indices.tolist(),
    ):

        top_predictions.append(
            {
                "intent":
                    id2label[
                        int(
                            index
                        )
                    ],

                "confidence":
                    round(
                        score,
                        4,
                    ),
            }
        )

    return (
        predicted_intent,
        confidence,
        top_predictions,
    )


# ============================================================
# RUN TESTS
# ============================================================

def main():

    (
        tokenizer,
        model,
        device,
        id2label,
    ) = load_model()

    expected_labels = []

    predicted_labels = []

    results = []

    print("\n")
    print("=" * 70)
    print(
        f"RUNNING {len(TEST_CASES)} ROBUST INTENT TESTS"
    )
    print("=" * 70)

    for index, (
        query,
        expected,
    ) in enumerate(
        TEST_CASES,
        start=1,
    ):

        (
            predicted,
            confidence,
            top_predictions,
        ) = predict(
            query,
            tokenizer,
            model,
            device,
            id2label,
        )

        correct = (
            predicted
            == expected
        )

        expected_labels.append(
            expected
        )

        predicted_labels.append(
            predicted
        )

        results.append(
            {
                "test_number":
                    index,

                "query":
                    query,

                "expected":
                    expected,

                "predicted":
                    predicted,

                "confidence":
                    round(
                        confidence,
                        4,
                    ),

                "correct":
                    correct,

                "top_3":
                    json.dumps(
                        top_predictions
                    ),
            }
        )

        status = (
            "PASS"
            if correct
            else "FAIL"
        )

        print(
            f"\n[{index:02d}] {status}"
        )

        print(
            f"Query      : {query}"
        )

        print(
            f"Expected   : {expected}"
        )

        print(
            f"Predicted  : {predicted}"
        )

        print(
            f"Confidence : {confidence:.2%}"
        )

        if not correct:

            print(
                "Top 3      :"
            )

            for item in (
                top_predictions
            ):

                print(
                    f"             "
                    f"{item['intent']:<22}"
                    f"{item['confidence']:.2%}"
                )


    # ========================================================
    # OVERALL RESULTS
    # ========================================================

    accuracy = accuracy_score(
        expected_labels,
        predicted_labels,
    )

    passed = sum(
        1
        for result
        in results
        if result[
            "correct"
        ]
    )

    failed = (
        len(
            results
        )
        - passed
    )

    print("\n\n")
    print("=" * 70)
    print("FINAL TEST RESULTS")
    print("=" * 70)

    print(
        f"\nTotal Tests : {len(results)}"
    )

    print(
        f"Passed      : {passed}"
    )

    print(
        f"Failed      : {failed}"
    )

    print(
        f"Accuracy    : {accuracy:.2%}"
    )


    # ========================================================
    # PER INTENT ACCURACY
    # ========================================================

    print("\n")
    print("=" * 70)
    print("PER-INTENT ACCURACY")
    print("=" * 70)

    intents = sorted(
        set(
            expected_labels
        )
    )

    for intent in intents:

        intent_results = [
            result
            for result
            in results
            if result[
                "expected"
            ]
            == intent
        ]

        intent_correct = sum(
            result[
                "correct"
            ]
            for result
            in intent_results
        )

        intent_total = len(
            intent_results
        )

        intent_accuracy = (
            intent_correct
            / intent_total
        )

        print(
            f"{intent:<25} "
            f"{intent_correct}/{intent_total} "
            f"({intent_accuracy:.2%})"
        )


    # ========================================================
    # CLASSIFICATION REPORT
    # ========================================================

    print("\n")
    print("=" * 70)
    print("CLASSIFICATION REPORT")
    print("=" * 70)

    print(
        classification_report(
            expected_labels,
            predicted_labels,
            labels=intents,
            zero_division=0,
        )
    )


    # ========================================================
    # CONFUSION MATRIX
    # ========================================================

    print("\n")
    print("=" * 70)
    print("CONFUSION MATRIX")
    print("=" * 70)

    matrix = confusion_matrix(
        expected_labels,
        predicted_labels,
        labels=intents,
    )

    matrix_df = pd.DataFrame(
        matrix,
        index=[
            f"Actual: {intent}"
            for intent
            in intents
        ],
        columns=[
            f"Pred: {intent}"
            for intent
            in intents
        ],
    )

    print(
        matrix_df.to_string()
    )


    # ========================================================
    # FAILED QUERIES
    # ========================================================

    failed_results = [
        result
        for result
        in results
        if not result[
            "correct"
        ]
    ]

    print("\n")
    print("=" * 70)
    print(
        f"MISCLASSIFIED QUERIES ({len(failed_results)})"
    )
    print("=" * 70)

    if not failed_results:

        print(
            "\nAll 90 queries were classified correctly."
        )

    else:

        for result in (
            failed_results
        ):

            print(
                f"\nQuery      : "
                f"{result['query']}"
            )

            print(
                f"Expected   : "
                f"{result['expected']}"
            )

            print(
                f"Predicted  : "
                f"{result['predicted']}"
            )

            print(
                f"Confidence : "
                f"{result['confidence']:.2%}"
            )


    # ========================================================
    # SAVE RESULTS
    # ========================================================

    results_df = pd.DataFrame(
        results
    )

    output_path = os.path.join(
        BASE_DIR,
        "results",
        "robust_90_query_test.csv",
    )

    os.makedirs(
        os.path.dirname(
            output_path
        ),
        exist_ok=True,
    )

    results_df.to_csv(
        output_path,
        index=False,
    )

    print("\n")
    print("=" * 70)

    print(
        f"Detailed results saved to:\n"
        f"{output_path}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()