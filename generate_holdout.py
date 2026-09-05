import csv
import random
import os
from datetime import datetime, timedelta

def main():
    # Use a different random seed than generate.py
    random.seed(999)

    categories = [
        'exact_match',
        'exact_match_diff_dateformat',
        'typo_reference',
        'reference_mismatch_amount_match',
        'split_payment',
        'date_lag',
        'amount_discrepancy_fee',
        'unmatched_orphan',
        # New edge cases
        'currency_rounding_diff',
        'payer_suffix_variation'
    ]

    ledgers = []
    statements = []
    ground_truths = []

    ledger_id_counter = 2000
    stmt_id_counter = 6000

    start_date = datetime(2023, 1, 1)

    counts = {cat: 0 for cat in categories}
    counts['missing_settlement'] = 0

    def get_date():
        return start_date + timedelta(days=random.randint(0, 300))

    def format_date(dt):
        return dt.strftime('%Y-%m-%d')

    for category in categories:
        if category == 'unmatched_orphan':
            for _ in range(8):
                dt = get_date()
                amt = round(random.uniform(10, 500), 2)
                stmt_id = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                
                statements.append({
                    'stmt_id': stmt_id,
                    'date': format_date(dt),
                    'amount': amt,
                    'narration': f"POS PUR {random.randint(1000, 9999)} UNKNOWN"
                })
                ground_truths.append({
                    'stmt_id': stmt_id,
                    'true_ledger_id': "",
                    'category': category
                })
                counts[category] += 1
            continue
            
        # Varying proportions (e.g. 10 instead of 7)
        for _ in range(10):
            dt = get_date()
            base_amt = round(random.uniform(50, 1000), 2)
            l_id = f"L{ledger_id_counter}"
            ledger_id_counter += 1
            ref = f"INV-{random.randint(10000, 99999)}"
            payer = f"Customer_{random.randint(1, 100)}"
            
            ledgers.append({
                'ledger_id': l_id,
                'date': format_date(dt),
                'amount': base_amt,
                'ref': ref,
                'payer': payer
            })
            
            if category == 'exact_match':
                stmt_id = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                statements.append({
                    'stmt_id': stmt_id,
                    'date': format_date(dt),
                    'amount': base_amt,
                    'narration': f"Transfer from {payer} Ref {ref}"
                })
                ground_truths.append({'stmt_id': stmt_id, 'true_ledger_id': l_id, 'category': category})
                counts[category] += 1
                
            elif category == 'exact_match_diff_dateformat':
                stmt_id = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                diff_date = dt.strftime('%d/%m/%Y') if random.choice([True, False]) else dt.strftime('%d-%b-%Y')
                statements.append({
                    'stmt_id': stmt_id,
                    'date': diff_date,
                    'amount': base_amt,
                    'narration': f"Payment Ref: {ref}"
                })
                ground_truths.append({'stmt_id': stmt_id, 'true_ledger_id': l_id, 'category': category})
                counts[category] += 1
                
            elif category == 'typo_reference':
                stmt_id = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                ref_chars = list(ref)
                if len(ref_chars) > 2:
                    idx = random.randint(0, len(ref_chars) - 2)
                    ref_chars[idx], ref_chars[idx+1] = ref_chars[idx+1], ref_chars[idx]
                typo_ref = "".join(ref_chars)
                statements.append({
                    'stmt_id': stmt_id,
                    'date': format_date(dt),
                    'amount': base_amt,
                    'narration': f"Payment Ref: {typo_ref}"
                })
                ground_truths.append({'stmt_id': stmt_id, 'true_ledger_id': l_id, 'category': category})
                counts[category] += 1
                
            elif category == 'reference_mismatch_amount_match':
                stmt_id = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                statements.append({
                    'stmt_id': stmt_id,
                    'date': format_date(dt),
                    'amount': base_amt,
                    'narration': "Generic Payment - No Ref Provided"
                })
                ground_truths.append({'stmt_id': stmt_id, 'true_ledger_id': l_id, 'category': category})
                counts[category] += 1
                
            elif category == 'split_payment':
                part1 = round(base_amt * random.uniform(0.3, 0.7), 2)
                part2 = round(base_amt - part1, 2)
                
                stmt_id1 = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                statements.append({
                    'stmt_id': stmt_id1,
                    'date': format_date(dt),
                    'amount': part1,
                    'narration': f"Split 1/2 for {ref}"
                })
                ground_truths.append({'stmt_id': stmt_id1, 'true_ledger_id': l_id, 'category': category})
                
                stmt_id2 = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                statements.append({
                    'stmt_id': stmt_id2,
                    'date': format_date(dt),
                    'amount': part2,
                    'narration': f"Split 2/2 for {ref}"
                })
                ground_truths.append({'stmt_id': stmt_id2, 'true_ledger_id': l_id, 'category': category})
                counts[category] += 2
                
            elif category == 'date_lag':
                stmt_id = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                lag_days = random.randint(1, 5)
                lag_dt = dt + timedelta(days=lag_days)
                statements.append({
                    'stmt_id': stmt_id,
                    'date': format_date(lag_dt),
                    'amount': base_amt,
                    'narration': f"Ref {ref} processed late"
                })
                ground_truths.append({'stmt_id': stmt_id, 'true_ledger_id': l_id, 'category': category})
                counts[category] += 1
                
            elif category == 'amount_discrepancy_fee':
                stmt_id = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                fee = round(random.uniform(1.0, 5.0), 2)
                received_amt = round(base_amt - fee, 2)
                statements.append({
                    'stmt_id': stmt_id,
                    'date': format_date(dt),
                    'amount': received_amt,
                    'narration': f"Payment {ref} minus processing fee"
                })
                ground_truths.append({'stmt_id': stmt_id, 'true_ledger_id': l_id, 'category': category})
                counts[category] += 1

            elif category == 'currency_rounding_diff':
                stmt_id = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                # E.g. off by $0.01 or $0.02
                diff = random.choice([-0.02, -0.01, 0.01, 0.02])
                received_amt = round(base_amt + diff, 2)
                statements.append({
                    'stmt_id': stmt_id,
                    'date': format_date(dt),
                    'amount': received_amt,
                    'narration': f"Transfer {ref} {payer}"
                })
                ground_truths.append({'stmt_id': stmt_id, 'true_ledger_id': l_id, 'category': category})
                counts[category] += 1

            elif category == 'payer_suffix_variation':
                stmt_id = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                suffixes = [" LLC", " Inc.", " Pvt Ltd", " Corp"]
                var_payer = payer + random.choice(suffixes)
                statements.append({
                    'stmt_id': stmt_id,
                    'date': format_date(dt),
                    'amount': base_amt,
                    'narration': f"Wire {ref} from {var_payer}"
                })
                ground_truths.append({'stmt_id': stmt_id, 'true_ledger_id': l_id, 'category': category})
                counts[category] += 1


    for _ in range(8):
        dt = get_date()
        base_amt = round(random.uniform(50, 1000), 2)
        l_id = f"L{ledger_id_counter}"
        ledger_id_counter += 1
        ref = f"INV-{random.randint(10000, 99999)}"
        payer = f"Customer_{random.randint(1, 100)}"
        
        ledgers.append({
            'ledger_id': l_id,
            'date': format_date(dt),
            'amount': base_amt,
            'ref': ref,
            'payer': payer
        })
        counts['missing_settlement'] += 1

    os.makedirs('data', exist_ok=True)
    
    with open('data/holdout_ledger.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['ledger_id', 'date', 'amount', 'ref', 'payer'])
        writer.writeheader()
        writer.writerows(ledgers)
        
    with open('data/holdout_statement.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['stmt_id', 'date', 'amount', 'narration'])
        writer.writeheader()
        writer.writerows(statements)
        
    with open('data/holdout_ground_truth.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['stmt_id', 'true_ledger_id', 'category'])
        writer.writeheader()
        writer.writerows(ground_truths)
        
    print(f"Holdout Summary:")
    print(f"- Number of ledger records: {len(ledgers)}")
    print(f"- Number of statement records: {len(statements)}")
    print(f"- Number of records in each category:")
    for cat in categories:
        print(f"  * {cat}: {counts[cat]}")
    print(f"- Number of ledger records intentionally missing from statement: {counts['missing_settlement']}")

if __name__ == '__main__':
    main()
