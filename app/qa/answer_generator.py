"""LLM response generation module using standard library urllib to query Groq and Cohere REST APIs."""

import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional, Generator

from app.config import settings
from app.schemas.api import ChatMessage
from app.schemas.domain import TaxProfile
from app.qa.retrieval import DocumentChunk


def build_system_and_user_prompts(
    query: str,
    retrieved_chunks: List[DocumentChunk],
    preferred_language: str,
    tax_profile: Optional[TaxProfile] = None
) -> tuple[str, str]:
    """Formats retrieved contexts and user tax profile into system and user prompts."""
    
    # 1. Format Context Snippets
    context_str = ""
    for i, chunk in enumerate(retrieved_chunks):
        title = chunk.source_title
        section = chunk.source_section or "General"
        snippet = chunk.snippet
        context_str += f"\n--- Context {i+1} ---\nSource: {title} - {section}\n{snippet}\n"
        
    # 2. Format Tax Profile details if available
    profile_str = "None provided."
    if tax_profile:
        income = tax_profile.income
        deductions = tax_profile.deductions
        profile_str = (
            f"Financial Year: {tax_profile.financial_year}\n"
            f"Age: {tax_profile.age or 'Not specified'}\n"
            f"Senior Citizen: {'Yes' if tax_profile.is_senior_citizen else 'No'}\n"
            f"Super Senior Citizen: {'Yes' if tax_profile.is_super_senior_citizen else 'No'}\n"
            f"Regime Preference: {tax_profile.regime_preference.value}\n"
            f"Income Details:\n"
            f"  - Salary: ₹{income.salary:,.2f}\n"
            f"  - House Property: ₹{income.house_property:,.2f}\n"
            f"  - Capital Gains (ST): ₹{income.capital_gains_short_term:,.2f}\n"
            f"  - Capital Gains (LT): ₹{income.capital_gains_long_term:,.2f}\n"
            f"  - Business/Profession: ₹{income.business_profession:,.2f}\n"
            f"  - Other Sources: ₹{income.other_sources:,.2f}\n"
            f"Deductions/Exemptions Claimed:\n"
            f"  - Section 80C: ₹{deductions.section_80c:,.2f}\n"
            f"  - Section 80D: ₹{deductions.section_80d:,.2f}\n"
            f"  - Section 80CCD(1B): ₹{deductions.section_80ccd_1b:,.2f}\n"
            f"  - Section 80CCD(2): ₹{deductions.section_80ccd_2:,.2f}\n"
            f"  - Section 24(b) Home Loan Interest: ₹{deductions.section_24b:,.2f}\n"
            f"  - HRA Exemption: ₹{deductions.hra_exemption:,.2f}\n"
        )
        
    language_instr = "English" if preferred_language.lower() != "hi" else "Hindi (using Hindi script or clear professional language)"
    
    system_prompt = (
        "You are an expert tax assistant for consulTax, a specialized tax optimization platform.\n"
        "Your goal is to provide accurate, helpful, and grounded advice on Indian income tax queries.\n\n"
        f"You must respond in: {language_instr}.\n\n"
        "Guidelines:\n"
        "1. Strictly use the provided Context Snippets to base your tax facts. Do not make up limits or rules.\n"
        "2. If the user's query cannot be answered using the provided context, state that clearly but offer a general helpful guideline if possible.\n"
        "3. Incorporate the user's Tax Profile details (if provided) to personalize the response (e.g. check their preferred regime, age, or claimed deductions).\n"
        "4. Be professional, structured, and cite sections (e.g., Section 80C, Section 80D) clearly.\n"
        "5. Keep responses concise and easy to read. Use bullet points where appropriate.\n"
    )
    
    user_content = (
        f"CONTEXT SNIPPETS:\n{context_str}\n"
        f"USER TAX PROFILE:\n{profile_str}\n\n"
        f"USER QUERY: {query}"
    )
    
    return system_prompt, user_content


