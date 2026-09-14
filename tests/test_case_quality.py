import unittest

from ai_test_framework.case_quality import check_case_granularity


class CaseGranularityTest(unittest.TestCase):
    def test_rejects_rule_coverage_concentrated_in_e2e_cases(self):
        rules = [f"A-DEMO-{index:03d}" for index in range(1, 21)]
        cases = [{
            "id": "TC-DEMO-E2E-001",
            "case_type": "端到端业务链路",
            "covered_flow_ids": ["BF-DEMO-001"],
            "covered_rule_ids": rules,
            "steps": ["执行完整链路"],
        }, {
            "id": "TC-DEMO-EDGE-001",
            "case_type": "边界",
            "covered_flow_ids": [],
            "covered_rule_ids": rules[:2],
            "steps": ["验证边界"],
        }]
        result = check_case_granularity(cases)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["metrics"]["e2e_only_rule_count"], 18)

    def test_accepts_e2e_plus_independent_execution_layer(self):
        rules = [f"A-DEMO-{index:03d}" for index in range(1, 21)]
        cases = [{
            "id": "TC-DEMO-E2E-001",
            "case_type": "端到端业务链路",
            "covered_flow_ids": ["BF-DEMO-001"],
            "covered_rule_ids": rules,
            "steps": ["执行完整链路"],
        }]
        for index in range(0, 20, 2):
            cases.append({
                "id": f"TC-DEMO-CHECK-{index // 2 + 1:03d}",
                "case_type": "独立业务检查",
                "covered_flow_ids": [],
                "covered_rule_ids": rules[index:index + 2],
                "steps": ["执行独立检查"],
            })
        result = check_case_granularity(cases)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["metrics"]["e2e_only_rule_count"], 0)


if __name__ == "__main__":
    unittest.main()
