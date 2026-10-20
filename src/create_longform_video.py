#!/usr/bin/env python3
"""Render ten validated scenes into a 90-second, 30 Mbps portrait MP4."""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import create_video as renderer

LONGFORM_SECONDS = 90.0
SLIDE_COUNT = 10
FPS = 24
BITRATE = "30M"
MIN_BYTES = 300_000_000
MAX_BYTES = 380_000_000

renderer.LONGFORM_MODE = True
renderer.EXPECTED_SLIDE_COUNT = SLIDE_COUNT
renderer.VIDEO_TARGET_SECONDS = LONGFORM_SECONDS
renderer.SLIDE_SECONDS = (LONGFORM_SECONDS + (SLIDE_COUNT - 1) * renderer.TRANSITION_SECONDS) / SLIDE_COUNT
renderer.TARGET_MIN_BYTES = MIN_BYTES
renderer.TARGET_MAX_BYTES = MAX_BYTES

def validate_content(data):
    if not isinstance(data, dict):
        raise RuntimeError("content.json must contain an object.")
    if data.get("topic") != "Structuring review data with MongoDB":
        raise RuntimeError("Long-form renderer only accepts the verified Day 15 topic.")
    if not data.get("post") or not data.get("video_title"):
        raise RuntimeError("Caption and video title are required.")
    words = len(str(data["post"]).split())
    if not 180 <= words <= 250:
        raise RuntimeError(f"Long-form caption must contain 180-250 words; got {words}.")
    slides = data.get("slides")
    if not isinstance(slides, list) or len(slides) != SLIDE_COUNT:
        raise RuntimeError("Long-form video requires exactly ten slides.")
    for i, slide in enumerate(slides, 1):
        if not isinstance(slide, dict) or not slide.get("title") or not slide.get("body"):
            raise RuntimeError(f"Slide {i} is missing its title or body.")
    if slides[0].get("layout") != "hero" or slides[-1].get("layout") != "closing":
        raise RuntimeError("Long-form video must start with a hero scene and end with a closing scene.")

def main():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and FFprobe are required for video rendering.")
    if not renderer.CONTENT_FILE.is_file():
        raise FileNotFoundError("content.json is missing.")
    data = json.loads(renderer.CONTENT_FILE.read_text(encoding="utf-8"))
    validate_content(data)

    with tempfile.TemporaryDirectory(prefix="linkedin-longform-") as temp_dir:
        temp = Path(temp_dir)
        slide_paths = []
        for index, slide in enumerate(data["slides"]):
            slide_path = temp / f"slide_{index + 1:02d}.png"
            renderer.render_slide(slide, index, len(data["slides"]), data["topic"], slide_path)
            slide_paths.append(slide_path)

        args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        for path in slide_paths:
            args.extend(["-loop", "1", "-framerate", str(FPS), "-t", str(renderer.SLIDE_SECONDS), "-i", str(path)])

        filter_parts = []
        labels = []
        for index in range(len(slide_paths)):
            label = f"v{index}"
            filter_parts.append(
                f"[{index}:v]zoompan=z='min(zoom+0.00025,1.025)':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d=1:s={renderer.WIDTH}x{renderer.HEIGHT}:fps={FPS},"
                f"trim=duration={renderer.SLIDE_SECONDS},setpts=PTS-STARTPTS,"
                f"settb=AVTB,format=yuv420p[{label}]"
            )
            labels.append(f"[{label}]")

        fade = renderer.TRANSITION_SECONDS
        filter_parts.append(
            f"{labels[0]}{labels[1]}xfade=transition=fade:duration={fade}:"
            f"offset={renderer.SLIDE_SECONDS - fade}[x1]"
        )
        previous_label = "x1"
        cumulative_duration = renderer.SLIDE_SECONDS * 2 - fade
        for slide_index in range(2, len(slide_paths)):
            next_label = f"x{slide_index}"
            offset = cumulative_duration - fade
            filter_parts.append(
                f"[{previous_label}][v{slide_index}]"
                f"xfade=transition=fade:duration={fade}:offset={offset}[{next_label}]"
            )
            previous_label = next_label
            cumulative_duration += renderer.SLIDE_SECONDS - fade

        args.extend([
            "-filter_complex", ";".join(filter_parts),
            "-map", f"[{previous_label}]",
            "-an",
            "-c:v", "libx264",
            "-preset", "medium",
            "-b:v", BITRATE,
            "-minrate", BITRATE,
            "-maxrate", BITRATE,
            "-bufsize", "30M",
            "-profile:v", "high",
            "-level:v", "4.2",
            "-x264-params", "nal-hrd=cbr:force-cfr=1",
            "-pix_fmt", "yuv420p",
            "-r", str(FPS),
            "-movflags", "+faststart",
            "-t", str(cumulative_duration),
            str(renderer.OUTPUT_FILE),
        ])
        print(f"Rendering {SLIDE_COUNT} scenes for {LONGFORM_SECONDS:.0f} seconds at a 30 Mbps target...")
        result = subprocess.run(args, capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError("FFmpeg render failed: " + (result.stderr[-2000:] or "unknown error"))

    size_bytes = renderer.OUTPUT_FILE.stat().st_size
    if not MIN_BYTES <= size_bytes <= MAX_BYTES:
        raise RuntimeError(f"Rendered video size {size_bytes:,} bytes falls outside {MIN_BYTES:,}-{MAX_BYTES:,}.")

    probe = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_name,codec_type,width,height,r_frame_rate,pix_fmt,profile,level,bit_rate",
        "-show_entries", "format=format_name,duration",
        "-of", "json", str(renderer.OUTPUT_FILE),
    ], capture_output=True, text=True, check=False)
    if probe.returncode:
        raise RuntimeError("FFprobe could not validate the rendered long-form MP4.")
    metadata = json.loads(probe.stdout)
    stream = next((s for s in metadata.get("streams", []) if s.get("codec_type") == "video"), None)
    duration = float(metadata.get("format", {}).get("duration", 0))
    formats = str(metadata.get("format", {}).get("format_name", "")).split(",")
    bitrate = int((stream or {}).get("bit_rate") or 0)
    if not stream or stream.get("codec_name") != "h264" or stream.get("width") != 1080 or stream.get("height") != 1350:
        raise RuntimeError("Output must be 1080x1350 H.264.")
    if stream.get("r_frame_rate") != "24/1" or stream.get("pix_fmt") != "yuv420p" or stream.get("profile") != "High" or stream.get("level") != 42:
        raise RuntimeError("Output encoding differs from the validated H.264 High@4.2 24 fps format.")
    if "mp4" not in formats or any(s.get("codec_type") == "audio" for s in metadata.get("streams", [])):
        raise RuntimeError("Output must be a silent MP4.")
    if not 89.5 <= duration <= 90.5 or not 25_000_000 <= bitrate <= 31_000_000:
        raise RuntimeError(f"Output duration/bitrate out of range: {duration:.2f}s, {bitrate:,} bps.")
    print(f"SUCCESS: {duration:.2f}s, {size_bytes:,} bytes, {bitrate:,} bps, 1080x1350 H.264.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
