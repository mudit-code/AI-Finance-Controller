import streamlit as st
import pandas as pd
import random
import os
import sys
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv

def clean_explanation(text):
    if not isinstance(text, str):
        return str(text)
    
    jargon_map = {
        "confidence threshold": "certainty level",
        "no_exact_match": "no matching record",
        "ambiguous split payment": "unclear split payment",
        "ambiguous_exact_reference": "unclear exact reference",
        "candidate_score": "system score"
    }
    
    # 1. Replace jargon terms
    for k, v in jargon_map.items():
        text = text.replace(k, v)
        text = text.replace(k.title(), v.title())
        
    # 2. Strip ALL markdown bold/italic/code markers (*, **, _, __, `)
    text = re.sub(r'[*_`]+', '', text)
    
    return text.strip()


# Ensure src modules can be imported
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
load_dotenv()

from src.reconciliation.matcher import match_exact
from src.reconciliation.llm_explainer import explain_exceptions

st.set_page_config(page_title="AI Finance Controller", layout="wide")

st.title("AI Finance Controller - Generation Mode")
st.write("Sandbox mode for dataset generation and reconciliation.")

if "statements" not in st.session_state:
    st.session_state.statements = []
if "ledgers" not in st.session_state:
    st.session_state.ledgers = []
if "reconciliation_results" not in st.session_state:
    st.session_state.reconciliation_results = []
if "reconciliation_enriched" not in st.session_state:
    st.session_state.reconciliation_enriched = []

def generate_dataset():
    random.seed() # Genuinely random seed
    categories = [
        'exact_match', 'exact_match_diff_dateformat', 'typo_reference',
        'reference_mismatch_amount_match', 'split_payment', 'date_lag',
        'amount_discrepancy_fee', 'unmatched_orphan', 'currency_rounding_diff',
        'payer_suffix_variation'
    ]

    ledgers = []
    statements = []

    ledger_id_counter = 3000
    stmt_id_counter = 7000
    start_date = datetime(2023, 1, 1)

    def get_date():
        return start_date + timedelta(days=random.randint(0, 300))
    
    def format_date(dt):
        return dt.strftime('%Y-%m-%d')

    for category in categories:
        if category == 'unmatched_orphan':
            for _ in range(5):
                dt = get_date()
                amt = round(random.uniform(10, 500), 2)
                stmt_id = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                statements.append({'stmt_id': stmt_id, 'date': format_date(dt), 'amount': amt, 'narration': f"POS PUR {random.randint(1000, 9999)} UNKNOWN"})
            continue

        for _ in range(5):
            dt = get_date()
            base_amt = round(random.uniform(50, 1000), 2)
            l_id = f"L{ledger_id_counter}"
            ledger_id_counter += 1
            ref = f"INV-{random.randint(10000, 99999)}"
            payer = f"Customer_{random.randint(1, 100)}"
            
            ledgers.append({'ledger_id': l_id, 'date': format_date(dt), 'amount': base_amt, 'ref': ref, 'payer': payer})
            
            if category == 'exact_match':
                stmt_id = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                statements.append({'stmt_id': stmt_id, 'date': format_date(dt), 'amount': base_amt, 'narration': f"Transfer from {payer} Ref {ref}"})
            elif category == 'exact_match_diff_dateformat':
                stmt_id = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                diff_date = dt.strftime('%d/%m/%Y') if random.choice([True, False]) else dt.strftime('%d-%b-%Y')
                statements.append({'stmt_id': stmt_id, 'date': diff_date, 'amount': base_amt, 'narration': f"Payment Ref: {ref}"})
            elif category == 'typo_reference':
                stmt_id = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                ref_chars = list(ref)
                if len(ref_chars) > 2:
                    idx = random.randint(0, len(ref_chars) - 2)
                    ref_chars[idx], ref_chars[idx+1] = ref_chars[idx+1], ref_chars[idx]
                typo_ref = "".join(ref_chars)
                statements.append({'stmt_id': stmt_id, 'date': format_date(dt), 'amount': base_amt, 'narration': f"Payment Ref: {typo_ref}"})
            elif category == 'reference_mismatch_amount_match':
                stmt_id = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                statements.append({'stmt_id': stmt_id, 'date': format_date(dt), 'amount': base_amt, 'narration': "Generic Payment - No Ref Provided"})
            elif category == 'split_payment':
                part1 = round(base_amt * random.uniform(0.3, 0.7), 2)
                part2 = round(base_amt - part1, 2)
                stmt_id1 = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                statements.append({'stmt_id': stmt_id1, 'date': format_date(dt), 'amount': part1, 'narration': f"Split 1/2 for {ref}"})
                stmt_id2 = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                statements.append({'stmt_id': stmt_id2, 'date': format_date(dt), 'amount': part2, 'narration': f"Split 2/2 for {ref}"})
            elif category == 'date_lag':
                stmt_id = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                lag_days = random.randint(1, 5)
                lag_dt = dt + timedelta(days=lag_days)
                statements.append({'stmt_id': stmt_id, 'date': format_date(lag_dt), 'amount': base_amt, 'narration': f"Ref {ref} processed late"})
            elif category == 'amount_discrepancy_fee':
                stmt_id = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                fee = round(random.uniform(1.0, 5.0), 2)
                received_amt = round(base_amt - fee, 2)
                statements.append({'stmt_id': stmt_id, 'date': format_date(dt), 'amount': received_amt, 'narration': f"Payment {ref} minus processing fee"})
            elif category == 'currency_rounding_diff':
                stmt_id = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                diff = random.choice([-0.02, -0.01, 0.01, 0.02])
                received_amt = round(base_amt + diff, 2)
                statements.append({'stmt_id': stmt_id, 'date': format_date(dt), 'amount': received_amt, 'narration': f"Transfer {ref} {payer}"})
            elif category == 'payer_suffix_variation':
                stmt_id = f"S{stmt_id_counter}"
                stmt_id_counter += 1
                suffixes = [" LLC", " Inc.", " Pvt Ltd", " Corp"]
                var_payer = payer + random.choice(suffixes)
                statements.append({'stmt_id': stmt_id, 'date': format_date(dt), 'amount': base_amt, 'narration': f"Wire {ref} from {var_payer}"})

    for _ in range(5):
        dt = get_date()
        base_amt = round(random.uniform(50, 1000), 2)
        l_id = f"L{ledger_id_counter}"
        ledger_id_counter += 1
        ref = f"INV-{random.randint(10000, 99999)}"
        payer = f"Customer_{random.randint(1, 100)}"
        ledgers.append({'ledger_id': l_id, 'date': format_date(dt), 'amount': base_amt, 'ref': ref, 'payer': payer})

    random.shuffle(statements)
    random.shuffle(ledgers)

    return statements, ledgers

