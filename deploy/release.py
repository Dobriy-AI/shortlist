"""Publish an already validated, committed static build on this server."""
import json
import os
from pathlib import Path
import shutil
import subprocess

project = Path(__file__).resolve().parents[1]
runtime = Path('/srv/workspace/users/1000/shortlist-runtime')

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
release = runtime / 'releases' / commit
release.parent.mkdir(parents=True, exist_ok=True)
if release.exists():
    raise SystemExit(f'Release already exists: {release}')
shutil.copytree(project / 'dist', release)
candidate = runtime / f'.current-{os.getpid()}'
candidate.symlink_to(release, target_is_directory=True)
candidate.replace(runtime / 'current')
print(f'Published {commit} to {release}')
