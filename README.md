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

```bash
pip install demucs
```

GPU使用の場合は PyTorch を別途インストール：
https://pytorch.org/get-started/locally/

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
