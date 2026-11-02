import importlib.util
import os
from pathlib import Path
import pty
import select
import shlex
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = f"source {shlex.quote(str(ROOT / 'src/update'))}\n"


class HookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        metadata = self.home / '.codex/packages/app-server-daemon/current/codex-package.json'
        metadata.parent.mkdir(parents=True)
        metadata.write_text('{}')
        self.metadata = metadata
        self.stub = SOURCE + r'''
getent() {
    case "$2" in
        alice) printf 'alice:x:1001:1001::%s:/bin/bash\n' "$FIXTURE_HOME" ;;
        bob) printf 'bob:x:1002:1002::%s:/bin/bash\n' "$FIXTURE_HOME" ;;
        root) printf 'root:x:0:0::/root:/bin/bash\n' ;;
        *) return 2 ;;
    esac
}
cmp() { [[ ${MATCHING:-0} == 1 ]]; }
pgrep() { [[ ${RUNNING:-0} == 1 ]]; }
systemd-run() {
    printf 'UPDATE_REQUESTED\n'
    printf '%s\n' "$@"
    [[ ${FAIL_UPDATE:-0} != 1 ]]
}
'''

    def run_hook(self, command, **env):
        return subprocess.run(['bash', '-c', self.stub + command], text=True,
                              capture_output=True, start_new_session=True,
                              env=dict(os.environ, FIXTURE_HOME=str(self.home), **env))

    def test_stopped_updates_with_resolved_identity(self):
        result = self.run_hook('process_user alice')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--uid=1001', result.stdout)
        self.assertIn('--gid=1001', result.stdout)
        self.assertIn('--unit=codex-daemon-update-hook-1001', result.stdout)
        self.assertIn('--setenv=HOME=' + str(self.home), result.stdout)
        self.assertIn('--from-cli', result.stdout)

    def test_matching_package_skips(self):
        result = self.run_hook('process_user alice', MATCHING='1')
        self.assertEqual(result.returncode, 0)
        self.assertNotIn('UPDATE_REQUESTED', result.stdout)

    def test_missing_daemon_skips(self):
        self.metadata.unlink()
        result = self.run_hook('process_user alice')
        self.assertEqual(result.returncode, 0)
        self.assertNotIn('UPDATE_REQUESTED', result.stdout)

    def test_running_without_terminal_skips(self):
        result = self.run_hook('process_user alice', RUNNING='1')
        self.assertEqual(result.returncode, 0)
        self.assertIn('no interactive terminal', result.stdout)
        self.assertNotIn('UPDATE_REQUESTED', result.stdout)

    def test_update_failure_reports_journal(self):
        result = self.run_hook('process_user alice', FAIL_UPDATE='1')
        self.assertEqual(result.returncode, 1)
        self.assertIn('journalctl -u codex-daemon-update-hook-1001.service', result.stderr)

    def test_invalid_and_root_accounts_rejected(self):
        for user in ['missing', 'root', '-bad', 'alice;id']:
            with self.subTest(user=user):
                result = self.run_hook('process_user ' + shlex.quote(user))
                self.assertEqual(result.returncode, 1)
                self.assertNotIn('UPDATE_REQUESTED', result.stdout)

    def test_config_continues_after_failure_and_deduplicates(self):
        config = self.home/'users'
        config.write_text('# comment\n\nmissing\nalice\nalice # duplicate\nbob\n')
        result = self.run_hook('process_config ' + shlex.quote(str(config)))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.count('UPDATE_REQUESTED'), 2)

    def test_config_rejects_extra_fields_and_reads_last_line(self):
        config = self.home/'users'
        config.write_text('alice bob\nbob')
        result = self.run_hook('process_config ' + shlex.quote(str(config)))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.count('UPDATE_REQUESTED'), 1)

    def test_empty_or_absent_config(self):
        config = self.home/'users'
        for contents in [None, '# comments only\n\n']:
            if contents is not None:
                config.write_text(contents)
            result = self.run_hook('process_config ' + shlex.quote(str(config)))
            self.assertEqual(result.returncode, 0)
            self.assertNotIn('UPDATE_REQUESTED', result.stdout)

    def prompt(self, reply, **changes):
        pid, fd = pty.fork()
        if pid == 0:
            env = dict(os.environ, TERM='xterm-256color', RUNNING='1', FIXTURE_HOME=str(self.home))
            env.pop('NO_COLOR', None)
            env.update(changes)
            os.execve('/bin/bash', ['bash', '-c', self.stub + 'process_user alice'], env)
        output = b''
        sent = False
        deadline = time.monotonic() + 5
        try:
            while time.monotonic() < deadline:
                if not select.select([fd], [], [], .1)[0]:
                    continue
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                output += chunk
                if b'[y/N]' in output and not sent:
                    os.write(fd, reply)
                    sent = True
            else:
                os.kill(pid, 9)
                self.fail('Prompt timed out')
            _, status = os.waitpid(pid, 0)
            self.assertEqual(status, 0, output)
            return output
        finally:
            os.close(fd)

    def test_prompt_choices_and_eof(self):
        for reply, approved in [(b'y\n', True), (b'YES\n', True), (b'n\n', False),
                                (b'\n', False), (b'\x04', False), (b'maybe\n', False)]:
            with self.subTest(reply=reply):
                output = self.prompt(reply)
                self.assertEqual(b'UPDATE_REQUESTED' in output, approved)
                self.assertIn(b'\x1b[1;33m', output)
                self.assertIn(b'UPDATE: alice', output)

    def test_no_colour_and_dumb_terminal(self):
        for changes in [{'NO_COLOR': '1'}, {'TERM': 'dumb'}]:
            with self.subTest(changes=changes):
                self.assertNotIn(b'\x1b[', self.prompt(b'\n', **changes))


spec = importlib.util.spec_from_file_location('version', ROOT/'scripts/version.py')
version = importlib.util.module_from_spec(spec)
spec.loader.exec_module(version)


class VersionTests(unittest.TestCase):
    def test_initial_version(self):
        self.assertEqual(version.next_version([], 'feat: initial package'), '0.1.0')

    def test_semantic_bumps(self):
        for message, expected in [('fix: error handling', '0.1.1'),
                                  ('feat(users): configuration', '0.2.0'),
                                  ('feat!: configuration format', '1.0.0'),
                                  ('change\nBREAKING CHANGE: config', '1.0.0')]:
            self.assertEqual(version.next_version(['v0.1.0', 'unrelated'], message), expected)
