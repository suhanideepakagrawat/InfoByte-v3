import os
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from transformers import (
    AutoTokenizer, 
    AutoModelForSequenceClassification, 
    TrainingArguments, 
    Trainer
)


# -------------------------------------------------------------
# 1. Custom Trainer for Class Weighting (Handles Imbalance)
# -------------------------------------------------------------
class WeightedTrainer(Trainer):
    def __init__(self, *args, class_weights=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Store as float originally
        self.class_weights = torch.tensor(class_weights, dtype=torch.float) if class_weights is not None else None

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.get("labels")
        outputs = model(**inputs)
        logits = outputs.get("logits")
        
        if self.class_weights is not None:
            # Fix: Dynamically cast the weights to match the logits precision (Half vs Float)
            # and send them to the correct device (CPU/MPS/CUDA)
            weights = self.class_weights.to(device=model.device, dtype=logits.dtype)
            loss_fct = nn.CrossEntropyLoss(weight=weights)
        else:
            loss_fct = nn.CrossEntropyLoss()
            
        loss = loss_fct(logits.view(-1, self.model.config.num_labels), labels.view(-1))
        return (loss, outputs) if return_outputs else loss

# -------------------------------------------------------------
# 2. PyTorch Dataset Wrapper
# -------------------------------------------------------------
class IntentDataset(torch.utils.data.Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        item['labels'] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item

    def __len__(self):
        return len(self.labels)

# -------------------------------------------------------------
# 3. Evaluation Metrics Customization
# -------------------------------------------------------------
def compute_metrics(pred):
    labels = pred.label_ids
    preds = pred.predictions.argmax(-1)
    precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average='macro')
    acc = accuracy_score(labels, preds)
    return {
        'accuracy': acc,
        'f1_macro': f1,
        'precision_macro': precision,
        'recall_macro': recall
    }

def main():
    # Load dataset
    DATA_PATH = "/Users/guddu/Desktop/InfoByte-v3/nlp/datasets/intent_dataset_augmented.csv"
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Please place {DATA_PATH} in the root directory.")
        
    df = pd.read_csv(DATA_PATH)
    
    # Map textual intents to integers
    unique_intents = sorted(df['intent'].unique())
    intent_to_id = {intent: i for i, intent in enumerate(unique_intents)}
    id_to_intent = {i: intent for intent, i in intent_to_id.items()}
    df['label'] = df['intent'].map(intent_to_id)
    
    print(f"Mapping configurations: {intent_to_id}")
    
    # -------------------------------------------------------------
    # 4. Stratified Data Splitting (80% Train, 10% Val, 10% Test)
    # -------------------------------------------------------------
    train_texts, temp_texts, train_labels, temp_labels = train_test_split(
        df['query'].astype(str).tolist(), 
        df['label'].tolist(), 
        test_size=0.2, 
        random_state=42, 
        stratify=df['label'].tolist()
    )
    
    val_texts, test_texts, val_labels, test_labels = train_test_split(
        temp_texts, 
        temp_labels, 
        test_size=0.5, 
        random_state=42, 
        stratify=temp_labels
    )
    
    # -------------------------------------------------------------
    # 5. Calculate Loss Balancing Weights
    # -------------------------------------------------------------
    class_weights = compute_class_weight(
        class_weight='balanced', 
        classes=np.unique(train_labels), 
        y=train_labels
    )
    print(f"Calculated class weights: {class_weights}")

    # -------------------------------------------------------------
    # 6. Model & Tokenizer Initializations
    # -------------------------------------------------------------
    MODEL_NAME = "roberta-base"  # Optimized for high classification accuracy
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    
    train_encodings = tokenizer(train_texts, truncation=True, padding=True, max_length=64)
    val_encodings = tokenizer(val_texts, truncation=True, padding=True, max_length=64)
    test_encodings = tokenizer(test_texts, truncation=True, padding=True, max_length=64)
    
    train_dataset = IntentDataset(train_encodings, train_labels)
    val_dataset = IntentDataset(val_encodings, val_labels)
    test_dataset = IntentDataset(test_encodings, test_labels)
    
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, 
        num_labels=len(unique_intents),
        id2label=id_to_intent,
        label2id=intent_to_id
    )

    # -------------------------------------------------------------
    # 7. Training Parameters Optimized for Full Fine-Tuning
    # -------------------------------------------------------------
    training_args = TrainingArguments(
        output_dir='./results',
        num_train_epochs=4,                     
        per_device_train_batch_size=16,          
        per_device_eval_batch_size=32,
        warmup_steps=118,                       # Replaced warmup_ratio with explicit step structure
        weight_decay=0.01,                      
        logging_steps=50,
        eval_strategy="epoch",                  # Updated to support modern v5 structure
        save_strategy="epoch",
        learning_rate=3e-5,                     
        load_best_model_at_end=True,            
        metric_for_best_model="accuracy",
        report_to="none"                        # Removed logging_dir argument to prevent conflicts
    )

    # Pass the custom class weights directly to our custom trainer
    trainer = WeightedTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        class_weights=class_weights
    )

    print("Beginning optimal transfer learning routine...")
    trainer.train()

    # -------------------------------------------------------------
    # 8. Unseen Test Dataset Performance Check
    # -------------------------------------------------------------
    print("\nEvaluating fine-tuned performance on out-of-sample Test Data:")
    test_results = trainer.evaluate(test_dataset)
    print(f"Final Evaluation Metrics: {test_results}")
    
    # Save optimized model weights & configurations
    model.save_pretrained("./optimized_intent_model")
    tokenizer.save_pretrained("./optimized_intent_model")
    print("\nModel pipeline successfully exported to './optimized_intent_model'")

if __name__ == "__main__":
    main()
