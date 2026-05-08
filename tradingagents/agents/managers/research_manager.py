"""Research Manager: turns the bull/bear debate into a structured investment plan for the trader."""

from __future__ import annotations

from tradingagents.agents.schemas import get_research_schema, get_research_renderer
from tradingagents.agents.utils.agent_utils import build_instrument_context
from tradingagents.agents.utils.instrument_mode import get_rating_scale
from tradingagents.agents.utils.structured import (
    bind_structured,
    invoke_structured_or_freetext,
)


def create_research_manager(llm):
    def research_manager_node(state) -> dict:
        instrument_context = build_instrument_context(state["company_of_interest"])
        history = state["investment_debate_state"].get("history", "")
        investment_debate_state = state["investment_debate_state"]

        schema = get_research_schema()
        renderer = get_research_renderer()
        structured_llm = bind_structured(llm, schema, "Research Manager")

        prompt = f"""As the Research Manager and debate facilitator, your role is to critically evaluate this round of debate and deliver a clear, actionable investment plan for the trader.

{instrument_context}

---

**Rating Scale** (use exactly one):
{get_rating_scale()}

Commit to a clear stance whenever the debate's strongest arguments warrant one; reserve the neutral option only when evidence is genuinely balanced.

---

**Debate History:**
{history}"""

        investment_plan = invoke_structured_or_freetext(
            structured_llm,
            llm,
            prompt,
            renderer,
            "Research Manager",
        )

        new_investment_debate_state = {
            "judge_decision": investment_plan,
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": investment_plan,
            "count": investment_debate_state["count"],
        }

        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": investment_plan,
        }

    return research_manager_node
