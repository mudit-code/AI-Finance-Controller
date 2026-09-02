import csv
import datetime
import difflib
import sys
import os

# Ensure we can import from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.reconciliation.split_matcher import match_splits
from src.reconciliation.fee_matcher import match_fees

def load_csv(path):
    with open(path, newline="") as file:
        return list(csv.DictReader(file))

ROUNDING_TOLERANCE = 0.02

def amounts_match(amt1, amt2):
    try:
        return abs(float(amt1) - float(amt2)) <= ROUNDING_TOLERANCE
    except ValueError:
        return amt1 == amt2


def normalize_reference(reference):
    if not reference:
        return ""
    ref = reference.upper()
    for char in [" ", "-", "/", "_"]:
        ref = ref.replace(char, "")
    return ref

def is_exact_token(ref, text):
    if not ref:
        return False
    idx = text.find(ref)
    while idx != -1:
        prev_char_ok = (idx == 0) or not text[idx - 1].isalnum()
        end_idx = idx + len(ref)
        next_char_ok = (end_idx == len(text)) or not text[end_idx].isalnum()
        if prev_char_ok and next_char_ok:
            return True
        idx = text.find(ref, idx + 1)
    return False

def damerau_levenshtein_distance(s1, s2):
    d = {}
    len1 = len(s1)
    len2 = len(s2)
    for i in range(-1, len1 + 1):
        d[(i, -1)] = i + 1
    for j in range(-1, len2 + 1):
        d[(-1, j)] = j + 1

    for i in range(len1):
        for j in range(len2):
            cost = 0 if s1[i] == s2[j] else 1
            d[(i, j)] = min(
                d[(i-1, j)] + 1,
                d[(i, j-1)] + 1,
                d[(i-1, j-1)] + cost
            )
            # Transposition check
            if i > 0 and j > 0 and s1[i] == s2[j-1] and s1[i-1] == s2[j]:
                d[(i, j)] = min(d[(i, j)], d[(i-2, j-2)] + cost)

    return d[(len1 - 1, len2 - 1)]

def extract_potential_payer(narration):
    upper_nar = narration.upper()
    keywords = ["FROM ", "BY ", "PAYER: ", "NAME: ", "CUSTOMER "]
    for kw in keywords:
        if kw in upper_nar:
            idx = upper_nar.find(kw) + len(kw)
            rest = upper_nar[idx:]
            return " ".join(rest.split()[:2])
    return upper_nar

def score_candidate(statement, ledger):
    score = 0.0
    evidence = []

    # Amount match (pre-requisite, strong signal)
    if amounts_match(statement["amount"], ledger["amount"]):
        score += 50
        evidence.append("amount_exact")

    # Date match (supporting signal)
    def parse_date(d_str):
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y"]:
            try:
                return datetime.datetime.strptime(d_str, fmt).date()
            except ValueError:
                pass
        return None

    s_date = parse_date(statement["date"])
    l_date = parse_date(ledger["date"])

    if s_date and l_date:
        days_diff = abs((s_date - l_date).days)
        if days_diff == 0:
            score += 30
            evidence.append("date_exact")
        elif days_diff <= 3:
            score += 15
            evidence.append("date_close")

    # Payer similarity (supporting signal)
    extracted_payer = extract_potential_payer(statement["narration"])
    ledger_payer = ledger["payer"].upper()

    sim = difflib.SequenceMatcher(None, ledger_payer, extracted_payer).ratio()
    if is_exact_token(ledger_payer, statement["narration"].upper()):
        score += 40
        evidence.append("payer_exact")
    elif sim > 0.6:
        score += sim * 20
        evidence.append(f"payer_sim_{sim:.2f}")
    elif ledger_payer in statement["narration"].upper():
        score += 20
        evidence.append("payer_in_narration")

    if "NO REF" in statement["narration"].upper():
        evidence.append("explicit_no_ref")

    # Reference similarity (weak supporting signal)
    ledger_ref = ledger["ref"].upper()
    ref_sim = difflib.SequenceMatcher(None, ledger_ref, statement["narration"].upper()).ratio()
    if ref_sim > 0.4:
        score += ref_sim * 10
        evidence.append(f"ref_sim_{ref_sim:.2f}")

    return score, evidence

