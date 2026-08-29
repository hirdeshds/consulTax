"""Tax findings explanation generator using Groq/Cohere REST APIs with offline fallback."""

import json
from app.config import settings
from app.schemas.api import AnalyzeResponse
from app.explanation.prompts import SYSTEM_EXPLANATION_PROMPT, USER_EXPLANATION_TEMPLATE


def get_local_fallback_explanation(analysis: AnalyzeResponse, lang: str = "en") -> str:
    """Generate a clean, structured tax explanation in pure Python for offline/fallback cases."""
    profile = analysis.tax_profile
    is_hindi = lang.lower() == "hi"
    
    rec_regime = (analysis.recommended_regime.value if analysis.recommended_regime else "new").upper()
    savings = analysis.potential_savings or 0.0
    
    if is_hindi:
        heading = "कर विश्लेषण सारांश"
        regime_rec = f"अनुशंसित व्यवस्था: {rec_regime}"
        savings_text = f"संभावित बचत: ₹{savings:,.2f}"
        
        applied_list = []
        for r in analysis.applied_rules:
            if r.is_applicable and r.is_eligible:
                applied_list.append(f"- {r.rule_name}: दावा किया गया ₹{r.claimed_amount:,.2f}, योग्य ₹{r.eligible_amount:,.2f}")
        applied_str = "\n".join(applied_list) if applied_list else "कोई नहीं"
        
        desc = (
            f"आपके वित्तीय विवरण के आधार पर, **{rec_regime}** व्यवस्था अधिक उपयुक्त है। "
            f"इससे आप ₹{savings:,.2f} की टैक्स बचत कर सकते हैं।\n\n"
            f"**विवरण:**\n"
            f"- सकल कुल आय (Gross Income): ₹{profile.gross_total_income:,.2f}\n"
            f"- कुल स्वीकृत कटौतियां (Deductions): ₹{profile.total_deductions:,.2f}\n"
            f"- कुल कर योग्य आय (Taxable Income): ₹{profile.net_taxable_income:,.2f}\n"
            f"- शुद्ध टैक्स देयता (Tax Liability): ₹{profile.total_tax_liability:,.2f}\n\n"
            f"**लागू नियम व कटौतियां:**\n{applied_str}"
        )
    else:
        heading = "Tax Analysis Explanation"
        regime_rec = f"Recommended Regime: {rec_regime}"
        savings_text = f"Potential Savings: ₹{savings:,.2f}"
        
        applied_list = []
        for r in analysis.applied_rules:
            if r.is_applicable and r.is_eligible:
                applied_list.append(f"- {r.rule_name}: Claimed ₹{r.claimed_amount:,.2f}, Eligible ₹{r.eligible_amount:,.2f}")
        applied_str = "\n".join(applied_list) if applied_list else "None"
        
        desc = (
            f"Based on your tax profile details, the **{rec_regime}** tax regime is recommended because it minimizes your tax liability. "
            f"By choosing this regime, your potential tax savings is **₹{savings:,.2f}** compared to the other regime.\n\n"
            f"**Financial Summary:**\n"
            f"- Gross Total Income: ₹{profile.gross_total_income:,.2f}\n"
            f"- Total Deductions: ₹{profile.total_deductions:,.2f}\n"
            f"- Net Taxable Income: ₹{profile.net_taxable_income:,.2f}\n"
            f"- Total Tax Liability: ₹{profile.total_tax_liability:,.2f}\n\n"
            f"**Deductions Applied:**\n{applied_str}"
        )
        
    return f"### {heading}\n\n**{regime_rec}**\n**{savings_text}**\n\n{desc}"


def generate_explanation(
    analysis: AnalyzeResponse,
    preferred_language: str = "en"
) -> str:
    """
    Generates a natural language explanation of tax analysis findings.
    Queries Groq or Cohere REST endpoints, falling back to local description if offline.
    """
    profile = analysis.tax_profile
    if not profile:
        return "No tax profile data available for explanation."
        
    applied_rules_list = []
    for rule in analysis.applied_rules:
        if rule.is_applicable and rule.is_eligible:
            sect = f" ({rule.legal_section})" if rule.legal_section else ""
            applied_rules_list.append(
                f"- {rule.rule_name}{sect}: Claimed ₹{rule.claimed_amount:,.2f}, "
                f"Eligible ₹{rule.eligible_amount:,.2f}. Limit: ₹{rule.max_limit or 'N/A'}"
            )
    applied_rules_str = "\n".join(applied_rules_list) if applied_rules_list else "None."
    
    tips_str = "\n".join(f"- {tip}" for tip in analysis.optimization_tips) if analysis.optimization_tips else "No specific tips."
    
    user_content = USER_EXPLANATION_TEMPLATE.format(
        financial_year=profile.financial_year,
        recommended_regime=analysis.recommended_regime.value if analysis.recommended_regime else "new",
        old_liability=analysis.old_regime_liability or 0.0,
        new_liability=analysis.new_regime_liability or 0.0,
        savings=analysis.potential_savings or 0.0,
        gross_income=profile.gross_total_income,
        salary=profile.income.salary,
        house_property=profile.income.house_property,
        capital_gains=profile.income.capital_gains_short_term + profile.income.capital_gains_long_term,
        business=profile.income.business_profession,
        other=profile.income.other_sources,
        applied_rules_str=applied_rules_str,
        tips_str=tips_str
    )
    
    system_prompt = SYSTEM_EXPLANATION_PROMPT
    if preferred_language.lower() == "hi":
        system_prompt += "\nRespond in Hindi (using Hindi script or clear professional language)."
        
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
    
    # Import REST helpers from answer_generator
    from app.qa.answer_generator import call_groq_rest, call_cohere_rest
    
    # Try Groq
    if settings.GROQ_API_KEY:
        try:
            response = call_groq_rest(messages, stream=False)
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["choices"][0]["message"]["content"]
        except Exception:
            if not settings.COHERE_API_KEY:
                return get_local_fallback_explanation(analysis, preferred_language)
                
    # Try Cohere Fallback
    if settings.COHERE_API_KEY:
        try:
            response = call_cohere_rest(messages, stream=False)
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["message"]["content"][0]["text"]
        except Exception:
            pass
            
    # Mock fallback description
    return get_local_fallback_explanation(analysis, preferred_language)
