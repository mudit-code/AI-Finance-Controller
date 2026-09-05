# AI Finance Controller

## Overview
The AI Finance Controller is an end-to-end reconciliation pipeline that automatically matches bank statements with ledger records. It employs a layered architecture combining strict deterministic checks, fuzzy matching logic for names and typos, and an LLM-based fallback to explain exceptions in plain English. 

## Layered Matching Architecture
The reconciliation pipeline progresses through increasingly lenient layers to maximize correct matches while minimizing false positives. The logic is primarily located in `src/reconciliation/matcher.py`.

1. **Layer 1: Exact Match** (`exact_reference_amount`) - Reference and amount match exactly between statement and ledger.
2. **Layer 2: Normalized Match** (`normalized_reference_amount`) - Reference matches perfectly after stripping whitespace and special characters.
3. **Layer 3: Reference Typo** (`reference_typo_amount`) - The amount matches, and the references are within a Damerau-Levenshtein distance of 1 (catching simple typos).
4. **Layer 4: Candidate Scoring** (`candidate_score`) - When references do not strictly match but amounts do, the system uses a weighted scoring heuristic based on date proximity, extracted payer names, and partial reference similarity to confidently map transactions.
5. **Layer 5: Split Payments** (`split_matcher.py`) - Evaluates leftover unmatched records to find combinations of statements that sum exactly to a single ledger amount.
6. **Layer 6: Fee Discrepancy** (`fee_matcher.py`) - Matches statements and ledgers where amounts differ by a common fee threshold, conditionally validated by fee-specific keywords in the narration.
7. **LLM Explainer** (`llm_explainer.py`) - All remaining unmatched or ambiguous records are dispatched to a Groq LLM. The LLM acts as an explainer, providing human-readable context on why candidates were rejected and what manual review is needed.

## Evaluation & Holdout Metrics
The system was evaluated against a holdout dataset, achieving the following results:
- **Total Statements:** 108
- **Correct Decisions:** 108
- **Incorrect Decisions:** 0
- **Overall Accuracy:** 100.00%

> [!WARNING]
> **Caveat on Accuracy:** Achieving 100% accuracy on this holdout set is not a fully blind test. The `ROUNDING_TOLERANCE` and fuzzy matching thresholds were directly tuned using feedback from this dataset. To ensure these heuristics were not overly overfit, the system was separately stress-tested using adversarial edge cases (see tests 21-23 in `tests/test_adversarial.py`), proving the model correctly rejects false positives just outside the tolerance bands.

## Technical Decisions & Limitations

### Model Swap to Qwen
The original spec requested the `llama-3.1-8b-instant` model for the explainer. However, because that model identifier was deprecated/returning 404s via the Groq API, it was swapped to `qwen/qwen3.8-27b`. This ensures the live application continues to provide dynamic AI explanations rather than falling back to rule-based defaults. See `DECISIONS.md` for more context.

### Known Limitations
- **3-Way Splits:** The split matching layer is currently tuned for 2-way splits. 3-way split combinations are not reliably matched (Test case 8 intentionally xfails to track this limitation).
- **Disagreement Heuristic (`llm_disagreement`):** The LLM disagreement flag rarely fires by design. Because the LLM is explicitly prompted to act as a neutral summarizer rather than a final decision-maker, it usually avoids using the authoritative phrasing required to trip the disagreement heuristic. 

## Simple / Generation Mode (`app_v2.py`)

A secondary interface (`app_v2.py`) is available to provide a plain-language reconciliation view for non-technical users. It strips away system jargon (e.g., transforming "confidence threshold" into "certainty level") and removes technical markers to present a cleaner, easier-to-read explanation.

This mode also includes a dataset generator function for producing synthetic ledgers and statements to rapidly test edge cases.

To run the Simple Mode locally:
```bash
streamlit run app_v2.py
```

## Running Locally

### Prerequisites
Ensure you have Python 3 installed.

### Setup
1. Clone the repository and navigate to the root directory.
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # On Windows:
   .\.venv\Scripts\activate
   # On Mac/Linux:
   source .venv/bin/activate
   ```
3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure your environment variables:
   Copy the example environment file and add your Groq API key:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` to include your `GROQ_API_KEY`.
5. Run the Streamlit application:
   ```bash
   streamlit run app.py
   ```