def match_exact(statement_rows, ledger_rows):
    results = []
    consumed_ledgers = set()
    consumed_stmts = set()
    top_candidates_for_stmt = {}

    # Pre-calculate normalized ledger references
    for ledger in ledger_rows:
        ledger["normalized_ref"] = normalize_reference(ledger["ref"])

    # Layers 1-4 pipeline
    for statement in statement_rows:
        matched = False

        # Layer 1: Exact reference and exact amount
        layer1_candidates = []
        for ledger in ledger_rows:
            if ledger["ledger_id"] in consumed_ledgers:
                continue

            if (
                amounts_match(statement["amount"], ledger["amount"])
                and is_exact_token(ledger["ref"], statement["narration"])
            ):
                layer1_candidates.append(ledger)

        if len(layer1_candidates) == 1:
            ledger = layer1_candidates[0]
            results.append({
                "stmt_id": statement["stmt_id"],
                "ledger_id": ledger["ledger_id"],
                "status": "MATCHED",
                "method": "exact_reference_amount"
            })
            consumed_ledgers.add(ledger["ledger_id"])
            consumed_stmts.add(statement["stmt_id"])
            matched = True
        elif len(layer1_candidates) > 1:
            unique_refs = set(l["ref"].upper() for l in layer1_candidates)
            if len(unique_refs) == 1:
                ledger = layer1_candidates[0]
                results.append({
                    "stmt_id": statement["stmt_id"],
                    "ledger_id": ledger["ledger_id"],
                    "status": "MATCHED",
                    "method": "exact_reference_amount"
                })
                consumed_ledgers.add(ledger["ledger_id"])
                consumed_stmts.add(statement["stmt_id"])
                matched = True
            else:
                results.append({
                    "stmt_id": statement["stmt_id"],
                    "ledger_id": None,
                    "status": "UNMATCHED",
                    "method": "ambiguous_exact_reference",
                    "rejected_candidates": layer1_candidates
                })
                consumed_stmts.add(statement["stmt_id"])
                matched = True

        # Layer 2: Normalized reference and exact amount
        if not matched:
            layer2_candidates = []
            for ledger in ledger_rows:
                if ledger["ledger_id"] in consumed_ledgers:
                    continue

                normalized_ref = ledger["normalized_ref"]
                normalized_narration = normalize_reference(statement["narration"])

                if (
                    amounts_match(statement["amount"], ledger["amount"])
                    and normalized_ref in normalized_narration
                ):
                    layer2_candidates.append(ledger)

            if len(layer2_candidates) == 1:
                ledger = layer2_candidates[0]
                results.append({
                    "stmt_id": statement["stmt_id"],
                    "ledger_id": ledger["ledger_id"],
                    "status": "MATCHED",
                    "method": "normalized_reference_amount"
                })
                consumed_ledgers.add(ledger["ledger_id"])
                consumed_stmts.add(statement["stmt_id"])
                matched = True
            elif len(layer2_candidates) > 1:
                unique_refs = set(l["normalized_ref"] for l in layer2_candidates)
                if len(unique_refs) == 1:
                    ledger = layer2_candidates[0]
                    results.append({
                        "stmt_id": statement["stmt_id"],
                        "ledger_id": ledger["ledger_id"],
                        "status": "MATCHED",
                        "method": "normalized_reference_amount"
                    })
                    consumed_ledgers.add(ledger["ledger_id"])
                    consumed_stmts.add(statement["stmt_id"])
                    matched = True
                else:
                    results.append({
                        "stmt_id": statement["stmt_id"],
                        "ledger_id": None,
                        "status": "UNMATCHED",
                        "method": "ambiguous_normalized_reference",
                        "rejected_candidates": layer2_candidates
                    })
                    consumed_stmts.add(statement["stmt_id"])
                    matched = True

        # Layer 3: Reference typo and exact amount
        if not matched:
            candidates = []
            stmt_tokens = [normalize_reference(t) for t in statement["narration"].split()]
            stmt_tokens = [t for t in stmt_tokens if t]

            for ledger in ledger_rows:
                if ledger["ledger_id"] in consumed_ledgers:
                    continue

                if amounts_match(statement["amount"], ledger["amount"]):
                    normalized_ledger_ref = ledger["normalized_ref"]

                    is_typo = False
                    for token in stmt_tokens:
                        if damerau_levenshtein_distance(token, normalized_ledger_ref) == 1:
                            is_typo = True
                            break

                    if is_typo:
                        candidates.append(ledger["ledger_id"])

            if len(candidates) == 1:
                results.append({
                    "stmt_id": statement["stmt_id"],
                    "ledger_id": candidates[0],
                    "status": "MATCHED",
                    "method": "reference_typo_amount"
                })
                consumed_ledgers.add(candidates[0])
                consumed_stmts.add(statement["stmt_id"])
                matched = True

        # Layer 4: Candidate scoring for reference-mismatch
        if not matched:
            scored_candidates = []
            for ledger in ledger_rows:
                if ledger["ledger_id"] in consumed_ledgers:
                    continue

                # Pre-requisite: exact amount
                if amounts_match(statement["amount"], ledger["amount"]):
                    score, evidence = score_candidate(statement, ledger)
                    scored_candidates.append((score, ledger["ledger_id"], evidence))

            if scored_candidates:
                scored_candidates.sort(key=lambda x: x[0], reverse=True)
                top_candidates_for_stmt[statement["stmt_id"]] = scored_candidates[:2]
                
                best_score, best_id, best_evidence = scored_candidates[0]

                THRESHOLD = 75.0
                GAP_REQUIRED = 15.0

                if best_score >= THRESHOLD:
                    has_identity = any(e.startswith('payer_') or e.startswith('ref_') or e == 'explicit_no_ref' for e in best_evidence)
                    if has_identity:
                        is_unambiguous = True
                        if len(scored_candidates) > 1:
                            second_best_score = scored_candidates[1][0]
                            if (best_score - second_best_score) < GAP_REQUIRED:
                                is_unambiguous = False

                        if is_unambiguous:
                            results.append({
                                "stmt_id": statement["stmt_id"],
                                "ledger_id": best_id,
                                "status": "MATCHED",
                                "method": "candidate_score"
                            })
                            consumed_ledgers.add(best_id)
                            consumed_stmts.add(statement["stmt_id"])
                            matched = True

                            # Print useful debug information
                            print(f"DEBUG (Layer 4): stmt={statement['stmt_id']} matched to ledger={best_id} with score={best_score:.1f}. Evidence: {', '.join(best_evidence)}")

    # Layer 5: Split Payment Matching
    unmatched_stmts = [s for s in statement_rows if s["stmt_id"] not in consumed_stmts]
    unmatched_ledgers = [l for l in ledger_rows if l["ledger_id"] not in consumed_ledgers]

    split_matches = match_splits(unmatched_stmts, unmatched_ledgers)

    for split_res in split_matches:
        if split_res.get("status") == "REVIEW_REQUIRED":
            for stmt_id in split_res["stmt_ids"]:
                results.append({
                    "stmt_id": stmt_id,
                    "ledger_id": None,
                    "status": "REVIEW_REQUIRED",
                    "method": "ambiguous_split_payment",
                    "rejected_candidates": []
                })
                consumed_stmts.add(stmt_id)
            # Do NOT consume the ledger
        else:
            ledger_id = split_res["ledger_id"]
            for stmt_id in split_res["stmt_ids"]:
                results.append({
                    "stmt_id": stmt_id,
                    "ledger_id": ledger_id,
                    "status": "MATCHED",
                    "method": "split_payment"
                })
                consumed_stmts.add(stmt_id)
            consumed_ledgers.add(ledger_id)

    # Layer 6: Fee Discrepancy Matching
    unmatched_stmts = [s for s in statement_rows if s["stmt_id"] not in consumed_stmts]
    unmatched_ledgers = [l for l in ledger_rows if l["ledger_id"] not in consumed_ledgers]

    fee_matches = match_fees(unmatched_stmts, unmatched_ledgers)

    for fee_res in fee_matches:
        results.append(fee_res)
        consumed_stmts.add(fee_res["stmt_id"])
        consumed_ledgers.add(fee_res["ledger_id"])

    # Finally, append UNMATCHED for anything remaining
    for statement in statement_rows:
        if statement["stmt_id"] not in consumed_stmts:
            cands = top_candidates_for_stmt.get(statement["stmt_id"], [])
            formatted_cands = [{"ledger_id": c[1], "score": c[0], "evidence": c[2]} for c in cands]
            results.append({
                "stmt_id": statement["stmt_id"],
                "ledger_id": None,
                "status": "UNMATCHED",
                "method": "no_exact_match",
                "rejected_candidates": formatted_cands
            })

    return results

if __name__ == "__main__":
    ledger = load_csv("data/ledger.csv")
    statement = load_csv("data/statement.csv")

    results = match_exact(statement, ledger)

    matched_count = sum(1 for r in results if r["status"] == "MATCHED")
    unmatched_count = sum(1 for r in results if r["status"] == "UNMATCHED")

    print(f"\nTotal statements: {len(results)}")
    print(f"Matched: {matched_count}")
    print(f"Unmatched: {unmatched_count}")

    print("\nFirst 10 results:")
    for result in results[:10]:
        print(result)
