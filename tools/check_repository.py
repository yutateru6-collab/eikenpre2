#!/usr/bin/env python3
"""Check repository consistency, not the pedagogical quality of any worksheet."""
from pathlib import Path
import json
import re
import sys
ROOT = Path(__file__).resolve().parents[1]


def check_repository() -> list[str]:
    errors = []
    required = ['README.md', 'AGENTS.md', 'MASTER_PROMPT.md', 'LAYOUT_MASTER_PROMPT.md',
                'specs/pre2_reading.json', 'references/OFFICIAL_PRE2_ANALYSIS.md',
                'references/official_pre2_observations.json',
                'references/EIKEN_PRE2_LAYOUT_REFERENCE.md', 'references/OFFICIAL_DISTRACTOR_CASEBOOK.md',
                'rules/DISTRACTOR_DESIGN.md', 'rules/FAMOUS_EPISODE_POLICY.md',
                'rules/NATURAL_JAPANESE_TRANSLATION.md', 'docs/DATA_CONTRACT.md',
                'docs/DESIGN_REVIEW.md', 'templates/REQUEST_TEMPLATE.md', 'CHANGELOG.md',
                'tools/validate_pack.py', 'tests/test_validation.py', '.github/workflows/validate.yml']
    for path in required:
        if not (ROOT / path).is_file():
            errors.append(f'missing {path}')
    if errors:
        return errors
    spec = json.loads((ROOT / 'specs/pre2_reading.json').read_text())
    observations = json.loads((ROOT / 'references/official_pre2_observations.json').read_text())
    numbers = [n for p in spec['parts'] for n in p['question_ids']]
    if numbers != list(range(1, 30)) or spec['total_questions'] != 29:
        errors.append('profile does not define the Pre-2 29-question baseline')
    if spec['grade'] != 'pre2' or spec['choices_per_question'] != 4:
        errors.append('wrong grade or number of choices')
    for p in spec['parts']:
        if sum(p['questions_per_unit']) != len(p['question_ids']):
            errors.append(f'inconsistent unit counts: {p["id"]}')
    if len(spec['reading_page_model']) != 7:
        errors.append('reading page model must contain seven pages')
    if len(observations['exams']) != observations['sample_size_exams']:
        errors.append('inconsistent observation sample size')
    for exam in observations['exams']:
        if sum(exam['answer_position_counts'].values()) != 29:
            errors.append(f'wrong answer distribution sum: {exam["exam"]}')
        for part in exam['parts'].values():
            if sum(part['printed_paragraph_words']) != part['printed_body_words']:
                errors.append(f'wrong paragraph sum: {exam["exam"]}')
            if part['completed_body_words'] < part['printed_body_words']:
                errors.append(f'completed count smaller than printed: {exam["exam"]}')
    for path in ROOT.rglob('*.md'):
        content = path.read_text(encoding='utf-8')
        for target in re.findall(r'\]\(([^)]+)\)', content):
            if re.match(r'^(https?://|mailto:|#)', target):
                continue
            destination = (path.parent / target.split('#')[0]).resolve()
            if not destination.is_relative_to(ROOT) or not destination.exists():
                errors.append(f'{path.relative_to(ROOT)}: broken local link {target}')
    return errors


if __name__ == '__main__':
    try:
        problems = check_repository()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        problems = [f'invalid repository data: {exc}']
    print(json.dumps({'repository_checks_ok': not problems, 'errors': problems}, ensure_ascii=False, indent=2))
    sys.exit(1 if problems else 0)
