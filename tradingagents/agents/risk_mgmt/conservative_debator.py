from tradingagents.agents.utils.instrument_mode import get_fundamental_report, get_fundamental_label, get_risk_framing


def create_conservative_debator(llm):
    def conservative_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        conservative_history = risk_debate_state.get("conservative_history", "")

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        econ_report = get_fundamental_report(state)
        trader_decision = state["trader_investment_plan"]

        framing = get_risk_framing()

        prompt = f"""As the Conservative Risk Analyst, your primary objective is to {framing['conservative_role']}. When evaluating the trader's decision, critically examine high-risk elements and highlight where more cautious alternatives would secure long-term capital preservation.

Trader's decision:
{trader_decision}

Actively counter the arguments of the Aggressive and Neutral Analysts, highlighting where their views may overlook threats or fail to prioritise sustainability. Draw from the following data:

Market/Technical Report: {market_research_report}
Sentiment Report: {sentiment_report}
Latest News: {news_report}
{get_fundamental_label()}: {econ_report}
Conversation history: {history}
Last aggressive argument: {current_aggressive_response}
Last neutral argument: {current_neutral_response}

If there are no responses yet from the other viewpoints, present your own argument based on the available data.
Question their optimism, emphasise potential downsides, and demonstrate why a conservative stance is the safest path. Focus on debating — not just presenting data. Output conversationally without special formatting."""

        response = llm.invoke(prompt)

        argument = f"Conservative Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": conservative_history + "\n" + argument,
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Conservative",
            "current_aggressive_response": risk_debate_state.get("current_aggressive_response", ""),
            "current_conservative_response": argument,
            "current_neutral_response": risk_debate_state.get("current_neutral_response", ""),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return conservative_node
