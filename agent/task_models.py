from pydantic import BaseModel, field_validator


class SubagentGoal(BaseModel):
    """A single research goal assigned to a subagent."""

    role: str
    goal: str
    domain: str | None = None

    @field_validator("role", "goal")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be empty")
        return stripped
