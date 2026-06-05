"""
demucs-core - 音源分離コアライブラリ
UIに依存しない。mr-demu および他アプリから呼び出される。
"""

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable

import torch
import torchaudio
import demucs.apply as _demucs_apply
from demucs.apply import apply_model
from demucs.pretrained import get_model


SUPPORTED_MODELS = {"htdemucs", "htdemucs_6s"}
SUPPORTED_FORMATS = {".mp3", ".wav", ".flac", ".m4a"}


class Separator:
    """
    Demucs を使った音源分離クラス。

    Parameters
    ----------
    model:
        使用するモデル名。"htdemucs"（4ステム）または "htdemucs_6s"（6ステム）。
    device:
        使用デバイス。None の場合は cuda → mps → cpu の順で自動選択。
    cache_dir:
        キャッシュ保存先ディレクトリ。None の場合はキャッシュ無効。
    """

    def __init__(
        self,
        model: str = "htdemucs",
        device: str | None = None,
        cache_dir: str | Path | None = None,
    ) -> None:
        if model not in SUPPORTED_MODELS:
            raise ValueError(
                f"サポート外のモデル: {model}。対応モデル: {SUPPORTED_MODELS}"
            )

        self._model_name = model
        self._device = self._resolve_device(device)
        self._cache_dir = Path(cache_dir) if cache_dir is not None else None
        self._model = None  # separate() 初回呼び出し時に遅延ロード

    @staticmethod
    def _resolve_device(device: str | None) -> str:
        if device is not None:
            return device
        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _load_model(self) -> None:
        if self._model is None:
            self._model = get_model(self._model_name)
            self._model.to(self._device)
            self._model.eval()

    @staticmethod
    def _compute_hash(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _cache_dir_for(self, audio_hash: str) -> Path:
        assert self._cache_dir is not None
        return self._cache_dir / f"{audio_hash[:16]}_{self._model_name}"

    def _check_cache(self, audio_hash: str) -> dict[str, Path] | None:
        if self._cache_dir is None:
            return None

        cache_path = self._cache_dir_for(audio_hash)
        meta_path = cache_path / "cache.json"

        if not meta_path.exists():
            return None

        with open(meta_path) as f:
            meta = json.load(f)

        # ハッシュとモデル名が一致しない場合はキャッシュ無効
        if meta.get("audio_hash") != audio_hash or meta.get("model") != self._model_name:
            return None

        result: dict[str, Path] = {}
        for stem in meta.get("stems", []):
            stem_path = cache_path / f"{stem}.wav"
            if not stem_path.exists():
                return None
            result[stem] = stem_path

        return result

    def _save_cache(self, audio_hash: str, stems: dict[str, Path]) -> dict[str, Path]:
        cache_path = self._cache_dir_for(audio_hash)
        cache_path.mkdir(parents=True, exist_ok=True)

        cached: dict[str, Path] = {}
        for stem_name, src_path in stems.items():
            dst_path = cache_path / f"{stem_name}.wav"
            if src_path.resolve() != dst_path.resolve():
                shutil.copy2(src_path, dst_path)
            cached[stem_name] = dst_path

        meta = {
            "audio_hash": audio_hash,
            "model": self._model_name,
            "stems": list(stems.keys()),
            "created_at": datetime.now().isoformat(),
        }
        with open(cache_path / "cache.json", "w") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        return cached

    def separate(
        self,
        audio_path: str | Path,
        output_dir: str | Path,
        progress_callback: Callable[[float], None] | None = None,
    ) -> dict[str, Path]:
        """
        音声ファイルをステムに分離して output_dir に保存する。

        Parameters
        ----------
        audio_path:
            入力音声ファイルのパス（MP3 / WAV / FLAC / M4A）。
        output_dir:
            分離済みステムの出力先ディレクトリ。
        progress_callback:
            進捗通知コールバック。引数は 0.0〜1.0 の進捗率。
            0.0 = 開始、1.0 = 完了。

        Returns
        -------
        dict[str, Path]
            ステム名をキー、出力ファイルパスを値とした辞書。
            例: {"drums": Path("drums.wav"), "vocals": Path("vocals.wav"), ...}

        Raises
        ------
        FileNotFoundError
            audio_path が存在しない場合。
        ValueError
            サポート外のモデルまたはフォーマットを指定した場合。
        RuntimeError
            Demucs 処理中にエラーが発生した場合。
        """
        audio_path = Path(audio_path)
        output_dir = Path(output_dir)

        if not audio_path.exists():
            raise FileNotFoundError(f"入力ファイルが存在しません: {audio_path}")

        if audio_path.suffix.lower() not in SUPPORTED_FORMATS:
            raise ValueError(
                f"サポート外のフォーマット: {audio_path.suffix}。"
                f"対応フォーマット: {SUPPORTED_FORMATS}"
            )

        # キャッシュヒット確認（ハッシュ計算はここで1回のみ）
        audio_hash = self._compute_hash(audio_path)
        cached = self._check_cache(audio_hash)
        if cached is not None:
            return cached

        # モデルの遅延ロード（初回のみ）
        self._load_model()

        # 音声読み込みとモデルのサンプルレートへのリサンプリング
        wav, orig_sr = torchaudio.load(str(audio_path))
        if orig_sr != self._model.samplerate:
            resampler = torchaudio.transforms.Resample(orig_sr, self._model.samplerate)
            wav = resampler(wav)

        # チャンネル数をモデルに合わせる
        if wav.shape[0] == 1:
            # モノラル -> ステレオに複製
            wav = wav.repeat(self._model.audio_channels, 1)
        elif wav.shape[0] > self._model.audio_channels:
            # 余分なチャンネルを切り捨て
            wav = wav[: self._model.audio_channels]

        wav = wav.to(self._device)
        # バッチ次元追加: [channels, samples] -> [1, channels, samples]
        wav = wav.unsqueeze(0)

        if progress_callback:
            progress_callback(0.0)

        try:
            sources = self._apply_with_progress(wav, progress_callback)
        except Exception as e:
            raise RuntimeError(f"Demucs 処理中にエラーが発生しました: {e}") from e

        # ステムをファイルに保存
        output_dir.mkdir(parents=True, exist_ok=True)
        result: dict[str, Path] = {}
        for i, stem_name in enumerate(self._model.sources):
            stem_wav = sources[0, i].cpu()
            stem_path = output_dir / f"{stem_name}.wav"
            torchaudio.save(str(stem_path), stem_wav, self._model.samplerate)
            result[stem_name] = stem_path

        if progress_callback:
            progress_callback(1.0)

        # キャッシュ保存
        if self._cache_dir is not None:
            self._save_cache(audio_hash, result)

        return result

    def _apply_with_progress(
        self,
        wav: torch.Tensor,
        progress_callback: Callable[[float], None] | None,
    ) -> torch.Tensor:
        """apply_model にプログレスコールバックを統合して実行する。

        demucs 4.0.1 には callback パラメータがないため、demucs.apply モジュール内の
        tqdm を一時的に差し替えてセグメント単位の進捗を取得する。
        """
        if progress_callback is None:
            return apply_model(self._model, wav, device=self._device, progress=False)

        def _make_progress_generator(iterable, **_kwargs):
            """tqdm の代替。各セグメント処理後にコールバックを呼び出す"""
            items = list(iterable)
            total = len(items)
            for i, item in enumerate(items):
                yield item
                # i+1 個処理完了: 0.05〜0.95 の範囲でレポート
                ratio = (i + 1) / total if total > 0 else 1.0
                progress_callback(0.05 + ratio * 0.9)

        class _FakeTqdmModule:
            tqdm = staticmethod(_make_progress_generator)

        original_tqdm = _demucs_apply.tqdm
        _demucs_apply.tqdm = _FakeTqdmModule()
        try:
            return apply_model(self._model, wav, device=self._device, progress=True)
        finally:
            # 必ず元に戻す
            _demucs_apply.tqdm = original_tqdm
