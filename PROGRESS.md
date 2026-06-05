# PROGRESS.md - demucs-core

## 現在の状態

🟡 基本実装完了・テスト済み

---

## 今回やったこと

1. `mr-demu/docs/spec.md` を読んでアプリ全体仕様を把握
2. `docs/spec.md` を作成（Separatorクラス・入出力・キャッシュ・プログレスコールバックの仕様）
3. `CLAUDE.md` に仕様書参照先を追記
4. `separator.py` を実装・動作確認
   - `Separator` クラスの設計と実装
   - `separate()` メソッド（音源分離・ステム保存）
   - モデル選択（htdemucs / htdemucs_6s）対応
   - デバイス自動選択（cuda → mps → cpu）
   - キャッシュ機能（SHA-256ハッシュ + モデル名で一意識別）
   - プログレスコールバック（demucs.apply.tqdmのモンキーパッチで実装）
5. 開発環境構築（.venv / demucs / FFmpeg）

---

## 次にやること

- [ ] 実音源ファイルでのテスト（MP3 / FLAC / M4A）
- [ ] `htdemucs_6s` モデルのテスト（6ステム）
- [ ] `mr-demu` から `separator.py` を呼び出して統合確認

---

## 未解決の問題

- プログレスコールバックの粒度が粗い（短いファイルはセグメント1個なので 0% → 95% → 100% の3値のみ）
  - 実際の楽曲（3〜5分）では複数セグメントになるため実用上は問題なし
- torchaudio 2.11.0 は FFmpeg（`brew install ffmpeg`）が必須
  - PyInstaller でバイナリ配布する際は FFmpeg のバンドルが必要
