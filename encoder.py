import os, platform, sys, argparse
import shutil, subprocess
from pathlib import Path
from copy import deepcopy
from datetime import datetime
import time
from itertools import product
import xml.etree.ElementTree as ElementTree

_module_date     = datetime(2026, 7, 19)
_module_designer = "Alexander Taluts"
_halt_on_exit    = True
_debug           = False

#Configuration =================================================================================================================================================
#Encoder arguments (except input and output files), use list["message", "default_value", "param_suffix"] for values that will be requested from the user
#%INPUT_FILE_PATH%      - full resolved path of the input file
#%INPUT_FILE_PREFIX%    - resolved path of the input file up to filename prefix length
#%PARAM_SUFFIX%         - suffix build from variable argument values
ENCODER_PRESETS = {
    "av1": [
        "-n", "-hide_banner",
        "-i", "%INPUT_FILE_PATH%",
        "-c:v", "libsvtav1", "-preset", "1", "-crf", ["Enter CRF value(s)", "27", "-crf?"], "-g", "300", "-r", "60000/1001", "-pix_fmt", "yuv420p", "-svtav1-params", "tune=0",
        "-c:a", "libopus", "-b:a", "128k", "-vbr", "on", "-application", "audio",
        "%INPUT_FILE_PREFIX%_av1%PARAM_SUFFIX%.mkv"
    ],
    "hevc_nvenc": [
        "-n", "-hide_banner",
        "-i", "%INPUT_FILE_PATH%",
        "-c:v", "hevc_nvenc", "-preset", "p7", "-cq", ["Enter CQ value(s)", "25", "-cq?"], "-g", "300", "-r", "60000/1001", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "%INPUT_FILE_PREFIX%_hevc-nvenc%PARAM_SUFFIX%.mkv"
    ],
    "lossless": [
        "-n", "-hide_banner",
        "-i", "%INPUT_FILE_PATH%", "-i", "%INPUT_FILE_PREFIX%_filtered.flac", "-map", "0:v", "-map", "1:a",
        "-c:v", "libx265", "-preset", "fast", "-x265-params", "lossless=1", "-r", "60000/1001", "-pix_fmt", "yuv420p", "-color_range", "pc", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-c:a", "flac", "-compression_level", "8", "-ac", "1",
        "%INPUT_FILE_PREFIX%_lossless.mkv"
    ],
    "demux": [
        "-y", "-hide_banner",
        "-i", "%INPUT_FILE_PATH%",
        "-vn",
        "-acodec", "flac", "-compression_level", "8", "-ac", "1",
        "%INPUT_FILE_PREFIX%.flac"
    ]
}
#Encoder arguments excluded from metadata iserted into output file, ("argument_value", <number_of_arguments_to_exclude>), last argument (output_file) also excluded
ENCODER_METADATA_EXCLUDE = (
    ("-n", 1),
    ("-y", 1),
    ("-hide_banner", 1),
    ("-i", 2), 
    ("-map", 2)
)

FILENAME_PREFIX_LENGTH = 8
CMD_INDENT             = " " * 4
CMD_HEADER_WIDTH       = 119
#===============================================================================================================================================================

#External executables path
ffmpeg_exe = None
mkvpropedit_exe = None


#Exits the program
def exit(code:int = 0) -> None:
    print("")
    if _halt_on_exit: input("Press any key to exit...")
    print("Exiting...")
    if code > 0 and _debug:
        print(f"DEBUG >> Exit code: {code}")
        sys.exit(0)
    else:
        sys.exit(code)


#Find an executable's full path
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

#Format time in seconds into string
def timedelta(seconds: int|float) -> str:
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


#Saves metadata dictionary into Matroska Tags XML
def metadata_save_mkvxml(metadata: dict, file: Path) -> Path:
    def add_simple(parent, name, value):
        simple = ElementTree.SubElement(parent, "Simple")
        ElementTree.SubElement(simple, "Name").text = str(name)

        if isinstance(value, dict):
            for child_name, child_value in value.items():
                add_simple(simple, child_name, child_value)
        else:
            ElementTree.SubElement(simple, "String").text = str(value)

    root = ElementTree.Element("Tags")
    tag = ElementTree.SubElement(root, "Tag")
    ElementTree.SubElement(tag, "Targets")

    for name, value in metadata.items():
        add_simple(tag, name, value)

    ElementTree.indent(root, space="  ")

    tree = ElementTree.ElementTree(root)
    tree.write(file, encoding="UTF-8", xml_declaration=True)
    return file


#Inserts metadada in MKV file
def metadata_insert_mkv(file_mkv: Path, file_xml: Path, mkvpropedit_path: Path = None) -> None:
    if mkvpropedit_path is None: mkvpropedit_path = mkvpropedit_exe
    if not (file_mkv.exists() and file_xml.exists()):
        raise FileNotFoundError()
    
    cmd = [str(mkvpropedit_path), str(file_mkv), "--tags", f'global:{file_xml}']

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60, encoding="utf-8", errors="replace")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"mkvpropedit failed for {file_mkv}\n"
            f"stderr:\n{e.stderr}"
        )

#Executes ffmpeg for encoding
def ffmpeg_version(ffmpeg_path: Path = None) -> str:
    if ffmpeg_path is None: ffmpeg_path = ffmpeg_exe
    cmd = [str(ffmpeg_path), "-version"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"ffmpeg failed\n"
            f"stderr:\n{e.stderr}"
        )

    return result.stdout.split(" Copyright")[0].strip()

