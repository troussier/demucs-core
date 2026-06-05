# demucs-core 仕様書 v0.1

## 概要

`demucs-core` は音源分離処理のみを担う共用コアライブラリ。
UIには一切依存せず、`mr-demu` およびその他のアプリから呼び出される。

---

## モジュール構成

```
demucs-core/
└── separator.py   # メインモジュール（Separatorクラスを定義）
```

---

## Separatorクラス

### クラス定義

```python
class Separator:
    def __init__(
        self,
        model: str = "htdemucs",
        device: str | None = None,
        cache_dir: str | Path | None = None,
    ) -> None:
        ...
```

### コンストラクタ引数

| 引数 | 型 | デフォルト | 説明 |
|------|----|-----------|------|
| `model` | `str` | `"htdemucs"` | 使用するDemucsモデル名。`"htdemucs"` または `"htdemucs_6s"` を想定 |
| `device` | `str \| None` | `None` | 使用デバイス。`None` の場合は自動選択（cuda → mps → cpu の優先順） |
| `cache_dir` | `str \| Path \| None` | `None` | キャッシュ保存先ディレクトリ。`None` の場合はキャッシュ無効 |

### メソッド

#### `separate()`

```python
def separate(
    self,
    audio_path: str | Path,
    output_dir: str | Path,
    progress_callback: Callable[[float], None] | None = None,
) -> dict[str, Path]:
    ...
```

音声ファイルをステムに分離して出力ディレクトリに保存する。

**引数**

| 引数 | 型 | 説明 |
|------|----|------|
| `audio_path` | `str \| Path` | 入力音声ファイルのパス |
| `output_dir` | `str \| Path` | 分離済みステムの出力先ディレクトリ |
| `progress_callback` | `Callable[[float], None] \| None` | 進捗通知コールバック。引数は0.0〜1.0の進捗率 |

**戻り値**

```python
{
    "drums":  Path("/path/to/output/drums.wav"),
    "bass":   Path("/path/to/output/bass.wav"),
    "other":  Path("/path/to/output/other.wav"),
    "vocals": Path("/path/to/output/vocals.wav"),
    # htdemucs_6s の場合はさらに:
    "guitar": Path("/path/to/output/guitar.wav"),
    "piano":  Path("/path/to/output/piano.wav"),
}
```

ステム名をキー、出力ファイルパスを値とした `dict` を返す。

**例外**

| 例外 | 発生条件 |
|------|---------|
| `FileNotFoundError` | `audio_path` が存在しない場合 |
| `ValueError` | サポート外のモデル名やフォーマットを指定した場合 |
| `RuntimeError` | Demucsの処理中にエラーが発生した場合 |

---

## 入出力仕様

### 入力

| 項目 | 仕様 |
|------|------|
| 対応フォーマット | MP3 / WAV / FLAC / M4A |
| チャンネル | モノラル・ステレオ両対応 |
| サンプルレート | Demucsが内部でリサンプリングするため制限なし |

### 出力

| 項目 | 仕様 |
|------|------|
| フォーマット | WAV（PCM 16bit または 32bit float） |
| サンプルレート | 入力と同じ（Demucs出力に準拠） |
| ファイル名 | `{stem_name}.wav`（例：`vocals.wav`） |

---

## キャッシュ仕様

### 概要

同じ曲・同じモデルで再実行した場合は再処理せずキャッシュを返す。

### キャッシュの有効条件

キャッシュヒットの判定は以下の両方が一致する場合：

1. 入力ファイルのSHA-256ハッシュ
2. モデル名

### キャッシュのデータ構造

```
{cache_dir}/
└── {sha256_of_input[:16]}_{model_name}/
    ├── drums.wav
    ├── bass.wav
    ├── other.wav
    ├── vocals.wav
    └── cache.json   # メタデータ（入力ファイルハッシュ・モデル名・作成日時）
```

### キャッシュヒット時の動作

- Demucsの処理をスキップしてキャッシュ内のファイルパスを返す
- `progress_callback` は呼び出さない（または即座に1.0を返す）

### キャッシュ無効化

- `cache_dir=None` を指定した場合はキャッシュを使用しない
- キャッシュの手動削除はディレクトリを直接操作することで行う（クリアAPIは提供しない）

---

## プログレスコールバック仕様

### シグネチャ

```python
Callable[[float], None]
```

### 引数

| 引数 | 型 | 説明 |
|------|----|------|
| `progress` | `float` | 進捗率（0.0〜1.0）。0.0が開始、1.0が完了 |

### 呼び出しタイミング

- 処理開始時：`0.0`
- 処理中：Demucsの進捗に応じて随時（目安として5〜10%刻み）
- 処理完了時：`1.0`

### 注意事項

- コールバックはメインスレッドから呼び出される
- コールバック内で重い処理を行う場合は呼び出し元の責任でスレッド処理すること
- コールバックが例外を投げた場合の動作は未定義（呼び出し元が適切にハンドリングすること）

---

## デバイス自動選択ロジック

`device=None` の場合、以下の優先順で自動選択する：

1. CUDA（`torch.cuda.is_available()`）
2. MPS（`torch.backends.mps.is_available()`）
3. CPU（フォールバック）

---

## 対応モデル

| モデル名 | ステム数 | ステム一覧 |
|----------|---------|-----------|
| `htdemucs` | 4 | drums, bass, other, vocals |
| `htdemucs_6s` | 6 | drums, bass, other, vocals, guitar, piano |

---

## 依存ライブラリ

| ライブラリ | 用途 |
|-----------|------|
| `demucs` | 音源分離モデル本体 |
| `torch` | PyTorch（GPU/MPS対応） |
| `torchaudio` | 音声ファイルの読み書き |
