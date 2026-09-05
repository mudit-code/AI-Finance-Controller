import streamlit as st
import pandas as pd
import json
import os
from dotenv import load_dotenv
import sys

# Ensure src modules can be imported
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.reconciliation.matcher import load_csv, match_exact
from src.reconciliation.llm_explainer import explain_exceptions
from src.evaluation.metrics_holdout import evaluate
from src.reconciliation.utils import clean_llm_text

st.set_page_config(page_title="AI Finance Controller", layout="wide")

load_dotenv()
API_KEY = os.environ.get("GROQ_API_KEY")

CACHE_FILE = "precomputed_results.json"

st.title("AI Finance Controller")
st.write("End-to-end deterministic + fuzzy + LLM reconciliation pipeline.")

if not API_KEY:
    st.warning("⚠️ **GROQ_API_KEY not found in environment.** LLM Explainer will run in offline/rule-based mode.")

def run_full_pipeline(live=False):
    statements = load_csv("data/holdout_statement.csv")
    ledgers = load_csv("data/holdout_ledger.csv")
    ground_truth = load_csv("data/holdout_ground_truth.csv")

    with st.spinner("Running match_exact() (Deterministic/Fuzzy matching layers)..."):
        matcher_results = match_exact(statements, ledgers)

    with st.spinner("Running explain_exceptions() (LLM Explainer)..."):
        # We process all exceptions in the holdout
        enriched_results = explain_exceptions(statements, ledgers, matcher_results)

    with st.spinner("Calculating metrics..."):
        metrics = evaluate(enriched_results, ground_truth)

    return {
        "results": enriched_results,
        "metrics": metrics
    }

# Initialization
if "pipeline_data" not in st.session_state:
    st.session_state.pipeline_data = None

# Action Bar
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("Run Reconciliation Live", type="primary"):
        st.session_state.pipeline_data = run_full_pipeline(live=True)
        # Save to cache
        with open(CACHE_FILE, "w") as f:
            json.dump(st.session_state.pipeline_data, f)
        st.success("Live pipeline executed and results cached!")

# Try loading from cache if not yet in state
if st.session_state.pipeline_data is None:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            st.session_state.pipeline_data = json.load(f)
        st.info("Loaded pre-computed results. Click 'Run Reconciliation Live' to re-run the pipeline.")
    else:
        st.info("No pre-computed results found. Click 'Run Reconciliation Live' to start.")

# Main Dashboard
if st.session_state.pipeline_data:
    data = st.session_state.pipeline_data
    results = data["results"]
    metrics = data["metrics"]

    st.header("Metrics Summary")
    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric("Overall Accuracy", f"{metrics['accuracy']:.2f}%")
    m_col2.metric("Total Statements", metrics['total'])
    m_col3.metric("Correct Decisions", metrics['correct'])

    with st.expander("View Category-by-Category Breakdown", expanded=False):
        cat_stats = metrics["category_stats"]
        cat_rows = []
        for cat, stats in cat_stats.items():
            acc = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
            cat_rows.append({"Category": cat, "Total": stats["total"], "Correct": stats["correct"], "Accuracy (%)": f"{acc:.2f}%"})
        st.table(pd.DataFrame(cat_rows))

    st.header("Results")
    
    # Process results for table
    table_data = []
    for r in results:
        # Confidence score check
        confidence = r.get("confidence", "N/A")
        if isinstance(confidence, float):
            confidence = f"{confidence:.1f}"
        
        table_data.append({
            "Statement ID": r["stmt_id"],
            "Matched Ledger ID": r.get("ledger_id") or "—",
            "Status": r["status"],
            "Method": r["method"],
            "Confidence": confidence
        })
    df_results = pd.DataFrame(table_data)
    st.dataframe(df_results, use_container_width=True)

    st.header("Exceptions & LLM Explanations")
    exceptions = [r for r in results if r["status"] in ["UNMATCHED", "REVIEW_REQUIRED"]]
    
    if not exceptions:
        st.success("No exceptions found!")
    else:
        for exc in exceptions:
            is_disagreement = exc.get("llm_disagreement", False)
            border_color = "red" if is_disagreement else "gray"
            
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.subheader(f"Statement: {exc['stmt_id']} ({exc['status']})")
                    st.write(f"**Matcher Reason:** {exc['method']}")
                    explanation = exc.get('llm_explanation', 'No explanation provided.')
                    explanation = clean_llm_text(explanation)
                    st.write(f"**LLM Explanation:** {explanation}")
                with c2:
                    if is_disagreement:
                        st.error("⚠️ LLM Disagrees with Matcher")
                        st.write(f"**Suggested:** {exc.get('suggested_ledger_id')}")
                    else:
                        st.success("No Disagreement")

    st.divider()
    st.header("Showcase: Ambiguous Cases")
    st.write("Curated examples of ambiguous scenarios with multiple rejected candidates to showcase LLM grounding. *Note: These are separate from the holdout metrics.*")
    
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
                                st.subheader(f"Statement: {exc['stmt_id']} ({exc['status']})")
                                st.write(f"**Matcher Reason:** {exc['method']}")
                                cands = exc.get("rejected_candidates", [])
                                st.write(f"**Rejected Candidates Count:** {len(cands)}")
                                
                                explanation = exc.get('llm_explanation', 'No explanation provided.')
                                explanation = clean_llm_text(explanation)
                                st.write(f"**LLM Explanation:** {explanation}")
                            with c2:
                                if is_disagreement:
                                    st.error("⚠️ LLM Disagrees")
                                    st.write(f"**Suggested:** {exc.get('suggested_ledger_id')}")
                                else:
                                    st.success("No Disagreement")
            except Exception as e:
                st.error(f"Failed to run showcase: {e}")
