#!/usr/bin/env python3
"""Offline synthetic speech, dialogue, and silence fixtures for the test-recording-generate Skill.

Requires macOS `say` for speech and ffmpeg/ffprobe for encoding and inspection.
No network, product API, or credentials are used.
"""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


CODECS = {"wav": "pcm_s16le", "mp3": "libmp3lame", "m4a": "aac"}
PROBE_CODECS = {"wav": "pcm_s16le", "mp3": "mp3", "m4a": "aac"}
FIXTURE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
SPEC_FIELDS = {"feature_id", "environment", "voice", "format", "rate_wpm", "fixtures"}
FIXTURE_FIELDS = {"fixture_id", "kind", "purpose", "text", "duration_seconds", "expectation_status",
                  "oracle_reference", "expected_tags", "turns", "pause_seconds",
                  "min_duration_seconds", "max_duration_seconds"}
TURN_FIELDS = {"speaker", "text", "voice"}
MAX_TURNS = 40
MAX_TEXT = 2000
MAX_FIXTURE_TEXT = 20000
AUDIBLE_DB_FLOOR = -60.0


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _text(value, field, limit=MAX_TEXT):
    if not isinstance(value, str) or not value.strip() or any(ord(char) < 32 for char in value):
        raise ValueError(f"{field} must be nonempty text without control characters")
    value = value.strip()
    if len(value) > limit:
        raise ValueError(f"{field} exceeds {limit} characters")
    return value


def _voice(value, field="voice"):
    value = _text(value, field, 80)
    if value.startswith("-"):
        raise ValueError(f"invalid {field}")
    return value


