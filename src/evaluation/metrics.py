import csv

def load_csv(path):
    with open(path, newline="") as file:
        return list(csv.DictReader(file))

def evaluate(predictions, ground_truth):
    # Convert predictions to a lookup dictionary keyed by stmt_id for faster matching
    pred_dict = {p["stmt_id"]: p for p in predictions}
    
    total = len(ground_truth)
    correct = 0
    
    category_stats = {}
    
    for gt in ground_truth:
        stmt_id = gt["stmt_id"]
        true_ledger_id = gt["true_ledger_id"]
        
        # When read from CSV, empty fields might be empty strings.
        # Normalize to None for comparison with prediction layer.
        if not true_ledger_id:
            true_ledger_id = None
            
        category = gt["category"]
        
        if category not in category_stats:
            category_stats[category] = {"total": 0, "correct": 0}
            
        category_stats[category]["total"] += 1
        
        pred = pred_dict.get(stmt_id)
        if pred:
            pred_ledger_id = pred.get("ledger_id")
        else:
            # If for some reason there is no prediction for this stmt_id, it is missing
            pred_ledger_id = None
            
        # Check correctness
        if pred_ledger_id == true_ledger_id:
            correct += 1
            category_stats[category]["correct"] += 1
            
    incorrect = total - correct
    accuracy = (correct / total * 100) if total > 0 else 0
    
    print("--- Evaluation Results ---")
    print(f"Total statements: {total}")
    print(f"Correct decisions: {correct}")
    print(f"Incorrect decisions: {incorrect}")
    print(f"Overall Accuracy: {accuracy:.2f}%\n")
    
    print("--- Category-wise Accuracy ---")
    for cat, stats in category_stats.items():
        cat_total = stats["total"]
        cat_correct = stats["correct"]
        cat_acc = (cat_correct / cat_total * 100) if cat_total > 0 else 0
        print(f"Category: {cat}")
        print(f"  Total: {cat_total}")
        print(f"  Correct: {cat_correct}")
        print(f"  Accuracy: {cat_acc:.2f}%")
        print()
        
    return {
        "total": total,
        "correct": correct,
        "incorrect": incorrect,
        "accuracy": accuracy,
        "category_stats": category_stats
    }
