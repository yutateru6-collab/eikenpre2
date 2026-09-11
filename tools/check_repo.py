#!/usr/bin/env python3
"""Offline repository integrity check; external URLs and meanings are not validated."""
import ast
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    errors = []
    profile = json.loads((ROOT / 'config/exam_profile.json').read_text(encoding='utf-8'))
    specs = profile['template']['sections']
    expected = [('p1', 15), ('p2', 5), ('p3', 2), ('p4a', 3), ('p4b', 4)]
    if [(s['id'], sum(s['questions_per_unit'])) for s in specs] != expected:
        errors.append('section allocations differ from the documented PRE2 baseline')
    if profile['grade'] != 'pre2' or profile['skill'] != 'reading':
        errors.append('grade/skill must be pre2/reading')
    if [n for s in specs for n in s['numbers']] != list(range(1, 30)):
        errors.append('section numbers must cover 1..29 in order')
    if specs[1]['questions_per_unit'] != [1, 1, 1, 2]:
        errors.append('dialogue blank distribution must be 1,1,1,2')
    if profile['official']['reading_questions'] != 29 or profile['official']['choices_per_question'] != 4:
        errors.append('official count constants differ from baseline')
    if profile['official']['time_scope'] != 'reading_and_writing':
        errors.append('80 minutes must not be labeled Reading alone')
    pages = profile['template']['reading_pages']
    if len(pages) != 7 or [n for p in pages for n in p.get('numbers', [])] != list(range(1, 30)):
        errors.append('seven-page model must cover 1..29 once')
    links = 0
    for path in ROOT.rglob('*.md'):
        text = path.read_text(encoding='utf-8')
        for target in re.findall(r'\]\(([^)]+)\)', text):
            target = target.split()[0]
            if urlparse(target).scheme or target.startswith('#'):
                continue
            dest = unquote(target.split('#', 1)[0])
            if not (path.parent / dest).is_file():
                errors.append(f'{path.relative_to(ROOT)}: broken link {target}')
            links += 1
    for path in ROOT.rglob('*.py'):
        try:
            ast.parse(path.read_text(encoding='utf-8'))
        except SyntaxError as exc:
            errors.append(f'{path.relative_to(ROOT)}: {exc}')
    print(json.dumps({'repository_integrity_pass': not errors, 'relative_links_checked': links, 'errors': errors, 'not_checked': ['external_URL_availability', 'semantic_quality', 'generated_DOCX_PDF']}, ensure_ascii=False, indent=2))
    return int(bool(errors))


if __name__ == '__main__':
    sys.exit(main())