def _seconds(value, field, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
        raise ValueError(f"{field} must be between {low} and {high}")
    return float(value)


def _duration_bounds(item):
    low = _seconds(item["min_duration_seconds"], "min_duration_seconds", 0.1, 600) \
        if "min_duration_seconds" in item else None
    high = _seconds(item["max_duration_seconds"], "max_duration_seconds", 0.1, 600) \
        if "max_duration_seconds" in item else None
    if low is not None and high is not None and low > high:
        raise ValueError("min_duration_seconds must not exceed max_duration_seconds")
    return low, high


def _validate(spec):
    if not isinstance(spec, dict):
        raise ValueError("spec must be a JSON object")
    unknown = set(spec) - SPEC_FIELDS
    if unknown:
        raise ValueError(f"unsupported spec fields: {', '.join(sorted(unknown))}")
    feature = _text(spec.get("feature_id"), "feature_id", 120)
    environment = _text(spec.get("environment"), "environment", 60)
    fmt = spec.get("format", "wav")
    if fmt not in CODECS:
        raise ValueError("format must be wav, mp3 or m4a")
    voice = _voice(spec.get("voice"))
    rate = spec.get("rate_wpm", 180)
    if type(rate) is not int or not 120 <= rate <= 240:
        raise ValueError("rate_wpm must be an integer between 120 and 240")
    fixtures = spec.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise ValueError("fixtures must be a nonempty list")
    seen = set()
    validated = []
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            raise ValueError("each fixture must be an object")
        item = dict(fixture)
        unknown = set(item) - FIXTURE_FIELDS
        if unknown:
            raise ValueError(f"unsupported fixture fields: {', '.join(sorted(unknown))}")
        identifier = item.get("fixture_id")
        if not isinstance(identifier, str) or not FIXTURE_ID.fullmatch(identifier) or identifier in (".", ".."):
            raise ValueError("unsafe fixture_id")
        if identifier in seen:
            raise ValueError("duplicate fixture_id")
        seen.add(identifier)
        item["purpose"] = _text(item.get("purpose"), "purpose", 200)
        kind = item.get("kind")
        if kind in ("speech", "dialogue"):
            if "duration_seconds" in item:
                raise ValueError(f"{kind} duration cannot be guaranteed; omit duration_seconds")
            item["min_duration_seconds"], item["max_duration_seconds"] = _duration_bounds(item)
        if kind == "speech":
            item["text"] = _text(item.get("text"), "text")
        elif kind == "dialogue":
            turns = item.get("turns")
            if not isinstance(turns, list) or not turns or len(turns) > MAX_TURNS:
                raise ValueError(f"dialogue turns must be a list of 1..{MAX_TURNS} objects")
            item["pause_seconds"] = _seconds(item.get("pause_seconds", 0.4), "pause_seconds", 0, 2)
            validated_turns = []
            total = 0
            for turn in turns:
                if not isinstance(turn, dict):
                    raise ValueError("each dialogue turn must be an object")
                unknown = set(turn) - TURN_FIELDS
                if unknown:
                    raise ValueError(f"unsupported turn fields: {', '.join(sorted(unknown))}")
                text = _text(turn.get("text"), "turn text")
                total += len(text)
                if total > MAX_FIXTURE_TEXT:
                    raise ValueError(f"dialogue text exceeds {MAX_FIXTURE_TEXT} characters")
                validated_turns.append({
                    "speaker": _text(turn.get("speaker"), "speaker", 40),
                    "text": text,
                    "voice": _voice(turn["voice"], "turn voice") if "voice" in turn else voice,
                })
            item["turns"] = validated_turns
        elif kind == "silence":
            if "text" in item or "turns" in item:
                raise ValueError("silence cannot have text or turns")
            _duration_bounds(item)
            item["duration_seconds"] = _seconds(item.get("duration_seconds"), "duration_seconds", 0.1, 60)
        else:
            raise ValueError("kind must be speech, dialogue or silence")
        status = item.get("expectation_status")
        if status not in ("pending", "approved"):
            raise ValueError("expectation_status must be pending or approved")
        if status == "approved":
            item["oracle_reference"] = _text(item.get("oracle_reference"), "oracle_reference", 300)
            tags = item.get("expected_tags")
            if not isinstance(tags, list) or not tags or any(
                    not isinstance(tag, str) or not tag.strip() for tag in tags):
                raise ValueError("approved expectation needs nonempty expected_tags")
            if len(tags) > 50:
                raise ValueError("too many expected_tags")
        elif "expected_tags" in item or "oracle_reference" in item:
            raise ValueError("pending expectation must not declare tags or oracle reference")
        validated.append(item)
    return feature, environment, fmt, voice, rate, validated


def _run_tool(arguments):
    result = subprocess.run(arguments, capture_output=True, text=True, check=False)
    if result.returncode:
        # Tool errors may echo input; never put subprocess stderr (or speech text) in a report.
        raise RuntimeError(f"audio tool failed: {Path(arguments[0]).name} (exit {result.returncode})")
    return result.stdout, result.stderr


def _run(arguments):
    return _run_tool(arguments)[0]


def _audible_db(path):
    """Reject silent synthesis: a playable file is not proof that speech was spoken."""
    _, stderr = _run_tool(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(path),
                           "-af", "volumedetect", "-f", "null", "-"])
    match = re.search(r"mean_volume:\s*(-?[\d.]+) dB", stderr)
    if not match:
        raise RuntimeError("unable to measure audio level")
    level = float(match.group(1))
    if level <= AUDIBLE_DB_FLOOR:
        raise RuntimeError("synthesized speech is effectively silent; check the installed voice")
    return round(level, 1)


def _say(text, voice, rate, target):
    """Synthesize one utterance through stdin so speech text never appears in argv."""
    aiff = target.with_suffix(".aiff")
    process = subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff)],
                             input=text, capture_output=True, text=True, check=False)
    if process.returncode or not aiff.is_file():
        raise RuntimeError("say failed; check the installed voice")
    _run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(aiff),
          "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(target)])
    aiff.unlink()


def _silence_wav(seconds, target):
    _run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
          "-i", "anullsrc=r=16000:cl=mono", "-t", str(seconds), "-c:a", "pcm_s16le", str(target)])


def _encode(source, target, fmt):
    if fmt == "wav":
        shutil.copy2(source, target)
        return
    _run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(source),
          "-ac", "1", "-ar", "16000", "-c:a", CODECS[fmt], str(target)])


