import sys, argparse
from datetime import datetime
import time
import json
import re
import shutil, subprocess
from dataclasses import dataclass, field
from pathlib import Path

_module_date = datetime(2026, 7, 19)
_module_designer = "Alexander Taluts"

#Configuration =================================================================================================================================================
ABAV1_OUTPUT_LOG        = False                 #log ab-av1 output into log file (for debug)
DEFAULT_CRFS            = "27 29 31 33 35"      #default list of tested crf values (separated by space)
DEFAULT_SAMPLE_NUMBER   = 6                     #default sample number
DEFAULT_SAMPLE_DURATION = "10s"                 #default sample duration
ABAV1_OPTIONS = (                               #other ab-av1 options (not asked in runtime)
    "--encoder", "svt-av1",
    "--preset", "1",
    "--pix-format", "yuv420p",
    "--keyint", "300",
    "--svt", "tune=0"
)
CMD_HEADER_WIDTH = 119                          #
TXT_HEADER_WIDTH = 119                          #

#ab-av1 output parsing strings
ABAV1_OUTPUT_SAMPLE_START    = re.compile(r"encoding sample\s+(?P<index>\d+)/(?P<total>\d+)\s+crf\s+(?P<crf>\d+)")
ABAV1_OUTPUT_SAMPLE_FILENAME = re.compile(r"\.sample(?P<index>\d+)\.(?P<start>\d+)\+(?P<length>\d+)f")
ABAV1_OUTPUT_SAMPLE_SCORE    = re.compile(r"sample\s+(?P<index>\d+)/(?P<total>\d+)\s+crf\s+(?P<crf>\d+)\s+VMAF\s+(?P<score>\d+(?:\.\d+)?)")
ABAV1_OUTPUT_SUMMARY         = re.compile(r"crf\s+(?P<crf>\d+)\s+VMAF\s+(?P<score>\d+(?:\.\d+)?)\s+predicted video stream size\s+(?P<size>\d+(?:\.\d+)?)\s*(?P<unit>KiB|MiB|GiB)\s*(?:\(\d+%\)\s*)?taking\s+(?P<time>.+?)(?:\s+\(cache\))?$")
#===============================================================================================================================================================

#Executables paths
ffprobe_exe = None
abav1_exe   = None

@dataclass
class Sample:
    index       : int               = 0
    bounds      : list[int, int]    = field(default_factory=lambda: [0, 0])
    score       : float             = 0.0

@dataclass
class CRF:
    value           : float         = 0
    score           : float         = 0.0
    filesize        : int           = 0
    bitrate         : int           = 0
    encode_time     : int           = 0
    test_time       : float         = 0
    samples         : list[Sample]  = field(default_factory=list)

@dataclass
class VideoInfo:
    width           : int       = 0
    height          : int       = 0
    duration        : float     = 0.0
    fps             : float     = 0.0

@dataclass
class VideoFile:
    path                : Path
    info                : VideoInfo
    sample_number       : int           = 0
    sample_duration     : str           = ""
    crfs                : list[float]   = field(default_factory=list)
    results             : list[CRF]     = field(default_factory=list)


# Convert crf value to string
def crf_to_str(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return str(value)


# Convert string value to crf value
def str_to_crf(value: str) -> float:
    value = value.replace(',', '.')
    return float(value)


# Find an executable's full path
def find_exe(name: str, search_list: Path | list[Path] = None) -> Path:
    if   name.endswith(".exe"):          exe = name
    elif sys.platform.startswith("win"): exe = f"{name}.exe"
    else:                                exe = name

    if isinstance(search_list, (tuple, list)): pass
    elif isinstance(search_list, Path): search_list = [search_list]
    else: search_list = []

    #add script directory path to search list
    search_list.append(Path(sys.argv[0]).resolve().parent) 

    #search in the search list
    for path in search_list:
        if path.name != exe:
            path = path / exe
        if path.is_file():
            return path

    #search in system PATH
    path = shutil.which(exe)
    if path:
        return path

    #not found
    raise FileNotFoundError(f"'{name}' not found in supplied paths, script directory, or system PATH.")


# Get information about video file
def videoinfo_get(file: Path) -> VideoInfo:
    cmd = [str(ffprobe_exe), "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(file)]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(proc.stdout)
    except Exception as e:
        raise RuntimeError(f"ffprobe failed for '{file}': {e}")

    streams = data.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)

    if not video_stream:
        raise RuntimeError("No video stream found")

    width = int(video_stream["width"])
    height = int(video_stream["height"])

    # FPS parsing (r_frame_rate like "30000/1001")
    rate = video_stream.get("r_frame_rate", "0/1")
    num, den = rate.split("/")
    fps = float(num) / float(den) if float(den) != 0 else 0.0

    duration = data.get("format", {}).get("duration")
    if duration is None:
        raise RuntimeError("Missing duration in ffprobe output")

    return VideoInfo(width=width, height=height, duration=float(duration), fps=fps)


# Format time in second into timestamp
def seconds_to_timestamp(seconds: float) -> str:
    ms = int(round((seconds - int(seconds)) * 1000))
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}.{ms:03d}"


