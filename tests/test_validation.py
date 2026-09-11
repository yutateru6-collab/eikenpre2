"""Synthetic fixtures test structure only. NEVER distribute them as Eiken questions."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tools.validate_pack import load_json, validate_pack, word_count, SPEC_PATH
from tools.check_repository import check_repository


def fixture(selected=None):
    spec = load_json(SPEC_PATH)
    selected = selected or [p['id'] for p in spec['parts']]
    data = {'schema_version': '1.0', 'grade': 'pre2', 'profile': spec['profile'],
            'scope': 'full' if len(selected) == 5 else 'parts', 'included_parts': selected,
            'theme': 'SYNTHETIC STRUCTURE TEST ONLY', 'sources': [], 'units': []}
    for p in spec['parts']:
        if p['id'] not in selected:
            continue
        cursor = 0
        for n, count in enumerate(p['questions_per_unit']):
            uid = f'{p["id"]}_{n}'
            numbers = p['question_ids'][cursor:cursor + count]
            cursor += count
            segment_count = p.get('paragraphs_per_unit', p.get('observed_turns', [1] * 15)[n])
            segments = [{'id': f'{uid}.s{k}', 'text': f'Synthetic segment {k}.',
                         'ja': '構造テスト専用の文です。'} for k in range(segment_count)]
            if p['id'] == 'p2':
                for k, seg in enumerate(segments):
                    seg['speaker'] = 'A' if k % 2 == 0 else 'B'
            questions = []
            for k, number in enumerate(numbers):
                if p['gap']:
                    segments[k]['text'] += ' {{q' + str(number) + '}}.'
                choices = [{'id': f'q{number}_{letter}', 'text': f'option {letter}', 'ja': f'選択肢{letter}'}
                           for letter in 'abcd']
                questions.append({'id': number, 'stem': '' if p['gap'] else 'What is true?',
                    'stem_ja': '' if p['gap'] else '正しい内容は何ですか。', 'choices': choices,
                    'answer_choice_id': choices[0]['id'], 'explanation_ja': '構造テスト用の説明。',
                    'evidence_segment_ids': [segments[k % len(segments)]['id']],
                    'distractor_notes': [{'choice_id': c['id'], 'reason_ja': '構造テスト用の排除理由。'} for c in choices[1:]]})
            unit = {'id': uid, 'part': p['id'], 'kind': p['kind'], 'factual_mode': 'original_fiction',
                    'source_ids': [], 'title': 'Synthetic title', 'title_ja': '構造テスト用',
                    'segments': segments, 'questions': questions}
            if p['id'] == 'p4a':
                unit['email'] = {key: {'en': 'Synthetic value', 'ja': 'テスト値'} for key in
                                ('from', 'to', 'date', 'subject', 'greeting', 'closing', 'signature')}
            data['units'].append(unit)
    return data


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.pack = fixture()

    def bad(self):
        result = validate_pack(self.pack)
        self.assertFalse(result['mechanical_ok'], result)
        self.assertIsNone(result['derived_answer_key'])

    def unit(self, part):
        return next(u for u in self.pack['units'] if u['part'] == part)

    def test_full_fixture_passes_structure_only(self):
        result = validate_pack(self.pack)
        self.assertTrue(result['mechanical_ok'], result['errors'])
        self.assertEqual(len(result['derived_answer_key']), 29)
        self.assertTrue(result['warnings'])  # Short nonsense fixture is not a model worksheet.
        self.assertEqual(result['semantic_validation'], 'not_performed')
        self.assertEqual(result['layout_validation'], 'not_performed')

    def test_explicit_partial(self):
        self.assertTrue(validate_pack(fixture(['p2', 'p4b']))['mechanical_ok'])

    def test_empty_selected_parts(self):
        self.pack['included_parts'] = []
        self.bad()

    def test_partial_cannot_claim_full(self):
        self.pack = fixture(['p3']); self.pack['scope'] = 'full'; self.bad()

    def test_grade_plus_is_rejected(self):
        self.pack['grade'] = 'pre2plus'; self.bad()

    def test_wrong_profile(self):
        self.pack['profile'] = 'grade2'; self.bad()

    def test_missing_question(self):
        self.pack['units'].pop(); self.bad()

    def test_five_dialogues_rejected(self):
        self.pack['units'].insert(19, copy.deepcopy(self.unit('p2'))); self.bad()

    def test_long_dialogue_needs_two_questions(self):
        [u for u in self.pack['units'] if u['part'] == 'p2'][-1]['questions'].pop(); self.bad()

    def test_missing_gap(self):
        self.pack['units'][0]['segments'][0]['text'] = 'No gap.'; self.bad()

    def test_repeated_gap(self):
        self.pack['units'][0]['segments'][0]['text'] += ' {{q1}}'; self.bad()

    def test_unknown_gap(self):
        self.pack['units'][0]['segments'][0]['text'] = '{{q77}}'; self.bad()

    def test_malformed_marker(self):
        self.pack['units'][0]['segments'][0]['text'] += ' {{bad}}'; self.bad()

    def test_p4_must_not_have_gaps(self):
        self.unit('p4b')['segments'][0]['text'] += '{{q26}}'; self.bad()

    def test_gap_each_paragraph(self):
        s = self.unit('p3')['segments']; s[0]['text'] += ' {{q22}}'; s[1]['text'] = 'No gap.'; self.bad()

    def test_wrong_paragraph_count(self):
        self.unit('p4b')['segments'].pop(); self.bad()

    def test_two_speakers_required(self):
        for s in self.unit('p2')['segments']: s['speaker'] = 'A'
        self.bad()

    def test_turn_count_warning_not_error(self):
        s = self.unit('p2')['segments']
        s.append({'id': 'extra.turn', 'text': 'One more turn.', 'ja': 'もう一つの発話。', 'speaker': 'B'})
        result = validate_pack(self.pack)
        self.assertTrue(result['mechanical_ok']); self.assertTrue(any('turn count' in w for w in result['warnings']))

    def test_three_choices_rejected(self):
        self.pack['units'][0]['questions'][0]['choices'].pop(); self.bad()

    def test_duplicate_choice_text(self):
        c = self.pack['units'][0]['questions'][0]['choices']; c[1]['text'] = ' OPTION A '; self.bad()

    def test_invalid_answer(self):
        self.pack['units'][0]['questions'][0]['answer_choice_id'] = 'missing'; self.bad()

    def test_choice_ids_global_unique(self):
        self.pack['units'][1]['questions'][0]['choices'][1]['id'] = 'q1_b'; self.bad()

    def test_bad_evidence_link(self):
        self.pack['units'][0]['questions'][0]['evidence_segment_ids'] = ['other.unit']; self.bad()

    def test_missing_distractor_note(self):
        self.pack['units'][0]['questions'][0]['distractor_notes'].pop(); self.bad()

    def test_missing_translation(self):
        self.pack['units'][0]['segments'][0]['ja'] = ''; self.bad()

    def test_unfilled_translation(self):
        self.pack['units'][0]['segments'][0]['ja'] += '{{q1}}'; self.bad()

    def test_missing_stem_translation(self):
        self.unit('p4b')['questions'][0]['stem_ja'] = ''; self.bad()

    def test_missing_email_header(self):
        del self.unit('p4a')['email']['subject']; self.bad()

    def test_verified_claims_need_source(self):
        self.unit('p3')['factual_mode'] = 'verified_canon'; self.bad()

    def test_source_reference(self):
        self.pack['sources'] = [{'id': 's1', 'url': 'https://example.org/source', 'note': 'Synthetic URL shape only'}]
        self.unit('p3')['factual_mode'] = 'verified_canon'; self.unit('p3')['source_ids'] = ['s1']
        self.assertTrue(validate_pack(self.pack)['mechanical_ok'])

    def test_unknown_source(self):
        self.unit('p3')['source_ids'] = ['missing']; self.bad()

    def test_invalid_source_url(self):
        self.pack['sources'] = [{'id': 's1', 'url': 'javascript:bad', 'note': 'bad'}]; self.bad()

    def test_bool_is_not_question_number(self):
        self.pack['units'][0]['questions'][0]['id'] = True; self.bad()

    def test_shuffled_choices_derive_new_number(self):
        q = self.pack['units'][0]['questions'][0]; q['choices'].reverse()
        result = validate_pack(self.pack)
        self.assertTrue(result['mechanical_ok']); self.assertEqual(result['derived_answer_key'][0]['answer'], 4)

    def test_stale_separate_key_rejected(self):
        self.pack['answer_key'] = [1] * 29; self.bad()

    def test_identical_position_runs_are_not_automatic_failure(self):
        result = validate_pack(self.pack)
        self.assertTrue(result['mechanical_ok']); self.assertEqual(result['metrics']['maximum_identical_answer_run'], 29)

    def test_part_order(self):
        self.pack['units'].reverse(); self.bad()

    def test_wrong_types_are_reported(self):
        mutations = [('units', None), ('included_parts', [True, {}]), ('sources', [None]), ('scope', {})]
        for field, value in mutations:
            with self.subTest(field=field):
                data = fixture(); data[field] = value
                self.assertFalse(validate_pack(data)['mechanical_ok'])
        for field in ('segments', 'questions', 'source_ids'):
            with self.subTest(unit_field=field):
                data = fixture(); data['units'][0][field] = 5
                self.assertFalse(validate_pack(data)['mechanical_ok'])

    def test_non_object_pack(self):
        for data in [None, [], 'bad', 42]:
            self.assertFalse(validate_pack(data)['mechanical_ok'])

    def test_word_count(self):
        self.assertEqual(word_count("Don't use eco-friendly {{q21}} signs — at 5:30 p.m."), 7)
        self.assertEqual(word_count('B\u00adlevel words'), 2)

    def test_duplicate_json_key_and_nan(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'bad.json'
            for raw in ['{"grade":"pre2","grade":"pre2plus"}', '{"x":NaN}']:
                p.write_text(raw)
                with self.assertRaises(ValueError): load_json(p)

    def test_cli_invalid_json_exit(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'bad.json'; p.write_text('{')
            result = subprocess.run([sys.executable, 'tools/validate_pack.py', str(p)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)

    def test_cli_answer_key(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'pack.json'; p.write_text(json.dumps(self.pack))
            result = subprocess.run([sys.executable, 'tools/validate_pack.py', str(p), '--answer-key'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(json.loads(result.stdout)), 29)

    def test_reference_profile_invariants(self):
        spec = load_json(SPEC_PATH)
        parts = {p['id']: p for p in spec['parts']}
        self.assertEqual(parts['p2']['questions_per_unit'], [1, 1, 1, 2])
        self.assertEqual(parts['p3']['questions_per_unit'], [2])
        self.assertEqual(parts['p4a']['questions_per_unit'], [3])
        self.assertEqual(parts['p4b']['questions_per_unit'], [4])
        self.assertEqual([parts[p]['paragraphs_per_unit'] for p in ['p3', 'p4a', 'p4b']], [2, 3, 4])
        self.assertEqual(spec['reading_page_model'], [['p1', 1, 10], ['p1', 11, 15],
            ['p2', 16, 20], ['p3', 21, 22], ['p4a', 23, 25], ['p4b', 'body'], ['p4b', 26, 29]])

    def test_nested_malformed_values_do_not_crash(self):
        paths = [('units', 0, 'questions', 0, f) for f in ['choices', 'id', 'answer_choice_id',
                 'evidence_segment_ids', 'distractor_notes', 'explanation_ja']]
        paths += [('units', 0, 'questions', 0, 'choices', 0, f) for f in ['id', 'text', 'ja']]
        paths += [('units', 0, 'segments', 0, f) for f in ['id', 'text', 'ja']]
        for path in paths:
            for replacement in [None, True, 5, [], {}]:
                with self.subTest(path=path, replacement=replacement):
                    data = fixture(); target = data
                    for key in path[:-1]: target = target[key]
                    target[path[-1]] = replacement
                    self.assertFalse(validate_pack(data)['mechanical_ok'])

    def test_cli_missing_file_exit(self):
        with tempfile.TemporaryDirectory() as d:
            result = subprocess.run([sys.executable, 'tools/validate_pack.py', str(Path(d) / 'missing.json')],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)

    def test_repository_integrity(self):
        self.assertEqual(check_repository(), [])


if __name__ == '__main__':
    unittest.main()
