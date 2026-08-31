import csv
import os

def load_csv(path):
    with open(path, newline="") as file:
        return list(csv.DictReader(file))

def match_splits(statement_rows, ledger_rows):
    results = []
    consumed_stmts = set()
    consumed_ledgers = set()

    for ledger in ledger_rows:
        if ledger["ledger_id"] in consumed_ledgers:
            continue

        # Find candidate statements referencing this ledger's ref
        candidates = []
        for stmt in statement_rows:
            if stmt["stmt_id"] in consumed_stmts:
                continue

            # Reference evidence is required
            if ledger["ref"] in stmt["narration"]:
                candidates.append(stmt)

        # Find all valid pairs
        valid_pairs = []
        for i in range(len(candidates)):
            for j in range(i+1, len(candidates)):
                s1 = candidates[i]
                s2 = candidates[j]

                sum_amt = float(s1["amount"]) + float(s2["amount"])
                if abs(sum_amt - float(ledger["amount"])) <= 0.01:
                    valid_pairs.append((s1, s2))

        if len(valid_pairs) == 1:
            s1, s2 = valid_pairs[0]
            results.append({
                "stmt_ids": [s1["stmt_id"], s2["stmt_id"]],
                "ledger_id": ledger["ledger_id"],
                "status": "MATCHED",
                "method": "split_payment"
            })
            consumed_ledgers.add(ledger["ledger_id"])
            consumed_stmts.add(s1["stmt_id"])
            consumed_stmts.add(s2["stmt_id"])

        elif len(valid_pairs) > 1:
            ambiguous_ids = set()
            for pair in valid_pairs:
                ambiguous_ids.add(pair[0]["stmt_id"])
                ambiguous_ids.add(pair[1]["stmt_id"])

            results.append({
                "stmt_ids": sorted(list(ambiguous_ids)),
                "ledger_id": ledger["ledger_id"],
                "status": "REVIEW_REQUIRED",
                "method": "ambiguous_split_payment"
            })
            # Do NOT consume ledger or statements

    return results

if __name__ == "__main__":
    # Resolve the data directory
    data_dir = "data"
    if not os.path.exists(data_dir):
        # Fallback if run directly from inside the src/reconciliation directory
        data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))

    ledger_path = os.path.join(data_dir, "ledger.csv")
    statement_path = os.path.join(data_dir, "statement.csv")

    ledger = load_csv(ledger_path)
    statement = load_csv(statement_path)

    split_matches = match_splits(statement, ledger)

    print(f"Total split matches found: {len(split_matches)}")
    print("\nFirst 10 split matches:")
    for result in split_matches[:10]:
        print(result)
