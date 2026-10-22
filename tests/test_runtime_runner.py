"""Exercise disposable runtime selection through the existing runner CLI."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAKE_DOCKER = r'''
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
fixture = sys.stdin.read() if 'shell' in args else None
with Path(os.environ['FAKE_DOCKER_LOG']).open('a') as stream:
    stream.write(json.dumps({'args': args, 'image': os.environ.get('ODOO_REVOLUT_BASE_IMAGE'),
                             'version': os.environ.get('ODOO_REVOLUT_ODOO_VERSION'),
                             'addons_dir': os.environ.get('ODOO_REVOLUT_ADDONS_DIR'),
                             'fixture': fixture}) + '\n')
if 'dpkg-query' in args:
    print(os.environ.get('FAKE_ODOO_VERSION', os.environ['ODOO_REVOLUT_ODOO_VERSION']), end='')
elif 'psql' in args:
    print('absent' if 'pos_revolut_restaurant' in args[-1] else 'installed')
'''


class TestRuntimeRunner(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='revolut-runtime-runner-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        binary = self.root / 'docker'
        binary.write_text(f'#!{sys.executable}\n' + FAKE_DOCKER)
        binary.chmod(0o755)
        self.log = self.root / 'docker.jsonl'
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith('ODOO_REVOLUT_')}
        self.env.update(PATH=f'{self.root}:{os.environ["PATH"]}', FAKE_DOCKER_LOG=str(self.log))

    def run_script(self, name='test-addon', *args, **environment):
        return subprocess.run([str(ROOT / 'scripts' / name), *args],
                              env={**self.env, **environment}, text=True,
                              capture_output=True, timeout=10)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_default_18_and_explicit_19_verify_the_selected_package(self):
        for major, version in ((None, '18.0.20261015'), ('19', '19.0.20260908')):
            with self.subTest(major=major):
                self.log.unlink(missing_ok=True)
                result = self.run_script(**({'ODOO_REVOLUT_ODOO_MAJOR': major} if major else {}))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(all(row['version'] == version for row in self.calls()))
                self.assertTrue(all('@sha256:' in row['image'] for row in self.calls()))
                self.assertTrue(any('verify_merchant_http_guard.py' in ' '.join(row['args'])
                                    for row in self.calls()))
                self.assertTrue(any('import websocket' in row['args'] for row in self.calls()))

    def test_wrong_package_stops_before_addon_installation(self):
        result = self.run_script(FAKE_ODOO_VERSION='18.0.other')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Expected Odoo 18.0.20261015', result.stderr)
        self.assertFalse(any('--init' in row['args'] for row in self.calls()))

    def test_fresh_delivered_scenario_retains_default_and_honors_selected_tests(self):
        for selected in (None, '/pos_revolut:InstallSlice'):
            with self.subTest(selected=selected):
                self.log.unlink(missing_ok=True)
                flags = ['--test-tags', selected] if selected else []
                result = self.run_script('test-addon', '--delivered-scenario', 'retail', *flags)
                self.assertEqual(result.returncode, 0, result.stderr)
                acceptance = [row['args'] for row in self.calls() if '--test-tags' in row['args']]
                self.assertEqual(len(acceptance), 1)
                tags = acceptance[0][acceptance[0].index('--test-tags') + 1]
                if selected:
                    self.assertEqual(tags, selected)
                else:
                    self.assertIn('TestRestaurantConsolidation', tags)

    def test_populated_database_is_checked_after_first_install_and_update(self):
        addons = self.root / 'addons'
        fixtures = addons / 'pos_revolut' / 'tests'
        fixtures.mkdir(parents=True)
        (fixtures / 'native_install_seed.py').write_text('native seed')
        (fixtures / 'native_install_verify.py').write_text('native verify')
        (fixtures / 'candidate_update_seed.py').write_text('candidate seed')
        (fixtures / 'candidate_update_verify.py').write_text('candidate verify')
        result = self.run_script('test-addon', '--verify-install-upgrade',
                                 '--addons-dir', str(addons))
        self.assertEqual(result.returncode, 0, result.stderr)
        operations = []
        for call in self.calls():
            args = call['args']
            if call['fixture'] is not None:
                operations.append(call['fixture'])
                self.assertIn('--no-http', args)
            elif '--init' in args:
                operations.append('install ' + args[args.index('--init') + 1])
            elif '--update' in args:
                operations.append('update ' + args[args.index('--update') + 1])
        self.assertEqual(operations, ['install point_of_sale,pos_restaurant', 'native seed',
                                     'install pos_revolut', 'native verify', 'candidate seed',
                                     'update pos_revolut', 'native verify', 'candidate verify'])

    def test_populated_delivered_artifact_preserves_records_and_selected_tests(self):
        repository = self.root / 'release-source'
        scripts = repository / 'scripts'
        scripts.mkdir(parents=True)
        for name in ('test-delivered-addon', 'test-addon', 'odoo-runtime', 'deploy-addon-remote'):
            shutil.copy2(ROOT / 'scripts' / name, scripts / name)
        addon = repository / 'addons' / 'pos_revolut'
        fixtures = addon / 'tests'
        fixtures.mkdir(parents=True)
        (addon / '__manifest__.py').write_text("{'name': 'Artifact fixture', 'version': '18.0.1.0.0'}")
        for name in ('native_install_seed', 'native_install_verify',
                     'candidate_update_seed', 'candidate_update_verify'):
            (fixtures / f'{name}.py').write_text(name)
        for command in (['init', '--quiet'], ['add', '.'],
                        ['-c', 'user.name=Runtime test', '-c', 'user.email=runtime@example.invalid',
                         'commit', '--quiet', '-m', 'Fixture artifact']):
            subprocess.run(['git', '-C', str(repository), *command], check=True,
                           capture_output=True)
        revision = subprocess.check_output(['git', '-C', str(repository), 'rev-parse', 'HEAD'],
                                           text=True).strip()
        for fixture in fixtures.iterdir():
            fixture.write_text('Uncommitted source must not be used')
        result = subprocess.run([str(scripts / 'test-delivered-addon'), '--revision', revision,
                                 '--scenario', 'populated', '--test-tags', '/pos_revolut:InstallSlice'],
                                env=self.env, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f'Artifact revision: {revision}', result.stdout)
        self.assertIn('Artifact SHA256:', result.stdout)
        self.assertTrue(all(row['addons_dir'] != str(repository / 'addons')
                            for row in self.calls()))
        self.assertEqual([row['fixture'] for row in self.calls() if row['fixture']],
                         ['native_install_seed', 'native_install_verify', 'candidate_update_seed',
                          'native_install_verify', 'candidate_update_verify'])
        acceptance = [row['args'] for row in self.calls()
                      if '--test-tags' in row['args']]
        self.assertEqual(len(acceptance), 2)
        for args in acceptance:
            self.assertEqual(args[args.index('--test-tags') + 1], '/pos_revolut:InstallSlice')

    def test_unsupported_major_is_rejected_before_docker(self):
        result = self.run_script(ODOO_REVOLUT_ODOO_MAJOR='20')
        self.assertEqual(result.returncode, 2)
        self.assertIn('18 or 19', result.stderr)
        self.assertEqual(self.calls(), [])

    def test_18_refuses_19_historical_upgrade_before_docker(self):
        result = self.run_script('test-historical-upgrade', 'cart-authority',
                                 ODOO_REVOLUT_ODOO_MAJOR='18')
        self.assertEqual(result.returncode, 2)
        self.assertIn('Odoo 19 history', result.stderr)
        self.assertEqual(self.calls(), [])

    def test_18_refuses_delivered_19_migration_before_docker(self):
        result = self.run_script(
            'test-delivered-addon', '--revision', 'a' * 40, '--scenario', 'migration',
            '--migration-from', 'b' * 40)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Odoo 19 history', result.stderr)
        self.assertEqual(self.calls(), [])


if __name__ == '__main__':
    unittest.main()
