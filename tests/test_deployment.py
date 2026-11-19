"""Exercise artifact boundaries and atomic deployment recovery without production."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('receiver', Path(__file__).parents[1] / 'deploy/receive.py')
receiver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receiver)
COMMIT = 'a' * 40


def artifact(extra=None, commit=COMMIT):
    content = {name: b'asset' for name in receiver.REQUIRED_FILES}
    content['release.json'] = json.dumps({'commit': commit}).encode()
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as bundle:
        for name, data in content.items():
            item = tarfile.TarInfo('./' + name)
            item.size = len(data)
            bundle.addfile(item, io.BytesIO(data))
        if extra:
            bundle.addfile(extra)
    return stream.getvalue()


class ArtifactTests(unittest.TestCase):
    def extract(self, data):
        with tempfile.TemporaryDirectory() as temporary:
            receiver.extract_static(data, Path(temporary), COMMIT)

    def test_valid_artifact(self):
        self.extract(artifact())

    def test_rejects_traversal_and_absolute_paths(self):
        for name in ('../outside.html', '/tmp/outside.html', 'assets/../../outside.js', '.ssh/authorized_keys'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.extract(artifact(tarfile.TarInfo(name)))

    def test_rejects_links_and_devices(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE):
            item = tarfile.TarInfo('assets/link.js')
            item.type = kind
            item.linkname = '/etc/passwd'
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.extract(artifact(item))

    def test_rejects_duplicate_files_and_server_code(self):
        for name in ('index.html', 'server.py'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.extract(artifact(tarfile.TarInfo(name)))

    def test_rejects_wrong_revision(self):
        with self.assertRaisesRegex(ValueError, 'revision'):
            self.extract(artifact(commit='b' * 40))

    def test_rejects_oversized_expansion(self):
        with patch.object(receiver, 'MAX_EXPANDED', 1), self.assertRaisesRegex(ValueError, 'too large'):
            self.extract(artifact())


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.runtime = Path(self.temporary.name)
        self.previous = self.runtime / 'releases' / 'previous'
        self.previous.mkdir(parents=True)
        (self.runtime / 'current').symlink_to(self.previous)
        self.data = artifact()
        self.digest = hashlib.sha256(self.data).hexdigest()

    def publish(self):
        receiver.publish(self.data, COMMIT, self.digest, self.runtime)

    @patch.object(receiver, 'verify_live')
    @patch.object(receiver, 'main_commit', return_value=COMMIT)
    def test_success_and_repeat_are_safe(self, main, health):
        self.publish()
        target = (self.runtime / 'current').resolve()
        self.assertNotEqual(target, self.previous)
        self.assertEqual(json.loads((target / 'release.json').read_text())['commit'], COMMIT)
        self.publish()
        self.assertEqual((self.runtime / 'current').resolve(), target)
        self.assertTrue(self.previous.exists())

    @patch.object(receiver.time, 'sleep')
    @patch.object(receiver, 'verify_live', side_effect=ValueError('failed health check'))
    @patch.object(receiver, 'main_commit', return_value=COMMIT)
    def test_health_failure_restores_previous(self, main, health, sleep):
        with self.assertRaisesRegex(ValueError, 'failed health check'):
            self.publish()
        self.assertEqual((self.runtime / 'current').resolve(), self.previous)

    @patch.object(receiver, 'verify_live', side_effect=SystemExit(143))
    @patch.object(receiver, 'main_commit', return_value=COMMIT)
    def test_interrupted_verification_restores_previous(self, main, health):
        with self.assertRaises(SystemExit):
            self.publish()
        self.assertEqual((self.runtime / 'current').resolve(), self.previous)

    @patch.object(receiver, 'main_commit', return_value='b' * 40)
    def test_stale_deployment_leaves_current_untouched(self, main):
        with self.assertRaisesRegex(ValueError, 'superseded'):
            self.publish()
        self.assertEqual((self.runtime / 'current').resolve(), self.previous)

    @patch.object(receiver, 'main_commit', side_effect=[COMMIT, 'b' * 40])
    def test_new_commit_during_unpack_leaves_current_untouched(self, main):
        with self.assertRaisesRegex(ValueError, 'newer commit'):
            self.publish()
        self.assertEqual((self.runtime / 'current').resolve(), self.previous)

    def test_checksum_failure_leaves_current_untouched(self):
        self.digest = '0' * 64
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.publish()
        self.assertEqual((self.runtime / 'current').resolve(), self.previous)


if __name__ == '__main__':
    unittest.main()
