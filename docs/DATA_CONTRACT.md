# 教材JSONのデータ契約 v1.0

このJSONは**内部の確定データ**。全体をそのまま生徒用に印刷しない。問題画面では英語だけ、解答・解説・訳・出典記録は所定の役割へ分けて使う。

## ルート

`schema_version: "1.0"`、`grade: "pre2"`、`profile: "pre2-reading-2026-09"`、`scope: "full" | "parts"`、`included_parts: ["p1", "p2", "p3", "p4a", "p4b"]`、`theme: 非空文字列`、`sources: []`、`units: []`。

fullは全パート、partsは明示選択したパートを本番の順に収録。選んだパートはそのパート全問を含める。勝手に問数を減らしたミニ版はこのプロファイルの対象外。問番号は部分制作でも公式対応の番号を保持する。`answer_key` は保存せず導出する。

sourceは `id`、`url`（http/https）、`note`（確認した内容・媒体を短く）。URLの形式検査はアクセスや主張の検証ではない。

## 単位（unit）

| フィールド | 内容 |
|---|---|
| id / part / kind | 固有の文字列ID、パートID、vocabulary/dialogue/cloze/email/expository |
| factual_mode | verified_canon / verified_nonfiction / fictional_context / original_fiction |
| source_ids | sourcesのID配列。verified系は最低1件必要 |
| title / title_ja | p3とp4bでは必須。その他は任意 |
| segments | `id, text, ja` を持つ配列。長文は1項目1段落。会話は1項目1発話とし `speaker` 必須 |
| questions | 下記の設問配列 |
| email | p4a必須。`from, to, date, subject, greeting, closing, signature` の各値は `{en, ja}` |

p1は1問1unitで、地の文または短い対話。p2は4unitsで最後のみ2問。p3/p4a/p4bは各1unit。構成・段落・番号の正本は `../specs/pre2_reading.json`。

## 設問（question）

```json
{
  "id": 16,
  "stem": "",
  "stem_ja": "",
  "choices": [
    {"id": "q16_a", "text": "I can help after lunch", "ja": "昼食の後なら手伝えるよ"},
    {"id": "q16_b", "text": "I have already sold it", "ja": "もう売ってしまったよ"},
    {"id": "q16_c", "text": "I forgot its name", "ja": "名前を忘れてしまったよ"},
    {"id": "q16_d", "text": "I have never lived there", "ja": "そこに住んだことはないよ"}
  ],
  "answer_choice_id": "q16_a",
  "explanation_ja": "実際の会話の前後関係に基づく説明を記す。",
  "evidence_segment_ids": ["dialogue1.turn3"],
  "distractor_notes": [
    {"choice_id": "q16_b", "reason_ja": "実際の本文で排除できる理由を記す。"},
    {"choice_id": "q16_c", "reason_ja": "実際の本文で排除できる理由を記す。"},
    {"choice_id": "q16_d", "reason_ja": "実際の本文で排除できる理由を記す。"}
  ]
}
```

これはフィールド形状の説明用断片で、会話本文を伴わないため問題として使用できない。文例や説明の仮文言を実教材に残さない。

p1〜3の空所は英語segmentに `{{q16}}` の形式で、設問IDごとにちょうど1回置く。括弧だけの空所や不明なIDを混ぜない。p4a/bには空所を置かず、`stem` と `stem_ja` に質問・未完の設問文を入れる。p1〜3のstemは空文字（空所位置はsegment内）。

全選択肢IDとsegment IDは全体で一意。`evidence_segment_ids` は同じunitの本文IDだけを参照。訳は正答補充後で、空所マーカーを含めない。正答以外の3IDそれぞれに排除理由を持たせる。肢の配列を並べ替えても `answer_choice_id` は変えず、現在の配列位置から正答番号を導出する。

## 検査結果

`mechanical_ok` は構造・対応のみ。`errors` があれば終了1。`warnings` は本文語数や会話発話数の目安との差等で、根拠を確認する。`metrics` は単位別の印字本文語数・完成本文語数、正答位置回数など。`semantic_validation` と `layout_validation` は常に `not_performed`。JSON自体が壊れていれば終了2。

一意解、英文・訳の自然さ、出典の真偽、答え漏れ、DOCX/PDFの配置はこのツールでは確認しない。前付、語彙表、後付の見出しなどの組版用データは別に設計し、確定問題データと最終出力を照合する。
