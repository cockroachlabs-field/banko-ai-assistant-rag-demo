"""Single source of truth for the Banko RAG prompt.

Every provider's RAG path used to ship its own near-identical f-string with the
text `"Provide helpful insights with numbers, markdown formatting, and
actionable advice."`. That hint was weak — chat models obeyed it with very
different enthusiasm, so the same query against watsonx could come back as a
markdown table on `openai/gpt-oss-120b` and as a flat bullet list on a less
expressive model. Demos were inconsistent across the provider switcher.

This helper centralizes the prompt and enforces explicit section headers so the
output shape stays stable regardless of which model is selected.
"""
from __future__ import annotations

# Map of language codes used by the chat UI to the human-readable names we put
# in the prompt. Keys cover what `/api/language` exposes today.
_LANGUAGE_NAMES = {
    "es-ES": "Spanish",
    "fr-FR": "French",
    "de-DE": "German",
    "it-IT": "Italian",
    "pt-PT": "Portuguese",
    "ja-JP": "Japanese",
    "ko-KR": "Korean",
    "zh-CN": "Chinese",
    "hi-IN": "Hindi",
}


def _resolve_language_instruction(language: str | None) -> str:
    """Return the trailing language clause, or empty string for English."""
    if not language:
        return ""
    norm = language.strip()
    if norm in ("", "en", "en-US", "English"):
        return ""
    name = _LANGUAGE_NAMES.get(norm, norm)
    return f" Respond entirely in {name}."


def build_banko_rag_prompt(
    question: str,
    expense_data: str,
    budget_recommendations: str = "",
    language: str | None = "en",
) -> str:
    """Build the prompt that gets sent to every chat model in the RAG path.

    The template enforces three named sections so different models produce the
    same shape on the same data — important because users switch providers
    mid-demo and expect consistent output.
    """
    language_instruction = _resolve_language_instruction(language)
    recommendations_block = budget_recommendations.strip() or "(none)"

    return f"""You are Banko, a friendly financial assistant inside a banking app demo. Answer the user's question using ONLY the expense data provided. Format your reply as GitHub-flavored markdown with this exact structure:

## 💡 Quick Answer
One or two sentences that directly answer the question and cite the key dollar amount(s).

## 📊 Breakdown
A short markdown table (preferred) or bulleted list of the relevant transactions or category totals. Use **bold** for dollar amounts and merchant names.

## 🎯 Recommendations
Two to four short, actionable suggestions tied to the spending shown. Start each bullet with a **bold** action verb.

User question: {question}

Expense data:
{expense_data}

Pre-computed insights:
{recommendations_block}

Rules:
- Use the exact section headers above (## 💡 Quick Answer, ## 📊 Breakdown, ## 🎯 Recommendations) — do not rename or skip them.
- Cite specific dollar amounts from the data above; never invent transactions or merchants that are not listed.
- Keep the whole response under 250 words.{language_instruction}"""
