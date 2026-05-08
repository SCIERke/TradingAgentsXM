from tradingagents.agents.utils.instrument_mode import get_fundamental_report, get_fundamental_label, get_researcher_framing


def create_bear_researcher(llm):
    def bear_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bear_history = investment_debate_state.get("bear_history", "")
        current_response = investment_debate_state.get("current_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        econ_report = get_fundamental_report(state)

        instrument = state["company_of_interest"]
        framing = get_researcher_framing(instrument)

        prompt = f"""You are a {framing['bear_role']}. Your goal is to present a well-reasoned argument emphasising {framing['bear_focus']}. Leverage the provided research and data to {framing['bear_counter']} effectively.

Key points to focus on:
- Build a strong case against the bull thesis using market, news, and economic data.
- Directly counter the bull's last argument with specific data and sound reasoning.
- Engage conversationally — debate the bull analyst rather than simply listing facts.

Resources available:
Market/Technical report: {market_research_report}
Sentiment report: {sentiment_report}
Latest news: {news_report}
{framing['action_vocab']} decision context — {get_fundamental_label()}: {econ_report}
Debate history: {history}
Last bull argument: {current_response}

Use this information to deliver a compelling bear argument for {framing['instrument_description']}, refute the bull's claims, and engage in a dynamic debate. Respond conversationally without special formatting."""

        response = llm.invoke(prompt)

        argument = f"Bear Analyst: {response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bear_history": bear_history + "\n" + argument,
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bear_node
