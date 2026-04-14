import os
import sys
import unittest
from unittest.mock import patch


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.domain.sa.nodes.sa_phase6 import (
    AuthzMatrixItem,
    RoleDefinition,
    SecurityDesignOutput,
    TrustBoundary,
    sa_phase6_node,
)


class SAPhase6Tests(unittest.TestCase):
    def test_create_mode_has_stable_empty_contract(self):
        state = {
            "action_type": "CREATE",
            "thinking_log": [],
        }

        result = sa_phase6_node(state)
        phase = result["sa_phase6"]

        self.assertEqual(phase["status"], "Skipped")
        self.assertIn("defined_roles", phase)
        self.assertIn("rbac_roles", phase)
        self.assertIn("authz_matrix", phase)
        self.assertIn("trust_boundaries", phase)
        self.assertEqual(phase["defined_roles"], [])
        self.assertEqual(phase["rbac_roles"], [])

    def test_needs_clarification_has_consistent_keys(self):
        state = {
            "action_type": "UPDATE",
            "sa_phase5": {"mapped_requirements": []},
            "thinking_log": [],
        }

        result = sa_phase6_node(state)
        phase = result["sa_phase6"]

        self.assertEqual(phase["status"], "Needs_Clarification")
        self.assertIn("defined_roles", phase)
        self.assertIn("rbac_roles", phase)
        self.assertIn("authz_matrix", phase)
        self.assertIn("trust_boundaries", phase)

    def test_pass_mode_populates_defined_and_legacy_roles(self):
        state = {
            "action_type": "UPDATE",
            "api_key": "fake",
            "model": "fake-model",
            "sa_phase5": {
                "mapped_requirements": [
                    {"REQ_ID": "REQ-001", "layer": "application", "description": "로그인"}
                ]
            },
            "thinking_log": [],
        }

        mock_output = SecurityDesignOutput(
            defined_roles=[
                RoleDefinition(role_name="AuthenticatedUser", description="인증 사용자")
            ],
            authz_matrix=[
                AuthzMatrixItem(
                    req_id="REQ-001",
                    allowed_roles=["AuthenticatedUser"],
                    restriction_level="Authorized",
                )
            ],
            trust_boundaries=[
                TrustBoundary(
                    boundary_name="Client-Server",
                    crossing_data="요청 본문",
                    security_controls="TLS 적용",
                )
            ],
        )

        with patch(
            "pipeline.domain.sa.nodes.sa_phase6.call_structured_with_thinking",
            return_value=(mock_output, "ok"),
        ):
            result = sa_phase6_node(state)

        phase = result["sa_phase6"]
        self.assertEqual(phase["status"], "Pass")
        self.assertEqual(phase["rbac_roles"], ["AuthenticatedUser"])
        self.assertEqual(phase["defined_roles"][0]["role_name"], "AuthenticatedUser")
        self.assertEqual(phase["authz_matrix"][0]["restriction_level"], "Authorized")
        self.assertEqual(phase["trust_boundaries"][0]["boundary_name"], "Client-Server")


if __name__ == "__main__":
    unittest.main()
