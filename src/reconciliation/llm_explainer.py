import copy
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

def explain_exceptions(statement_rows, ledger_rows, results, limit=None):
    """
    Enriches exception results with LLM-generated explanations for why they didn't match.
    Returns a new list of results (deep copy) rather than mutating in place.
    """
    new_results = copy.deepcopy(results)
    
    # Extract only exceptions (UNMATCHED or REVIEW_REQUIRED)
    exceptions = [r for r in new_results if r.get("status") in ["UNMATCHED", "REVIEW_REQUIRED"]]
    
    if limit is not None:
        exceptions = exceptions[:limit]
        
    # First try Streamlit secrets, then fall back to os.environ
    api_key = None
    try:
        import streamlit as st
        if "GROQ_API_KEY" in st.secrets:
            api_key = st.secrets["GROQ_API_KEY"]
    except Exception:
        pass
        
    if not api_key:
        api_key = os.environ.get("GROQ_API_KEY")
        
    if not api_key:
        print("Warning: GROQ_API_KEY not found. Skipping LLM explanations.")
        for ext in exceptions:
            ext["llm_explanation"] = f"Key Missing (Rule-based: {ext.get('method')})"
            ext["llm_disagreement"] = False
        return new_results

    try:
        client = Groq(api_key=api_key)
    except Exception as e:
        print(f"Warning: Failed to initialize Groq client: {e}")
        import traceback
        traceback.print_exc()
        for ext in exceptions:
            ext["llm_explanation"] = f"Client Init Error: {type(e).__name__}: {str(e)}"
            ext["llm_disagreement"] = False
        return new_results

    # Pre-index statements and ledgers for quick lookup
    stmt_map = {s["stmt_id"]: s for s in statement_rows}
    ledger_map = {l["ledger_id"]: l for l in ledger_rows}
    
    for exc in exceptions:
        stmt = stmt_map.get(exc["stmt_id"])
        if not stmt:
            continue
            
        method = exc.get("method", "unknown")
        rejected_cands = exc.get("rejected_candidates", [])
        
        prompt = f"""
You are an AI assistant helping a human review a financial reconciliation exception.
A bank statement transaction failed to automatically match to any ledger transaction.
The rule-based matcher marked it as: {method}

Statement Transaction:
- Narration: {stmt['narration']}
- Amount: {stmt['amount']}
- Date: {stmt['date']}

Rejected Candidates considered by the matcher:
"""
        if rejected_cands:
            for i, cand in enumerate(rejected_cands):
                if isinstance(cand, dict) and "ledger_id" in cand:
                    lid = cand["ledger_id"]
                    score = cand.get("score", "N/A")
                    evidence = cand.get("evidence", "N/A")
                    
                    # Look up the actual ledger row to get ref and other details
                    l_row = ledger_map.get(lid, {})
                    ref = l_row.get("ref", "N/A")
                    amt = l_row.get("amount", "N/A")
                    
                    prompt += f"Candidate {i+1}: ID={lid}, Amount={amt}, Score={score}, Evidence={evidence}, Ref={ref}\n"
                else:
                    prompt += f"Candidate {i+1}: {cand}\n"
        else:
            prompt += "None considered strong enough to list.\n"
            
        prompt += """
Write a 1-2 sentence explanation of why this is an exception and what a human reviewer should check.
Keep it factual, concise, and focused on the discrepancy. Do not try to make a final decision.
"""
        try:
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="openai/gpt-oss-20b",
                temperature=0.0
            )
            explanation = chat_completion.choices[0].message.content.strip()
            exc["llm_explanation"] = explanation
            
            # Simple heuristic for disagreement
            disagreement = False
            suggested_ledger_id = None
            lower_exp = explanation.lower()
            if "actually matches" in lower_exp or "likely corresponds to" in lower_exp or "better match" in lower_exp or "should match" in lower_exp:
                for cand in rejected_cands:
                    if isinstance(cand, dict) and "ledger_id" in cand:
                        lid = cand["ledger_id"]
                        if lid.lower() in lower_exp:
                            disagreement = True
                            suggested_ledger_id = lid
                            break
            
            exc["llm_disagreement"] = disagreement
            if disagreement:
                exc["suggested_ledger_id"] = suggested_ledger_id
                
        except Exception as e:
            print(f"Warning: Groq API call failed for {exc['stmt_id']}: {e}")
            import traceback
            traceback.print_exc()
            exc["llm_explanation"] = f"API Error: {type(e).__name__}: {str(e)} (Rule-based: {method})"
            exc["llm_disagreement"] = False

    return new_results
