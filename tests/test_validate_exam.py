"""Synthetic structural fixtures, not English learning materials."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from validate_exam import load_profile, validate_exam, word_count  # noqa: E402


def synthetic_exam():
    profile = load_profile()
    data = {'metadata': {'schema_version': 1, 'profile_id': profile['profile_id'],
            'grade': 'pre2', 'skill': 'reading', 'mode': 'full',
            'theme': '構造検査専用・教材利用不可', 'reference_exam': '2026-1',
            'official_checked_on': '2026-09-11'}, 'sources': [], 'sections': []}
    for spec in profile['template']['sections']:
        section = {'id': spec['id'], 'units': []}
        offset = 0
        for ui, n in enumerate(spec['questions_per_unit']):
            uid = f"{spec['id']}u{ui + 1}"
            numbers = spec['numbers'][offset:offset + n]
            offset += n
            seg_count = spec.get('segments_per_unit', spec.get('suggested_turns'))[ui]
            segments = [{'id': f'{uid}.s{i + 1}', 'text': 'This text is only for a software test.'}
                        for i in range(seg_count)]
            if spec['has_blanks']:
                for i, number in enumerate(numbers):
                    segments[i]['text'] += ' {{q' + str(number) + '}}'
            if spec['kind'] == 'dialogue':
                for i, seg in enumerate(segments):
                    seg['speaker'] = 'A' if i % 2 == 0 else 'B'
            unit = {'id': uid, 'kind': spec['kind'], 'fact_mode': 'fiction',
                    'fiction_notice': '架空の構造テスト。教材利用不可。', 'source_refs': [],
                    'segments': segments, 'questions': [],
                    'translation': [{'segment_id': s['id'], 'text_ja': '構造を試すための仮の訳。'} for s in segments]}
            if spec['kind'] in ('cloze', 'passage'):
                unit.update(title='A Software Test', title_ja='構造テスト')
            if spec['kind'] == 'email':
                unit['email'] = {field: 'Synthetic header' for field in ('from', 'to', 'date', 'subject', 'greeting', 'closing', 'signature')}
                unit['email_ja'] = {field: '構造テスト用' for field in unit['email']}
            for number in numbers:
                qid = f'q{number}'
                choices = [{'id': f'{qid}.{letter}', 'text': f'{label} synthetic option'} for letter, label in zip('abcd', ['First', 'Second', 'Third', 'Fourth'])]
                answer = choices[(number - 1) % 4]['id']
                question = {'id': qid, 'number': number,
                            'prompt': '' if spec['has_blanks'] else 'Which test option is stored?',
                            'choices': choices, 'answer_choice_id': answer,
                            'explanation_ja': '構造テスト用。意味の妥当性を主張しない。',
                            'choice_reviews': [{'choice_id': ch['id'], 'decision': 'accept' if ch['id'] == answer else 'reject',
                                                'evidence_segment_ids': [segments[0]['id']], 'reason_ja': '構造テスト用の欄。'} for ch in choices]}
                unit['questions'].append(question)
            section['units'].append(unit)
        data['sections'].append(section)
    return data


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.data = synthetic_exam()
        self.today = date(2026, 9, 11)

    def result(self, data=None):
        return validate_exam(self.data if data is None else data, today=self.today)

    def reject(self, fragment):
        result = self.result()
        self.assertFalse(result['structural_pass'])
        self.assertTrue(any(fragment in error for error in result['errors']), result['errors'])

    def first_question(self):
        return self.data['sections'][0]['units'][0]['questions'][0]

    def test_valid_structure_does_not_approve_meaning(self):
        result = self.result()
        self.assertTrue(result['structural_pass'], result['errors'])
        self.assertEqual(len(result['derived_answer_key']), 29)
        self.assertTrue(result['manual_review_required'])
        self.assertTrue(result['warnings'])  # synthetic passages are deliberately short

    def test_input_is_not_mutated(self):
        before = deepcopy(self.data)
        self.result()
        self.assertEqual(self.data, before)

    def test_pre2plus_is_rejected(self):
        self.data['metadata']['grade'] = 'pre2plus'
        self.reject('metadata.grade')

    def test_part_mode_not_silently_treated_as_full(self):
        self.data['metadata']['mode'] = 'part_only'
        self.reject('metadata.mode')

    def test_schema_boolean_is_not_integer_one(self):
        self.data['metadata']['schema_version'] = True
        self.reject('schema_version')

    def test_future_date_is_rejected(self):
        self.data['metadata']['official_checked_on'] = '2099-01-01'
        self.reject('official_checked_on')

    def test_invalid_date_is_rejected(self):
        self.data['metadata']['official_checked_on'] = '2026-99-99'
        self.reject('official_checked_on')

    def test_section_order_is_checked(self):
        self.data['sections'][0], self.data['sections'][1] = self.data['sections'][1], self.data['sections'][0]
        self.reject('.id')

    def test_missing_question_is_rejected(self):
        self.data['sections'][0]['units'].pop()
        self.reject('expected 15 units')

    def test_five_dialogues_are_rejected(self):
        units = self.data['sections'][1]['units']
        units.append(deepcopy(units[0]))
        self.reject('expected 4 units')

    def test_dialogue_distribution_is_checked(self):
        units = self.data['sections'][1]['units']
        units[0]['questions'].append(units[-1]['questions'].pop())
        self.reject('.questions')

    def test_dialogue_speaker_is_required(self):
        del self.data['sections'][1]['units'][0]['segments'][0]['speaker']
        self.reject('.speaker')

    def test_three_cloze_paragraphs_are_rejected(self):
        unit = self.data['sections'][2]['units'][0]
        unit['segments'].append({'id': 'extra.segment', 'text': 'Extra paragraph.'})
        self.reject('expected 2 segments')

    def test_cloze_blanks_must_be_in_separate_paragraphs(self):
        segments = self.data['sections'][2]['units'][0]['segments']
        segments[0]['text'] += ' {{q22}}'
        segments[1]['text'] = segments[1]['text'].replace('{{q22}}', '')
        self.reject('one cloze blank per paragraph')

    def test_unknown_blank_is_rejected(self):
        self.data['sections'][0]['units'][0]['segments'][0]['text'] += ' {{q99}}'
        self.reject('blank IDs')

    def test_malformed_blank_is_rejected(self):
        self.data['sections'][0]['units'][0]['segments'][0]['text'] += ' {{broken}}'
        self.reject('blank token')

    def test_five_choices_are_rejected(self):
        self.first_question()['choices'].append({'id': 'q1.e', 'text': 'Fifth option'})
        self.reject('four choices')

    def test_duplicate_choice_text_is_normalized(self):
        choices = self.first_question()['choices']
        choices[1]['text'] = '  FIRST   synthetic option '
        self.reject('duplicate choice text')

    def test_duplicate_choice_id_is_rejected(self):
        self.first_question()['choices'][1]['id'] = 'q1.a'
        self.reject('duplicate identifier')

    def test_wrong_answer_id_is_rejected(self):
        self.first_question()['answer_choice_id'] = 'q2.b'
        self.reject('answer_choice_id')

    def test_stale_key_is_rejected(self):
        self.data['answer_key'] = self.result()['derived_answer_key']
        self.data['answer_key']['q1'] = 4
        self.reject('stale or invalid')

    def test_boolean_key_is_rejected(self):
        self.data['answer_key'] = self.result()['derived_answer_key']
        self.data['answer_key']['q1'] = True
        self.reject('stale or invalid')

    def test_reordering_choices_regenerates_key_from_id(self):
        q = self.first_question()
        q['choices'].reverse()
        result = self.result()
        self.assertTrue(result['structural_pass'], result['errors'])
        self.assertEqual(result['derived_answer_key']['q1'], 4)

    def test_reordering_with_old_key_is_rejected(self):
        self.data['answer_key'] = self.result()['derived_answer_key']
        self.first_question()['choices'].reverse()
        self.reject('stale or invalid')

    def test_review_cannot_refer_to_another_units_evidence(self):
        self.first_question()['choice_reviews'][0]['evidence_segment_ids'] = ['p2u1.s1']
        self.reject('must refer to a segment in this unit')

    def test_missing_choice_review_is_rejected(self):
        self.first_question()['choice_reviews'].pop()
        self.reject('one review for every choice')

    def test_wrong_review_decision_is_rejected(self):
        self.first_question()['choice_reviews'][1]['decision'] = 'accept'
        self.reject('must agree')

    def test_missing_translation_is_rejected(self):
        self.data['sections'][4]['units'][0]['translation'].pop()
        self.reject('translated segments')

    def test_unfilled_translation_is_rejected(self):
        self.data['sections'][2]['units'][0]['translation'][0]['text_ja'] += '{{q21}}'
        self.reject('blank token')

    def test_translation_order_is_checked(self):
        self.data['sections'][4]['units'][0]['translation'].reverse()
        self.reject('source order')

    def test_email_headers_and_japanese_are_required(self):
        del self.data['sections'][3]['units'][0]['email_ja']['subject']
        self.reject('email_ja.subject')

    def test_passage_title_is_required(self):
        del self.data['sections'][4]['units'][0]['title']
        self.reject('.title')

    def test_source_based_content_requires_a_source(self):
        self.data['sections'][4]['units'][0]['fact_mode'] = 'source_based'
        self.reject('requires sources')

    def test_unknown_source_id_is_rejected(self):
        self.data['sections'][4]['units'][0]['source_refs'] = ['missing']
        self.reject('unknown source ID')

    def test_mixed_content_needs_fiction_notice(self):
        self.data['sections'][0]['units'][0]['fact_mode'] = 'mixed'
        del self.data['sections'][0]['units'][0]['fiction_notice']
        self.reject('fiction_notice')

    def test_source_metadata_is_not_actual_source_verification(self):
        self.data['sources'] = [{'id': 'src1', 'title': 'Synthetic metadata', 'url': 'https://example.com/source',
                                 'locator': 'Test location', 'checked_on': '2026-09-11'}]
        unit = self.data['sections'][4]['units'][0]
        unit['fact_mode'] = 'source_based'
        unit['source_refs'] = ['src1']
        result = self.result()
        self.assertTrue(result['structural_pass'], result['errors'])
        self.assertIn('actual_source_verification', result['manual_review_required'])

    def test_nonuniform_keys_are_not_treated_as_official_violation(self):
        for section in self.data['sections']:
            for unit in section['units']:
                for q in unit['questions']:
                    q['answer_choice_id'] = q['choices'][0]['id']
                    for review in q['choice_reviews']:
                        review['decision'] = 'accept' if review['choice_id'] == q['answer_choice_id'] else 'reject'
        result = self.result()
        self.assertTrue(result['structural_pass'], result['errors'])
        self.assertEqual(result['answer_position_counts'], {'1': 29})
        self.assertIn('answer_leakage', result['manual_review_required'])

    def test_word_count_uses_declared_convention(self):
        self.assertEqual(word_count("It’s eco-friendly and costs 20 dollars. {{q21}}"), 6)

    def test_unicode_word_forms_are_counted_consistently(self):
        self.assertEqual(word_count("Pokémon café eco‑friendly it’s"), 4)

    def test_wrong_container_types_do_not_crash(self):
        for bad in (None, [], 7, True, 'text', {'sections': [None]}):
            with self.subTest(bad=bad):
                self.assertFalse(validate_exam(bad, today=self.today)['structural_pass'])
        for field in ('choices', 'choice_reviews', 'number', 'answer_choice_id'):
            for bad in (None, [], {}, True):
                with self.subTest(field=field, bad=bad):
                    data = synthetic_exam()
                    data['sections'][0]['units'][0]['questions'][0][field] = bad
                    self.assertFalse(validate_exam(data, today=self.today)['structural_pass'])

    def test_cli_rejects_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.json'
            path.write_text('{"metadata":{},"metadata":{}}', encoding='utf-8')
            run = subprocess.run([sys.executable, str(ROOT / 'tools/validate_exam.py'), str(path)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertIn('duplicate JSON key', json.loads(run.stdout)['input_error'])

    def test_cli_rejects_nan(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.json'
            path.write_text('{"metadata": NaN}', encoding='utf-8')
            run = subprocess.run([sys.executable, str(ROOT / 'tools/validate_exam.py'), str(path)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertIn('non-finite', json.loads(run.stdout)['input_error'])

    def test_cli_missing_file_is_an_input_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'missing.json'
            run = subprocess.run([sys.executable, str(ROOT / 'tools/validate_exam.py'), str(path)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertFalse(json.loads(run.stdout)['structural_pass'])


if __name__ == '__main__':
    unittest.main()
