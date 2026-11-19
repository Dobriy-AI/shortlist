"""Restricted SSH command for publishing static Shortlist artifacts.

Install this file as root-owned /usr/local/lib/shortlist/receive.py.
Never execute a deployment script supplied inside an uploaded artifact.
"""
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.request import Request, urlopen

RUNTIME = Path('/srv/workspace/users/1000/shortlist-runtime')
SITE = 'https://fundings.wiki'
MAX_ARCHIVE = 20 * 1024 * 1024
MAX_EXPANDED = 50 * 1024 * 1024
MAX_MEMBERS = 2000
ALLOWED_SUFFIXES = {'.html', '.css', '.js', '.json', '.woff2', '.png', '.svg', '.txt', '.xml', '.ts', '.map'}
REQUIRED_FILES = {'index.html', 'style.css', 'main.js', 'release.json', 'interface-style/landing.css', 'interface-style/fonts/poppins-400.woff2'}


def get_url(url):
    request = Request(url, headers={'User-Agent': 'Shortlist-deployment', 'Cache-Control': 'no-cache'})
    with urlopen(request, timeout=8) as response:
        if response.status != 200:
            raise ValueError(f'HTTP check failed for {url}')
        return response.read(MAX_EXPANDED)


def main_commit():
    data = json.loads(get_url('https://api.github.com/repos/Dobriy-AI/shortlist/git/ref/heads/main'))
    return data['object']['sha']


def verify_live(commit):
    release = json.loads(get_url(f'{SITE}/release.json?deployment={commit}'))
    if release.get('commit') != commit:
        raise ValueError('The public site is not serving the expected commit')
    if b'Shortlist' not in get_url(f'{SITE}/?deployment={commit}'):
        raise ValueError('The landing page did not load')
    for asset in ('/style.css', '/main.js', '/interface-style/landing.css', '/interface-style/fonts/poppins-400.woff2'):
        if not get_url(f'{SITE}{asset}?deployment={commit}'):
            raise ValueError(f'Empty asset: {asset}')
    if get_url(f'{SITE}/healthz').strip() != b'ok':
        raise ValueError('The web service is not healthy')


def extract_static(archive, destination, commit):
    """Extract only bounded, regular static files into a new empty directory."""
    seen = set()
    total = 0
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as bundle:
        for number, member in enumerate(bundle):
            if number >= MAX_MEMBERS:
                raise ValueError('Too many archive entries')
            name = member.name
            while name.startswith('./'):
                name = name[2:]
            if name in ('', '.') and member.isdir():
                continue
            parts = PurePosixPath(name).parts
            if not parts or name.startswith('/') or '\\' in name or any(part.startswith('.') for part in parts):
                raise ValueError('Unsafe archive path')
            normalized = '/'.join(parts)
            if normalized in seen:
                raise ValueError('Duplicate archive path')
            seen.add(normalized)
            if len(normalized) > 240 or not (member.isdir() or member.isfile()):
                raise ValueError('Only regular static files and directories are allowed')
            target = destination.joinpath(*parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True, mode=0o755)
                continue
            if target.suffix.lower() not in ALLOWED_SUFFIXES or member.size < 0:
                raise ValueError('Unsupported file type')
            total += member.size
            if total > MAX_EXPANDED:
                raise ValueError('Expanded archive is too large')
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            with bundle.extractfile(member) as source, target.open('xb') as output:
                shutil.copyfileobj(source, output)
            target.chmod(0o644)
    if not REQUIRED_FILES.issubset(seen):
        raise ValueError('Required site assets are missing')
    release = json.loads((destination / 'release.json').read_text())
    if release.get('commit') != commit:
        raise ValueError('Build revision does not match the requested commit')


def point_to(runtime, release):
    candidate = runtime / f'.current-{os.getpid()}'
    try:
        candidate.symlink_to(release, target_is_directory=True)
        candidate.replace(runtime / 'current')
    finally:
        candidate.unlink(missing_ok=True)


def publish(archive, commit, digest, runtime=RUNTIME):
    if not re.fullmatch(r'[0-9a-f]{40}', commit) or not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise ValueError('Invalid commit or checksum')
    if len(archive) > MAX_ARCHIVE or hashlib.sha256(archive).hexdigest() != digest:
        raise ValueError('Artifact size or checksum mismatch')
    if main_commit() != commit:
        raise ValueError('Refusing to deploy a superseded commit')
    releases = runtime / 'releases'
    releases.mkdir(exist_ok=True)
    with (runtime / '.deploy.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = (runtime / 'current').resolve(strict=True)
        if not previous.is_relative_to(releases.resolve()) or not previous.is_dir():
            raise ValueError('Current release is outside the managed release directory')
        target = releases / f'{commit}-{digest[:16]}'
        if not target.exists():
            with tempfile.TemporaryDirectory(prefix='.incoming-', dir=releases) as temporary:
                staging = Path(temporary)
                extract_static(archive, staging, commit)
                staging.chmod(0o755)
                staging.rename(target)
        if main_commit() != commit:
            raise ValueError('A newer commit arrived while preparing deployment')
        try:
            point_to(runtime, target)
            for attempt in range(3):
                try:
                    verify_live(commit)
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    time.sleep(2)
        except BaseException:
            point_to(runtime, previous)
            print(f'Health check failed. Restored {previous.name}.', file=sys.stderr)
            raise
        print(json.dumps({'status': 'deployed', 'commit': commit, 'sha256': digest, 'release': target.name, 'previous': previous.name, 'url': SITE}))


def main():
    match = re.fullmatch(r'deploy ([0-9a-f]{40}) ([0-9a-f]{64})', os.environ.get('SSH_ORIGINAL_COMMAND', ''))
    if not match:
        raise ValueError('This key only accepts a Shortlist deployment artifact')
    def interrupted(signum, frame):
        raise SystemExit(128 + signum)
    for signum in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM, signal.SIGALRM):
        signal.signal(signum, interrupted)
    signal.alarm(180)
    subprocess.run(['/usr/local/bin/workspace-run', '--check'], check=True)
    # No shell, port forwarding, SFTP, arbitrary paths, or uploaded code execution.
    archive = sys.stdin.buffer.read(MAX_ARCHIVE + 1)
    publish(archive, match[1], match[2])


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Deployment rejected: {error}', file=sys.stderr)
        sys.exit(1)
