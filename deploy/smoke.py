"""Read-only production verification from a GitHub-hosted runner."""
import re
import sys
from receive import verify_live

if len(sys.argv) != 2 or not re.fullmatch(r'[0-9a-f]{40}', sys.argv[1]):
    raise SystemExit('Usage: python3 deploy/smoke.py <commit-sha>')
verify_live(sys.argv[1])
print(f'HTTPS, public release identity, page content, styles, script and font verified for {sys.argv[1]}.')
