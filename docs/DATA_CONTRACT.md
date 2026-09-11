# 内容データの形式（v1）

CLIは全29問の構造確認専用。入力を変更せず、解答番号をIDから導出する。部分演習は未対応。コードは [validate_exam.py](../tools/validate_exam.py)、合成データの作り方は [テスト](../tests/test_validate_exam.py)。テスト用の英文と訳は教材ではない。

## 最上位

`metadata` は schema_version（整数1）、profile_id（exam_profile.jsonの値）、grade（pre2）、skill（reading）、mode（full）、theme、reference_exam、official_checked_on（YYYY-MM-DD）。確認日は未来日を認めないが、記入だけでは実際の確認を証明しない。

`sources` は id、title、url（HTTPS）、locator（該当章・場面・見出し等）、checked_on を持つ配列。CLIはURLへアクセスしない。外部情報を含まない完全架空の練習文なら空配列も可。

`sections` は p1、p2、p3、p4a、p4b の順の配列。各要素は `id` と `units`。問題数・単位数は [JSON正本](../config/exam_profile.json)。

## unit

`id`（全体で一意）、`kind`（short / dialogue / cloze / email / passage）、`fact_mode`（fiction / source_based / mixed）、`source_refs`（sourcesのID）、`segments`、`questions`、`translation`。

fiction / mixed では `fiction_notice` が必須。source_based / mixed では出典が必要。出典の中身との対応は手動確認する。

各segmentは一意な `id` と `text`。会話は1発話1segmentとし、`speaker` も付ける。短文は1問を1segment、長文は1段落を1segment。短文中のA/B対話は1segment内の改行で保持してよい。P3とP4Bは `title` と `title_ja` も必要。

空所は `{{q1}}` のように記す。P1〜P3は関連する問IDが本文にそれぞれ一度だけ出る。P3は1段落1空所。P4では空所を作らない。表示用の括弧への変換は組版工程で行う。

P4Aには `email` と `email_ja` が必要。それぞれ from、to、date、subject、greeting、closing、signature を持つ。本文段落はsegmentsへ置く。英語語数にはヘッダー等を含めない。

## question

`id` は q1〜q29、`number` は同じ整数。`prompt` はP4で非空、P1〜P3では空文字可。空所をpromptや選択肢へ重複記入しない。

`choices` は4件で各 `id` と `text`。選択肢IDは全体で一意にし、並べ替えでも変えない。`answer_choice_id` はその問の選択肢IDを参照。`explanation_ja` に学習用解説を書く。

`choice_reviews` は4件。choice_id、decision（正答accept／他reject）、evidence_segment_ids（同じunitの本文ID）、reason_jaを記録する。これは内部資料で生徒用に直接出力しない。理由欄に文字があっても正しい一意解と自動認定されない。

## translation と解答表

`translation` はsegment_id、text_jaの配列。元segmentsと同じ順に1対1対応し、空所を残さない。会話の話者表示は元segmentのspeakerから復元する。日本語の内容・空所補完・話者の意味的整合は手動検査も必要。

最上位の `answer_key` は任意。保存する場合は `{"q1": 2, ...}` のように表示位置を整数で記す。CLIのderived_answer_keyと異なる古いキーはエラーになる。解答表を手で更新するより、IDから再生成する。

## 結果の解釈

終了コード0＝構造エラーなし、1＝構造エラーあり、2＝ファイルまたはJSONの読み込み失敗。重複JSONキー・NaN・不正な型を見逃さない。語数は正答補完後の本文だけ計数し、目安外は警告。正答番号の偏りそのものでは落とさない。

`manual_review_required` の項目は、CLI成功後も必ず残る。生成したWord/PDF、公式出典の実在、英語の自然さ、選択肢の一意性、訳の正確さを、このツールだけで確認したと説明しない。
