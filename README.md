# eikenpre2 — 英検準2級 Reading 教材制作

好きな作品・題材で、準2級の形式に沿ったオリジナル問題を作るためのプロンプトと構造検査ツールです。**準2級プラス・2級・準1級とは別仕様**です。

## 使い方

> このリポジトリの AGENTS.md から必須ファイルを全文読み、テーマ「○○」で準2級Reading全29問を作成。解答解説と自然な全文和訳を付け、最終組版・検査後にWordとPDFで出力。

テーマだけの依頼では全29問を既定とします。ユーザーが「長文だけ」などと指定した場合は指定範囲を優先し、「全形式の模試」とは呼びません。現在の検査CLIは全29問モード専用です。

## 読む順序

1. [AGENTS.md](AGENTS.md)：作業範囲と検証の手順。
2. [MASTER_PROMPT.md](MASTER_PROMPT.md) と [形式の正本](config/exam_profile.json)。
3. [公式資料](references/OFFICIAL_SOURCES.md)、[語数校正](references/CALIBRATION.md)、[公式選択肢の分析](references/OFFICIAL_DISTRACTOR_CASEBOOK.md)。
4. [誤答設計](rules/DISTRACTOR_DESIGN.md)、[題材の事実確認](rules/FAMOUS_EPISODE_POLICY.md)、[自然な和訳](rules/NATURAL_JAPANESE_TRANSLATION.md)。
5. [最終組版](LAYOUT_MASTER_PROMPT.md)、[準2級の配置](references/EIKEN_PRE2_LAYOUT_REFERENCE.md)、[品質ゲート](rules/QUALITY_GATES.md)。

数値の正本はJSONです。公式仕様・過去問からの観測・独自の編集基準を混同しません。確認日：2026-09-11。新規制作時は公式公開ページの更新を再確認します。

## 実装済みの範囲

Python標準ライブラリだけで、問題数、会話の空所配分、4択、ID、空所対応、解答表の同期、訳・解説・根拠欄の欠落などを検査します。CIはこの検査コードのテストと内部リンク等の整合確認を実行します。

```sh
python -m unittest discover -s tests -v
python tools/check_repo.py
python tools/validate_exam.py /path/to/exam.json
```

データの作り方は [DATA_CONTRACT.md](docs/DATA_CONTRACT.md)。終了コード0は**構造検査のみの合格**で、英文・一意解・事実・和訳・印刷品質の合格ではありません。語数の目安外は警告で、理由を確認してから修正または承認します。

**このリポジトリ単体でAIの文章生成やWord/PDF変換が自動実行されるわけではありません。** 制作するAI・編集者と変換環境が別途必要です。受験者への試行による難易度・識別力の検証、教材の初回生成と全ページ検査は、この初期実装には含みません。

標準納品は、紹介→問題→必要な語彙→解答→解説→最後に全文和訳。内部の検査表は生徒用教材に入れません。Readingのみの教材に「一次試験全体」「80分のReading」と表示しません。

## 改善の根拠

[計画の批判的見直し](docs/DESIGN_REVIEW.md) / [変更履歴](CHANGELOG.md)。元の `yutateru6-collab/eikenreading` は変更せず、共通方針を準2級用に再設計しました。元リポジトリの変更を自動同期する機能はありません。

本教材は独自の練習教材です。公式問題・公式ロゴの転載、公式教材であるとの表示はしません。公式資料はリンクと短い分析だけを管理し、全文や紙面画像をこのリポジトリへコピーしません。
