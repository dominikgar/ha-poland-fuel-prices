"""Publish the manifest version only after all integration checks pass."""
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

manifest = json.loads(Path('custom_components/poland_fuel_prices/manifest.json').read_text())
tag = 'v' + manifest['version']
base = f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/releases"
headers = {'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
           'Accept': 'application/vnd.github+json',
           'X-GitHub-Api-Version': '2022-11-28'}

try:
    with urllib.request.urlopen(urllib.request.Request(base + '/tags/' + tag,
                                headers=headers), timeout=30):
        print(f'{tag} is already published; leaving it unchanged.')
except urllib.error.HTTPError as error:
    if error.code != 404:
        raise
    changelog = Path('CHANGELOG.md').read_text()
    section = changelog.split('## ' + manifest['version'] + ' ', 1)[1]
    notes = section.split('\n', 1)[1].split('\n## ', 1)[0].strip()
    payload = {'tag_name': tag, 'target_commitish': os.environ['GITHUB_SHA'],
               'name': 'Poland Fuel Prices ' + manifest['version'],
               'body': notes, 'draft': False, 'prerelease': False}
    request = urllib.request.Request(base, headers={**headers, 'Content-Type': 'application/json'},
                                     data=json.dumps(payload).encode(), method='POST')
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.load(response)
    print(release['html_url'])
