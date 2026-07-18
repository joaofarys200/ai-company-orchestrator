import asyncio
import os
import re
import shutil
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agents import tools as ag_tools
from agents.orchestrator import project_builder


TEST_ROOT_REL = f"workspace/projects/_project_builder_supervision_{os.getpid()}"


FIXTURE_SOURCE = r"""
const { spawn } = require('child_process');

const mode = process.argv[2];
const hold = () => setInterval(() => {}, 1000);

if (mode === 'no-output') {
  hold();
} else if (mode === 'stdout') {
  const chunk = 'O'.repeat(8192);
  const pump = () => {
    while (process.stdout.write(chunk)) {}
    process.stdout.once('drain', pump);
  };
  pump();
} else if (mode === 'stderr') {
  const chunk = 'E'.repeat(8192);
  const pump = () => {
    while (process.stderr.write(chunk)) {}
    process.stderr.once('drain', pump);
  };
  pump();
} else if (mode === 'child-inherits') {
  const child = spawn(process.execPath, [__filename, 'no-output'], {
    stdio: ['ignore', 'inherit', 'inherit'],
    windowsHide: true,
  });
  console.log(`CHILD_PID=${child.pid}`);
  hold();
} else if (mode === 'parent-exits') {
  const child = spawn(process.execPath, [__filename, 'no-output'], {
    stdio: ['ignore', 'inherit', 'inherit'],
    windowsHide: true,
  });
  console.log(`CHILD_PID=${child.pid}`);
  child.unref();
  setTimeout(() => process.exit(0), 300);
} else if (mode === 'ignore-stop') {
  process.on('SIGINT', () => {});
  process.on('SIGTERM', () => {});
  if (process.platform === 'win32') process.on('SIGBREAK', () => {});
  const child = spawn(process.execPath, [__filename, 'no-output'], {
    stdio: ['ignore', 'inherit', 'inherit'],
    windowsHide: true,
  });
  console.log(`CHILD_PID=${child.pid}`);
  hold();
} else if (mode === 'normal') {
  console.log('NORMAL_OK');
} else {
  console.error(`unknown mode: ${mode}`);
  process.exit(2);
}
"""