# Run one 'ab-av1 sample-encode' command
def abav1_run(cmd: list[str], log: Path = None) -> CRF:
    time_start = time.monotonic()
    result = None

    try:
        if log is not None: log_file = log.open("w", encoding="utf-8", newline="")
        else:               log_file = None

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            if log_file is not None: log_file.write(line)

            #detect new sample encoding start
            m = ABAV1_OUTPUT_SAMPLE_START.search(line)
            if m:
                sample_index = int(m.group("index"))
                crf = str_to_crf(m.group("crf"))
                if result is None:  result = CRF(value=crf)
                result.samples.append(Sample(index=sample_index))
                continue

            #info from sample filename (absent in cache mode)
            m = ABAV1_OUTPUT_SAMPLE_FILENAME.search(line)
            if m:
                sample_index  = int(m.group("index"))
                sample_start  = int(m.group("start"))
                sample_length = int(m.group("length"))
                result.samples[-1].bounds[0] = sample_start
                result.samples[-1].bounds[1] = sample_start + sample_length - 1
                continue

            #sample score
            m = ABAV1_OUTPUT_SAMPLE_SCORE.search(line)
            if m:
                result.samples[-1].score = float(m.group("score"))
                continue

            #summary
            m = ABAV1_OUTPUT_SUMMARY.search(line)
            if m:
                result.score = float(m.group("score"))
                size = float(m.group("size"))
                unit = m.group("unit").lower()
                if   unit == "kib": result.filesize = int(size * 1024)
                elif unit == "mib": result.filesize = int(size * 1024 ** 2)
                elif unit == "gib": result.filesize = int(size * 1024 ** 3)
                elif unit == "tib": result.filesize = int(size * 1024 ** 4)
                else: raise ValueError(f"Unknown unit: {unit}")
                result.encode_time = m.group("time").strip()

        process.stdout.close()
        rc = process.wait()
        result.test_time = time.monotonic() - time_start

    finally:
        if log_file is not None: log_file.close()

    if rc != 0:
        raise RuntimeError(f"ab-av1 exited with code {rc}")

    return result


