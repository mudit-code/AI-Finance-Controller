import sys
import os
import pytest

# Add root directory to sys path so we can import from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.reconciliation.matcher import match_exact

adversarial_cases = [
    {
        "name": "1. Duplicate ledger amounts",
        "ledgers": [
            {"ledger_id": "L1-A", "date": "2023-01-01", "amount": "100.00", "ref": "INV-01", "payer": "Customer A"},
            {"ledger_id": "L1-B", "date": "2023-01-01", "amount": "100.00", "ref": "INV-02", "payer": "Customer B"}
        ],
        "statements": [
            {"stmt_id": "S1", "date": "2023-01-01", "amount": "100.00", "narration": "Generic Payment"}
        ],
        "expected": lambda results: len(results) == 1 and results[0]['status'] == 'UNMATCHED'
    },
    {
        "name": "2. Duplicate statement amounts",
        "ledgers": [
            {"ledger_id": "L2", "date": "2023-01-02", "amount": "50.00", "ref": "INV-03", "payer": "Customer C"}
        ],
        "statements": [
            {"stmt_id": "S2-A", "date": "2023-01-02", "amount": "50.00", "narration": "Payment for INV-03"},
            {"stmt_id": "S2-B", "date": "2023-01-02", "amount": "50.00", "narration": "Payment for INV-03"}
        ],
        "expected": lambda results: (len([r for r in results if r['status'] == 'MATCHED']) == 1 and 
                                     len([r for r in results if r['status'] == 'UNMATCHED']) == 1) or \
                                    (len([r for r in results if r['status'] == 'REVIEW_REQUIRED']) > 0) or \
                                    (len([r for r in results if r['status'] == 'UNMATCHED']) == 2)
    },
    {
        "name": "3. Similar references belonging to different transactions",
        "ledgers": [
            {"ledger_id": "L3-A", "date": "2023-01-03", "amount": "200.00", "ref": "INV-100", "payer": "Cust D"},
            {"ledger_id": "L3-B", "date": "2023-01-03", "amount": "200.00", "ref": "INV-1000", "payer": "Cust E"}
        ],
        "statements": [
            {"stmt_id": "S3", "date": "2023-01-03", "amount": "200.00", "narration": "Paid INV-1000"}
        ],
        "expected": lambda results: len(results) == 1 and results[0]['ledger_id'] == 'L3-B'
    },
    {
        "name": "4. Ambiguous reference typos",
        "ledgers": [
            {"ledger_id": "L4-A", "date": "2023-01-04", "amount": "150.00", "ref": "INV-A", "payer": "F"},
            {"ledger_id": "L4-B", "date": "2023-01-04", "amount": "150.00", "ref": "INV-B", "payer": "G"}
        ],
        "statements": [
            {"stmt_id": "S4", "date": "2023-01-04", "amount": "150.00", "narration": "INV-C"}
        ],
        "expected": lambda results: len(results) == 1 and results[0]['status'] in ['UNMATCHED', 'REVIEW_REQUIRED']
    },
    {
        "name": "5. Same payer with different transactions",
        "ledgers": [
            {"ledger_id": "L5-A", "date": "2023-01-05", "amount": "500.00", "ref": "INV-X", "payer": "Acme"},
            {"ledger_id": "L5-B", "date": "2023-01-05", "amount": "500.00", "ref": "INV-Y", "payer": "Acme"}
        ],
        "statements": [
            {"stmt_id": "S5", "date": "2023-01-05", "amount": "500.00", "narration": "Payment from Acme"}
        ],
        "expected": lambda results: len(results) == 1 and results[0]['status'] == 'UNMATCHED'
    },
    {
        "name": "6. Same reference fragment appearing in multiple ledger references",
        "ledgers": [
            {"ledger_id": "L6-A", "date": "2023-01-06", "amount": "400.00", "ref": "2023-01", "payer": "H"},
            {"ledger_id": "L6-B", "date": "2023-01-06", "amount": "400.00", "ref": "2023-01-A", "payer": "I"}
        ],
        "statements": [
            {"stmt_id": "S6", "date": "2023-01-06", "amount": "400.00", "narration": "Ref 2023-01"}
        ],
        "expected": lambda results: len(results) == 1 and results[0]['ledger_id'] == 'L6-A'
    },
    {
        "name": "7. Split-payment combinations with multiple possible pairs",
        "ledgers": [
            {"ledger_id": "L7", "date": "2023-01-07", "amount": "100.00", "ref": "SPLIT", "payer": "J"}
        ],
        "statements": [
            {"stmt_id": "S7-A", "date": "2023-01-07", "amount": "50.00", "narration": "SPLIT part 1"},
            {"stmt_id": "S7-B", "date": "2023-01-07", "amount": "50.00", "narration": "SPLIT part 2"},
            {"stmt_id": "S7-C", "date": "2023-01-07", "amount": "50.00", "narration": "SPLIT part 3"}
        ],
        "expected": lambda results: all(r['status'] in ['UNMATCHED', 'REVIEW_REQUIRED'] for r in results)
    },
    {
        "name": "8. Three statement records that could potentially form a split",
        "ledgers": [
            {"ledger_id": "L8", "date": "2023-01-08", "amount": "150.00", "ref": "3WAY", "payer": "K"}
        ],
        "statements": [
            {"stmt_id": "S8-A", "date": "2023-01-08", "amount": "50.00", "narration": "3WAY"},
            {"stmt_id": "S8-B", "date": "2023-01-08", "amount": "50.00", "narration": "3WAY"},
            {"stmt_id": "S8-C", "date": "2023-01-08", "amount": "50.00", "narration": "3WAY"}
        ],
        "expected": lambda results: all(r['ledger_id'] == 'L8' for r in results)
    },
    {
        "name": "9. Statement amount slightly higher than ledger amount",
        "ledgers": [
            {"ledger_id": "L9", "date": "2023-01-09", "amount": "100.00", "ref": "FEE-UP", "payer": "L"}
        ],
        "statements": [
            {"stmt_id": "S9", "date": "2023-01-09", "amount": "105.00", "narration": "FEE-UP processing fee"}
        ],
        "expected": lambda results: len(results) == 1 and results[0]['status'] == 'UNMATCHED'
    },
    {
        "name": "10. Fee-like narration with an unexpected amount difference",
        "ledgers": [
            {"ledger_id": "L10", "date": "2023-01-10", "amount": "100.00", "ref": "FEE-HIGH", "payer": "M"}
        ],
        "statements": [
            {"stmt_id": "S10", "date": "2023-01-10", "amount": "10.00", "narration": "FEE-HIGH processing fee"}
        ],
        "expected": lambda results: len(results) == 1 and results[0]['status'] in ['UNMATCHED', 'REVIEW_REQUIRED']
    },
    {
        "name": "11. Missing ledger transaction",
        "ledgers": [],
        "statements": [
            {"stmt_id": "S11", "date": "2023-01-11", "amount": "500.00", "narration": "Valid looking payment INV-999"}
        ],
        "expected": lambda results: len(results) == 1 and results[0]['status'] == 'UNMATCHED'
    },
    {
        "name": "12. Extra statement transaction",
        "ledgers": [
            {"ledger_id": "L12", "date": "2023-01-12", "amount": "100.00", "ref": "X", "payer": "N"}
        ],
        "statements": [
            {"stmt_id": "S12-A", "date": "2023-01-12", "amount": "100.00", "narration": "X"},
            {"stmt_id": "S12-B", "date": "2023-01-12", "amount": "100.00", "narration": "X"}
        ],
        "expected": lambda results: (len([r for r in results if r['status'] == 'MATCHED']) == 1 and 
                                     len([r for r in results if r['status'] == 'UNMATCHED']) == 1) or \
                                    all(r['status'] == 'UNMATCHED' for r in results)
    },
    {
        "name": "13. Conflicting date and reference evidence",
        "ledgers": [
            {"ledger_id": "L13-A", "date": "2023-01-01", "amount": "100.00", "ref": "INV-A", "payer": "O"},
            {"ledger_id": "L13-B", "date": "2023-12-31", "amount": "100.00", "ref": "INV-B", "payer": "P"}
        ],
        "statements": [
            {"stmt_id": "S13", "date": "2023-01-01", "amount": "100.00", "narration": "Payment for INV-B"}
        ],
        "expected": lambda results: len(results) == 1 and results[0]['ledger_id'] == 'L13-B'
    },
    {
        "name": "14. Exact amount but completely unrelated narration",
        "ledgers": [
            {"ledger_id": "L14", "date": "2023-01-14", "amount": "999.99", "ref": "UNIQUE", "payer": "Q"}
        ],
        "statements": [
            {"stmt_id": "S14", "date": "2023-01-14", "amount": "999.99", "narration": "Totally different"}
        ],
        "expected": lambda results: len(results) == 1 and results[0]['status'] == 'UNMATCHED'
    },
    {
        "name": "15. Very similar payer names",
        "ledgers": [
            {"ledger_id": "L15-A", "date": "2023-01-15", "amount": "100.00", "ref": "INV-15", "payer": "Jon Doe"},
            {"ledger_id": "L15-B", "date": "2023-01-15", "amount": "100.00", "ref": "INV-16", "payer": "John Doe"}
        ],
        "statements": [
            {"stmt_id": "S15", "date": "2023-01-15", "amount": "100.00", "narration": "Payment by Jon Doe"}
        ],
        "expected": lambda results: len(results) == 1 and results[0]['ledger_id'] == 'L15-A'
    },
    {
        "name": "16. Very similar transaction references",
        "ledgers": [
            {"ledger_id": "L16-A", "date": "2023-01-16", "amount": "100.00", "ref": "0001", "payer": "R"},
            {"ledger_id": "L16-B", "date": "2023-01-16", "amount": "100.00", "ref": "O001", "payer": "S"}
        ],
        "statements": [
            {"stmt_id": "S16", "date": "2023-01-16", "amount": "100.00", "narration": "0001"}
        ],
        "expected": lambda results: len(results) == 1 and results[0]['ledger_id'] == 'L16-A'
    },
    {
        "name": "17. Duplicate-looking transactions on the same date",
        "ledgers": [
            {"ledger_id": "L17-A", "date": "2023-01-17", "amount": "50.00", "ref": "SUB", "payer": "T"},
            {"ledger_id": "L17-B", "date": "2023-01-17", "amount": "50.00", "ref": "SUB", "payer": "T"}
        ],
        "statements": [
            {"stmt_id": "S17-A", "date": "2023-01-17", "amount": "50.00", "narration": "SUB"},
            {"stmt_id": "S17-B", "date": "2023-01-17", "amount": "50.00", "narration": "SUB"}
        ],
        "expected": lambda results: len([r for r in results if r['status'] == 'MATCHED']) == 2
    },
    {
        "name": "18. One statement that could match multiple ledgers",
        "ledgers": [
            {"ledger_id": "L18-A", "date": "2023-01-18", "amount": "100.00", "ref": "INV-A", "payer": "U"},
            {"ledger_id": "L18-B", "date": "2023-01-18", "amount": "100.00", "ref": "INV-B", "payer": "U"}
        ],
        "statements": [
            {"stmt_id": "S18", "date": "2023-01-18", "amount": "100.00", "narration": "INV-A and INV-B"}
        ],
        "expected": lambda results: len(results) == 1 and results[0]['status'] in ['UNMATCHED', 'REVIEW_REQUIRED']
    },
    {
        "name": "19. One ledger that could match multiple statements",
        "ledgers": [
            {"ledger_id": "L19", "date": "2023-01-19", "amount": "100.00", "ref": "PAYMENT", "payer": "V"}
        ],
        "statements": [
            {"stmt_id": "S19-A", "date": "2023-01-19", "amount": "100.00", "narration": "PAYMENT"},
            {"stmt_id": "S19-B", "date": "2023-01-19", "amount": "100.00", "narration": "PAYMENT"}
        ],
        "expected": lambda results: all(r['status'] in ['UNMATCHED', 'REVIEW_REQUIRED'] for r in results) or \
                                    (len([r for r in results if r['status'] == 'MATCHED']) == 1 and \
                                     len([r for r in results if r['status'] == 'UNMATCHED']) == 1)
    },
    {
        "name": "20. Completely ambiguous transaction with insufficient evidence",
        "ledgers": [
            {"ledger_id": "L20", "date": "2023-01-20", "amount": "10.00", "ref": "10-DOLLARS", "payer": "W"}
        ],
        "statements": [
            {"stmt_id": "S20", "date": "2023-01-20", "amount": "10.00", "narration": ""}
        ],
        "expected": lambda results: len(results) == 1 and results[0]['status'] == 'UNMATCHED'
    },
    {
        "name": "21. Orphan within tolerance (false positive check)",
        "ledgers": [
            {"ledger_id": "L21", "date": "2023-01-21", "amount": "100.02", "ref": "SOME-REF", "payer": "Some Payer"}
        ],
        "statements": [
            {"stmt_id": "S21", "date": "2023-01-21", "amount": "100.00", "narration": "Totally Unrelated Transaction"}
        ],
        "expected": lambda results: len(results) == 1 and results[0]['status'] == 'UNMATCHED'
    },
    {
        "name": "22. Two ledgers differing by 0.01",
        "ledgers": [
            {"ledger_id": "L22-A", "date": "2023-01-22", "amount": "50.00", "ref": "INV-22", "payer": "Cust 22"},
            {"ledger_id": "L22-B", "date": "2023-01-22", "amount": "50.01", "ref": "INV-22-ALT", "payer": "Cust 22"}
        ],
        "statements": [
            {"stmt_id": "S22", "date": "2023-01-22", "amount": "50.00", "narration": "Payment for INV-22"}
        ],
        "expected": lambda results: len(results) == 1 and (
            (results[0]['status'] == 'MATCHED' and results[0]['ledger_id'] == 'L22-A') or
            (results[0]['status'] in ['UNMATCHED', 'REVIEW_REQUIRED'] and results[0].get('ledger_id') is None)
        )
    },
    {
        "name": "23. Amount off by exactly 0.03 (outside tolerance)",
        "ledgers": [
            {"ledger_id": "L23", "date": "2023-01-23", "amount": "75.03", "ref": "INV-23", "payer": "Cust 23"}
        ],
        "statements": [
            {"stmt_id": "S23", "date": "2023-01-23", "amount": "75.00", "narration": "Payment for INV-23"}
        ],
        "expected": lambda results: len(results) == 1 and results[0]['status'] == 'UNMATCHED'
    }
]

case_params = [
    pytest.param(c, marks=pytest.mark.xfail(reason="3-way split payments not yet supported - see README limitations")) 
    if c["name"].startswith("8.") else c 
    for c in adversarial_cases
]

@pytest.mark.parametrize("case", case_params, ids=[c["name"] for c in adversarial_cases])
def test_adversarial(case):
    # Suppress standard output during match_exact to hide debug prints from Layer 4
    old_stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w')
    try:
        results = match_exact(case['statements'], case['ledgers'])
    finally:
        sys.stdout.close()
        sys.stdout = old_stdout

    assert case["expected"](results), f"Failed: Matcher output was {results}"
