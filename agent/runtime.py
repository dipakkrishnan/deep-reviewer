from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from agent.claude_tools import ORCHESTRATOR_TOOLS


async def run_agent(
    system_prompt: str,
    user_prompt: str,
    model: str = "claude-opus-4-6",
    cwd: str | None = None,
    provider: str = "anthropic",
) -> str:
    """Run a prompt through the Claude Agent SDK and return the result text."""
    if provider == "anthropic":
        options = ClaudeAgentOptions(
            allowed_tools=ORCHESTRATOR_TOOLS,
            permission_mode="bypassPermissions",
            system_prompt=system_prompt,
            model=model,
            cwd=cwd,
        )
        result_text = ""
        async for message in query(prompt=user_prompt, options=options):
            if isinstance(message, ResultMessage):
                result_text = message.result
        return result_text

    raise NotImplementedError(f"Unsupported provider: {provider}")
