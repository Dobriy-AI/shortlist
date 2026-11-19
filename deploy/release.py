"""Send a local, checked build through the same restricted release receiver as CI."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile

project = Path(__file__).resolve().parents[1]

def git(*args):
    return subprocess.check_output(['git', *args], cwd=project, text=True).strip()

subprocess.run(['workspace-run', '--check'], check=True)
if git('status', '--porcelain'):
    raise SystemExit('Commit source changes before publishing.')
subprocess.run(['git', 'fetch', 'origin', 'main'], cwd=project, check=True)
commit = git('rev-parse', 'HEAD')
if git('rev-parse', 'origin/main') != commit:
    raise SystemExit('Push this commit to origin/main before publishing.')
if json.loads((project / 'dist/release.json').read_text())['commit'] != commit:
    raise SystemExit('Build again after committing.')
stream = io.BytesIO()
with tarfile.open(fileobj=stream, mode='w:gz') as bundle:
    bundle.add(project / 'dist', arcname='.')
archive = stream.getvalue()
digest = hashlib.sha256(archive).hexdigest()
subprocess.run(
    ['/usr/bin/python3', '/usr/local/lib/shortlist/receive.py'],
    input=archive,
    env={**os.environ, 'SSH_ORIGINAL_COMMAND': f'deploy {commit} {digest}'},
    check=True,
)
