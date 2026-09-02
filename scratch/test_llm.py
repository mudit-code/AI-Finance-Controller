import os
import sys

# Add src directory to sys.path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from reconciliation.matcher import load_csv, match_exact
from reconciliation.llm_explainer import explain_exceptions

def main():
    print("Loading holdout data...")
    statements = load_csv('data/holdout_statement.csv')
    ledgers = load_csv('data/holdout_ledger.csv')

    print("Running match_exact...")
    results = match_exact(statements, ledgers)

    print("Running explain_exceptions (limit=10)...")
    enriched_results = explain_exceptions(statements, ledgers, results, limit=10)

    exceptions = [r for r in enriched_results if r.get("status") in ["UNMATCHED", "REVIEW_REQUIRED"]]
    
    disagreement_count = 0
    print("\n" + "="*80)
    for exc in exceptions:
        stmt_id = exc.get("stmt_id")
        explanation = exc.get("llm_explanation")
        disagreement = exc.get("llm_disagreement")
        method = exc.get("method")
        
        print(f"Statement ID: {stmt_id} | Status: {exc.get('status')} | Method: {method}")
        print(f"Explanation:\n{explanation}")
        if disagreement:
            print(f"Disagreement Flag: TRUE (Suggested Ledger: {exc.get('suggested_ledger_id')})")
            disagreement_count += 1
        print("-" * 80)

    print(f"\nTotal Disagreements Flagged: {disagreement_count} / {len(exceptions)}")

if __name__ == "__main__":
    main()
