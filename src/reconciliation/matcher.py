import csv

def load_csv(path):
    with open(path, newline="") as file:
        return list(csv.DictReader(file))

def normalize_reference(reference):
    if not reference:
        return ""
    ref = reference.upper()
    for char in [" ", "-", "/", "_"]:
        ref = ref.replace(char, "")
    return ref

def match_exact(statement_rows, ledger_rows):
    results = []
    consumed_ledgers = set()

    for statement in statement_rows:
        matched = False
        
        # Layer 1: Exact reference and exact amount
        for ledger in ledger_rows:
            if ledger["ledger_id"] in consumed_ledgers:
                continue
                
            if (
                statement["amount"] == ledger["amount"]
                and ledger["ref"] in statement["narration"]
            ):
                results.append({
                    "stmt_id": statement["stmt_id"],
                    "ledger_id": ledger["ledger_id"],
                    "status": "MATCHED",
                    "method": "exact_reference_amount"
                })
                consumed_ledgers.add(ledger["ledger_id"])
                matched = True
                break
                
        # Layer 2: Normalized reference and exact amount
        if not matched:
            for ledger in ledger_rows:
                if ledger["ledger_id"] in consumed_ledgers:
                    continue
                
                normalized_ref = normalize_reference(ledger["ref"])
                normalized_narration = normalize_reference(statement["narration"])
                
                if (
                    statement["amount"] == ledger["amount"]
                    and normalized_ref in normalized_narration
                ):
                    results.append({
                        "stmt_id": statement["stmt_id"],
                        "ledger_id": ledger["ledger_id"],
                        "status": "MATCHED",
                        "method": "normalized_reference_amount"
                    })
                    consumed_ledgers.add(ledger["ledger_id"])
                    matched = True
                    break

        if not matched:
            results.append({
                "stmt_id": statement["stmt_id"],
                "ledger_id": None,
                "status": "UNMATCHED",
                "method": "no_exact_match"
            })

    return results

if __name__ == "__main__":
    ledger = load_csv("data/ledger.csv")
    statement = load_csv("data/statement.csv")

    results = match_exact(statement, ledger)

    matched_count = sum(1 for r in results if r["status"] == "MATCHED")
    unmatched_count = sum(1 for r in results if r["status"] == "UNMATCHED")

    print(f"Total statements: {len(results)}")
    print(f"Matched: {matched_count}")
    print(f"Unmatched: {unmatched_count}")

    print("\nFirst 10 results:")
    for result in results[:10]:
        print(result)