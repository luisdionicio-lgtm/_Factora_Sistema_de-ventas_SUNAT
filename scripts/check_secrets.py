"""Scan tracked files and every reachable Git blob without printing secrets."""
import re
import subprocess
import sys

PATTERNS = [
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),
    re.compile(rb'github_pat_[A-Za-z0-9_]{40,}'),
    re.compile(rb'(?i)(?:api[_-]?(?:key|secret)|password|token)\s*[\x22\x27]?\s*[:=]\s*[\x22\x27]([A-Za-z0-9+/=_-]{40,})[\x22\x27]'),
]


def git(*args):
    return subprocess.check_output(['git', *args])


def main():
    problems = set()
    for name in git('ls-files', '-z').decode().split('\0'):
        if not name:
            continue
        if name.startswith(('data/', 'backups/', '.venv/', 'node_modules/')) or name.endswith(('.db', '.pfx', '.p12', '.key')):
            problems.add('Private file tracked: ' + name)
        try:
            from pathlib import Path
            if any(pattern.search(Path(name).read_bytes()) for pattern in PATTERNS):
                problems.add('Potential secret in working file: ' + name)
        except FileNotFoundError:
            pass
    for entry in git('rev-list', '--objects', '--all').decode().splitlines():
        oid, _, name = entry.partition(' ')
        if git('cat-file', '-t', oid).strip() != b'blob':
            continue
        if any(pattern.search(git('cat-file', 'blob', oid)) for pattern in PATTERNS):
            problems.add('Potential secret in history: ' + (name or oid[:12]))
    for problem in sorted(problems):
        print(problem)
    print('Scan failed.' if problems else 'No matching secrets found in tracked files or reachable history.')
    return bool(problems)


if __name__ == '__main__':
    sys.exit(main())
