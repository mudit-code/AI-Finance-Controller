import csv
import os

def load_csv(path):
    with open(path, newline="") as file:
        return list(csv.DictReader(file))

def match_fees(statement_rows, ledger_rows):
    results = []
    consumed_stmts = set()
    consumed_ledgers = set()

    for statement in statement_rows:
        if statement["stmt_id"] in consumed_stmts:
            continue

        narration = statement["narration"].lower()

        # Requirement 2b: explicitly contains "processing fee"
        if "processing fee" not in narration:
            continue

        stmt_amt = float(statement["amount"])

        found_ledger = None
        for ledger in ledger_rows:
            if ledger["ledger_id"] in consumed_ledgers:
                continue

            # Requirement 2a: ledger reference appears in statement narration
            if ledger["ref"].lower() in narration:
                ledger_amt = float(ledger["amount"])

                # Requirement 2c & 11: statement amount is LOWER than ledger amount
                # using a small tolerance for floating point safety
                if ledger_amt - stmt_amt >= 0.01:
                    fee = ledger_amt - stmt_amt
                    if fee / ledger_amt <= 0.10:
                        found_ledger = ledger
                        break

        if found_ledger:
            ledger_amt = float(found_ledger["amount"])
            fee = round(ledger_amt - stmt_amt, 2)

            results.append({
                "stmt_id": statement["stmt_id"],
                "ledger_id": found_ledger["ledger_id"],
                "status": "MATCHED",
                "method": "amount_discrepancy_fee",
                "fee_amount": fee
            })
            consumed_stmts.add(statement["stmt_id"])
            consumed_ledgers.add(found_ledger["ledger_id"])

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

    fee_matches = match_fees(statement, ledger)

    print(f"Total fee matches found: {len(fee_matches)}")
    print("\nFirst 10 fee matches:")
    for result in fee_matches[:10]:
        print(result)
