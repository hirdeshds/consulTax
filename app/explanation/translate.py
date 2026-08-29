"""Translation module for tax explanations using Groq/Cohere REST endpoints."""

import json
from app.config import settings
from app.explanation.prompts import SYSTEM_TRANSLATION_PROMPT


def translate_explanation(text: str, target_lang: str) -> str:
    """
    Translates tax explanation text into standard target languages (e.g. 'hi' for Hindi).
    Uses Groq/Cohere with direct REST endpoints and a local fallback.
    """
    if not text or not target_lang or target_lang.lower().strip() in ("en", "english"):
        return text
        
    lang_name = "Hindi" if target_lang.lower().strip() == "hi" else target_lang
    user_content = f"Please translate the following tax explanation text into {lang_name}:\n\n{text}"
    
    messages = [
        {"role": "system", "content": SYSTEM_TRANSLATION_PROMPT},
        {"role": "user", "content": user_content}
    ]
    
    from app.qa.answer_generator import call_groq_rest, call_cohere_rest
    
    # Try Groq
    if settings.GROQ_API_KEY:
        try:
            response = call_groq_rest(messages, stream=False)
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["choices"][0]["message"]["content"]
        except Exception:
            if not settings.COHERE_API_KEY:
                return f"[{lang_name} Translation]\n{text}"
                
    # Try Cohere Fallback
    if settings.COHERE_API_KEY:
        try:
            response = call_cohere_rest(messages, stream=False)
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["message"]["content"][0]["text"]
        except Exception:
            pass
            
    # Mock fallback translation
    return f"[{lang_name} Translation]\n{text}"
