import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_adversarial import adversarial_cases
from reconciliation.matcher import match_exact
from reconciliation.llm_explainer import explain_exceptions

def main():
    print("Extracting specific adversarial cases with rejected candidates...")
    # Cases 4 (Ambiguous typo), 7 (Split payments), 18 (Ambiguous exact ref), 19 (Ambiguous ledger)
    target_names = ["4.", "7.", "18.", "19."]
    
    statements = []
    ledgers = []
    for case in adversarial_cases:
        if any(case["name"].startswith(n) for n in target_names):
            statements.extend(case["statements"])
            ledgers.extend(case["ledgers"])

    print("Running match_exact...")
    results = match_exact(statements, ledgers)

    print("Running explain_exceptions...")
    enriched_results = explain_exceptions(statements, ledgers, results, limit=5)

    exceptions = [r for r in enriched_results if r.get("status") in ["UNMATCHED", "REVIEW_REQUIRED"]]
    
    disagreement_count = 0
    print("\n" + "="*80)
    for exc in exceptions:
        stmt_id = exc.get("stmt_id")
        explanation = exc.get("llm_explanation")
        disagreement = exc.get("llm_disagreement")
        method = exc.get("method")
        cands = exc.get("rejected_candidates", [])
        
        print(f"Statement ID: {stmt_id} | Status: {exc.get('status')} | Method: {method}")
        print(f"Rejected Candidates Count: {len(cands)}")
        print(f"Explanation:\n{explanation}")
        if disagreement:
            print(f"Disagreement Flag: TRUE (Suggested Ledger: {exc.get('suggested_ledger_id')})")
            disagreement_count += 1
        print("-" * 80)

    print(f"\nTotal Disagreements Flagged: {disagreement_count} / {len(exceptions)}")

if __name__ == "__main__":
    main()
