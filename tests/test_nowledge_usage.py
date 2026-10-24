import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
import sys

sys.path.insert(0, str(SRC))

from ai_test_framework.nowledge_usage import (
    analyze_codex_session,
    compact_usage_summary,
    update_usage_ledger,
)


def write_jsonl(path: Path, rows) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


class NowledgeUsageAnalysisTest(unittest.TestCase):
    def test_reports_bounded_nowledge_estimate_and_official_turn_total(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory) / "session.jsonl"
            write_jsonl(
                session,
                [
                    {
                        "timestamp": "2026-09-12T08:00:00Z",
                        "ordinal": 1,
                        "type": "event_msg",
                        "payload": {"type": "task_started", "turn_id": "turn-1"},
                    },
                    {
                        "timestamp": "2026-09-12T08:00:01Z",
                        "ordinal": 2,
                        "type": "response_item",
                        "payload": {
                            "type": "custom_tool_call",
                            "name": "exec",
                            "call_id": "call-1",
                            "input": (
                                "const r = await tools.mcp__nowledge_mem__memory_search("
                                "{query: 'secret query', limit: 3}); text(r);"
                            ),
                        },
                    },
                    {
                        "timestamp": "2026-09-12T08:00:01Z",
                        "ordinal": 3,
                        "type": "token_usage_record",
                        "payload": {
                            "turn_id": "turn-1",
                            "usage": {"total_tokens": 1200},
                            "turn_token_usage": {"total_tokens": 1200},
                        },
                    },
                    {
                        "timestamp": "2026-09-12T08:00:02Z",
                        "ordinal": 4,
                        "type": "response_item",
                        "payload": {
                            "type": "custom_tool_call_output",
                            "call_id": "call-1",
                            "output": "memory body that must not be copied into the ledger",
                        },
                    },
                    {
                        "timestamp": "2026-09-12T08:00:03Z",
                        "ordinal": 5,
                        "type": "token_usage_record",
                        "payload": {
                            "turn_id": "turn-1",
                            "usage": {"total_tokens": 3000},
                            "turn_token_usage": {
                                "input_tokens": 4000,
                                "cached_input_tokens": 1000,
                                "output_tokens": 200,
                                "reasoning_output_tokens": 50,
                                "total_tokens": 4200,
                            },
                        },
                    },
                    {
                        "timestamp": "2026-09-12T08:00:04Z",
                        "ordinal": 6,
                        "type": "event_msg",
                        "payload": {"type": "task_complete", "turn_id": "turn-1"},
                    },
                ],
            )

            report = analyze_codex_session(session)

            self.assertEqual(report["summary"]["nowledge_call_count"], 1)
            turn = report["turns"][0]
            self.assertEqual(turn["turn_id"], "turn-1")
            self.assertEqual(turn["official_turn_usage"]["total_tokens"], 4200)
            self.assertEqual(turn["calls"][0]["tools"], ["memory_search"])
            self.assertEqual(turn["calls"][0]["context_replay_count"], 1)
            self.assertGreater(turn["estimated_nowledge_token_volume"], 0)
            serialized = json.dumps(report, ensure_ascii=False)
            self.assertNotIn("secret query", serialized)
            self.assertNotIn("memory body", serialized)
            self.assertEqual(report["methodology"]["classification"], "estimate")

    def test_marks_batched_exec_as_upper_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory) / "session.jsonl"
            write_jsonl(
                session,
                [
                    {
                        "ordinal": 1,
                        "type": "event_msg",
                        "payload": {"type": "task_started", "turn_id": "turn-mixed"},
                    },
                    {
                        "ordinal": 2,
                        "type": "response_item",
                        "payload": {
                            "type": "custom_tool_call",
                            "name": "exec",
                            "call_id": "call-mixed",
                            "input": (
                                "await Promise.all(["
                                "tools.mcp__nowledge_mem__thread_search({query:'x'}),"
                                "tools.exec_command({cmd:'pwd'})]);"
                            ),
                        },
                    },
                    {
                        "ordinal": 3,
                        "type": "response_item",
                        "payload": {
                            "type": "custom_tool_call_output",
                            "call_id": "call-mixed",
                            "output": "combined output",
                        },
                    },
                    {
                        "ordinal": 4,
                        "type": "event_msg",
                        "payload": {"type": "task_complete", "turn_id": "turn-mixed"},
                    },
                ],
            )

            call = analyze_codex_session(session)["turns"][0]["calls"][0]

            self.assertTrue(call["mixed_exec"])
            self.assertEqual(call["precision"], "upper_bound")

    def test_does_not_count_shell_text_that_only_mentions_a_tool_name(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory) / "session.jsonl"
            write_jsonl(
                session,
                [
                    {
                        "ordinal": 1,
                        "type": "event_msg",
                        "payload": {"type": "task_started", "turn_id": "turn-shell"},
                    },
                    {
                        "ordinal": 2,
                        "type": "response_item",
                        "payload": {
                            "type": "custom_tool_call",
                            "name": "exec",
                            "call_id": "call-shell",
                            "input": (
                                "const r = await tools.exec_command({"
                                "cmd: \"rg 'mcp__nowledge_mem__memory_search' .\"});"
                            ),
                        },
                    },
                    {
                        "ordinal": 3,
                        "type": "response_item",
                        "payload": {
                            "type": "custom_tool_call_output",
                            "call_id": "call-shell",
                            "output": "ordinary shell result",
                        },
                    },
                    {
                        "ordinal": 4,
                        "type": "event_msg",
                        "payload": {"type": "task_complete", "turn_id": "turn-shell"},
                    },
                ],
            )

            report = analyze_codex_session(session)

            self.assertEqual(report["summary"]["nowledge_call_count"], 0)
            self.assertEqual(report["turns"], [])

    def test_ledger_is_idempotent_for_the_same_turn(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.jsonl"
            report = {
                "session_id": "session-1",
                "turns": [
                    {
                        "turn_id": "turn-1",
                        "started_at": "2026-09-12T08:00:00Z",
                        "nowledge_call_count": 2,
                        "estimated_nowledge_token_volume": 321,
                        "official_turn_usage": {"total_tokens": 5000},
                        "tools": ["memory_search"],
                        "precision": "estimate",
                    }
                ],
            }

            first = update_usage_ledger(ledger, report)
            second = update_usage_ledger(ledger, report)

            self.assertEqual(first["appended"], 1)
            self.assertEqual(second["appended"], 0)
            rows = [json.loads(line) for line in ledger.read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertNotIn("calls", rows[0])

    def test_compact_summary_omits_call_details(self):
        report = {
            "session_id": "session-1",
            "summary": {
                "turn_count": 1,
                "nowledge_call_count": 2,
                "estimated_nowledge_token_volume": 321,
                "official_turn_total_tokens": 5000,
            },
            "turns": [{"calls": [{"request_bytes": 9999}]}],
            "methodology": {"classification": "estimate"},
        }

        compact = compact_usage_summary(report)

        self.assertEqual(compact["estimated_nowledge_token_volume"], 321)
        self.assertEqual(compact["official_turn_total_tokens"], 5000)
        self.assertEqual(compact["precision"], "estimate")
        self.assertNotIn("turns", compact)
        self.assertNotIn("calls", compact)


class NowledgeUsageEdgeTest(unittest.TestCase):
    def analyze_rows(self, rows, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.jsonl'
            write_jsonl(path, rows)
            return analyze_codex_session(path, **kwargs)

    def call(self, call_id='c', name='mcp__nowledge_mem__memory_search', **extra):
        return {'type': 'response_item', 'payload': {
            'type': 'function_call', 'name': name, 'call_id': call_id,
            'arguments': '{"query":"private query"}', **extra}}

    def start(self, turn_id):
        return {'type': 'event_msg', 'payload': {'type': 'task_started', 'turn_id': turn_id}}

    def test_latest_turn_means_latest_matching_turn(self):
        report = self.analyze_rows([
            self.start('a'), self.call('a'), self.start('b'), self.call('b'),
            self.start('ordinary'),
        ], latest_turn=True)
        self.assertEqual([t['turn_id'] for t in report['turns']], ['b'])
        self.assertEqual(report['summary']['nowledge_call_count'], 1)
        self.assertIsNone(report['turns'][0]['official_turn_usage'])

    def test_ignores_comments_and_string_literals_in_exec(self):
        source = '''// tools.mcp__nowledge_mem__memory_search({})
        /* tools.mcp__nowledge_mem__thread_search({}) */
        const example = "tools.mcp__nowledge_mem__memory_search({})";
        const template = `tools.mcp__nowledge_mem__memory_search({})`;
        tools.exec_command({cmd: "echo mcp__nowledge_mem__memory_search"});'''
        report = self.analyze_rows([self.start('a'), self.call(
            name='exec', type='custom_tool_call', input=source)])
        self.assertEqual(report['turns'], [])

    def test_cumulative_usage_is_never_reported_as_official_turn_usage(self):
        report = self.analyze_rows([self.start('a'), self.call(), {
            'type': 'token_usage_record', 'payload': {'turn_id': 'a',
            'usage': {'total_tokens': 99000}}}])
        self.assertIsNone(report['turns'][0]['official_turn_usage'])
        self.assertIsNone(report['summary']['official_turn_total_tokens'])

    def test_replay_count_stops_at_turn_boundary_and_requires_response(self):
        report = self.analyze_rows([
            self.start('a'), self.call(),
            {'type': 'response_item', 'payload': {'type': 'function_call_output',
                'call_id': 'c', 'output': 'private result'}},
            {'type': 'token_usage_record', 'payload': {'turn_id': 'a'}},
            {'type': 'token_usage_record', 'payload': {'turn_id': 'a'}},
            self.start('b'), {'type': 'token_usage_record', 'payload': {'turn_id': 'b'}},
        ])
        self.assertEqual(report['turns'][0]['calls'][0]['context_replay_count'], 2)
        missing = self.analyze_rows([self.start('a'), self.call()])
        self.assertEqual(missing['turns'][0]['calls'][0]['context_replay_count'], 0)
        self.assertEqual(missing['turns'][0]['calls'][0]['estimated_response_tokens'], 0)

    def test_ledger_updates_running_turn_and_rejects_unapproved_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / 'ledger.jsonl'
            report = self.analyze_rows([self.start('a'), self.call()])
            update_usage_ledger(ledger, report)
            report['turns'][0]['estimated_nowledge_token_volume'] += 8
            report['turns'][0]['query'] = 'PRIVATE-QUERY'
            report['turns'][0]['official_turn_usage'] = {'total_tokens': 5, 'secret': 'PRIVATE-SECRET'}
            result = update_usage_ledger(ledger, report)
            self.assertEqual(result['updated'], 1)
            rows = ledger.read_text().splitlines()
            self.assertEqual(len(rows), 1)
            self.assertNotIn('PRIVATE', rows[0])
            self.assertEqual(json.loads(rows[0])['estimated_nowledge_token_volume'],
                report['turns'][0]['estimated_nowledge_token_volume'])

    def test_malformed_jsonl_reports_line_without_echoing_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.jsonl'
            path.write_text('{PRIVATE-SECRET}\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'line 1') as error:
                analyze_codex_session(path)
            self.assertNotIn('PRIVATE', str(error.exception))


    def test_multibyte_output_and_replay_volume_follow_documented_formula(self):
        report = self.analyze_rows([
            {'type': 'session_meta', 'payload': {'id': 'session-utf8'}},
            self.start('a'), self.call(),
            {'type': 'response_item', 'payload': {'type': 'function_call_output',
                'call_id': 'c', 'output': '中文结果'}},
            {'type': 'token_usage_record', 'payload': {'turn_id': 'a',
                'turn_token_usage': {'total_tokens': 100}}},
        ])
        call = report['turns'][0]['calls'][0]
        self.assertEqual(report['session_id'], 'session-utf8')
        self.assertEqual(call['response_bytes'], 12)
        self.assertEqual(call['estimated_response_tokens'], 3)
        request_bytes = len('mcp__nowledge_mem__memory_search'.encode('utf-8')) + len('{"query":"private query"}'.encode('utf-8'))
        self.assertEqual(call['request_bytes'], request_bytes)
        request_tokens = (request_bytes + 3) // 4
        self.assertEqual(call['estimated_nowledge_token_volume'], request_tokens * 2 + 3)
        self.assertEqual(report['summary']['official_turn_total_tokens'], 100)



class NowledgeUsageCliTest(unittest.TestCase):
    def test_cli_compact_uses_local_fixture_and_never_emits_body(self):
        import contextlib
        import io
        from ai_test_framework.cli import main
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'session.jsonl'
            write_jsonl(source,[
                {'type':'event_msg','payload':{'type':'task_started','turn_id':'turn-local'}},
                {'type':'response_item','payload':{'type':'function_call','name':'mcp__nowledge_mem__memory_search','arguments':'private words','call_id':'c'}},
                {'type':'response_item','payload':{'type':'function_call_output','call_id':'c','output':'private body'}},
            ])
            output=io.StringIO()
            with contextlib.redirect_stdout(output):
                code=main(['nowledge-usage','--session',str(source),'--compact'])
            self.assertEqual(code,0)
            result=json.loads(output.getvalue())
            self.assertEqual(result['nowledge_call_count'],1)
            self.assertNotIn('private',output.getvalue())
    def test_ledger_cannot_overwrite_analyzed_session(self):
        import contextlib
        import io
        from ai_test_framework.cli import main
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'session.jsonl'
            write_jsonl(source,[{'type':'event_msg','payload':{'type':'task_started','turn_id':'t'}}])
            original=source.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                code=main(['nowledge-usage','--session',str(source),'--write-ledger','--ledger',str(source)])
            self.assertNotEqual(code,0)
            self.assertEqual(source.read_bytes(),original)

if __name__ == "__main__":
    unittest.main()
