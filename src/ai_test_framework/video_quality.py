"""Deterministic technical quality checks for video evidence."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


DEFAULT_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "black_frames": {
        "min_segment_seconds": 0.5,
        "picture_black_ratio": 0.98,
        "pixel_black_threshold": 0.10,
        "max_total_ratio": 0.05,
        "max_segment_seconds": 2.0,
        "rerecord_ratio": 0.50,
    },
    "static_frames": {
        "min_segment_seconds": 3.0,
        "noise_tolerance": 0.003,
        "max_total_ratio": 0.25,
        "max_segment_seconds": 10.0,
        "rerecord_ratio": 0.80,
    },
}

BLACK_RE = re.compile(
    r"black_start:(?P<start>[0-9.]+)\s+black_end:(?P<end>[0-9.]+)"
    r"\s+black_duration:(?P<duration>[0-9.]+)"
)
FREEZE_RE = re.compile(r"freeze_(?P<kind>start|duration|end):\s*(?P<value>[0-9.]+)")


class ToolUnavailable(RuntimeError):
    """Raised when ffprobe or ffmpeg cannot be launched."""


def _run_command(
    command: List[str], runner: Callable[..., Any]
) -> Any:
    try:
        return runner(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise ToolUnavailable(command[0]) from exc
    except OSError as exc:
        raise ToolUnavailable(command[0]) from exc


def _thresholds(spec: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    merged = {name: dict(values) for name, values in DEFAULT_THRESHOLDS.items()}
    for source in (spec.get("defaults", {}), item.get("thresholds", {})):
        for name in ("black_frames", "static_frames"):
            values = source.get(name, {}) if isinstance(source, dict) else {}
            if isinstance(values, dict):
                merged[name].update(values)
    return merged


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _valid_threshold_source(source: Any) -> bool:
    if not isinstance(source, dict) or not set(source).issubset(DEFAULT_THRESHOLDS):
        return False
    for name, values in source.items():
        if not isinstance(values, dict) or not set(values).issubset(DEFAULT_THRESHOLDS[name]):
            return False
    return True


def _valid_item_configuration(spec: Dict[str, Any], item: Dict[str, Any]) -> bool:
    allowed = {
        "evidence_id", "case_id", "path", "expected_duration_seconds", "step_labels", "thresholds"
    }
    if not set(item).issubset(allowed):
        return False
    if not all(isinstance(item.get(name), str) and item[name] for name in ("evidence_id", "case_id")):
        return False
    labels = item.get("step_labels", [])
    if (
        not isinstance(labels, list)
        or any(not isinstance(label, str) or not label for label in labels)
        or len(labels) != len(set(labels))
    ):
        return False
    if not _valid_threshold_source(spec.get("defaults", {})):
        return False
    if not _valid_threshold_source(item.get("thresholds", {})):
        return False
    expected = item.get("expected_duration_seconds")
    if not isinstance(expected, dict) or not expected or not set(expected).issubset({"minimum", "maximum"}):
        return False
    if any(not _is_number(value) for value in expected.values()):
        return False
    minimum = expected.get("minimum")
    maximum = expected.get("maximum")
    if minimum is not None and minimum < 0:
        return False
    if maximum is not None and maximum <= 0:
        return False
    if minimum is not None and maximum is not None and minimum > maximum:
        return False

    thresholds = _thresholds(spec, item)
    black = thresholds["black_frames"]
    static = thresholds["static_frames"]
    if any(not _is_number(value) for values in thresholds.values() for value in values.values()):
        return False
    ratio_fields = (
        black["picture_black_ratio"], black["pixel_black_threshold"],
        black["max_total_ratio"], black["rerecord_ratio"],
        static["max_total_ratio"], static["rerecord_ratio"],
    )
    if any(value < 0 or value > 1 for value in ratio_fields):
        return False
    if black["min_segment_seconds"] <= 0 or static["min_segment_seconds"] <= 0:
        return False
    if black["max_segment_seconds"] < 0 or static["max_segment_seconds"] < 0:
        return False
    if static["noise_tolerance"] < 0:
        return False
    return (
        black["rerecord_ratio"] >= black["max_total_ratio"]
        and static["rerecord_ratio"] >= static["max_total_ratio"]
    )


def _segment(start: float, end: float) -> Dict[str, float]:
    start = max(0.0, start)
    end = max(start, end)
    return {
        "start_seconds": round(start, 6),
        "end_seconds": round(end, 6),
        "duration_seconds": round(end - start, 6),
    }


def _merge_segments(segments: List[Dict[str, float]], duration: float) -> List[Dict[str, float]]:
    ranges: List[Tuple[float, float]] = []
    for item in segments:
        start = min(duration, max(0.0, float(item["start_seconds"])))
        end = min(duration, max(start, float(item["end_seconds"])))
        if end > start:
            ranges.append((start, end))
    ranges.sort()
    merged: List[Tuple[float, float]] = []
    for start, end in ranges:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return [_segment(start, end) for start, end in merged]


def _parse_black_segments(output: str, duration: float) -> List[Dict[str, float]]:
    segments = [
        _segment(float(match.group("start")), float(match.group("end")))
        for match in BLACK_RE.finditer(output)
    ]
    return _merge_segments(segments, duration)


def _parse_static_segments(output: str, duration: float) -> List[Dict[str, float]]:
    segments: List[Dict[str, float]] = []
    current: Optional[Dict[str, float]] = None
    for match in FREEZE_RE.finditer(output):
        kind = match.group("kind")
        value = float(match.group("value"))
        if kind == "start":
            if current is not None:
                segments.append(_segment(current["start"], value))
            current = {"start": value}
        elif kind == "duration" and current is not None:
            current["duration"] = value
        elif kind == "end" and current is not None:
            start = current["start"]
            end = value
            if end < start and "duration" in current:
                end = start + current["duration"]
            segments.append(_segment(start, end))
            current = None
    if current is not None:
        end = current["start"] + current.get("duration", duration - current["start"])
        segments.append(_segment(current["start"], min(duration, end)))
    return _merge_segments(segments, duration)


def _metrics(segments: List[Dict[str, float]], duration: float) -> Tuple[float, float, float]:
    total = sum(item["duration_seconds"] for item in segments)
    longest = max((item["duration_seconds"] for item in segments), default=0.0)
    ratio = total / duration if duration > 0 else 0.0
    return round(total, 6), round(longest, 6), round(ratio, 6)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _input_sha256(spec: Any) -> str:
    canonical = json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_bytes(canonical.encode("utf-8"))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _probe_video(path: Path, executable: str, runner: Callable[..., Any]) -> Dict[str, Any]:
    result = _run_command([
        executable,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "format=duration:stream=width,height,duration",
        "-of", "json",
        str(path),
    ], runner)
    if result.returncode != 0:
        raise ValueError("ffprobe_failed")
    try:
        payload = json.loads(result.stdout)
        stream = payload.get("streams", [])[0]
        duration = None
        for candidate in (payload.get("format", {}).get("duration"), stream.get("duration")):
            try:
                duration = float(candidate)
                break
            except (ValueError, TypeError):
                continue
        width = int(stream["width"])
        height = int(stream["height"])
    except (ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError) as exc:
        raise ValueError("video_metadata_unreadable") from exc
    if duration is None or duration <= 0 or width <= 0 or height <= 0:
        raise ValueError("video_metadata_unreadable")
    return {
        "duration_seconds": round(duration, 6),
        "width": width,
        "height": height,
        "sha256": _file_sha256(path),
    }


def _analyze_filter(
    path: Path,
    executable: str,
    filter_value: str,
    runner: Callable[..., Any],
) -> str:
    result = _run_command([
        executable, "-hide_banner", "-nostats", "-i", str(path),
        "-vf", filter_value, "-an", "-f", "null", "-",
    ], runner)
    if result.returncode != 0:
        raise ValueError("ffmpeg_analysis_failed")
    return "\n".join(part for part in (result.stdout, result.stderr) if part)


def _blocked_item(
    item: Dict[str, Any], code: str, probe: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    return {
        "evidence_id": item.get("evidence_id", "UNKNOWN"),
        "case_id": item.get("case_id", "UNKNOWN"),
        "path": item.get("path", ""),
        "step_labels": item.get("step_labels", []),
        "status": "blocked",
        "disposition": "blocked",
        "probe": probe,
        "checks": {},
        "issues": [{"code": code, "severity": "error"}],
        "recommended_actions": ["restore_input_or_analysis_tool_and_retry"],
    }


def _resolve_video(root: Path, relative: str) -> Optional[Path]:
    root = root.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path


def _check_item(
    spec: Dict[str, Any],
    item: Dict[str, Any],
    *,
    root: Path,
    ffprobe: str,
    ffmpeg: str,
    runner: Callable[..., Any],
) -> Dict[str, Any]:
    if not _valid_item_configuration(spec, item):
        return _blocked_item(item, "invalid_video_item")
    path_value = item.get("path")
    if not isinstance(path_value, str) or not path_value:
        return _blocked_item(item, "invalid_video_path")
    path = _resolve_video(root, path_value)
    if path is None:
        return _blocked_item(item, "path_outside_root")
    if not path.is_file():
        return _blocked_item(item, "video_missing")

    try:
        probe = _probe_video(path, ffprobe, runner)
    except ToolUnavailable:
        return _blocked_item(item, "ffprobe_unavailable")
    except ValueError as exc:
        return _blocked_item(item, str(exc))

    thresholds = _thresholds(spec, item)
    black = thresholds["black_frames"]
    static = thresholds["static_frames"]
    try:
        analysis_output = _analyze_filter(
            path,
            ffmpeg,
            "blackdetect=d={}:pic_th={}:pix_th={},freezedetect=n={}:d={}".format(
                black["min_segment_seconds"],
                black["picture_black_ratio"],
                black["pixel_black_threshold"],
                static["noise_tolerance"],
                static["min_segment_seconds"],
            ),
            runner,
        )
    except ToolUnavailable:
        return _blocked_item(item, "ffmpeg_unavailable", probe)
    except ValueError as exc:
        return _blocked_item(item, str(exc), probe)

    duration = probe["duration_seconds"]
    black_segments = _parse_black_segments(analysis_output, duration)
    static_segments = _parse_static_segments(analysis_output, duration)
    black_total, black_longest, black_ratio = _metrics(black_segments, duration)
    static_total, static_longest, static_ratio = _metrics(static_segments, duration)

    issues: List[Dict[str, Any]] = []
    actions: List[str] = []
    disposition = "passed"

    expected = item.get("expected_duration_seconds", {})
    minimum = expected.get("minimum")
    maximum = expected.get("maximum")
    duration_status = "passed"
    if minimum is not None and duration < float(minimum):
        duration_status = "failed"
        disposition = "rerecord_required"
        issues.append({"code": "duration_below_minimum", "severity": "error"})
        actions.append("rerecord_complete_flow")
    if maximum is not None and duration > float(maximum):
        duration_status = "failed"
        if disposition == "passed":
            disposition = "trim_required"
        issues.append({"code": "duration_above_maximum", "severity": "warning"})
        actions.append("trim_nonessential_waiting")

    black_failed = black_ratio > float(black["max_total_ratio"]) or black_longest > float(
        black["max_segment_seconds"]
    )
    if black_ratio > float(black["max_total_ratio"]):
        issues.append({"code": "black_ratio_exceeded", "severity": "error"})
    if black_longest > float(black["max_segment_seconds"]):
        issues.append({"code": "black_segment_too_long", "severity": "error"})
    if black_failed:
        if black_ratio >= float(black["rerecord_ratio"]):
            disposition = "rerecord_required"
            actions.append("rerecord_visible_target_window")
        else:
            if disposition == "passed":
                disposition = "trim_required"
            actions.append("trim_black_segments")

    static_failed = static_ratio > float(static["max_total_ratio"]) or static_longest > float(
        static["max_segment_seconds"]
    )
    if static_ratio > float(static["max_total_ratio"]):
        issues.append({"code": "static_ratio_exceeded", "severity": "warning"})
    if static_longest > float(static["max_segment_seconds"]):
        issues.append({"code": "static_segment_too_long", "severity": "warning"})
    if static_failed:
        if static_ratio >= float(static["rerecord_ratio"]):
            disposition = "rerecord_required"
            actions.append("rerecord_without_long_static_waits")
        else:
            if disposition == "passed":
                disposition = "trim_required"
            actions.append("trim_static_waiting_segments")

    checks = {
        "duration": {
            "status": duration_status,
            "actual_seconds": duration,
            "minimum_seconds": minimum,
            "maximum_seconds": maximum,
        },
        "black_frames": {
            "status": "failed" if black_failed else "passed",
            "total_seconds": black_total,
            "longest_segment_seconds": black_longest,
            "ratio": black_ratio,
            "segments": black_segments,
            "thresholds": black,
        },
        "static_frames": {
            "status": "failed" if static_failed else "passed",
            "total_seconds": static_total,
            "longest_segment_seconds": static_longest,
            "ratio": static_ratio,
            "segments": static_segments,
            "thresholds": static,
        },
    }
    return {
        "evidence_id": item.get("evidence_id", "UNKNOWN"),
        "case_id": item.get("case_id", "UNKNOWN"),
        "path": path_value,
        "step_labels": item.get("step_labels", []),
        "status": "passed" if disposition == "passed" else "repair_required",
        "disposition": disposition,
        "probe": probe,
        "checks": checks,
        "issues": issues,
        "recommended_actions": list(dict.fromkeys(actions)),
    }


def check_videos(
    spec: Dict[str, Any],
    *,
    root: Path,
    ffprobe: str = "ffprobe",
    ffmpeg: str = "ffmpeg",
    runner: Callable[..., Any] = subprocess.run,
) -> Dict[str, Any]:
    """Check duration, black frames, and static intervals for declared video evidence."""

    videos = spec.get("videos") if isinstance(spec, dict) else None
    if (
        not isinstance(spec, dict)
        or not set(spec).issubset({"schema_version", "run_id", "defaults", "videos"})
        or spec.get("schema_version") != 1
        or not isinstance(videos, list)
        or not videos
        or not isinstance(spec.get("run_id"), str)
        or not spec.get("run_id")
        or not _valid_threshold_source(spec.get("defaults", {}))
    ):
        return {
            "schema_version": 1,
            "receipt_type": "video_quality",
            "run_id": spec.get("run_id", "UNKNOWN") if isinstance(spec, dict) else "UNKNOWN",
            "input_sha256": _input_sha256(spec),
            "status": "blocked",
            "scope": {
                "technical_checks": ["duration", "black_frames", "static_frames"],
                "semantic_content_check": "not_performed",
            },
            "summary": {"total": 0, "passed": 0, "trim_required": 0,
                        "rerecord_required": 0, "blocked": 0},
            "items": [],
            "errors": [{"code": "invalid_video_check_input"}],
        }

    results = [
        _check_item(
            spec, item, root=Path(root), ffprobe=ffprobe, ffmpeg=ffmpeg, runner=runner
        )
        if isinstance(item, dict) else _blocked_item({}, "invalid_video_item")
        for item in videos
    ]
    counts = {name: 0 for name in ("passed", "trim_required", "rerecord_required", "blocked")}
    for item in results:
        counts[item["disposition"]] += 1
    if counts["blocked"]:
        status = "blocked"
    elif counts["trim_required"] or counts["rerecord_required"]:
        status = "repair_required"
    else:
        status = "passed"
    return {
        "schema_version": 1,
        "receipt_type": "video_quality",
        "run_id": spec["run_id"],
        "input_sha256": _input_sha256(spec),
        "status": status,
        "scope": {
            "technical_checks": ["duration", "black_frames", "static_frames"],
            "semantic_content_check": "not_performed",
        },
        "summary": {"total": len(results), **counts},
        "items": results,
    }