def _build_dialogue(item, fmt, rate, stage, target):
    parts = []
    for index, turn in enumerate(item["turns"]):
        part = stage / f"{item['fixture_id']}_turn{index:02d}.wav"
        _say(turn["text"], turn["voice"], rate, part)
        parts.append(part)
        if item["pause_seconds"] and index < len(item["turns"]) - 1:
            gap = stage / f"{item['fixture_id']}_gap{index:02d}.wav"
            _silence_wav(item["pause_seconds"], gap)
            parts.append(gap)
    listing = stage / f"{item['fixture_id']}_concat.txt"
    listing.write_text("".join(f"file '{part.name}'\n" for part in parts), encoding="utf-8")
    merged = stage / f"{item['fixture_id']}_merged.wav"
    _run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "concat",
          "-safe", "0", "-i", str(listing), "-c", "copy", str(merged)])
    _encode(merged, target, fmt)
    for part in parts + [listing, merged]:
        part.unlink()
    return [{"speaker": turn["speaker"], "text": turn["text"], "voice": turn["voice"]}
            for turn in item["turns"]]


def _probe(path, fmt):
    output = _run(["ffprobe", "-v", "error", "-show_entries",
                   "stream=codec_name,sample_rate,channels:format=duration",
                   "-select_streams", "a:0", "-of", "json", str(path)])
    metadata = json.loads(output)
    streams = metadata.get("streams", [])
    if len(streams) != 1:
        raise RuntimeError("audio stream missing")
    stream = streams[0]
    duration = float(metadata.get("format", {}).get("duration", "0"))
    if (stream.get("codec_name") != PROBE_CODECS[fmt]
            or int(stream.get("sample_rate", 0)) != 16000
            or int(stream.get("channels", 0)) != 1
            or not 0 < duration <= 900):
        raise RuntimeError("audio probe mismatch")
    return {"codec": stream["codec_name"], "sample_rate": 16000,
            "channels": 1, "duration_seconds": round(duration, 3)}


TRANSCRIPT_FILE = "recording_transcripts.md"


def transcripts_markdown(manifest):
    """One human-readable document holding the spoken text of every recording.

    The manifest keeps machine fields; this document is what a reviewer reads and
    what a later semantic check compares against the transcription.
    """
    lines = ["# 合成录音逐字稿", "",
             f'- feature_id: {manifest["feature_id"]}',
             f'- environment: {manifest["environment"]}',
             f'- 输出格式: {manifest["format"]} / 16000Hz / 单声道',
             f'- 语速(rate_wpm): {manifest["rate_wpm"]}',
             f'- 生成器: {manifest["generator"]} ({manifest["platform"]})',
             f'- 生成时间: {manifest["generated_at"]}',
             f'- spec_sha256: {manifest["spec_sha256"]}',
             f'- 预期核对状态: expectations_verified={str(manifest["expectations_verified"]).lower()}'
             '（语料内容仍需人工试听或独立转写复核）', "",
             '| 文件 | 类型 | 时长 | 轮次 | 预期状态 |', '| --- | --- | --- | --- | --- |']
    for item in manifest["fixtures"]:
        turns = item.get("turn_count", "-")
        lines.append(f'| {item["path"]} | {item["kind"]} | '
                     f'{item["probe"]["duration_seconds"]}s | {turns} | {item["expectation_status"]} |')
    lines.append("")
    for item in manifest["fixtures"]:
        lines.extend([f'## {item["fixture_id"]}', "",
                      f'- 文件: {item["path"]}',
                      f'- 用途: {item["purpose"]}',
                      f'- 时长: {item["probe"]["duration_seconds"]}s（{item["probe"]["codec"]} '
                      f'{item["probe"]["sample_rate"]}Hz {item["probe"]["channels"]}ch）',
                      f'- 预期状态: {item["expectation_status"]}', ""])
        if item["kind"] == "dialogue":
            lines.extend([f'- 说话人: {"、".join(item["speakers"])}',
                          f'- 轮次: {item["turn_count"]}'])
            for turn in item["turns"]:
                lines.append(f'- {turn["speaker"]}（{turn["voice"]}）：{turn["text"]}')
        elif item["kind"] == "speech":
            lines.extend([f'- 音色: {item["voice"]}', f'- 文本: {item["text"]}'])
        else:
            lines.append(f'- 静音 {item["requested_duration_seconds"]}s，无台词')
        lines.append("")
    return "\n".join(lines) + "\n"


