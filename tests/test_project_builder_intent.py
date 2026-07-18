import unittest

from agents.orchestrator import project_builder


class CapturingRequester:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def __call__(self, prompt, correction=None):
        self.calls.append((prompt, correction))
        return self.response


class ProjectBuilderIntentTest(unittest.IsolatedAsyncioTestCase):
    def test_a_plain_full_stack_creation_is_accepted(self):
        intent = project_builder.detect_project_creation_intent("Cria uma app full stack.")

        self.assertTrue(intent.is_creation_request)
        self.assertEqual(intent.creation_signals, ["cria", "app", "full stack"])
        self.assertEqual(intent.negative_constraints, [])
        self.assertIsNone(intent.rejection_reason)

    def test_b_negative_obsidian_constraint_does_not_cancel_creation(self):
        intent = project_builder.detect_project_creation_intent(
            "Cria uma app full stack. N\u00e3o uses Obsidian."
        )

        self.assertTrue(intent.is_creation_request)
        self.assertIn("N\u00e3o uses Obsidian", intent.negative_constraints)
        self.assertIn("Obsidian", intent.excluded_targets)
        self.assertFalse(intent.compound_intent)

    def test_c_without_docker_is_a_constraint(self):
        intent = project_builder.detect_project_creation_intent("Cria uma app sem Docker.")

        self.assertTrue(intent.is_creation_request)
        self.assertIn("sem Docker", intent.negative_constraints)
        self.assertIn("Docker", intent.excluded_targets)

    def test_d_negated_creation_is_rejected(self):
        intent = project_builder.detect_project_creation_intent(
            "N\u00e3o cries nenhum projeto."
        )

        self.assertFalse(intent.is_creation_request)
        self.assertEqual(intent.rejection_reason, "creation_explicitly_negated")
        self.assertNotIn("cries", intent.creation_signals)

    def test_e_obsidian_note_is_not_a_project_creation_request(self):
        intent = project_builder.detect_project_creation_intent("Cria uma nota no Obsidian.")

        self.assertFalse(intent.is_creation_request)
        self.assertEqual(intent.rejection_reason, "external_workspace_is_primary_target")
        self.assertEqual(intent.separate_work, ["Obsidian"])

    def test_f_creation_after_negative_obsidian_clause_is_accepted(self):
        intent = project_builder.detect_project_creation_intent(
            "N\u00e3o escrevas no Obsidian; cria tudo em workspace/projects."
        )

        self.assertTrue(intent.is_creation_request)
        self.assertIn("Obsidian", intent.excluded_targets)
        self.assertIn("workspace/projects", intent.creation_signals)

    def test_g_positive_obsidian_work_is_registered_as_separate(self):
        intent = project_builder.detect_project_creation_intent(
            "Cria uma app e documenta no Obsidian."
        )

        self.assertTrue(intent.is_creation_request)
        self.assertTrue(intent.compound_intent)
        self.assertEqual(intent.separate_work, ["Obsidian"])
        self.assertNotIn("Obsidian", intent.excluded_targets)

    def test_h_stack_selection_with_react_excluded_is_accepted(self):
        intent = project_builder.detect_project_creation_intent(
            "Evita React e usa outra stack."
        )

        self.assertTrue(intent.is_creation_request)
        self.assertIn("React", intent.excluded_targets)
        self.assertIn("outra stack", intent.creation_signals)

    def test_i_distant_negation_does_not_apply_to_later_target(self):
        intent = project_builder.detect_project_creation_intent(
            "N\u00e3o uses Docker nesta app porque a equipa rejeitou essa op\u00e7\u00e3o h\u00e1 muito tempo. "
            "Cria uma app com React."
        )

        self.assertTrue(intent.is_creation_request)
        self.assertIn("Docker", intent.excluded_targets)
        self.assertNotIn("React", intent.excluded_targets)

    async def test_excluded_targets_are_sent_to_plan_requester(self):
        requester = CapturingRequester({
            "project_name": "Intent constraints",
            "stack": "Node.js",
            "files": [{"path": "app.js", "content": "console.log('ok');\n"}],
            "validation_commands": ["node --check app.js"],
            "preview_command": "",
        })

        await project_builder.get_valid_project_plan(
            "Cria uma app. N\u00e3o uses Obsidian e evita React.",
            requester,
        )

        sent_prompt = requester.calls[0][0]
        self.assertIn('"excluded_targets": ["Obsidian", "React"]', sent_prompt)
        self.assertIn("separate_work_not_executed", sent_prompt)

    def test_obsidian_path_policy_remains_enforced(self):
        with self.assertRaises(project_builder.ProjectBuilderError):
            project_builder._safe_relative_file_path("obsidian_vault/project/app.js")

    def test_english_negative_constraint_is_supported(self):
        intent = project_builder.detect_project_creation_intent(
            "Create an app without Docker and do not use Obsidian."
        )

        self.assertTrue(intent.is_creation_request)
        self.assertEqual(intent.excluded_targets, ["Obsidian", "Docker"])


if __name__ == "__main__":
    unittest.main()
