#!/usr/bin/env python3
"""Structural checks only; this does NOT judge meaning, facts or rendered pages."""
from __future__ import annotations
import argparse
from collections import Counter
from itertools import groupby
import json
from pathlib import Path
import re
import sys
import unicodedata
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / 'specs/pre2_reading.json'
GAP = re.compile(r'\{\{q([1-9][0-9]*)\}\}')
MAX_JSON_BYTES = 8 * 1024 * 1024
FACT_MODES = {'verified_canon', 'verified_nonfiction', 'fictional_context', 'original_fiction'}


def word_count(text: str) -> int:
    """Exclude gap markers; contractions/hyphenated words are one token."""
    text = GAP.sub(' ', text).replace('\u00ad', '-').replace('—', ' ').replace('–', ' ')
    return sum(bool(re.search(r'[A-Za-z0-9]', token)) for token in text.split())


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f'non-finite JSON number: {value}')


def load_json(path: Path) -> Any:
    # Bound the actual read, not only stat(), so oversized/changing files stay bounded.
    with path.open('rb') as source:
        raw = source.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError('JSON file exceeds the 8 MiB input limit')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                      parse_constant=_reject_constant)


def validate_pack(data: Any, spec: dict[str, Any] | None = None) -> dict[str, Any]:
    spec = load_json(SPEC_PATH) if spec is None else spec
    errors: list[str] = []
    warnings: list[str] = []
    unit_metrics: list[dict[str, Any]] = []
    key_rows: list[dict[str, Any]] = []
    seen_units: set[str] = set()
    seen_segments: set[str] = set()
    seen_choices: set[str] = set()
    seen_questions: set[int] = set()

    def check(condition: bool, where: str, message: str) -> None:
        if not condition:
            errors.append(f'{where}: {message}')

    def obj(value: Any, where: str) -> dict[str, Any]:
        check(isinstance(value, dict), where, 'must be an object')
        return value if isinstance(value, dict) else {}

    def array(value: Any, where: str) -> list[Any]:
        check(isinstance(value, list), where, 'must be an array')
        return value if isinstance(value, list) else []

    def text(value: Any, where: str, allow_empty: bool = False) -> str:
        check(isinstance(value, str), where, 'must be a string')
        value = value if isinstance(value, str) else ''
        if not allow_empty:
            check(bool(value.strip()), where, 'must not be empty')
        return value

    def literal_text(value: Any, where: str) -> str:
        value = text(value, where)
        check('{{' not in value and '}}' not in value, where, 'unexpected marker outside an English gap segment')
        return value

    def strings(value: Any, where: str, nonempty: bool = False) -> list[str]:
        values = array(value, where)
        valid = [text(v, f'{where}[{i}]') for i, v in enumerate(values)]
        check(len(set(valid)) == len(valid), where, 'duplicate entries')
        if nonempty:
            check(bool(valid), where, 'at least one entry required')
        return valid

    def unique(value: str, seen: set[str], where: str) -> None:
        if value:
            check(value not in seen, where, 'duplicate ID')
            seen.add(value)

    data = obj(data, 'pack')
    allowed = {'schema_version', 'grade', 'profile', 'scope', 'included_parts', 'theme', 'sources', 'units'}
    check(not (set(data) - allowed), 'pack', 'unknown root field (do not store a separate answer_key)')
    for name in ('schema_version', 'grade', 'profile'):
        check(data.get(name) == spec[name], name, f'must be {spec[name]}')
    literal_text(data.get('theme'), 'theme')
    mode = data.get('scope')
    check(mode in ('full', 'parts'), 'scope', 'must be full or parts')
    part_specs = {p['id']: p for p in spec['parts']}
    selected = strings(data.get('included_parts'), 'included_parts', True)
    check(all(p in part_specs for p in selected), 'included_parts', 'unknown part')
    canonical = [p for p in part_specs if p in selected]
    check(selected == canonical, 'included_parts', 'must be unique and in exam order')
    if mode == 'full':
        check(selected == list(part_specs), 'included_parts', 'full requires all parts')

    source_ids: set[str] = set()
    for i, raw in enumerate(array(data.get('sources'), 'sources')):
        loc = f'sources[{i}]'
        source = obj(raw, loc)
        sid = text(source.get('id'), loc + '.id')
        unique(sid, source_ids, loc + '.id')
        url = text(source.get('url'), loc + '.url')
        try:
            parsed = urlparse(url)
            check(parsed.scheme in ('http', 'https') and bool(parsed.netloc), loc + '.url', 'invalid URL')
        except ValueError:
            errors.append(loc + '.url: invalid URL')
        text(source.get('note'), loc + '.note')

    actual_order: list[str] = []
    part_units: dict[str, list[dict[str, Any]]] = {p: [] for p in part_specs}
    for i, raw in enumerate(array(data.get('units'), 'units')):
        loc = f'units[{i}]'
        unit = obj(raw, loc)
        uid = text(unit.get('id'), loc + '.id')
        unique(uid, seen_units, loc + '.id')
        part = text(unit.get('part'), loc + '.part')
        check(part in selected and part in part_specs, loc, 'part not included/known')
        if part not in part_specs:
            continue
        cfg = part_specs[part]
        actual_order.append(part)
        part_units[part].append(unit)
        check(unit.get('kind') == cfg['kind'], loc + '.kind', 'wrong kind for part')
        fact_mode = text(unit.get('factual_mode'), loc + '.factual_mode')
        check(fact_mode in FACT_MODES, loc + '.factual_mode', 'unknown mode')
        refs = strings(unit.get('source_ids'), loc + '.source_ids', fact_mode.startswith('verified_'))
        check(all(r in source_ids for r in refs), loc + '.source_ids', 'unknown source')
        for field in ('title', 'title_ja'):
            if part in ('p3', 'p4b') or field in unit:
                literal_text(unit.get(field), loc + '.' + field)
        if part == 'p4a':
            mail = obj(unit.get('email'), loc + '.email')
            for field in ('from', 'to', 'date', 'subject', 'greeting', 'closing', 'signature'):
                pair = obj(mail.get(field), loc + '.email.' + field)
                for lang in ('en', 'ja'):
                    literal_text(pair.get(lang), loc + '.email.' + field + '.' + lang)

        segments = array(unit.get('segments'), loc + '.segments')
        check(bool(segments), loc + '.segments', 'no segments')
        if 'paragraphs_per_unit' in cfg:
            check(len(segments) == cfg['paragraphs_per_unit'], loc + '.segments', 'wrong paragraph count')
        if part == 'p2':
            unit_index = len(part_units[part]) - 1
            expected_turns = cfg['observed_turns']
            if unit_index < len(expected_turns) and len(segments) != expected_turns[unit_index]:
                warnings.append(f'{loc}: turn count differs from observed model; review load/layout')
        local_segments: set[str] = set()
        speakers: set[str] = set()
        texts: list[str] = []
        gap_ids: list[int] = []
        for j, raw_segment in enumerate(segments):
            sloc = f'{loc}.segments[{j}]'
            segment = obj(raw_segment, sloc)
            sid = text(segment.get('id'), sloc + '.id')
            unique(sid, seen_segments, sloc + '.id')
            if sid:
                local_segments.add(sid)
            en = text(segment.get('text'), sloc + '.text')
            ja = text(segment.get('ja'), sloc + '.ja')
            check('{{' not in ja and '}}' not in ja, sloc + '.ja', 'unfilled translation marker')
            remainder = GAP.sub('', en)
            check('{{' not in remainder and '}}' not in remainder, sloc + '.text', 'malformed marker')
            found = [int(v) for v in GAP.findall(en)]
            gap_ids.extend(found)
            if part == 'p3':
                check(len(found) == 1, sloc, 'one gap per paragraph required by profile')
            if part == 'p2':
                speaker = literal_text(segment.get('speaker'), sloc + '.speaker')
                if speaker:
                    speakers.add(speaker)
            texts.append(en)
        if part == 'p2':
            check(len(speakers) >= 2, loc + '.segments', 'dialogue needs at least two speakers')

        qids: list[int] = []
        fills: dict[int, str] = {}
        questions = array(unit.get('questions'), loc + '.questions')
        for j, raw_question in enumerate(questions):
            qloc = f'{loc}.questions[{j}]'
            q = obj(raw_question, qloc)
            qid = q.get('id')
            valid_qid = type(qid) is int and qid in cfg['question_ids']
            check(valid_qid, qloc + '.id', 'invalid question number for part')
            if valid_qid:
                check(qid not in seen_questions, qloc + '.id', 'duplicate question')
                seen_questions.add(qid)
                qids.append(qid)
            for field in ('stem', 'stem_ja'):
                stem = text(q.get(field), qloc + '.' + field, allow_empty=cfg['gap'])
                if cfg['gap']:
                    check(stem == '', qloc + '.' + field, 'gap question stem must be empty')
                check('{{' not in stem and '}}' not in stem, qloc + '.' + field, 'unexpected marker')
            choices = array(q.get('choices'), qloc + '.choices')
            check(len(choices) == spec['choices_per_question'], qloc + '.choices', 'exactly four required')
            cids: list[str] = []
            ctexts: list[str] = []
            for k, raw_choice in enumerate(choices):
                cloc = f'{qloc}.choices[{k}]'
                choice = obj(raw_choice, cloc)
                cid = text(choice.get('id'), cloc + '.id')
                unique(cid, seen_choices, cloc + '.id')
                cids.append(cid)
                en = text(choice.get('text'), cloc + '.text')
                ja = text(choice.get('ja'), cloc + '.ja')
                check('{{' not in en + ja and '}}' not in en + ja, cloc, 'unexpected marker')
                ctexts.append(en)
            normalized = [' '.join(unicodedata.normalize('NFKC', s).casefold().split()) for s in ctexts]
            check(len(set(normalized)) == len(normalized), qloc + '.choices', 'duplicate choice text')
            answer = text(q.get('answer_choice_id'), qloc + '.answer_choice_id')
            check(answer in cids and cids.count(answer) == 1, qloc, 'answer must identify one choice')
            if valid_qid and answer in cids and cids.count(answer) == 1:
                index = cids.index(answer)
                fills[qid] = ctexts[index]
                key_rows.append({'question': qid, 'choice_id': answer, 'answer': index + 1})
            literal_text(q.get('explanation_ja'), qloc + '.explanation_ja')
            evidence = strings(q.get('evidence_segment_ids'), qloc + '.evidence_segment_ids', True)
            check(all(s in local_segments for s in evidence), qloc, 'evidence must refer to this unit')
            notes = array(q.get('distractor_notes'), qloc + '.distractor_notes')
            noted: list[str] = []
            for k, raw_note in enumerate(notes):
                note = obj(raw_note, f'{qloc}.distractor_notes[{k}]')
                noted.append(text(note.get('choice_id'), qloc + '.distractor_notes.choice_id'))
                literal_text(note.get('reason_ja'), qloc + '.distractor_notes.reason_ja')
            wanted = [cid for cid in cids if cid != answer]
            check(len(notes) == 3 and len(set(noted)) == 3 and Counter(noted) == Counter(wanted),
                  qloc + '.distractor_notes', 'one reason for each of the three wrong choices required')
        if cfg['gap']:
            check(Counter(gap_ids) == Counter(qids), loc, 'gap IDs must match questions once each')
        else:
            check(not gap_ids, loc, 'content questions must not have blanks')
        body = '\n'.join(texts)
        filled = GAP.sub(lambda m: fills.get(int(m.group(1)), m.group(0)), body)
        completed = None if GAP.search(filled) else word_count(filled)
        unit_metrics.append({'unit': uid, 'part': part, 'printed_body_words': word_count(body),
                             'completed_body_words': completed})
        target = cfg.get('completed_body_word_target')
        if target and completed is not None and not target[0] <= completed <= target[1]:
            warnings.append(f'{loc}: completed body {completed} words outside editorial band {target}; review')

    expected_order: list[str] = []
    for part in canonical:
        cfg = part_specs[part]
        units = part_units[part]
        expected_order.extend([part] * len(cfg['questions_per_unit']))
        counts = [len(u['questions']) if isinstance(u.get('questions'), list) else -1 for u in units]
        check(counts == cfg['questions_per_unit'], part, 'wrong unit/question pattern')
        numbers = [q.get('id') for u in units for q in (u.get('questions') if isinstance(u.get('questions'), list) else []) if isinstance(q, dict)]
        check(numbers == cfg['question_ids'], part, 'wrong question numbers/order')
    check(actual_order == expected_order, 'units', 'wrong unit order or number')
    expected_questions = sum(len(part_specs[p]['question_ids']) for p in canonical)
    check(len(seen_questions) == expected_questions, 'questions', 'wrong total')
    if mode == 'full':
        check(len(seen_questions) == spec['total_questions'], 'questions', 'full total incorrect')
    positions = [row['answer'] for row in key_rows]
    distribution = {str(i): positions.count(i) for i in range(1, 5)}
    longest_run = max((len(list(g)) for _, g in groupby(positions)), default=0)
    return {'mechanical_ok': not errors, 'errors': errors, 'warnings': warnings,
            'metrics': {'units': unit_metrics, 'answer_position_counts': distribution,
                        'maximum_identical_answer_run': longest_run},
            'derived_answer_key': key_rows if not errors else None,
            'semantic_validation': 'not_performed', 'layout_validation': 'not_performed'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pack', type=Path)
    parser.add_argument('--answer-key', action='store_true', help='derive key after structural checks pass')
    args = parser.parse_args()
    try:
        result = validate_pack(load_json(args.pack))
    except (OSError, ValueError, RecursionError) as exc:
        print(json.dumps({'mechanical_ok': False, 'input_error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    output = result['derived_answer_key'] if args.answer_key and result['mechanical_ok'] else result
    if args.answer_key and result['mechanical_ok']:
        # Keep stdout machine-readable without silently discarding unresolved warnings.
        print(json.dumps({'warnings': result['warnings'],
                          'semantic_validation': result['semantic_validation'],
                          'layout_validation': result['layout_validation']},
                         ensure_ascii=False), file=sys.stderr)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if result['mechanical_ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