# Build report file header
def report_build_header(video_file: VideoFile) -> str:
    duration_h = int(video_file.info.duration // 3600)
    duration_m = int((video_file.info.duration % 3600) // 60)
    duration_s = video_file.info.duration % 60
    duration_str = f"{duration_h:02d}:{duration_m:02d}:{duration_s:06.3f}"
    crfs_str = [crf_to_str(crf) for crf in video_file.crfs]

    return (
        f"{'=' * TXT_HEADER_WIDTH}\n"
        f"File              : {video_file.path.name}\n"
        f"Resolution        : {video_file.info.width} x {video_file.info.height}\n"
        f"FPS               : {video_file.info.fps:.3f}\n"
        f"Duration          : {duration_str}\n"
        f"CRFs              : {', '.join(crfs_str)}\n"
        f"Sample number     : {video_file.sample_number}\n"
        f"Sample duration   : {video_file.sample_duration}\n"
        f"Options           : {' '.join(ABAV1_OPTIONS)}\n"
        f"{'=' * TXT_HEADER_WIDTH}"
    )

# Build report file crf block
def report_build_crf(crf: CRF, fps: float) -> str:
    sample_index_width = len(str(len(crf.samples)))
    label_width = 12
    
    score_min_value = 1000000.0
    score_min_index = 0
    score_max_value = 0.0
    score_max_index = 0
    for sample in crf.samples:
        if sample.score < score_min_value:
            score_min_value = sample.score
            score_min_index = sample.index
        if sample.score > score_max_value:
            score_max_value = sample.score
            score_max_index = sample.index

    result = f"CRF {crf_to_str(crf.value)} ".ljust(TXT_HEADER_WIDTH, '-') + "\n"
    for sample in crf.samples:
        result += f"sample #{str(sample.index).ljust(sample_index_width)}".ljust(label_width)
        result += " : "
        result += f"{sample.score:5.2f}"
        if sample.bounds[0] != sample.bounds[1]:
            result += ' ' * 4
            result += f"({sample.bounds[0]:>6} \u2026 {sample.bounds[1]:>6} / {seconds_to_timestamp(sample.bounds[0] / fps)} \u2026 {seconds_to_timestamp(sample.bounds[1] / fps)})" 
        result += "\n"
    result += "\n"
    result += "Average".ljust(label_width) + " : " + f"{crf.score:5.2f}{' ' * 4}(min {score_min_value:.2f} @ #{score_min_index}, max {score_max_value:.2f} @ #{score_max_index})\n"
    result += "File size".ljust(label_width) + " : "
    if   crf.filesize >= 1024 ** 4: result += f"{(crf.filesize / 1024 ** 4):.2f} TiB"
    if   crf.filesize >= 1024 ** 3: result += f"{(crf.filesize / 1024 ** 3):.2f} GiB"
    elif crf.filesize >= 1024 ** 2: result += f"{(crf.filesize / 1024 ** 2):.2f} MiB"
    elif crf.filesize >= 1024 ** 1: result += f"{(crf.filesize / 1024 ** 1):.2f} kiB"
    else:                           result += f"{crf.filesize} B"
    result += " ("
    if   crf.bitrate  >= 1000 ** 4: result += f"{(crf.bitrate  / 1000 ** 4):.2f} Tb/s"
    if   crf.bitrate  >= 1000 ** 3: result += f"{(crf.bitrate  / 1000 ** 3):.2f} Gb/s"
    elif crf.bitrate  >= 1000 ** 2: result += f"{(crf.bitrate  / 1000 ** 2):.2f} Mb/s"
    elif crf.bitrate  >= 1000 ** 1: result += f"{(crf.bitrate  / 1000 ** 1):.2f} kb/s"
    else:                           result += f"{crf.bitrate } b/s"
    result += ")\n"
    result += "Encode time".ljust(label_width) + " : " + crf.encode_time + "\n"
    result += "Test time".ljust(label_width) + " : " + seconds_to_timestamp(crf.test_time) + "\n"
    result += '-' * TXT_HEADER_WIDTH

    return result


def main():
    #parse call arguments
    parser = argparse.ArgumentParser(description=f"video-reencode-tools:abav1-crfprobe v.{_module_date:%Y-%m-%d} by {_module_designer}.")
    parser.add_argument("inputs",       nargs="+", type=Path,                                 help="Input video files (drag & drop supported)")
    parser.add_argument("--ffprobe",               type=Path, default=None, metavar="<file>", help="Path to ffprobe.")
    parser.add_argument("--abav1",                 type=Path, default=None, metavar="<file>", help="Path to ab-av1.")
    args = parser.parse_args()

    #locate external executables
    global ffprobe_exe, abav1_exe
    ffprobe_exe = find_exe("ffprobe", args.ffprobe)
    abav1_exe   = find_exe("ab-av1",  args.abav1)

    #create videofiles and obtain information about them
    videofiles = []
    for file in args.inputs:
        path = file.resolve()
        info = videoinfo_get(path)
        videofiles.append(VideoFile(path=path, info=info))

    #ask user for encoding parameters
    print("Input encoding params for each file ".ljust(CMD_HEADER_WIDTH, "*"))
    for videofile in videofiles:
        print(f"{videofile.path.name} ".ljust(CMD_HEADER_WIDTH, "="))
        crfs = input(f"    CRF values [{DEFAULT_CRFS}]: ").strip()
        sample_quantity = input(f"    Number of samples [{DEFAULT_SAMPLE_NUMBER}]: ").strip()
        sample_duration = input(f"    Sample duration [{DEFAULT_SAMPLE_DURATION}]: ").strip()
        if sample_duration.isdecimal(): sample_duration += "s"                  #treat plain number as duration in seconds
        videofile.crfs = list(map(float, (crfs or DEFAULT_CRFS).split()))
        videofile.sample_number = int(sample_quantity or DEFAULT_SAMPLE_NUMBER)
        videofile.sample_duration = sample_duration or DEFAULT_SAMPLE_DURATION
        print("")

    #processing videofiles
    time_job_start = time.monotonic()
    print("Starting batch processing ".ljust(CMD_HEADER_WIDTH, "*"))
    for videofile in videofiles:
        time_file_start = time.monotonic()
        print(f"{videofile.path.name} ".ljust(CMD_HEADER_WIDTH, "="))
        
        #create report file and write header to it
        report_file = videofile.path.with_name(f"{videofile.path.stem}_crf-test").with_suffix(".txt")
        report_file.write_text(report_build_header(videofile))
        
        #loop through crf values
        for crf in videofile.crfs:
            print(f"CRF {crf_to_str(crf)} ".ljust(CMD_HEADER_WIDTH, "-"))
            
            cmd = [str(abav1_exe), "sample-encode", "--input", str(videofile.path), 
                   "--crf", crf_to_str(crf),
                   "--samples", str(videofile.sample_number), "--sample-duration", videofile.sample_duration,
                   *ABAV1_OPTIONS]

            if ABAV1_OUTPUT_LOG: log_file = videofile.path.with_name(f"{videofile.path.stem}_crf{crf}.log")
            else:                log_file = None

            result = abav1_run(cmd, log_file)
            result.bitrate = int((result.filesize * 8) / videofile.info.duration)
            videofile.results.append(result)

            with report_file.open(mode="a") as file:
                file.write("\n\n" + report_build_crf(videofile.results[-1], videofile.info.fps))
            print("")

        with report_file.open(mode="a") as file:
            file.write("\n\nTotal time   : " + seconds_to_timestamp(time.monotonic() - time_file_start))

    print(f"Job done in {seconds_to_timestamp(time.monotonic() - time_job_start)} ".ljust(CMD_HEADER_WIDTH, "*"))


if __name__ == "__main__":
    main()