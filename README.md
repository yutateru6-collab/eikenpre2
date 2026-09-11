# eikenpre2 — 英検準2級 Reading教材

好きな作品・人物・テーマを入口に、**準2級Readingの29問**と解答解説・自然な全文和訳を制作するための指示・参照資料・構造検査ツールです。準2級プラスではありません。英検協会の公式教材でもありません。

## 使い方

GitHubを読める制作環境で、次のように依頼します。

> `yutateru6-collab/eikenpre2` の `AGENTS.md` から必読ファイルを全文読み、準2級Readingをテーマ「ドラえもん」で作成。現行公式資料を確認し、29問の問題・語彙・解答解説・最後に自然な全文和訳を、WordとPDFで。作品の実際のエピソードを使い、原作にない出来事を本編の事実にしない。内部検査表は教材に載せない。

詳しい指定は [依頼テンプレート](templates/REQUEST_TEMPLATE.md)。参照できない環境では、必読ファイルを渡す必要があります。リポジトリ名だけで、どの環境にも自動で指示が適用されるわけではありません。

## 最初に読む

[AGENTS.md](AGENTS.md) → [作問](MASTER_PROMPT.md) → [組版](LAYOUT_MASTER_PROMPT.md) → そこで指定する規則・参照資料。

数値・構成の機械可読な正本は [specs/pre2_reading.json](specs/pre2_reading.json)。公式に明示された構成、直近3回で観察した配置、本教材の設定値を区別します。公式確認日は2026-09-11。新規制作時には公式掲載ページを再確認してください。

| 大問 | 内容 | 問番号 |
|---|---|---|
| 1 | 短文空所15問 | 1–15 |
| 2 | 4会話・5空所。最後の会話に2空所 | 16–20 |
| 3 | 1長文・2空所 | 21–22 |
| 4A | Eメール・3問 | 23–25 |
| 4B | 説明文・4問 | 26–29 |

出典と確認範囲は [公式分析](references/OFFICIAL_PRE2_ANALYSIS.md)。80分は公式のReading＋Writing合計であり、このReading専用教材の公式制限時間ではありません。Writing・Listening・面接は今回の対象外です。

## 実装されていること

- 準2級専用プロンプト、7ページのReading問題配置、公式3回分の観察記録、誤答設計・和訳・事実確認の規則。
- Python標準ライブラリによる教材JSONの構造検査、本文語数集計、安定IDからの解答番号導出。
- 不正なデータを検出する回帰テストと、GitHub Actionsによるテスト実行。

```bash
python3 -m unittest discover -s tests -v
python3 tools/check_repository.py
python3 tools/validate_pack.py path/to/pack.json
python3 tools/validate_pack.py path/to/pack.json --answer-key
```

Python 3.10以降を想定。基本検査にはAPIキー・追加パッケージは不要です。JSONの作り方は [データ契約](docs/DATA_CONTRACT.md)。終了コード0は**機械的条件を通過しただけ**で、意味・事実・訳の品質・最終レイアウトの合格を意味しません。語数警告は修正または根拠のある確認が必要です。

## 実装していないこと

このリポジトリ単体は、テーマ入力だけでAI生成・Word/PDF作成・公開まで自動実行するアプリではありません。AI呼び出し、DOCX/PDFレンダラー、内容の自動正誤判定、受験者による難易度・識別力測定は未実装です。制作環境で作問・組版を行い、意味の確認と全ページ画像確認を別に実施します。CIが緑でも教材の完成を保証しません。

[設計の見直し](docs/DESIGN_REVIEW.md) / [変更履歴](CHANGELOG.md)。元の `eikenreading` は変更せず、共通思想を参照して準2級専用に再設計しました。公式問題の本文・選択肢・画像・フォントファイルは同梱しません。
