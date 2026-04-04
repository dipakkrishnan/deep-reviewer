from claude_agent_sdk import AgentDefinition

from agent.claude_tools import SUBAGENT_TOOLS

DEFAULT_AGENTS: dict[str, AgentDefinition] = {
    "literature-searcher": AgentDefinition(
        description="Find and summarize relevant prior work for the paper under review.",
        prompt=(
            "You are an expert research librarian. Given a paper's topic and claims, "
            "search for the most relevant prior work — seminal papers, recent advances, "
            "and directly competing results. For each source, provide the title, authors, "
            "year, and a concise summary of how it relates to the paper under review."
        ),
        tools=SUBAGENT_TOOLS,
        model="sonnet",
    ),
    "logical-consistency-checker": AgentDefinition(
        description="Check the paper's arguments and reasoning for logical errors.",
        prompt=(
            "You are a rigorous logician. Examine the paper's chain of reasoning from "
            "assumptions through to conclusions. Identify any logical fallacies, unstated "
            "assumptions, circular arguments, or gaps where a claim does not follow from "
            "the evidence presented. Be specific — cite the exact passage and explain the flaw."
        ),
        tools=SUBAGENT_TOOLS,
        model="opus",
    ),
    "factual-accuracy-checker": AgentDefinition(
        description="Verify factual claims, data, and citations in the paper.",
        prompt=(
            "You are a meticulous fact-checker. Verify the paper's factual claims — "
            "statistics, dates, named results, and attributed quotes. Cross-reference "
            "citations to confirm they support the claims made. Flag anything that is "
            "incorrect, unsupported, or misleadingly presented."
        ),
        tools=SUBAGENT_TOOLS,
        model="sonnet",
    ),
}
