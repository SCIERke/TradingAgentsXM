from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import build_instrument_context, get_language_instruction
from tradingagents.agents.utils.forex_data_tools import get_forex_macro
from tradingagents.agents.utils.news_data_tools import get_global_news


def create_macro_analyst(llm):
    def macro_analyst_node(state):
        current_date = state["trade_date"]
        pair = state["company_of_interest"]
        instrument_context = build_instrument_context(pair)

        tools = [get_forex_macro, get_global_news]

        system_message = (
            f"You are a macro economic analyst specialising in forex markets. "
            f"Your task is to analyse the macroeconomic environment relevant to the currency pair `{pair}` "
            f"and write a comprehensive report covering:\n"
            "1. **Interest rate differentials** — current and expected rates for both economies (use yield data)\n"
            "2. **Economic momentum** — growth, inflation, and labour market signals\n"
            "3. **Risk sentiment** — VIX, gold, safe-haven flows\n"
            "4. **Capital flows** — commodity prices for commodity-linked currencies (AUD, CAD, NOK)\n"
            "5. **Key upcoming events** — central bank meetings, CPI releases, NFP, or GDP prints\n\n"
            f"Use `get_forex_macro(pair='{pair}', curr_date=...)` to retrieve macro proxy data. "
            "Use `get_global_news` to find recent central bank statements and economic releases. "
            "Conclude with a clear directional bias (bullish base / bearish base / neutral) supported by evidence. "
            "Append a Markdown table summarising key indicators at the end."
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **LONG/FLAT/SHORT** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **LONG/FLAT/SHORT** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    " For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([t.name for t in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])

        report = ""
        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "macro_report": report,
        }

    return macro_analyst_node
