from tradingagents.agents.utils.instrument_mode import get_fundamental_report, get_fundamental_label, get_risk_framing


def create_aggressive_debator(llm):
    def aggressive_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        aggressive_history = risk_debate_state.get("aggressive_history", "")

        current_conservative_response = risk_debate_state.get("current_conservative_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        econ_report = get_fundamental_report(state)
        trader_decision = state["trader_investment_plan"]

        framing = get_risk_framing()

        prompt = f"""As the Aggressive Risk Analyst, your role is to {framing['aggressive_role']}. When evaluating the trader's decision, focus on the potential upside and champion the opportunity — even when it comes with elevated risk. Use the provided data to strengthen your arguments and directly challenge the conservative and neutral analysts' caution.

Trader's decision:
{trader_decision}

Build a compelling case for the trader's decision by questioning and critiquing the conservative and neutral stances. Show why a higher-conviction approach offers the best path forward. Incorporate insights from:

Market/Technical Report: {market_research_report}
Sentiment Report: {sentiment_report}
Latest News: {news_report}
{get_fundamental_label()}: {econ_report}
Conversation history: {history}
Last conservative argument: {current_conservative_response}
Last neutral argument: {current_neutral_response}

If there are no responses yet from the other viewpoints, present your own argument based on the available data.
Engage actively — address specific concerns, refute weaknesses in their logic, and assert the benefits of the {framing['action_vocab']} action. Output conversationally without special formatting."""

        response = llm.invoke(prompt)

        argument = f"Aggressive Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": aggressive_history + "\n" + argument,
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Aggressive",
            "current_aggressive_response": argument,
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": risk_debate_state.get("current_neutral_response", ""),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return aggressive_node
