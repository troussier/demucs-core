# demucs-core

音源分離ライブラリ。[Meta Demucs](https://github.com/facebookresearch/demucs) のラッパーとして、ステム分離処理のみを担う共用コアモジュール。

デミュ九郎 (Mr.Demu) およびその他のアプリから参照される。

---

## 対応モデル

| モデル | ステム数 | 特徴 |
|--------|----------|------|
| `htdemucs` | 4 | デフォルト。品質と速度のバランスが良い |
| `htdemucs_6s` | 6 | ギター・ピアノも分離可能 |

## 出力ステム

- **4ステム：** drums / bass / vocals / other
- **6ステム：** drums / bass / vocals / guitar / piano / other

---

## セットアップ

**システム依存（pip管理外）**

```bash
# macOS
brew install ffmpeg
```

**Python 依存**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

GPU使用の場合は PyTorch を別途インストール：
https://pytorch.org/get-started/locally/

**注意事項**

- Python 3.13.x を使用すること（バージョンが異なると torch のインストールに失敗する場合あり）
- Intel Mac / Linux では `requirements.txt` のホイールが合わない場合があるので `pip install demucs` から入れ直す
- モデルファイル（約80MB）は初回実行時に `~/.cache/torch/hub/checkpoints/` へ自動ダウンロードされる（ネット接続が必要）

---

## 使い方

```python
from separator import Separator

sep = Separator(model="htdemucs")
sep.separate("song.mp3", output_dir="./output")
```

---

## ライセンス

MIT
