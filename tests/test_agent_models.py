import unittest

from pydantic import ValidationError

from agent import (
    AgentSettings,
    ReviewMode,
    ReviewPreset,
    ReviewRequest,
    ReviewRunResult,
    SubagentGoal,
    get_review_preset,
    run_review,
)
from models import Artifact, ArtifactSource


class ReviewRequestTests(unittest.TestCase):
    def test_defaults(self) -> None:
        request = ReviewRequest()

        self.assertEqual(request.mode, ReviewMode.STANDARD)
        self.assertEqual(request.model, "claude-opus-4-6")

    def test_rejects_invalid_max_subagents(self) -> None:
        with self.assertRaises(ValidationError):
            ReviewRequest(max_subagents=0)


class ReviewPresetTests(unittest.TestCase):
    def test_quick_preset(self) -> None:
        preset = get_review_preset(ReviewMode.QUICK)

        self.assertEqual(preset.subagent_count, 2)
        self.assertEqual(preset.self_play_rounds, 1)

    def test_standard_preset(self) -> None:
        preset = get_review_preset(ReviewMode.STANDARD)

        self.assertEqual(preset.subagent_count, 4)
        self.assertEqual(preset.self_play_rounds, 1)

    def test_deep_preset(self) -> None:
        preset = get_review_preset(ReviewMode.DEEP)

        self.assertEqual(preset.subagent_count, 8)
        self.assertEqual(preset.self_play_rounds, 2)

    def test_rejects_invalid_preset_values(self) -> None:
        with self.assertRaises(ValidationError):
            ReviewPreset(
                mode=ReviewMode.QUICK,
                subagent_count=0,
                self_play_rounds=1,
            )


class AgentSettingsTests(unittest.TestCase):
    def test_resolves_from_mode_defaults(self) -> None:
        settings = AgentSettings.from_request(ReviewRequest(mode=ReviewMode.QUICK))

        self.assertEqual(settings.mode, ReviewMode.QUICK)
        self.assertEqual(settings.subagent_count, 2)
        self.assertEqual(settings.self_play_rounds, 1)

    def test_respects_max_subagent_override(self) -> None:
        settings = AgentSettings.from_request(
            ReviewRequest(mode=ReviewMode.QUICK, max_subagents=5)
        )

        self.assertEqual(settings.subagent_count, 5)


class SubagentGoalTests(unittest.TestCase):
    def test_accepts_valid_goal(self) -> None:
        goal = SubagentGoal(role="math reviewer", goal="Check derivations.")

        self.assertEqual(goal.role, "math reviewer")
        self.assertEqual(goal.goal, "Check derivations.")

    def test_rejects_empty_role(self) -> None:
        with self.assertRaises(ValidationError):
            SubagentGoal(role="   ", goal="Check derivations.")

    def test_rejects_empty_goal(self) -> None:
        with self.assertRaises(ValidationError):
            SubagentGoal(role="math reviewer", goal="   ")


class AgentExportsTests(unittest.TestCase):
    def test_public_exports(self) -> None:
        self.assertIsNotNone(AgentSettings)
        self.assertIsNotNone(ReviewMode)
        self.assertIsNotNone(ReviewPreset)
        self.assertIsNotNone(ReviewRequest)
        self.assertIsNotNone(ReviewRunResult)
        self.assertIsNotNone(SubagentGoal)
        self.assertTrue(callable(get_review_preset))
        self.assertTrue(callable(run_review))


class ReviewRunnerTypesTests(unittest.IsolatedAsyncioTestCase):
    def test_review_run_result_shape(self) -> None:
        result = ReviewRunResult(
            artifact_title="Test Paper",
            settings=AgentSettings.from_request(ReviewRequest()),
            report_markdown="# Review\n\nHigh-level summary.",
        )

        self.assertEqual(result.artifact_title, "Test Paper")
        self.assertEqual(result.report_markdown, "# Review\n\nHigh-level summary.")

    async def test_run_review_is_not_implemented(self) -> None:
        artifact = Artifact(
            source=ArtifactSource.PDF,
            url="/tmp/paper.pdf",
            title="Test Paper",
            text="Paper body.",
        )

        with self.assertRaises(NotImplementedError):
            await run_review(ReviewRequest(), artifact)


if __name__ == "__main__":
    unittest.main()
