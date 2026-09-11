#!/usr/bin/env python3
"""Validate PRE2 Reading data structure, NOT meaning, difficulty, or print layout.

Python 3.11+. No network access or third-party packages. The input is never changed.
Exit codes: 0 structure passes, 1 structure errors, 2 unreadable/invalid JSON.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any
import unicodedata
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
BLANK = re.compile(r"\{\{(q[1-9][0-9]*)\}\}")
WORD = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*", re.UNICODE)
IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_.-]*\Z")
EMAIL_FIELDS = ("from", "to", "date", "subject", "greeting", "closing", "signature")


def word_count(text: str) -> int:
    """Count contractions/hyphenated words/numbers as one; ignore blank tokens."""
    text = text.replace("\u2010", "-").replace("\u2011", "-").replace("\u00ad", "")
    return len(WORD.findall(BLANK.sub("", text)))


def load_profile() -> dict[str, Any]:
    return json.loads((ROOT / "config/exam_profile.json").read_text(encoding="utf-8"))


class Check:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.ids: set[str] = set()

    def error(self, path: str, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def obj(self, value: Any, path: str) -> dict:
        if not isinstance(value, dict):
            self.error(path, "must be an object")
            return {}
        return value

    def seq(self, value: Any, path: str) -> list:
        if not isinstance(value, list):
            self.error(path, "must be an array")
            return []
        return value

    def text(self, value: Any, path: str, *, empty: bool = False) -> str:
        if not isinstance(value, str) or (not empty and not value.strip()):
            self.error(path, "must be a nonempty string" if not empty else "must be a string")
            return ""
        return value

    def identifier(self, value: Any, path: str) -> str:
        text = self.text(value, path)
        if not IDENT.fullmatch(text):
            self.error(path, "invalid identifier")
        elif text in self.ids:
            self.error(path, "duplicate identifier")
        self.ids.add(text)
        return text

    def day(self, value: Any, path: str, today: date) -> None:
        text = self.text(value, path)
        try:
            parsed = date.fromisoformat(text)
            if parsed.isoformat() != text or parsed > today:
                raise ValueError
        except ValueError:
            self.error(path, "must be YYYY-MM-DD and not in the future")

    def no_blanks(self, value: str, path: str) -> None:
        if "{{" in value or "}}" in value:
            self.error(path, "unresolved/misplaced blank token")


def validate_exam(data: Any, *, today: date | None = None) -> dict[str, Any]:
    """Return structural errors, warnings and a derived answer key without mutation."""
    c = Check()
    profile = load_profile()
    today = today or datetime.now(timezone(timedelta(hours=9))).date()
    root = c.obj(data, "exam")
    meta = c.obj(root.get("metadata"), "metadata")
    for name, expected in (("grade", "pre2"), ("skill", "reading"), ("mode", "full"),
                           ("profile_id", profile["profile_id"])):
        if meta.get(name) != expected:
            c.error(f"metadata.{name}", f"must be {expected!r}")
    if type(meta.get("schema_version")) is not int or meta["schema_version"] != 1:
        c.error("metadata.schema_version", "must be integer 1")
    c.text(meta.get("theme"), "metadata.theme")
    reference = c.text(meta.get("reference_exam"), "metadata.reference_exam")
    if reference and reference not in profile["references"]:
        c.warnings.append("metadata.reference_exam: update/verify the profile against this reference")
    c.day(meta.get("official_checked_on"), "metadata.official_checked_on", today)

    source_ids: set[str] = set()
    for i, raw in enumerate(c.seq(root.get("sources"), "sources")):
        path = f"sources[{i}]"
        source = c.obj(raw, path)
        sid = c.identifier(source.get("id"), path + ".id")
        source_ids.add(sid)
        for field in ("title", "locator"):
            c.text(source.get(field), path + "." + field)
        url = c.text(source.get("url"), path + ".url")
        try:
            parsed = urlparse(url)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError
        except ValueError:
            c.error(path + ".url", "must be an HTTPS URL (not fetched by this validator)")
        c.day(source.get("checked_on"), path + ".checked_on", today)

    sections = c.seq(root.get("sections"), "sections")
    specs = profile["template"]["sections"]
    if len(sections) != len(specs):
        c.error("sections", "must contain the five sections p1, p2, p3, p4a, p4b")
    derived: dict[str, int] = {}
    measured: dict[str, int] = {}
    all_numbers: list[Any] = []
    for si, spec in enumerate(specs):
        sp = f"sections[{si}]"
        section = c.obj(sections[si] if si < len(sections) else None, sp)
        if section.get("id") != spec["id"]:
            c.error(sp + ".id", f"expected {spec['id']} in this order")
        units = c.seq(section.get("units"), sp + ".units")
        expected_counts = spec["questions_per_unit"]
        if len(units) != len(expected_counts):
            c.error(sp + ".units", f"expected {len(expected_counts)} units")
        section_numbers: list[Any] = []
        for ui, raw in enumerate(units):
            up = f"{sp}.units[{ui}]"
            unit = c.obj(raw, up)
            uid = c.identifier(unit.get("id"), up + ".id")
            if unit.get("kind") != spec["kind"]:
                c.error(up + ".kind", f"expected {spec['kind']}")
            mode = unit.get("fact_mode")
            if mode not in ("fiction", "source_based", "mixed"):
                c.error(up + ".fact_mode", "expected fiction, source_based, or mixed")
            if mode in ("fiction", "mixed"):
                c.text(unit.get("fiction_notice"), up + ".fiction_notice")
            refs = c.seq(unit.get("source_refs"), up + ".source_refs")
            for ri, ref in enumerate(refs):
                if not isinstance(ref, str) or ref not in source_ids:
                    c.error(f"{up}.source_refs[{ri}]", "unknown source ID")
            if mode in ("source_based", "mixed") and not refs:
                c.error(up + ".source_refs", "source-based content requires sources")

            segments = c.seq(unit.get("segments"), up + ".segments")
            if not segments:
                c.error(up + ".segments", "at least one segment is required")
            counts = spec.get("segments_per_unit", [])
            if ui < len(counts) and len(segments) != counts[ui]:
                c.error(up + ".segments", f"expected {counts[ui]} segments in the full-mode template")
            turns = spec.get("suggested_turns", [])
            if ui < len(turns) and len(segments) != turns[ui]:
                c.warnings.append(up + f": observed dialogue model has {turns[ui]} turns; review manually")
            segment_ids: list[str] = []
            texts: list[str] = []
            for ti, item in enumerate(segments):
                tp = f"{up}.segments[{ti}]"
                seg = c.obj(item, tp)
                segment_ids.append(c.identifier(seg.get("id"), tp + ".id"))
                text = c.text(seg.get("text"), tp + ".text")
                texts.append(text)
                c.no_blanks(BLANK.sub("", text), tp + ".text")
                if spec["kind"] == "dialogue":
                    c.text(seg.get("speaker"), tp + ".speaker")
            if spec["kind"] in ("cloze", "passage"):
                c.text(unit.get("title"), up + ".title")
                c.text(unit.get("title_ja"), up + ".title_ja")
            if spec["kind"] == "email":
                for field in ("email", "email_ja"):
                    header = c.obj(unit.get(field), up + "." + field)
                    for name in EMAIL_FIELDS:
                        text = c.text(header.get(name), f"{up}.{field}.{name}")
                        c.no_blanks(text, f"{up}.{field}.{name}")

            questions = c.seq(unit.get("questions"), up + ".questions")
            if ui < len(expected_counts) and len(questions) != expected_counts[ui]:
                c.error(up + ".questions", f"expected {expected_counts[ui]} questions")
            qids: list[str] = []
            replacements: dict[str, str] = {}
            for qi, rawq in enumerate(questions):
                qp = f"{up}.questions[{qi}]"
                question = c.obj(rawq, qp)
                qid = c.identifier(question.get("id"), qp + ".id")
                qids.append(qid)
                number = question.get("number")
                if type(number) is not int or not 1 <= number <= profile["official"]["reading_questions"]:
                    c.error(qp + ".number", "must be an integer in 1..29")
                elif qid != f"q{number}":
                    c.error(qp + ".id", "must match q + question number")
                section_numbers.append(number)
                prompt = c.text(question.get("prompt"), qp + ".prompt", empty=spec["has_blanks"])
                c.no_blanks(prompt, qp + ".prompt")
                c.text(question.get("explanation_ja"), qp + ".explanation_ja")
                choices = c.seq(question.get("choices"), qp + ".choices")
                if len(choices) != profile["official"]["choices_per_question"]:
                    c.error(qp + ".choices", "exactly four choices required")
                ids: list[str] = []
                choice_texts: list[str] = []
                for ci, rawchoice in enumerate(choices):
                    cp = f"{qp}.choices[{ci}]"
                    choice = c.obj(rawchoice, cp)
                    ids.append(c.identifier(choice.get("id"), cp + ".id"))
                    text = c.text(choice.get("text"), cp + ".text")
                    c.no_blanks(text, cp + ".text")
                    choice_texts.append(text)
                normalized = [" ".join(unicodedata.normalize("NFKC", s).casefold().split()) for s in choice_texts]
                if len(set(normalized)) != len(normalized):
                    c.error(qp + ".choices", "duplicate choice text")
                answer = c.text(question.get("answer_choice_id"), qp + ".answer_choice_id")
                if answer not in ids or not answer:
                    c.error(qp + ".answer_choice_id", "must reference a choice of this question")
                else:
                    pos = ids.index(answer)
                    derived[qid] = pos + 1
                    replacements[qid] = choice_texts[pos]
                reviews = c.seq(question.get("choice_reviews"), qp + ".choice_reviews")
                reviewed: list[str] = []
                for ri, raw_review in enumerate(reviews):
                    rp = f"{qp}.choice_reviews[{ri}]"
                    review = c.obj(raw_review, rp)
                    rid = c.text(review.get("choice_id"), rp + ".choice_id")
                    reviewed.append(rid)
                    expected = "accept" if rid == answer else "reject"
                    if review.get("decision") != expected:
                        c.error(rp + ".decision", "must agree with answer_choice_id")
                    c.text(review.get("reason_ja"), rp + ".reason_ja")
                    evidence = c.seq(review.get("evidence_segment_ids"), rp + ".evidence_segment_ids")
                    if not evidence:
                        c.error(rp + ".evidence_segment_ids", "evidence location required")
                    for ev in evidence:
                        if not isinstance(ev, str) or ev not in segment_ids:
                            c.error(rp + ".evidence_segment_ids", "must refer to a segment in this unit")
                if Counter(reviewed) != Counter(ids):
                    c.error(qp + ".choice_reviews", "one review for every choice required")

            body = "\n".join(texts)
            found = Counter(BLANK.findall(body))
            expected_blanks = Counter(qids) if spec["has_blanks"] else Counter()
            if found != expected_blanks:
                c.error(up + ".segments", "blank IDs must match this unit's questions exactly once")
            if spec["kind"] == "cloze" and any(len(BLANK.findall(t)) != 1 for t in texts):
                c.error(up + ".segments", "one cloze blank per paragraph required")
            translated = c.seq(unit.get("translation"), up + ".translation")
            translated_ids: list[str] = []
            for ti, raw_trans in enumerate(translated):
                tp = f"{up}.translation[{ti}]"
                trans = c.obj(raw_trans, tp)
                translated_ids.append(c.text(trans.get("segment_id"), tp + ".segment_id"))
                text = c.text(trans.get("text_ja"), tp + ".text_ja")
                c.no_blanks(text, tp + ".text_ja")
            if translated_ids != segment_ids:
                c.error(up + ".translation", "translated segments must match the source order exactly")
            completed = BLANK.sub(lambda match: replacements.get(match[1], ""), body)
            measured[uid] = word_count(completed)
            band = profile["editorial"]["completed_body_words"].get(spec["id"])
            if band and not band[0] <= measured[uid] <= band[1]:
                c.warnings.append(up + f": completed body has {measured[uid]} words; editorial band {band[0]}..{band[1]}, not an official limit")
        if section_numbers != spec["numbers"]:
            c.error(sp + ".numbers", f"expected {spec['numbers']}")
        all_numbers.extend(section_numbers)
    if all_numbers != list(range(1, profile["official"]["reading_questions"] + 1)):
        c.error("exam.numbers", "exactly 1..29 in section order required")
    if "answer_key" in root:
        saved = c.obj(root["answer_key"], "answer_key")
        if saved != derived or any(type(v) is not int for v in saved.values()):
            c.error("answer_key", "stale or invalid; regenerate from stable choice IDs")
    return {
        "structural_pass": not c.errors,
        "errors": c.errors,
        "warnings": c.warnings,
        "derived_answer_key": derived,
        "completed_body_word_counts": measured,
        "answer_position_counts": {str(k): v for k, v in sorted(Counter(derived.values()).items())},
        "manual_review_required": ["actual_source_verification", "unique_answer_and_distractors", "english_level_and_naturalness", "answer_leakage", "japanese_accuracy", "docx_pdf_identity_and_all_page_visual_review"],
        "notice": "Structure only. No semantic, factual, psychometric, or print-layout approval.",
    }


def unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="UTF-8 exam JSON; full 29-question mode")
    args = parser.parse_args()
    try:
        if args.file.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("JSON file exceeds 8 MiB safety limit")
        data = json.loads(args.file.read_text(encoding="utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant)
        result = validate_exam(data)
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        print(json.dumps({"structural_pass": False, "input_error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["structural_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