def call_groq_rest(messages: List[Dict[str, str]], stream: bool = False) -> Any:
    """Helper to query Groq chat completion API using standard urllib POST request."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": settings.GROQ_MODEL,
        "messages": messages,
        "stream": stream
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    
    try:
        response = urllib.request.urlopen(req)
        return response
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        raise RuntimeError(f"Groq API returned HTTP {e.code}: {err_msg}")
    except Exception as e:
        raise RuntimeError(f"Groq API connection failed: {str(e)}")


def call_cohere_rest(messages: List[Dict[str, str]], stream: bool = False) -> Any:
    """Helper to query Cohere chat V2 API using standard urllib POST request."""
    url = "https://api.cohere.com/v2/chat"
    headers = {
        "Authorization": f"Bearer {settings.COHERE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Map messages to Cohere format
    cohere_messages = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role in ("system", "user", "assistant"):
            cohere_messages.append({"role": role, "content": content})
        else:
            cohere_messages.append({"role": "assistant", "content": content})
            
    payload = {
        "model": settings.COHERE_MODEL,
        "messages": cohere_messages,
        "stream": stream
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    
    try:
        response = urllib.request.urlopen(req)
        return response
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        raise RuntimeError(f"Cohere API returned HTTP {e.code}: {err_msg}")
    except Exception as e:
        raise RuntimeError(f"Cohere API connection failed: {str(e)}")


def generate_answer(
    query: str,
    retrieved_chunks: List[DocumentChunk],
    history: List[ChatMessage],
    preferred_language: str = "en",
    tax_profile: Optional[TaxProfile] = None
) -> str:
    """
    Generates a complete response from the LLM based on context, history, and profile.
    Tries Groq API first, falling back to Cohere API.
    """
    system_prompt, user_content = build_system_and_user_prompts(
        query=query,
        retrieved_chunks=retrieved_chunks,
        preferred_language=preferred_language,
        tax_profile=tax_profile
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_content})
    
    # 1. Try Groq
    if settings.GROQ_API_KEY:
        try:
            response = call_groq_rest(messages, stream=False)
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["choices"][0]["message"]["content"]
        except Exception as e:
            if not settings.COHERE_API_KEY:
                raise e
                
    # 2. Try Cohere Fallback
    if settings.COHERE_API_KEY:
        response = call_cohere_rest(messages, stream=False)
        res_data = json.loads(response.read().decode("utf-8"))
        # Cohere V2 response structure: message.content[0].text
        return res_data["message"]["content"][0]["text"]
        
    raise ValueError("No LLM API keys configured in settings.")


def generate_answer_stream(
    query: str,
    retrieved_chunks: List[DocumentChunk],
    history: List[ChatMessage],
    preferred_language: str = "en",
    tax_profile: Optional[TaxProfile] = None
) -> Generator[str, None, None]:
    """
    Generates a streaming response (token by token) from the LLM.
    Tries Groq API first, falling back to Cohere API.
    """
    system_prompt, user_content = build_system_and_user_prompts(
        query=query,
        retrieved_chunks=retrieved_chunks,
        preferred_language=preferred_language,
        tax_profile=tax_profile
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_content})
    
    # 1. Try Groq Streaming
    if settings.GROQ_API_KEY:
        try:
            response = call_groq_rest(messages, stream=True)
            try:
                for line in response:
                    line_str = line.decode("utf-8").strip()
                    if not line_str:
                        continue
                    if line_str == "data: [DONE]":
                        break
                    if line_str.startswith("data: "):
                        try:
                            data_json = json.loads(line_str[6:])
                            delta = data_json["choices"][0]["delta"]
                            if "content" in delta:
                                yield delta["content"]
                        except Exception:
                            pass
            finally:
                response.close()
            return
        except Exception as e:
            if not settings.COHERE_API_KEY:
                raise e
                
    # 2. Try Cohere Streaming Fallback
    if settings.COHERE_API_KEY:
        response = call_cohere_rest(messages, stream=True)
        try:
            for line in response:
                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue
                if line_str.startswith("data: "):
                    try:
                        data_json = json.loads(line_str[6:])
                        # Cohere v2 content-delta structure
                        if data_json.get("type") == "content-delta":
                            text = data_json["delta"]["message"]["content"]["text"]
                            yield text
                    except Exception:
                        pass
        finally:
            response.close()
        return
        
    raise ValueError("No LLM API keys configured in settings.")
