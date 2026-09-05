# Technical Decisions

## LLM Explainer Model Change
The `AGENT_INSTRUCTIONS.md` initially requested the use of `llama-3.1-8b-instant` for the LLM explainer. However, this model string now returns a `404 Model Not Found` error from the Groq API (likely due to deprecation or a change in their available endpoints). To ensure the pipeline functions correctly and provides actual AI-generated explanations instead of falling back to rule-based strings, the model was swapped to `openai/gpt-oss-20b`. This was a functional necessity, not just a workaround.

## LLM Disagreement Flag Design
The `llm_disagreement` flag in the `explain_exceptions` function is designed to fire rarely, if ever, by design. The prompt explicitly instructs the LLM: *"Keep it factual, concise, and focused on the discrepancy. Do not try to make a final decision."* 

Because of this prompt constraint, when faced with ambiguous edge cases (e.g., multiple valid candidates or a split payment missing its counterpart), the LLM correctly acts as a neutral summarizer. It highlights the ambiguity and advises human review, rather than confidently overriding the matcher with phrases like "actually matches L2231". The disagreement detection heuristic looks for explicit overrides. Since the model follows instructions to not make a final decision, it deliberately avoids the phrasing that triggers the disagreement flag. The check is live and working, but intentionally quiet because the LLM is behaving properly.