def map_status(s):
    if s == "MATCHED":
        return "Matched"
    return "Needs a quick look"

col1, col2 = st.columns(2)
with col1:
    if st.button("Generate New Dataset", type="primary"):
        stmts, ldgs = generate_dataset()
        st.session_state.statements = stmts
        st.session_state.ledgers = ldgs
        st.session_state.reconciliation_results = []
        st.session_state.reconciliation_enriched = []
        st.success(f"Generated {len(stmts)} statements and {len(ldgs)} ledgers.")

with col2:
    if st.button("Run Reconciliation", type="secondary"):
        if not st.session_state.statements:
            st.error("Generate a dataset first!")
        else:
            with st.spinner("Checking automatically..."):
                results = match_exact(st.session_state.statements, st.session_state.ledgers)
                st.session_state.reconciliation_results = results
            
            with st.spinner("Asking LLM for a quick look..."):
                enriched = explain_exceptions(st.session_state.statements, st.session_state.ledgers, results)
                st.session_state.reconciliation_enriched = enriched
            st.success("Reconciliation complete!")

if st.session_state.statements:
    with st.expander("View Dataset", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Statement Data")
            st.dataframe(pd.DataFrame(st.session_state.statements), use_container_width=True)
        with c2:
            st.subheader("Ledger Data")
            st.dataframe(pd.DataFrame(st.session_state.ledgers), use_container_width=True)

if st.session_state.reconciliation_enriched:
    enriched = st.session_state.reconciliation_enriched
    
    total = len(enriched)
    matched = sum(1 for r in enriched if r["status"] == "MATCHED")
    match_rate = round((matched / total) * 100) if total > 0 else 0
    
    st.header(f"{matched} out of {total} transactions checked automatically ({match_rate}% match rate)")
    
    table_data = []
    stmt_map = {s["stmt_id"]: s for s in st.session_state.statements}
    for r in enriched:
        amt = stmt_map[r["stmt_id"]]["amount"] if r["stmt_id"] in stmt_map else 0
        table_data.append({
            "Transaction": r["stmt_id"],
            "Status": map_status(r["status"]),
            "Amount": amt
        })
        
    st.dataframe(pd.DataFrame(table_data), use_container_width=True)
    
    st.subheader("Exceptions")
    exceptions = [r for r in enriched if r["status"] != "MATCHED"]
    
    if not exceptions:
        st.success("No exceptions found!")
    else:
        for exc in exceptions:
            is_disagreement = exc.get("llm_disagreement", False)
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.write(f"**Transaction:** {exc['stmt_id']} ({map_status(exc['status'])})")
                    explanation = exc.get('llm_explanation', 'No explanation provided.')
                    explanation = clean_explanation(explanation)
                    st.write(f"**Here's why:** {explanation}")
                with c2:
                    if is_disagreement:
                        st.info("Found a match")
                        st.write(f"**Suggested:** {exc.get('suggested_ledger_id')}")

st.divider()

st.header("Showcase: Ambiguous Cases")
if st.button("Run Ambiguous Cases Showcase"):
    with st.spinner("Running showcase cases..."):
        try:
            from tests.test_adversarial import adversarial_cases
            from src.reconciliation.matcher import match_exact
            from src.reconciliation.llm_explainer import explain_exceptions
            
            target_names = ["4.", "7.", "18."]
            sh_stmts, sh_ledgers = [], []
            for case in adversarial_cases:
                if any(case["name"].startswith(n) for n in target_names):
                    sh_stmts.extend(case["statements"])
                    sh_ledgers.extend(case["ledgers"])
            
            sh_results = match_exact(sh_stmts, sh_ledgers)
            sh_enriched = explain_exceptions(sh_stmts, sh_ledgers, sh_results)
            sh_exceptions = [r for r in sh_enriched if r["status"] in ["UNMATCHED", "REVIEW_REQUIRED"]]
            
            if not sh_exceptions:
                st.info("No exceptions found in showcase.")
            else:
                for exc in sh_exceptions:
                    is_disagreement = exc.get("llm_disagreement", False)
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            st.write(f"**Transaction:** {exc['stmt_id']} ({map_status(exc['status'])})")
                            
                            explanation = exc.get('llm_explanation', 'No explanation provided.')
                            explanation = clean_explanation(explanation)
                            st.write(f"**Here's why:** {explanation}")
                        with c2:
                            if is_disagreement:
                                st.info("Found a match")
                                st.write(f"**Suggested:** {exc.get('suggested_ledger_id')}")
        except Exception as e:
            st.error(f"Failed to run showcase: {e}")
