"""
FinTwin AI Copilot: conversational layer over the Financial Twin.

Pipeline:  question -> Financial Twin (deterministic analysis on real data)
           -> financial context -> optional LLM rewrite -> response

If an LLM is configured, it receives the twin's context and computed
analysis with strict rules (use only these numbers, never invent data).
If the LLM is unavailable or fails, the twin's own answer is returned.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.financial_twin import FinancialTwin, TwinAnswer
from app.ai.llm_provider import LLMError, get_llm_provider
from app.database import insight_repository
from app.services.transaction_service import transactions_dataframe
from app.utils.logger import get_logger
from app.utils.validators import clean_text

log = get_logger("ai.copilot")

SYSTEM_PROMPT = """You are FinTwin AI Copilot, a careful personal-finance analysis assistant inside an
educational app. Rules:
1. Use ONLY the numbers in the provided FINANCIAL CONTEXT and TWIN ANALYSIS. Never invent figures.
2. If information needed to answer is missing, say exactly what is missing.
3. Present results as estimates, scenarios or potential recommendations, never guarantees.
4. Do not recommend specific stocks, funds or products. You are not a licensed financial advisor.
5. Use Indian Rupees (₹) and Indian number formatting. Be concise and use short markdown sections.
6. Keep the twin analysis's verdict and numbers; you may explain them more clearly."""

MAX_QUESTION_LENGTH = 500


@dataclass
class CopilotReply:
    markdown: str
    source: str  # "twin" or LLM provider name
    intent: str


def ask(user_id: str, question: str, save: bool = True) -> CopilotReply:
    question = clean_text(question, MAX_QUESTION_LENGTH)
    if not question:
        return CopilotReply("Ask a question about your finances to get started.", "twin", "empty")

    twin = FinancialTwin.from_dataframe(transactions_dataframe(user_id), insight_repository.get_profile(user_id))
    analysis: TwinAnswer = twin.answer(question)
    reply = CopilotReply(analysis.as_markdown(), "Financial Twin", analysis.intent)

    provider = get_llm_provider()
    if provider is not None and analysis.intent != "no_data":
        history = [{"role": m["role"], "content": m["content"]} for m in insight_repository.get_messages(user_id, 6)]
        prompt = (
            f"FINANCIAL CONTEXT\n{twin.context_summary()}\n\n"
            f"TWIN ANALYSIS (computed from the user's data)\n{analysis.as_markdown()}\n\n"
            f"USER QUESTION\n{question}"
        )
        try:
            text = provider.generate(SYSTEM_PROMPT, prompt, history)
            reply = CopilotReply(text, provider.name, analysis.intent)
        except LLMError as exc:
            log.warning("LLM unavailable, using twin answer: %s", exc)

    if save:
        insight_repository.add_message(user_id, "user", question)
        insight_repository.add_message(user_id, "assistant", reply.markdown, {"source": reply.source, "intent": reply.intent})
    return reply


SUGGESTED_QUESTIONS = [
    "Can I afford a ₹15 lakh car next year?",
    "What happens if my salary increases by 20%?",
    "How much can I save in one year?",
    "What happens if my expenses increase by ₹10,000?",
    "How much should I invest monthly to reach ₹50 lakh in 10 years?",
    "Where am I spending the most?",
]
