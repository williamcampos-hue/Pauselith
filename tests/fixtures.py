"""Small deterministic public synthetic media for UC-001 integration tests.

No user recordings. Tools are supplied with KIYOCUT_FFMPEG/KIYOCUT_FFPROBE.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import wave

def required_tool(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError("Set " + name + " or run scripts/test.ps1 -Suite Full")
    return Path(value)


FFMPEG = required_tool("KIYOCUT_FFMPEG")
FFPROBE = required_tool("KIYOCUT_FFPROBE")


def run(args, log=None):
    result = subprocess.run([str(a) for a in args], capture_output=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if log:
        Path(log).write_bytes(result.stderr)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace"))
    return result.stdout


def probe(path, count=False):
    args = [FFPROBE, "-v", "error", "-show_streams", "-show_format", "-of", "json"]
    if count:
        args += ["-count_frames"]
    return json.loads(run(args + [path]))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def make_source(folder, kind="normal"):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / (kind + ".mkv")
    # Chirp plus a varying envelope avoids a periodic tone's ambiguous offsets.
    voice = "aevalsrc=0.2*sin(2*PI*(443*t+37*t*t))*(0.6+0.4*sin(2*PI*2.3*t))*between(t\\,0.5\\,3.4):s=44100:d=4"
    args = [FFMPEG, "-hide_banner", "-nostdin", "-v", "error", "-n",
            "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=4",
            "-f", "lavfi", "-i", "sine=frequency=110:sample_rate=44100:duration=4",
            "-f", "lavfi", "-i", voice,
            "-map", "0:v:0", "-map", "1:a:0", "-map", "2:a:0"]
    if kind == "gap3":
        args += ["-vf", "select='not(between(n,116,118))'", "-fps_mode", "vfr"]
    elif kind == "vfr":
        args += ["-vf", "setpts='PTS+if(gte(N,60),0.1/TB,0)'", "-fps_mode", "vfr"]
    args += ["-c:v", "libx264", "-crf", "16", "-preset", "medium", "-threads", "2",
             "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", source]
    run(args)
    return source


def make_reference_audio(source, folder, frames=120):
    """Match the legacy PCM slicing/padding contract for one full segment."""
    folder = Path(folder)
    raw = folder / "original_voice.wav"
    reference = folder / "reference.wav"
    run([FFMPEG, "-hide_banner", "-nostdin", "-v", "error", "-n", "-copyts",
         "-i", source, "-map", "0:a:1", "-af", "aresample=44100:async=1:first_pts=0",
         "-c:a", "pcm_s16le", raw])
    with wave.open(str(raw), "rb") as original, wave.open(str(reference), "wb") as output:
        output.setparams(original.getparams())
        count = frames * 1470
        width = original.getnchannels() * original.getsampwidth()
        pcm = original.readframes(count)
        output.writeframes(pcm + bytes(max(0, count * width - len(pcm))))
    return reference


def make_export(source, reference, folder, frames=120, black=False, muted=False):
    folder = Path(folder)
    final = folder / ("black.mp4" if black else "muted.mp4" if muted else "final.mp4")
    vf = "trim=start=0:end={:.9f},setpts=PTS-STARTPTS".format(frames / 30)
    if black:
        vf += ",drawbox=color=black:t=fill"
    args = [FFMPEG, "-hide_banner", "-nostdin", "-v", "error", "-n", "-threads", "2",
            "-copyts", "-i", source, "-i", reference,
            "-map", "0:v:0", "-map", "1:a:0", "-vf", vf,
            "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-threads", "2",
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-r", "30", "-fps_mode", "cfr",
            "-video_track_timescale", "30", "-c:a", "aac", "-b:a", "256k"]
    if muted:
        args += ["-af", "volume=0"]
    run(args + ["-movflags", "+faststart", final])
    return final