def generate_recordings(spec, output_dir):
    feature, environment, fmt, voice, rate, fixtures = _validate(spec)
    output = Path(output_dir).absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"output already exists: {output}")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg and ffprobe are required on PATH")
    needs_say = any(f["kind"] in ("speech", "dialogue") for f in fixtures)
    if needs_say and (platform.system() != "Darwin" or not shutil.which("say")):
        raise RuntimeError("speech synthesis requires macOS say; no silent fallback")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".recordings-", dir=output.parent))
    try:
        results = []
        for item in fixtures:
            identifier = item["fixture_id"]
            path = stage / f"{identifier}.{fmt}"
            turns = None
            if item["kind"] == "speech":
                raw = stage / f"{identifier}_raw.wav"
                _say(item["text"], voice, rate, raw)
                _encode(raw, path, fmt)
                raw.unlink()
            elif item["kind"] == "dialogue":
                turns = _build_dialogue(item, fmt, rate, stage, path)
            else:
                raw = stage / f"{identifier}_raw.wav"
                _silence_wav(item["duration_seconds"], raw)
                _encode(raw, path, fmt)
                raw.unlink()
            probe = _probe(path, fmt)
            level = _audible_db(path) if item["kind"] in ("speech", "dialogue") else None
            if item["kind"] == "silence" and abs(probe["duration_seconds"] - item["duration_seconds"]) > 0.15:
                raise RuntimeError("silence duration mismatch")
            if item.get("min_duration_seconds") is not None:
                if probe["duration_seconds"] < item["min_duration_seconds"]:
                    raise RuntimeError(
                        f"{identifier} is shorter than min_duration_seconds "
                        f"({probe['duration_seconds']} < {item['min_duration_seconds']})")
                if item["max_duration_seconds"] and probe["duration_seconds"] > item["max_duration_seconds"]:
                    raise RuntimeError(
                        f"{identifier} is longer than max_duration_seconds "
                        f"({probe['duration_seconds']} > {item['max_duration_seconds']})")
            result = {"fixture_id": identifier, "kind": item["kind"], "purpose": item["purpose"],
                      "path": path.name, "sha256": sha256(path), "probe": probe,
                      "expectation_status": item["expectation_status"],
                      "audio_content_review": "not_performed", "cleanup": "run_local_remove_after_use"}
            if level is not None:
                result["mean_volume_db"] = level
            if item.get("min_duration_seconds") is not None:
                result["enforced_min_duration_seconds"] = item["min_duration_seconds"]
            if item.get("max_duration_seconds") is not None:
                result["enforced_max_duration_seconds"] = item["max_duration_seconds"]
            if item["kind"] == "speech":
                result["text"] = item["text"]
                result["voice"] = voice
            elif item["kind"] == "dialogue":
                result["turns"] = turns
                result["turn_count"] = len(turns)
                result["speakers"] = list(dict.fromkeys(turn["speaker"] for turn in turns))
                result["voices"] = list(dict.fromkeys(turn["voice"] for turn in turns))
                result["pause_seconds"] = item["pause_seconds"]
            else:
                result["requested_duration_seconds"] = item["duration_seconds"]
            if item["expectation_status"] == "approved":
                result["oracle_reference"] = item["oracle_reference"]
                result["expected_tags"] = item["expected_tags"]
            results.append(result)
        manifest = {"schema_version": 1, "status": "generated", "feature_id": feature,
                    "environment": environment, "format": fmt, "voice": voice, "rate_wpm": rate,
                    "generator": "macos-say+ffmpeg" if needs_say else "ffmpeg-anullsrc",
                    "platform": platform.system(),
                    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "transcripts": TRANSCRIPT_FILE,
                    "spec_sha256": hashlib.sha256(
                        json.dumps(spec, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
                    "expectations_verified": False, "fixtures": results}
        (stage / "recording_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (stage / TRANSCRIPT_FILE).write_text(transcripts_markdown(manifest), encoding="utf-8")
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"output appeared during generation: {output}")
        os.rename(stage, output)
        return manifest
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description="Generate offline synthetic recording fixtures")
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="new run-local output directory; never overwritten")
    args = parser.parse_args()
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        manifest = generate_recordings(spec, args.output)
    except (ValueError, RuntimeError, FileExistsError, OSError, json.JSONDecodeError) as error:
        print(f"blocked: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": manifest["status"],
                      "manifest": str(args.output / "recording_manifest.json"),
                      "transcripts": str(args.output / TRANSCRIPT_FILE),
                      "count": len(manifest["fixtures"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