#Executes ffmpeg for encoding
def ffmpeg_encode(args: list(str), ffmpeg_path: Path = None) -> None:
    if ffmpeg_path is None: ffmpeg_path = ffmpeg_exe
    cmd = [str(ffmpeg_path)]
    cmd.extend(args)

    try:
        if platform.system() == "Windows":
            subprocess.run(cmd, creationflags=subprocess.IDLE_PRIORITY_CLASS)
        else:
            subprocess.run(cmd, preexec_fn=lambda: os.nice(19))
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg failed for '{' '.join(args)}'\n")


def main():
    #parse call arguments
    parser = argparse.ArgumentParser(description=f"video-reencode-tools:encoder v.{_module_date:%Y-%m-%d} by {_module_designer}.")
    parser.add_argument("inputs",       nargs="+", type=Path,                                 help="Input files (drag & drop supported)")
    parser.add_argument("--ffmpeg",                type=Path, default=None, metavar="<file>", help="Path to ffmpeg.")
    parser.add_argument("--mkvpropedit",           type=Path, default=None, metavar="<file>", help="Path to mkvpropedit.")
    parser.add_argument('--nohalt',                action='store_true',                       help='Do not halt terminal when finished')
    args = parser.parse_args()

    inputs = [f.resolve() for f in args.inputs]
    if args.nohalt: 
        global _halt_on_exit
        _halt_on_exit = False

    global ffmpeg_exe
    ffmpeg_exe = find_exe("ffmpeg", args.ffmpeg)

    #acquire all necessary data
    print("Requesting encoding parameters ".ljust(CMD_HEADER_WIDTH, '='))
    encoding_preset = next(iter(ENCODER_PRESETS))
    while True:
        user_input = input(f"Enter encoding preset name [{encoding_preset}]: ").strip()
        if not user_input:
            break
        elif user_input in ENCODER_PRESETS.keys():
            encoding_preset = user_input
            break
        else:
            print(f"{CMD_INDENT}No such preset. Choose from these: {', '.join(list(ENCODER_PRESETS.keys()))}")
    job_queue = []
    for file in inputs:
        print(f"{file.name}:")
        #ask user for variable arguments values
        job = deepcopy(ENCODER_PRESETS[encoding_preset])
        job_suffix = []
        for i, arg in enumerate(job):
            if isinstance(arg, (tuple, list)):
                #argument is a list -> user input required
                user_input = input(f"{CMD_INDENT}{arg[0]} [{arg[1]}]: ").strip()
                if not user_input:
                    user_input = arg[1]
                job[i] = user_input.split(" ")
                #expand value into job suffix
                arg_suffix = job[i].copy()
                for i, value in enumerate(arg_suffix):
                    arg_suffix[i] = arg[2].replace("?", value)
                job_suffix.append(arg_suffix)
            else:
                #generic argument -> copy
                job[i] = [arg]
        #generate a product of all combinations
        jobs = [list(job) for job in product(*job)]
        jobs_suffix = ["".join(job_suffix) for job_suffix in product(*job_suffix)]
        #expand variables
        for j, job in enumerate(jobs):
            for i, arg in enumerate(job):
                job[i] = job[i].replace("%INPUT_FILE_PATH%", str(file))
                job[i] = job[i].replace("%INPUT_FILE_PREFIX%", str(file.with_name(file.name[:FILENAME_PREFIX_LENGTH])))
                job[i] = job[i].replace("%PARAM_SUFFIX%", jobs_suffix[j])
        job_queue.extend(jobs)
    print("")

    #processing jobs
    print("Processing files ".ljust(CMD_HEADER_WIDTH, '='))
    queue_start = time.monotonic()
    queue_counter = 0
    metadata_encoder_name = ffmpeg_version()
    for job in job_queue:
        #remove args containing file paths
        print("".ljust(CMD_HEADER_WIDTH, '-'))
        print(f"{ffmpeg_exe} {' '.join(job)}")
        queue_counter += 1
        output_file = Path(job[-1])
        #encoding
        ffmpeg_encode(job)
        print("")
        #inserting metadata
        if output_file.suffix.lower() == ".mkv":
            print("inserting encoder metadata in mkv container...")
            global mkvpropedit_exe
            mkvpropedit_exe = find_exe("mkvpropedit", args.mkvpropedit)
            metadata_file = output_file.with_name(f"{output_file.stem}_metadata.xml")
            #filter metadata arguments
            metadata_encoder_settings = []
            i = 0
            while i < len(job) - 1:
                for arg in ENCODER_METADATA_EXCLUDE:
                    if job[i] == arg[0]:
                        i += arg[1]
                        continue
                else:
                    metadata_encoder_settings.append(job[i])
                    i += 1
            metadata = {
                "Encoder": {
                    "Name": metadata_encoder_name,
                    "Settings": ' '.join(metadata_encoder_settings)
                }
            }
            metadata_save_mkvxml(metadata, metadata_file)
            metadata_insert_mkv(output_file, metadata_file)
            metadata_file.unlink(missing_ok=True)
    queue_finish = time.monotonic()

    print("".ljust(CMD_HEADER_WIDTH, '='))
    print(f"Done. Encoded {len(job_queue)} inputs into {queue_counter} outputs in {timedelta(queue_finish-queue_start)}")


if __name__ == "__main__":
    exit_code = 0
    #checking launch from IDE
    if '--debug' in sys.argv:
        sys.argv.remove('--debug')
        _debug = True
        main()
    else:
        #catching all errors to display error info and prevent terminal from closing
        try:
            main()
        except Exception as e:
            exit_code = 1
            print(f"ERROR >> {e}")
            
    exit(exit_code)