@unittest.skipUnless(shutil.which("node"), "Node is required for process supervision tests")
class ProjectBuilderProcessSupervisionTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.project = Path(ag_tools.resolve_workspace_path(TEST_ROOT_REL))
        shutil.rmtree(self.project, ignore_errors=True)
        self.project.mkdir(parents=True)
        (self.project / "supervision_fixture.js").write_text(FIXTURE_SOURCE, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.project, ignore_errors=True)

    async def run_mode(self, mode, *, timeout=0.25, output_limit_bytes=4096):
        started = time.monotonic()
        result = await asyncio.wait_for(
            project_builder._run_project_command(
                f"node supervision_fixture.js {mode}",
                str(self.project),
                str(self.project),
                timeout=timeout,
                output_limit_bytes=output_limit_bytes,
                graceful_shutdown_seconds=0.15,
                force_shutdown_seconds=1.0,
                reader_shutdown_seconds=0.3,
            ),
            timeout=5.0,
        )
        self.assertLess(time.monotonic() - started, 5.0)
        return result

    def assert_timeout_clean(self, result):
        self.assertTrue(result.timed_out)
        self.assertIsNone(result.exit_code)
        self.assertTrue(result.process_started)
        self.assertTrue(result.termination_attempted)
        self.assertTrue(result.termination_succeeded, result.cleanup_errors)
        self.assertTrue(result.cleanup_completed, result.cleanup_errors)
        self.assertFalse(project_builder._pid_exists(result.process_id or -1))
        self.assertNotIn(result.process_id, project_builder._owned_process_registry)

    @staticmethod
    def child_pids(output):
        return [int(value) for value in re.findall(r"CHILD_PID=(\d+)", output)]

    async def test_a_no_output_times_out_and_returns(self):
        result = await self.run_mode("no-output")
        self.assert_timeout_clean(result)

    async def test_b_infinite_stdout_does_not_block(self):
        result = await self.run_mode("stdout")
        self.assert_timeout_clean(result)
        self.assertGreater(len(result.stdout), 0)

    async def test_c_infinite_stderr_does_not_block(self):
        result = await self.run_mode("stderr")
        self.assert_timeout_clean(result)
        self.assertGreater(len(result.stderr), 0)

    async def test_d_child_with_inherited_pipes_is_terminated(self):
        result = await self.run_mode("child-inherits", timeout=0.5)
        self.assert_timeout_clean(result)
        child_pids = self.child_pids(result.stdout)
        self.assertTrue(child_pids)
        self.assertGreaterEqual(result.descendant_count, 1)
        self.assertFalse(any(project_builder._pid_exists(pid) for pid in child_pids))

    async def test_e_parent_exit_does_not_leave_descendant_pipe_open(self):
        result = await self.run_mode("parent-exits", timeout=2.0)
        self.assertTrue(result.ok, result.output)
        self.assertFalse(result.timed_out)
        child_pids = self.child_pids(result.stdout)
        self.assertTrue(child_pids)
        self.assertFalse(any(project_builder._pid_exists(pid) for pid in child_pids))
        self.assertTrue(result.cleanup_completed, result.cleanup_errors)

    @unittest.skipUnless(os.name == "nt", "Force-path assertion targets Windows process groups")
    async def test_f_failed_graceful_stop_reaches_force_cleanup(self):
        with self.assertLogs(project_builder.logger, level="DEBUG") as captured:
            with patch.object(project_builder.os, "kill", side_effect=OSError("graceful blocked")):
                result = await self.run_mode("ignore-stop", timeout=0.5)
        self.assert_timeout_clean(result)
        self.assertTrue(any("process.force_stop" in line for line in captured.output))
        self.assertFalse(any(project_builder._pid_exists(pid) for pid in self.child_pids(result.stdout)))

    async def test_g_blocked_reader_task_is_cancelled_finitely(self):
        cleanup_errors = []
        blocked = asyncio.create_task(asyncio.Event().wait())
        await project_builder._cancel_task_finitely(blocked, 0.2, cleanup_errors, "test_reader")
        self.assertTrue(blocked.done())
        self.assertTrue(blocked.cancelled())
        self.assertEqual(cleanup_errors, [])

    async def test_h_output_is_truncated_while_pipe_is_drained(self):
        result = await self.run_mode("stdout", timeout=0.5, output_limit_bytes=1024)
        self.assert_timeout_clean(result)
        self.assertTrue(result.stdout_truncated)
        self.assertIn("output truncated", result.stdout)
        self.assertLessEqual(len(result.stdout.encode("utf-8")), 1400)

    async def test_i_no_runner_tasks_remain_pending(self):
        baseline = set(asyncio.all_tasks())
        result = await self.run_mode("no-output")
        self.assert_timeout_clean(result)
        await asyncio.sleep(0)
        leaked = [
            task for task in asyncio.all_tasks()
            if task not in baseline and not task.done()
        ]
        self.assertEqual(leaked, [])

    async def test_j_no_owned_pid_or_registry_entry_remains(self):
        result = await self.run_mode("child-inherits", timeout=0.5)
        self.assert_timeout_clean(result)
        self.assertEqual(project_builder._owned_process_registry, {})
        self.assertFalse(any(project_builder._pid_exists(pid) for pid in self.child_pids(result.stdout)))

    async def test_k_timeout_exit_code_is_none_even_after_shell_kill(self):
        result = await self.run_mode("no-output")
        self.assert_timeout_clean(result)
        self.assertIsNone(result.exit_code)

    async def test_l_normal_command_still_works(self):
        result = await self.run_mode("normal", timeout=2.0)
        self.assertTrue(result.ok, result.output)
        self.assertEqual(result.exit_code, 0)
        self.assertFalse(result.timed_out)
        self.assertIn("NORMAL_OK", result.stdout)
        self.assertTrue(result.cleanup_completed, result.cleanup_errors)
        self.assertFalse(project_builder._pid_exists(result.process_id or -1))


if __name__ == "__main__":
    unittest.main()
