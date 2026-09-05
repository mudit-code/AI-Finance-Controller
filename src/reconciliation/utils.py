import re

def clean_llm_text(text: str) -> str:
    if not isinstance(text, str):
        return str(text)
        
    # 1. Apply jargon replacement FIRST so terms with underscores aren't broken
    jargon_map = {
        "confidence threshold": "certainty level",
        "no_exact_match": "no matching record",
        "ambiguous split payment": "unclear split payment",
        "ambiguous_exact_reference": "unclear exact reference",
        "candidate_score": "system score"
    }
    
    for k, v in jargon_map.items():
        text = text.replace(k, v)
        text = text.replace(k.title(), v.title())
        
    # 2. Escape dollar signs to prevent LaTeX math rendering in Streamlit
    text = text.replace('$', r'\$')
        
    # 3. Strip markdown formatting characters: `, *, _, ~, |
    text = re.sub(r'[`\*_~\|]+', '', text)
    
    # 4. Collapse any resulting double-spaces
    text = re.sub(r' {2,}', ' ', text)
        
    return text.strip()
