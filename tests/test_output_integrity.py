"""Regression tests for unfinished output fields; fixtures are not learning material."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_validation import fixture
from tools.validate_pack import load_json, validate_pack

ROOT = Path(__file__).resolve().parents[1]


class OutputIntegrityTests(unittest.TestCase):
    def reject(self, pack, fragment):
        result = validate_pack(pack)
        self.assertFalse(result['mechanical_ok'])
        self.assertIsNone(result['derived_answer_key'])
        self.assertTrue(any(fragment in error for error in result['errors']), result['errors'])

    def test_email_headers_cannot_contain_unfilled_markers(self):
        for field in ('from', 'to', 'date', 'subject', 'greeting', 'closing', 'signature'):
            for language in ('en', 'ja'):
                with self.subTest(field=field, language=language):
                    pack = fixture(['p4a'])
                    pack['units'][0]['email'][field][language] += '{{q23}}'
                    self.reject(pack, '.email.' + field + '.' + language)

    def test_titles_cannot_contain_unfilled_markers(self):
        for part in ('p3', 'p4b'):
            for field in ('title', 'title_ja'):
                with self.subTest(part=part, field=field):
                    pack = fixture([part])
                    pack['units'][0][field] += '{{q21}}'
                    self.reject(pack, '.' + field)

    def test_optional_title_is_checked_when_present(self):
        pack = fixture(['p1'])
        pack['units'][0]['title_ja'] += '{{unfinished}}'
        self.reject(pack, '.title_ja')

    def test_explanations_cannot_contain_unfilled_markers(self):
        pack = fixture(['p1'])
        pack['units'][0]['questions'][0]['explanation_ja'] += '{{q1}}'
        self.reject(pack, '.explanation_ja')

    def test_distractor_reasons_cannot_contain_unfilled_markers(self):
        pack = fixture(['p1'])
        pack['units'][0]['questions'][0]['distractor_notes'][0]['reason_ja'] += '{{q1}}'
        self.reject(pack, '.distractor_notes.reason_ja')

    def test_speaker_label_cannot_contain_unfilled_markers(self):
        pack = fixture(['p2'])
        pack['units'][0]['segments'][0]['speaker'] += '{{q16}}'
        self.reject(pack, '.speaker')

    def test_theme_cannot_contain_unfilled_markers(self):
        pack = fixture(['p3'])
        pack['theme'] += '{{unfinished}}'
        self.reject(pack, 'theme')

    def test_gap_ids_must_use_canonical_ascii_numbers(self):
        for replacement in ('{{q021}}', '{{q２１}}', '{{q٢١}}', '{{q0}}'):
            with self.subTest(replacement=replacement):
                pack = fixture(['p3'])
                segment = pack['units'][0]['segments'][0]
                segment['text'] = segment['text'].replace('{{q21}}', replacement)
                self.reject(pack, 'malformed marker')

    def test_valid_full_and_partial_modes_still_work(self):
        for selected in (None, ['p2'], ['p3', 'p4a', 'p4b']):
            with self.subTest(selected=selected):
                result = validate_pack(fixture(selected))
                self.assertTrue(result['mechanical_ok'], result['errors'])
                self.assertEqual(result['semantic_validation'], 'not_performed')
                self.assertEqual(result['layout_validation'], 'not_performed')

    def test_validation_does_not_modify_the_pack(self):
        pack = fixture()
        before = copy.deepcopy(pack)
        validate_pack(pack)
        self.assertEqual(pack, before)

    def test_bounded_input_read_rejects_oversized_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'large.json'
            path.write_text(' ' * 17, encoding='utf-8')
            with patch('tools.validate_pack.MAX_JSON_BYTES', 16):
                with self.assertRaisesRegex(ValueError, 'input limit'):
                    load_json(path)

    def test_input_at_limit_is_not_rejected_as_oversized(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'small.json'
            path.write_text('{}', encoding='utf-8')
            with patch('tools.validate_pack.MAX_JSON_BYTES', 2):
                self.assertEqual(load_json(path), {})

    def test_answer_key_mode_keeps_warnings_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'pack.json'
            path.write_text(json.dumps(fixture(['p3'])), encoding='utf-8')
            run = subprocess.run([sys.executable, str(ROOT / 'tools/validate_pack.py'), str(path), '--answer-key'],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(len(json.loads(run.stdout)), 2)
            notice = json.loads(run.stderr)
            self.assertTrue(notice['warnings'])
            self.assertEqual(notice['semantic_validation'], 'not_performed')
            self.assertEqual(notice['layout_validation'], 'not_performed')

    def test_answer_key_mode_does_not_hide_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            pack = fixture(['p4a'])
            pack['units'][0]['email']['subject']['ja'] += '{{q23}}'
            path = Path(directory) / 'bad.json'
            path.write_text(json.dumps(pack), encoding='utf-8')
            run = subprocess.run([sys.executable, str(ROOT / 'tools/validate_pack.py'), str(path), '--answer-key'],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 1)
            result = json.loads(run.stdout)
            self.assertFalse(result['mechanical_ok'])
            self.assertIsNone(result['derived_answer_key'])


if __name__ == '__main__':
    unittest.main()
