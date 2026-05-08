from tradingagents.agents.utils.instrument_mode import get_fundamental_report, get_fundamental_label, get_risk_framing


def create_neutral_debator(llm):
    def neutral_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        neutral_history = risk_debate_state.get("neutral_history", "")

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_conservative_response = risk_debate_state.get("current_conservative_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        econ_report = get_fundamental_report(state)
        trader_decision = state["trader_investment_plan"]

        framing = get_risk_framing()

        prompt = f"""As the Neutral Risk Analyst, your role is to {framing['neutral_role']}. Evaluate the upsides and downsides while factoring in broader market trends, potential economic shifts, and prudent position management.

Trader's decision:
{trader_decision}

Challenge both the Aggressive and Conservative Analysts, pointing out where each may be overly optimistic or overly cautious. Use these data sources to support a balanced, sustainable strategy:

Market/Technical Report: {market_research_report}
Sentiment Report: {sentiment_report}
Latest News: {news_report}
{get_fundamental_label()}: {econ_report}
Conversation history: {history}
Last aggressive argument: {current_aggressive_response}
Last conservative argument: {current_conservative_response}

If there are no responses yet from the other viewpoints, present your own balanced argument based on the available data.
Critically analyse both sides, advocate for a moderate approach, and illustrate why balanced risk management yields the most reliable outcomes. Output conversationally without special formatting."""

        response = llm.invoke(prompt)

        argument = f"Neutral Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": neutral_history + "\n" + argument,
            "latest_speaker": "Neutral",
            "current_aggressive_response": risk_debate_state.get("current_aggressive_response", ""),
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": argument,
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return neutral_node
