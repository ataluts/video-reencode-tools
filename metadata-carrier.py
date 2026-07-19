import sys, argparse
import shutil, subprocess
from pathlib import Path
import json
import struct
import zipfile
import re
import math
from datetime import datetime
from collections import defaultdict
from typing import Any
import xml.etree.ElementTree as ElementTree

_module_date     = datetime(2026, 7, 19)
_module_designer = "Alexander Taluts"
_halt_on_exit    = True
_debug           = False

PRESET_GPS = { #'preset': (±lat, ±lon[, ±alt[, 'areaname']])
    "home": (0.000000, 0.000000, None, "Home")
}

PRESET_LENS = {
    "samyang-8": {
        ("ExifTool", "ExifIFD", "FocalLength"): "8mm",
        ("ExifTool", "ExifIFD", "LensInfo"): "8mm f/3.5",
        ("ExifTool", "ExifIFD", "LensModel"): "Samyang MF 8mm F3.5 fish-eye CS",
        #("ExifTool", "ExifIFD", "LensSerialNumber"): "XXXXXXXXX",
        ("ExifTool", "Canon", "LensType"): "Samyang MF 8mm F3.5 fish-eye CS",
        ("ExifTool", "Canon", "MaxFocalLength"): "8 mm",
        ("ExifTool", "Canon", "MinFocalLength"): "8 mm",
        ("ExifTool", "Canon", "MaxAperture"): 3.5,
        ("ExifTool", "Canon", "MinAperture"): 22,
        ("ExifTool", "Canon", "LensModel"): "Samyang MF 8mm F3.5 fish-eye CS",
        ("ExifTool", "Canon", "FocalLength"): "8 mm",
        ("ExifTool", "Canon", "MinFocalLength2"): "8 mm",
        ("ExifTool", "Canon", "MaxFocalLength2"): "8 mm"
    },
    "Canon 18-50mm F2.8 DC DN | Contemporary 021": {
        ("ExifTool", "ExifIFD", "LensInfo"): "18-50mm f/2.8",
        ("ExifTool", "ExifIFD", "LensModel"): "Sigma 18-50mm F2.8 DC DN | Contemporary 021",
        #("ExifTool", "ExifIFD", "LensSerialNumber"): "XXXXXXXX",
        ("ExifTool", "Canon", "LensType"): "Sigma 18-50mm F2.8 DC DN | Contemporary 021",
        ("ExifTool", "Canon", "LensModel"): "Sigma 18-50mm F2.8 DC DN | Contemporary 021"
    },
    "Sigma 16-300mm F3.5-6.7 DC OS | C (025)": {
        ("ExifTool", "ExifIFD", "LensInfo"): "16-300mm f/3.5-6.7",
        ("ExifTool", "ExifIFD", "LensModel"): "Sigma 16-300mm F3.5-6.7 DC OS | Contemporary 025",
        #("ExifTool", "ExifIFD", "LensSerialNumber"): "XXXXXXXX",
        ("ExifTool", "Canon", "LensType"): "Sigma 16-300mm F3.5-6.7 DC OS | Contemporary 025",
        ("ExifTool", "Canon", "LensModel"): "Sigma 16-300mm F3.5-6.7 DC OS | Contemporary 025"
    },
    "Canon EF 50mm f/1.8 STM": {
        ("ExifTool", "ExifIFD", "LensInfo"): "50mm f/1.8",
        ("ExifTool", "ExifIFD", "LensModel"): "Canon EF 50mm f/1.8 STM",
        #("ExifTool", "ExifIFD", "LensSerialNumber"): "XXXXXXXXXX",
        ("ExifTool", "Canon", "LensType"): "Canon EF 50mm f/1.8 STM",
        ("ExifTool", "Canon", "LensModel"): "Canon EF 50mm f/1.8 STM"
    },
    "Sigma 8-16mm f/4.5-5.6 DC HSM": {
        ("ExifTool", "ExifIFD", "LensInfo"): "8-16mm f/4.5-5.6",
        ("ExifTool", "ExifIFD", "LensModel"): "Sigma 8-16mm f/4.5-5.6 DC HSM",
        #("ExifTool", "ExifIFD", "LensSerialNumber"): "XXXXXXXX",
        ("ExifTool", "Canon", "LensType"): "Sigma 8-16mm f/4.5-5.6 DC HSM",
        ("ExifTool", "Canon", "LensModel"): "Sigma 8-16mm f/4.5-5.6 DC HSM"
    }
}

CMD_INDENT = " " * 4

#External executables path
exiftool_exe    = None
ffprobe_exe     = None
mkvpropedit_exe = None
mkvextract_exe = None

class NestedDict():
    def get(d: dict, path: str | tuple[str], default = None) -> Any:
        if not path:
            return default

        if isinstance(path, (tuple, list)):
            current = d
            for key in path:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return default
            return current
        else:
            return d.get(path, default)

    def set(d: dict, path: str | tuple[str], value: Any) -> None:
        if not path:
            raise ValueError("Path sequence cannot be empty")

        if isinstance(path, (tuple, list)):
            current = d
            for key in path[:-1]:
                #if the path doesn't exist or isn't a dict, create an empty dict
                if key not in current or not isinstance(current[key], dict):
                    current[key] = {}
                current = current[key]
            current[path[-1]] = value
        else:
            d[path] = value

    def pop(d: dict, path: str | tuple[str], default:Any = None) -> Any:
        if not path: raise ValueError("Path sequence cannot be empty")
        if not isinstance(path, (tuple, list)): path = (path, )
        if len(path) == 1: return d.pop(path[0], default)
        current_key = path[0]
        if isinstance(d, dict) and current_key in d and isinstance(d[current_key], dict):
            result = NestedDict.pop(d[current_key], path[1:], default)
            if not d[current_key]: del d[current_key]
            return result
        return default

    def replace_value(d: dict, old, new):
        for key, value in d.items():
            if isinstance(value, dict): NestedDict.replace_value(value, old, new)
            elif value == old: d[key] = new

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


#Finds an executable's full path
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


#Gets whole metadata binary block from a file
def metadada_get_binary(file: Path) -> bytes:
    with file.open("rb") as f:
        while True:
            atom_start = f.tell()

            header = f.read(8)
            if len(header) < 8:
                raise ValueError("No mdat atom found")

            size32, atom_type = struct.unpack(">I4s", header)
            atom_type = atom_type.decode("ascii", "replace")

            if size32 == 1:
                # 64-bit atom size
                largesize = struct.unpack(">Q", f.read(8))[0]
                atom_size = largesize
                header_size = 16
            elif size32 == 0:
                # extends to EOF
                f.seek(0, 2)
                atom_size = f.tell() - atom_start
                header_size = 8
            else:
                atom_size = size32
                header_size = 8

            if atom_type == "mdat":
                header_end = atom_start
                break

            if atom_size < header_size:
                raise ValueError(f"Invalid atom '{atom_type}'")

            f.seek(atom_start + atom_size)

        f.seek(0)
        return f.read(header_end)


#Decodes metadata from exiftool output provided as plain text in json formatting
def metadata_decode_exiftool_text(text: str) -> dict:
    def nested_dict():
        return defaultdict(nested_dict)

    def clean_nested_dict(d):
        """
        Recursively converts defaultdict structure into a plain dict.
        Ensures JSON-safe output and removes lazy-evaluation behavior.
        """
        if isinstance(d, defaultdict):
            d = dict(d)
        if isinstance(d, dict):
            return {k: clean_nested_dict(v) for k, v in d.items()}
        return d

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Failed to parse JSON from text\n"
            f"Error: {e}\n"
            f"Output was:\n{text[:500]}"
        )

    if not data:
        raise RuntimeError(f"No metadata parsed from text")

    root = nested_dict()
    for key, value in data[0].items():
        parts = key.split(":")
        if len(parts) == 1:
            node = root
            node[parts[0]] = value
            continue
        node = root

        for part in parts[:-1]:
            node = node[part]
        tag = parts[-1]

        #protection from duplicates (-a)
        if tag in node:
            if not isinstance(node[tag], list):
                node[tag] = [node[tag]]
            node[tag].append(value)
        else:
            node[tag] = value

    return clean_nested_dict(root)


#Decodes metadata from exiftool output in stdout
def metadata_decode_exiftool_stdout(file: Path, exiftool_path: Path = None) -> dict:
    if exiftool_path is None: exiftool_path = exiftool_exe
    cmd = [str(exiftool_path), "-json", "-G1", "-a", "-s", "-api", "largefilesupport=1", "-api", "LimitLongValues=0", str(file)]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"ExifTool failed for {file}\n"
            f"stderr:\n{e.stderr}"
        )

    return metadata_decode_exiftool_text(result.stdout)


#Decodes metadata from exiftool output stored in text file
def metadata_decode_exiftool_file(file: Path) -> dict:
    with open(file, "r", encoding="utf-8") as f:
        result = f.read()
    return metadata_decode_exiftool_text(result)


#Decodes metadata from ffprobe output provided as plain text in json formatting
def metadata_decode_ffprobe_text(text: str) -> dict:
    def convert(obj):
        if isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert(v) for v in obj]
        return obj

    data = json.loads(text)
    result = {}

    for key, value in data.items():
        if key == "streams":
            streams = {}
            type_count = {}
            for stream in value:
                stream_type = stream.get("codec_type", "stream").capitalize()
                #rename QuickTime timecode streams
                if stream.get("codec_type") == "data" and stream.get("codec_tag_string") == "tmcd":
                    stream_type = "Timecode"

                count = type_count.get(stream_type, 0) + 1
                type_count[stream_type] = count

                name = stream_type if count == 1 else f"{stream_type}{count}"
                streams[name] = convert(stream)

            result["streams"] = streams
        else:
            result[key] = convert(value)
    return result


#Decodes metadata from ffprobe output in stdout
def metadata_decode_ffprobe_stdout(file: Path, ffprobe_path: Path = None) -> dict:
    if ffprobe_path is None: ffprobe_path = ffprobe_exe
    cmd = [str(ffprobe_path), "-v", "quiet", "-of", "json", "-show_streams", "-show_program_version", str(file)]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"ffprobe failed for {file}\n"
            f"stderr:\n{e.stderr}"
        )

    return metadata_decode_ffprobe_text(result.stdout)


#Decodes metadata from mkvextract output in stdout for existing MKV file
def metadata_decode_mkvxml_stdout(file: Path, mkvextract_path: Path = None) -> dict:
    if mkvextract_path is None: mkvextract_path = mkvextract_exe
    cmd = [str(mkvextract_path), "tags", str(file)]

    #extract tags XML from MKV
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60, encoding="utf-8", errors="replace")
    if not result.stdout.strip():
        return {}

    root = ElementTree.fromstring(result.stdout)
    return metadata_decode_mkvxml_root(root)


#Decodes metadata from XML tree
def metadata_decode_mkvxml_root(root: ElementTree.Element) -> dict:
    def parse_simple(simple):
        name = simple.findtext("Name")
        children = simple.findall("Simple")
        if children:
            return name, {
                child_name: child_value
                for child_name, child_value in (
                    parse_simple(child) for child in children
                )
            }
        return name, simple.findtext("String", "")

    metadata = {}
    for tag in root.findall("Tag"):
        for simple in tag.findall("Simple"):
            name, value = parse_simple(simple)
            metadata[name] = value

    return metadata


#Decodes metadata from XML file
def metadata_decode_mkvxml_file(file: Path) -> dict:
    tree = ElementTree.parse(file)
    return metadata_decode_mkvxml_root(tree.getroot())


#Encodes metadata dictionary into Matroska Tags XML
def metadata_encode_mkvxml(metadata: dict) -> str:
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

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ElementTree.tostring(root, encoding="unicode")


#Encodes metadata dictionary into JSON
def metadata_encode_json(metadata: dict) -> str:
    return json.dumps(metadata, ensure_ascii=False, indent=4)


#Saves metadata
def metadata_save(files: dict, compression: int | None = None, zip_path: Path | None = None) -> None:
    if compression is None:
        for path, data in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(data, str):
                with path.open("w", encoding="utf-8", newline="") as f:
                    f.write(data)
            else:
                with path.open("wb") as f:
                    f.write(data)
    else:
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", compression=compression, compresslevel=9) as z:
            for path, data in files.items():
                z.writestr(path.name, data)


#Inserts metadada into MKV file
def metadata_insert_mkv(file_mkv: Path, file_xml: Path, file_zip: Path, mkvpropedit_path: Path = None) -> None:
    if mkvpropedit_path is None: mkvpropedit_path = mkvpropedit_exe
    if not (file_mkv.exists() and file_xml.exists() and file_zip.exists()):
        raise FileNotFoundError()
    
    cmd = [str(mkvpropedit_path), str(file_mkv), "--tags", f'global:{file_xml}', "--attachment-name", "source_metadata.zip", "--attachment-mime-type", "application/zip", "--attachment-description", "Source metadata archive", "--add-attachment", str(file_zip)]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60, encoding="utf-8", errors="replace")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"mkvpropedit failed for {file_mkv}\n"
            f"stderr:\n{e.stderr}"
        )


#Refactors metadata dictionary
def metadata_refactor(metadata: dict) -> dict:
    result = {}

    NestedDict.pop(metadata, ("ExifTool", "SourceFile"))

    #ExifTool.Version
    NestedDict.set(result, ("ExifTool", "Version"), NestedDict.pop(metadata, ("ExifTool", "ExifTool", "ExifToolVersion"), "<unknown>"))

    #ExifTool.File
    ExifTool_File = {}
    ExifTool_File["Name"]       = NestedDict.get(metadata, ("ExifTool", "System", "FileName"))
    ExifTool_File["ModifyDate"] = NestedDict.get(metadata, ("ExifTool", "System", "FileModifyDate"))
    ExifTool_File["Size"]       = NestedDict.get(metadata, ("ExifTool", "System", "FileSize"))
    ExifTool_File["Duration"]   = NestedDict.get(metadata, ("ExifTool", "QuickTime", "Duration"))
    ExifTool_File["AvgBitrate"] = NestedDict.get(metadata, ("ExifTool", "Composite", "AvgBitrate"))
    ExifTool_File["MIMEType"]   = NestedDict.get(metadata, ("ExifTool", "File", "MIMEType"))
    ExifTool_File["Size"]      += f" ({NestedDict.get(metadata, ('ExifTool', 'QuickTime', 'MediaDataSize')) + NestedDict.get(metadata, ('ExifTool', 'QuickTime', 'MediaDataOffset'))} bytes)"
    NestedDict.set(result, ("ExifTool", "File"), ExifTool_File)
    NestedDict.pop(metadata, ("ExifTool", "System"))
    NestedDict.pop(metadata, ("ExifTool", "File"))
    NestedDict.pop(metadata, ("ExifTool", "QuickTime"))
    
    #ExifTool.IFD0
    ExifTool_IFD0_in = NestedDict.pop(metadata, ("ExifTool", "IFD0"))
    if ExifTool_IFD0_in:
        ExifTool_IFD0_out = {}
        if "Make" in ExifTool_IFD0_in: ExifTool_IFD0_out["Make"] = ExifTool_IFD0_in["Make"]
        if "Model" in ExifTool_IFD0_in: ExifTool_IFD0_out["Model"] = ExifTool_IFD0_in["Model"]
        ExifTool_IFD0_out["DocumentName"] = NestedDict.get(result, ("ExifTool", "File", "Name"))[:8]
        if "Orientation" in ExifTool_IFD0_in: ExifTool_IFD0_out["Orientation"] = ExifTool_IFD0_in["Orientation"]
        user_ImageDescription = input(f"{CMD_INDENT}Add description [skip]: ").strip()
        if user_ImageDescription: ExifTool_IFD0_out["ImageDescription"] = user_ImageDescription
        if ExifTool_IFD0_out:
            NestedDict.set(result, ("ExifTool", "IFD0"), ExifTool_IFD0_out)

    #ExifTool.ExifIFD
    ExifTool_ExifIFD = NestedDict.pop(metadata, ("ExifTool", "ExifIFD"))
    ExifTool_InteropIFD = NestedDict.pop(metadata, ("ExifTool", "InteropIFD"))
    if ExifTool_ExifIFD:
        NestedDict.set(result, ("ExifTool", "ExifIFD"), ExifTool_ExifIFD)
        if ExifTool_InteropIFD:
            ExifTool_ExifIFD_ExifImageWidth = NestedDict.get(ExifTool_ExifIFD, "ExifImageWidth")
            ExifTool_ExifIFD_FocalPlaneXResolution = NestedDict.get(ExifTool_ExifIFD, "FocalPlaneXResolution")
            ExifTool_InteropIFD_RelatedImageWidth = NestedDict.get(ExifTool_InteropIFD, "RelatedImageWidth")
            NestedDict.set(ExifTool_ExifIFD, "ExifImageWidth", ExifTool_InteropIFD_RelatedImageWidth)
            NestedDict.set(ExifTool_ExifIFD, "FocalPlaneXResolution", ExifTool_ExifIFD_FocalPlaneXResolution * (ExifTool_InteropIFD_RelatedImageWidth / ExifTool_ExifIFD_ExifImageWidth))
            ExifTool_ExifIFD_ExifImageHeight = NestedDict.get(ExifTool_ExifIFD, "ExifImageHeight")
            ExifTool_ExifIFD_FocalPlaneYResolution = NestedDict.get(ExifTool_ExifIFD, "FocalPlaneYResolution")
            ExifTool_InteropIFD_RelatedImageHeight = NestedDict.get(ExifTool_InteropIFD, "RelatedImageHeight")
            NestedDict.set(ExifTool_ExifIFD, "ExifImageHeight", ExifTool_InteropIFD_RelatedImageHeight)
            NestedDict.set(ExifTool_ExifIFD, "FocalPlaneXResolution", ExifTool_ExifIFD_FocalPlaneYResolution * (ExifTool_InteropIFD_RelatedImageHeight / ExifTool_ExifIFD_ExifImageHeight))

    #ExifTool.Canon
    ExifTool_Canon = NestedDict.pop(metadata, ("ExifTool", "Canon"))
    if ExifTool_Canon:
        NestedDict.set(result, ("ExifTool", "Canon"), ExifTool_Canon)
        NestedDict.pop(result, ("ExifTool", "Canon", "ThumbnailImage")) 

    #ExifTool.CanonCustom
    ExifTool_CanonCustom = NestedDict.pop(metadata, ("ExifTool", "CanonCustom"))
    if ExifTool_CanonCustom:
        NestedDict.set(result, ("ExifTool", "CanonCustom"), ExifTool_CanonCustom)

    #Lens data
    ExifTool_Composite_LensID = NestedDict.get(metadata, ("ExifTool", "Composite", "LensID"), "").strip()
    if not ExifTool_Composite_LensID:
        #LensID is not present -> ask user
        user_LensID = input(f"{CMD_INDENT}Lens model is not present, add it manually {{'model'|'preset'}} [skip]: ").strip()
        if user_LensID:
            #user entered data -> check for preset
            if user_LensID in PRESET_LENS:
                #preset is present -> fill data from preset
                for key, value in PRESET_LENS[user_LensID].items():
                    NestedDict.set(result, key, value)
            else:
                #no such preset -> fill lens name with user string
                if NestedDict.get(result, ("ExifTool", "ExifIFD")):
                    NestedDict.set(result, ("ExifTool", "ExifIFD", "LensModel"), user_LensID)
                if NestedDict.get(result, ("ExifTool", "Canon")):
                    NestedDict.set(result, ("ExifTool", "Canon", "LensType"), user_LensID)
                    NestedDict.set(result, ("ExifTool", "Canon", "LensModel"), user_LensID)
                #ask for LensInfo
                while True:
                    user_LensInfo_data = {}
                    user_LensInfo_input = input(f"{CMD_INDENT}Lens info is not present, add it manually {{MinFocalLength, MaxFocalLength, Aperture@MinFocalLength, Aperture@MaxFocalLength}} [skip]: ").strip()
                    if user_LensInfo_input:
                        try:
                            match = re.match(r'^(?P<focal_min_length>\d+),\s*(?P<focal_max_length>\d+),\s*(?P<focal_min_aperture>\d+(?:\.\d+)?),\s*(?P<focal_max_aperture>\d+(?:\.\d+)?)$', user_LensInfo_input)
                            if match:
                                #user specified numeric values
                                user_LensInfo_data["focal_min_length"] = float(match["focal_min_length"])
                                user_LensInfo_data["focal_max_length"] = float(match["focal_max_length"])
                                user_LensInfo_data["focal_min_aperture"] = float(match["focal_min_aperture"])
                                user_LensInfo_data["focal_max_aperture"] = float(match["aperture_max_aperture"])
                                if not (user_LensInfo_data["focal_min_length"] > 0 and user_LensInfo_data["focal_max_length"] > 0 and user_LensInfo_data["focal_max_length"] >= user_LensInfo_data["focal_min_length"] and user_LensInfo_data["aperture_min"] > 0 and user_LensInfo_data["aperture_max"] > 0):
                                    raise ValueError
                                if user_LensInfo_data["focal_min_length"] == user_LensInfo_data["focal_max_length"]: lensinfo_str = f"{user_LensInfo_data['focal_min_length']:g}mm"
                                else:                                                                                lensinfo_str = f"{user_LensInfo_data['focal_min_length']:g}-{user_LensInfo_data['focal_max_length']:g}mm"
                                if user_LensInfo_data["focal_min_aperture"] == user_LensInfo_data["focal_max_aperture"]: lensinfo_str += f" f/{user_LensInfo_data['focal_min_aperture']:.2g}"
                                else:                                                                                    lensinfo_str += f" f/{user_LensInfo_data['focal_min_aperture']:.2g}-{user_LensInfo_data['focal_max_aperture']:.2g}"  
                                if NestedDict.get(result, ("ExifTool", "ExifIFD")):
                                    NestedDict.set(result, ("ExifTool", "ExifIFD", "LensInfo"), lensinfo_str)
                                if NestedDict.get(result, ("ExifTool", "Canon")):
                                    NestedDict.set(result, ("ExifTool", "Canon", "MaxFocalLength"),  f"{user_LensInfo_data['focal_max_length']:g} mm")
                                    NestedDict.set(result, ("ExifTool", "Canon", "MinFocalLength"),  f"{user_LensInfo_data['focal_min_length']:g} mm")
                                    NestedDict.set(result, ("ExifTool", "Canon", "MinFocalLength2"), f"{user_LensInfo_data['focal_min_length']:g} mm")
                                    NestedDict.set(result, ("ExifTool", "Canon", "MaxFocalLength2"), f"{user_LensInfo_data['focal_max_length']:g} mm")
                                #ask for aperture values
                                while True:
                                    user_LensInfo_input = input(f"{CMD_INDENT}Lens aperture values are not present, add them manually {{MaxAperture, MinAperture}} [skip]: ").strip()
                                    if user_LensInfo_input:
                                        try:
                                            match = re.match(r'^(?P<aperture_max>\d+(?:\.\d+)?),\s*(?P<aperture_min>\d+(?:\.\d+)?)$', user_LensInfo_input)
                                            if not match: raise ValueError
                                            #user specified numeric values
                                            user_LensInfo_data["aperture_max"] = float(match["aperture_max"])
                                            user_LensInfo_data["aperture_min"] = float(match["aperture_min"])
                                            if not (user_LensInfo_data["aperture_max"] <= user_LensInfo_data["aperture_min"] and user_LensInfo_data["aperture_min"] > 0 and user_LensInfo_data["aperture_max"] > 0): raise ValueError
                                            if NestedDict.get(result, ("ExifTool", "Canon")):
                                                NestedDict.set(result, ("ExifTool", "Canon", "MaxAperture"), user_LensInfo_data["aperture_max"])
                                                NestedDict.set(result, ("ExifTool", "Canon", "MinAperture"), user_LensInfo_data["aperture_min"])
                                            #ask for LensSerialNumber
                                            user_LensInfo_data["serial_number"] = input(f"{CMD_INDENT}Enter lens serial number [skip]: ").strip()
                                            if user_LensInfo_data["serial_number"]:
                                                if NestedDict.get(result, ("ExifTool", "ExifIFD")):
                                                    NestedDict.set(result, ("ExifTool", "ExifIFD", "LensSerialNumber"), user_LensInfo_data["serial_number"])
                                        except ValueError:
                                            print(f"{CMD_INDENT}{CMD_INDENT}Invalid data.")
                                            continue
                                    break
                                break
                        except ValueError:
                            print(f"{CMD_INDENT}{CMD_INDENT}Invalid data.")
                            continue
                    break
    else:
        #LensID is present -> check if preset for such ID is present
        if ExifTool_Composite_LensID in PRESET_LENS:
            #preset is present -> overwrite data from preset
            for key, value in PRESET_LENS[ExifTool_Composite_LensID].items():
                NestedDict.set(result, key, value)

    #Focal Length
    ExifTool_ExifIFD_FocalLength = NestedDict.get(result, ("ExifTool", "ExifIFD", "FocalLength"), "0").strip()
    try:
        match = re.search(r'\d+(?:\.\d+)?', ExifTool_ExifIFD_FocalLength)
        if not match: raise ValueError
        ExifTool_ExifIFD_FocalLength = float(match.group())
    except ValueError:
        ExifTool_ExifIFD_FocalLength = 0
    if ExifTool_ExifIFD_FocalLength <= 0:
        #FocalLength is not present -> ask user
        while True:
            user_FocalLength = input(f"{CMD_INDENT}Focal length is not present, add it manually [skip]: ").strip()
            if user_FocalLength:
                try:
                    user_FocalLength = float(user_FocalLength)
                    if user_FocalLength <= 0: raise ValueError
                except ValueError:
                    print(f"{CMD_INDENT}{CMD_INDENT}Invalid value.")
                    continue
                user_FocalLength = f"{user_FocalLength:.2g}mm"
                if NestedDict.get(result, ("ExifTool", "ExifIFD")):
                    NestedDict.set(result, ("ExifTool", "ExifIFD", "FocalLength"), user_FocalLength)
                if NestedDict.get(result, ("ExifTool", "Canon")):
                    NestedDict.set(result, ("ExifTool", "Canon", "FocalLength"), user_FocalLength)
            break

    ExifTool_ExifIFD_FNumber = NestedDict.get(result, ("ExifTool", "ExifIFD", "FNumber"), 0)
    if ExifTool_ExifIFD_FNumber != "undef" and isinstance(ExifTool_ExifIFD_FNumber, (int, float)) and ExifTool_ExifIFD_FNumber <= 0:
        #FNumber is not present -> ask user
        while True:
            user_FNumber = input(f"{CMD_INDENT}Aperture value is not specified, add it manually [skip]: ").strip()
            if user_FNumber:
                try:
                    user_FNumber = float(user_FNumber)
                    if user_FNumber <= 0: raise ValueError
                except ValueError:
                    print(f"{CMD_INDENT}{CMD_INDENT}Invalid value.")
                    continue
                if NestedDict.get(result, ("ExifTool", "ExifIFD")):
                    NestedDict.set(result, ("ExifTool", "ExifIFD", "FNumber"), user_FNumber)
                    NestedDict.set(result, ("ExifTool", "ExifIFD", "ApertureValue"), user_FNumber)
                if NestedDict.get(result, ("ExifTool", "Canon")):
                    NestedDict.set(result, ("ExifTool", "Canon", "TargetAperture"), user_FNumber)
                    NestedDict.set(result, ("ExifTool", "Canon", "FNumber"), user_FNumber)
            break

    #ExifTool.GPS
    gps_data = {}
    ExifTool_GPS = NestedDict.pop(metadata, ("ExifTool", "GPS"))
    ExifTool_UserData = NestedDict.pop(metadata, ("ExifTool", "UserData"))
    if ExifTool_GPS:
        if "GPSVersionID" in ExifTool_GPS: NestedDict.set(result, ("ExifTool", "GPS", "GPSVersionID"), ExifTool_GPS.pop("GPSVersionID"))
        if "GPSStatus"    in ExifTool_GPS: NestedDict.set(result, ("ExifTool", "GPS", "GPSStatus"),    ExifTool_GPS.pop("GPSStatus"))
        if "GPSDateStamp" in ExifTool_GPS: NestedDict.set(result, ("ExifTool", "GPS", "GPSDateStamp"), ExifTool_GPS.pop("GPSDateStamp"))
        if "GPSTimeStamp" in ExifTool_GPS: NestedDict.set(result, ("ExifTool", "GPS", "GPSTimeStamp"), ExifTool_GPS.pop("GPSTimeStamp"))
        for key, value in ExifTool_GPS.items():
            NestedDict.set(result, ("ExifTool", "GPS", key), value)
        ExifTool_GPS_GPSStatus = NestedDict.get(result, ("ExifTool", "GPS", "GPSStatus"))
        if ExifTool_GPS_GPSStatus == "Measurement Active":
            #GPS data was available to the camera -> get coordinates from gimmic tag ("UserData:LocationInformation")
            ExifTool_UserData_LocationInformation = dict(re.findall(r'(\w+)=([^\s]*)', NestedDict.get(ExifTool_UserData, "LocationInformation")))
            try:
                if "Lat" in ExifTool_UserData_LocationInformation: gps_data["lat"] = float(ExifTool_UserData_LocationInformation["Lat"])
                if "Lon" in ExifTool_UserData_LocationInformation: gps_data["lon"] = float(ExifTool_UserData_LocationInformation["Lon"])
                if "Alt" in ExifTool_UserData_LocationInformation: gps_data["alt"] = float(ExifTool_UserData_LocationInformation["Alt"])
                if "lat" in gps_data and "lon" in gps_data:
                    gps_data["method"] = "GPS"
                else:
                    raise ValueError
            except ValueError:
                gps_data = {}
        elif ExifTool_GPS_GPSStatus == "Unknown ()":
            NestedDict.set(ExifTool_GPS, "GPSStatus", "Unknown")
    if not gps_data:
        #GPS data was not available to the camera -> ask user
        while True:
            gps_data = {}
            user_gps = input(f"{CMD_INDENT}GPS info is not present or invalid, add it manually {{±lat, ±lon[, ±alt[, areaname]]|'preset'}} [skip]: ").strip()
            if user_gps:
                match = re.match(r"^\s*(?P<lat>[+-]?\d+(?:\.\d+)?)\s*,\s*(?P<lon>[+-]?\d+(?:\.\d+)?)(?:\s*,\s*(?P<alt>[+-]?\d+(?:\.\d+)?)(?:\s*,\s*'(?P<area>[^']*)')?)?\s*$", user_gps)
                if match:
                    #user specified numeric coordinates
                    try:
                        gps_data["lat"] = float(match["lat"])
                        gps_data["lon"] = float(match["lon"])
                        if match["alt"] is not None: gps_data["alt"] = float(match["alt"])
                        if match["area"] is not None: gps_data["area"] = match["area"]
                        if (not -90 <= gps_data["lat"] <= 90) or (not -180 <= gps_data["lon"] <= 180):
                            raise ValueError
                    except ValueError:
                        print(f"{CMD_INDENT}{CMD_INDENT}Invalid coordinates.")
                        continue
                else:
                    if user_gps in PRESET_GPS:
                        #user specified location in preset
                        gps_data["lat"] = PRESET_GPS[user_gps][0]
                        gps_data["lon"] = PRESET_GPS[user_gps][1]
                        if len(PRESET_GPS[user_gps]) > 2:
                            if PRESET_GPS[user_gps][2] is not None: gps_data["alt"] = PRESET_GPS[user_gps][2]
                        if len(PRESET_GPS[user_gps]) > 3:
                            if PRESET_GPS[user_gps][3]: gps_data["area"] = PRESET_GPS[user_gps][3]
                    else:
                        print(f"{CMD_INDENT}{CMD_INDENT}No such preset.")
                        continue
                gps_data["method"] = "MANUAL"
            break
    if gps_data:
        NestedDict.set(result, ("ExifTool", "GPS", "GPSLatitude"), abs(gps_data["lat"]))
        if gps_data["lat"] >= 0: NestedDict.set(result, ("ExifTool", "GPS", "GPSLatitudeRef"), "North")
        else:                    NestedDict.set(result, ("ExifTool", "GPS", "GPSLatitudeRef"), "South")
        NestedDict.set(result, ("ExifTool", "GPS", "GPSLongitude"), abs(gps_data["lon"]))
        if gps_data["lon"] >= 0: NestedDict.set(result, ("ExifTool", "GPS", "GPSLongitudeRef"), "East")
        else:                    NestedDict.set(result, ("ExifTool", "GPS", "GPSLongitudeRef"), "West")
        if "alt" in gps_data:
            NestedDict.set(result, ("ExifTool", "GPS", "GPSAltitude"), abs(gps_data["alt"]))
            if gps_data["alt"] >= 0: NestedDict.set(result, ("ExifTool", "GPS", "GPSAltitudeRef"), "Above Sea Level")
            else:                    NestedDict.set(result, ("ExifTool", "GPS", "GPSAltitudeRef"), "Below Sea Level")
        if "area" in gps_data:
            NestedDict.set(result, ("ExifTool", "GPS", "GPSAreaInformation"), gps_data["area"])
        NestedDict.set(result, ("ExifTool", "GPS", "GPSProcessingMethod"), gps_data["method"])
    
    #ExifTool.Track#
    i = 1
    while NestedDict.pop(metadata, ("ExifTool", f"Track{i}")) is not None:
        i += 1

    #ExifTool.Composite
    NestedDict.pop(metadata, ("ExifTool", "Composite"))

    #ExifTool.Unexpected
    ExifTool_Unexpected = NestedDict.pop(metadata, "ExifTool")
    if ExifTool_Unexpected:
        NestedDict.set(result, ("ExifTool", "Unexpected"), ExifTool_Unexpected)

    #ExifTool: shorten message for binary data 
    ExifTool_binary_pattern = re.compile(r"Binary data (\d+) bytes")
    stack = [result]
    while stack:
        current = stack.pop()
        for key, value in current.items():
            if isinstance(value, dict):
                stack.append(value)
            elif isinstance(value, str):
                match = ExifTool_binary_pattern.search(value)
                if match:
                    current[key] = f"<binary data: {match.group(1)} bytes>"

    #ffprobe.Version
    ffprobe_ProgramVersion = NestedDict.pop(metadata, ("ffprobe", "program_version"))
    if ffprobe_ProgramVersion:
        NestedDict.set(result, ("ffprobe", "Version"), NestedDict.get(ffprobe_ProgramVersion, "version", "<unknown>"))

    #ffprobe.Streams
    ffprobe_Streams = NestedDict.pop(metadata, ("ffprobe", "streams"))
    if ffprobe_Streams:
        NestedDict.set(result, ("ffprobe", "Streams"), ffprobe_Streams)
        for stream, value in ffprobe_Streams.items():
            NestedDict.pop(value, "disposition")
            timecode = NestedDict.get(value, ("tags", "timecode"))
            if timecode:
                NestedDict.set(value, "timecode", timecode)
            NestedDict.pop(value, "tags")
        
    return result


#Builds composite from metadata
def composite_build(metadata: dict) -> dict:
    result = {}
    
    #EXIF -> Description
    description = NestedDict.get(metadata, ("ExifTool", "IFD0", "ImageDescription"))
    if description:
        NestedDict.set(result, ("EXIF", "Description"), description)

    #EXIF -> Original DateTime
    datetime_value  = NestedDict.get(metadata, ("ExifTool", "ExifIFD", "DateTimeOriginal"))
    datetime_offset = NestedDict.get(metadata, ("ExifTool", "ExifIFD", "OffsetTimeOriginal"))
    if datetime_value:
        if datetime_offset: datetime_value += f" ({datetime_offset})"
        NestedDict.set(result, ("EXIF", "DateTimeOriginal"), datetime_value)

    #EXIF -> GPS
    gps = NestedDict.get(metadata, ("ExifTool", 'GPS'))
    if gps:
        gps_lat = gps.get('GPSLatitude')
        gps_lon = gps.get('GPSLongitude')
        if gps_lat is not None and gps_lon is not None:
            if "S" in gps.get("GPSLatitudeRef", ""): gps_lat = -gps_lat
            if "W" in gps.get("GPSLongitudeRef", ""): gps_lon = -gps_lon
            gps_str = f"lat: {gps_lat:.6f}; lon: {gps_lon:.6f}"
            gps_alt = gps.get('GPSAltitude')
            if gps_alt:
                if "B" in gps.get("GPSAltitudeRef", ""): gps_alt = -gps_alt
                gps_str += f"; alt: {gps_alt:.1f}"
            gps_date = gps.get("GPSDateStamp")
            gps_time = gps.get("GPSTimeStamp")
            if gps_date and gps_time:
                gps_str += f"; time: {gps_date} {gps_time}"
            gps_area = gps.get("GPSAreaInformation")
            if gps_area: gps_str += f"; area: {gps_area}"

            NestedDict.set(result, ("EXIF", "GPS"), gps_str)

    #EXIF -> Camera
    camera_make  = NestedDict.get(metadata, ("ExifTool", "IFD0", "Make"))
    camera_model = NestedDict.get(metadata, ("ExifTool", "IFD0", "Model"))
    camera_fv    = NestedDict.get(metadata, ("ExifTool", "Canon", "CanonFirmwareVersion"))
    camera_sn    = NestedDict.get(metadata, ("ExifTool", "ExifIFD", "SerialNumber"))
    camera_owner = NestedDict.get(metadata, ("ExifTool", "Canon", "OwnerName"))
    if camera_make in camera_model: camera_str = camera_model
    else:                           camera_str = f"{camera_make} {camera_model}"
    if camera_fv: camera_fv = camera_fv.replace("Firmware Version ", "")
    if camera_fv or camera_sn or camera_owner:
        camera_str += " ("
        if camera_fv: camera_str += f"f/v: {camera_fv}; "
        if camera_sn: camera_str += f"s/n: {camera_sn}; "
        if camera_owner: camera_str += f"owner: {camera_owner}"
        camera_str = camera_str.strip(" ").strip(";")
        camera_str += ")"
    NestedDict.set(result, ("EXIF", "Camera"), camera_str)

    #EXIF -> Lens
    lens_model = NestedDict.get(metadata, ("ExifTool", "ExifIFD", "LensModel"))
    lens_sn    = NestedDict.get(metadata, ("ExifTool", "ExifIFD", "LensSerialNumber"))
    if lens_model:
        if (isinstance(lens_sn, int) and lens_sn != 0) or (isinstance(lens_sn, str) and len(lens_sn.strip().replace('0', '')) > 0):
            lens_model += f" (s/n: {lens_sn})"
        NestedDict.set(result, ("EXIF", "Lens"), lens_model)

    #EXIF -> Focal length
    focal_length = NestedDict.get(metadata, ("ExifTool", "ExifIFD", "FocalLength"))
    if focal_length:
        if isinstance(focal_length, (int, float)):
            pass
        elif isinstance(focal_length, str):
            match = re.search(r'\d+(?:\.\d+)?', focal_length)
            if match:
                try: focal_length = float(match.group())
                except ValueError: focal_length = 0
        if focal_length > 0:
            NestedDict.set(result, ("EXIF", "FocalLength"), f"{focal_length:g}mm")

    #EXIF -> Orientation
    orientation = NestedDict.get(metadata, ("ExifTool", "IFD0", "Orientation"))
    if orientation:
        orientation_str = orientation.replace(" (normal)", "")
        orientation_roll = NestedDict.get(metadata, ("ExifTool", "Canon", "RollAngle"))
        orientation_pitch = NestedDict.get(metadata, ("ExifTool", "Canon", "PitchAngle"))
        if orientation_roll is not None and orientation_pitch is not None:
            orientation_str += f" (roll: {orientation_roll:.1f}°; pitch: {orientation_pitch:.1f}°)"
        NestedDict.set(result, ("EXIF", "Orientation"), orientation_str)

    #EXIF -> Exposure
    exposure_prog = NestedDict.get(metadata, ("ExifTool", "ExifIFD", "ExposureProgram"))

    exposure_tv = NestedDict.get(metadata, ("ExifTool", "ExifIFD", "ExposureTime"))
    if isinstance(exposure_tv, (int, float)):
        exposure_tv_num = exposure_tv
    elif exposure_tv == "undef":
        exposure_tv = 0
        exposure_tv_num = exposure_tv
    else:
        match = re.search(r'\b(\d+)/(\d+)\b', exposure_tv)
        if match:
            exposure_tv = (int(match.group(1)), int(match.group(2)))
            exposure_tv_num = exposure_tv[0] / exposure_tv[1]
        else:
            exposure_tv = -1
            exposure_tv_num = exposure_tv

    exposure_av = NestedDict.get(metadata, ("ExifTool", "ExifIFD", "FNumber"))
    if isinstance(exposure_av, (int, float)):
        pass
    elif exposure_av == "undef":
        exposure_av = 0
    else:
        match = re.search(r'[fF]/(\d+\.\d+)', exposure_av)
        if match:
            exposure_av = float(match.group(1))
        else:
            exposure_av = -1
    
    exposure_iso = NestedDict.get(metadata, ("ExifTool", "ExifIFD", "ISO"))
    if isinstance(exposure_iso, (int, float)):
        pass
    elif exposure_iso == "undef":
        exposure_iso = 0
    else:
        try:
            exposure_iso = float(exposure_iso)
        except ValueError:
            exposure_iso = -1

    exposure_lv = NestedDict.get(metadata, ("ExifTool", "Canon", "MeasuredEV"))
    if isinstance(exposure_lv, (int, float)):
        pass
    else:
        try:
            exposure_lv = float(exposure_iso)
        except ValueError:
            exposure_lv = None

    exposure_ec = NestedDict.get(metadata, ("ExifTool", "ExifIFD", "ExposureCompensation"))
    if isinstance(exposure_ec, (int, float)):
        pass
    else:
        match = re.search(r'([+-]?)\b(\d+)/(\d+)\b', exposure_ec)
        if match:
            if match.group(1) == "-": exposure_ec = (-int(match.group(2)), int(match.group(3)))
            else:                     exposure_ec = ( int(match.group(2)), int(match.group(3)))
        else:
            exposure_ec = None

    if   exposure_prog == "Not Defined":                exposure_prog = "n/d"
    elif exposure_prog == "Manual":                     exposure_prog = "M"
    elif exposure_prog == "Program AE":                 exposure_prog = "P"
    elif exposure_prog == "Aperture-priority AE":       exposure_prog = "Av"
    elif exposure_prog == "Shutter speed priority AE":  exposure_prog = "Tv"
    elif exposure_prog == "Creative (Slow speed)":      exposure_prog = "Creative"
    elif exposure_prog == "Action (High speed)":        exposure_prog = "Action"
    elif exposure_prog == "Portrait":                   exposure_prog = "Portrait"
    elif exposure_prog == "Landscape":                  exposure_prog = "Landscape"
    elif exposure_prog == "Bulb":                       exposure_prog = "B"
    else: pass

    if   exposure_tv_num > 0 and exposure_av > 0 and exposure_iso > 0: exposure_ev = f"{math.log2((exposure_av ** 2) / exposure_tv_num) - math.log2(exposure_iso / 100):.2f}"
    elif exposure_tv_num < 0 or exposure_av < 0 or exposure_iso < 0:   exposure_ev = "n/d"
    else:                                                              exposure_ev = "Auto"

    if exposure_tv_num > 0:
        if isinstance(exposure_tv, tuple): exposure_tv = f"{exposure_tv[0]}/{exposure_tv[1]}s"
        else: exposure_tv = f"{exposure_tv:g}s"
    elif exposure_tv_num == 0: exposure_tv = "Auto"
    else:                      exposure_tv = "n/d"

    if   exposure_av >  0: exposure_av = f"f/{exposure_av:.2g}"
    elif exposure_av == 0: exposure_av = "Auto"
    else:                  exposure_av = "n/d"

    if   exposure_iso >  0: exposure_iso = f"{exposure_iso:g}"
    elif exposure_iso == 0: exposure_iso = "Auto"
    else:                   exposure_iso = "n/d"

    if exposure_lv is not None: exposure_lv = f"{exposure_lv:.2f}"
    else:                       exposure_lv = "n/d"

    if exposure_ec is not None:
        if isinstance(exposure_ec, tuple): exposure_ec = f"{exposure_ec[0]:+}/{exposure_ec[1]}"
        elif exposure_ec == 0:             exposure_ec = "0"
        else:                              exposure_ec = f"{exposure_ec:+g}"
    else:                                  exposure_ec = "n/d"

    exposure_str = f"Program: {exposure_prog}; Tv: {exposure_tv}; Av: {exposure_av}; ISO: {exposure_iso} (EV: {exposure_ev}; LV: {exposure_lv}; EC: {exposure_ec})"
    NestedDict.set(result, ("EXIF", "Exposure"), exposure_str)

    #EXIF -> Dynamic Range
    dynamicrange_hdrpq = NestedDict.get(metadata, ("ExifTool", "Canon", "HDR-PQ"))
    dynamicrange_clog = NestedDict.get(metadata, ("ExifTool", "Canon", "CanonLogVersion"))
    if isinstance(dynamicrange_hdrpq, str) and dynamicrange_hdrpq.lower() == "on":
        dynamicrange_str = "HDR-PQ"
    elif isinstance(dynamicrange_clog, str) and len(dynamicrange_clog.strip()) > 0 and dynamicrange_clog.lower() != "off":
        dynamicrange_clog_cs = NestedDict.get(metadata, ("ExifTool", "Canon", "ColorSpace2"))
        dynamicrange_str = f"{dynamicrange_clog} [{dynamicrange_clog_cs}]"
    else:
        dynamicrange_str = "SDR"
    NestedDict.set(result, ("EXIF", "DynamicRange"), dynamicrange_str)

    #EXIF -> White Balance
    wb_value = NestedDict.get(metadata, ("ExifTool", "Canon", "WhiteBalance"))
    if wb_value:
        if wb_value == "Manual Temperature (Kelvin)":
            wb_temp  = NestedDict.get(metadata, ("ExifTool", "Canon", "ColorTemperature"))
            wb_str = f"{wb_temp} K"
        else:
            wb_str = wb_value
        wb_shiftAB = NestedDict.get(metadata, ("ExifTool", "Canon", "WBShiftAB"))
        wb_shiftGM = NestedDict.get(metadata, ("ExifTool", "Canon", "WBShiftGM"))
        if wb_shiftAB is not None and wb_shiftGM is not None:
            if wb_shiftAB == 0: wb_shiftAB = "0"
            else:               wb_shiftAB = f"{wb_shiftAB:+g}"
            if wb_shiftGM == 0: wb_shiftGM = "0"
            else:               wb_shiftGM = f"{wb_shiftGM:+g}"
            wb_str += f" (shift: AB={wb_shiftAB}, GM={wb_shiftGM})"
        NestedDict.set(result, ("EXIF", "WhiteBalance"), wb_str)

    #EXIF -> Picture Style
    picstyle_name = NestedDict.get(metadata, ("ExifTool", "Canon", "PictureStyle"))
    if picstyle_name:
        picstyle_sharp = NestedDict.get(metadata, ("ExifTool", "Canon", "Sharpness"))
        picstyle_cont  = NestedDict.get(metadata, ("ExifTool", "Canon", "Contrast"))
        picstyle_sat   = NestedDict.get(metadata, ("ExifTool", "Canon", "Saturation"))
        picstyle_tone  = NestedDict.get(metadata, ("ExifTool", "Canon", "ColorTone"))
        picstyle_clar  = NestedDict.get(metadata, ("ExifTool", "Canon", "Clarity"))
        picstyle_str = picstyle_name
        if picstyle_sharp or picstyle_cont or picstyle_sat or picstyle_tone or picstyle_clar:
            picstyle_str += " ("
            if picstyle_sharp:
                if isinstance(picstyle_sharp, str) and picstyle_sharp.lower() == "normal": picstyle_sharp = "0"
                picstyle_str += f"sharp: {picstyle_sharp}; "
            if picstyle_cont:
                if isinstance(picstyle_cont, str) and picstyle_cont.lower() == "normal": picstyle_cont = "0"
                picstyle_str += f"cont: {picstyle_cont}; "
            if picstyle_sat:
                if isinstance(picstyle_sat, str) and picstyle_sat.lower() == "normal": picstyle_sat = "0"
                picstyle_str += f"sat: {picstyle_sat}; "
            if picstyle_tone:
                if isinstance(picstyle_tone, str) and picstyle_tone.lower() == "normal": picstyle_tone = "0"
                picstyle_str += f"tone: {picstyle_tone}"
            if picstyle_clar:
                if isinstance(picstyle_clar, str) and picstyle_clar.lower() == "normal": picstyle_clar = "0"
                picstyle_str += f"clar: {picstyle_clar}"
            picstyle_str = picstyle_str.strip(" ").strip(";")
            picstyle_str += ")"
        NestedDict.set(result, ("EXIF", "PictureStyle"), picstyle_str)

    #EXIF -> Focus
    focus_mode = NestedDict.get(metadata, ("ExifTool", "Canon", "FocusMode"))
    if focus_mode:
        focus_str = focus_mode
        NestedDict.set(result, ("EXIF", "Focus"), focus_str)

    #EXIF -> Image stabilization
    imgstab = NestedDict.get(metadata, ("ExifTool", "Canon", "ImageStabilization"))
    if imgstab:
        imgstab_str = imgstab
        NestedDict.set(result, ("EXIF", "ImageStabilization"), imgstab_str)

    #Source -> Video
    ffprobe_Streams_Video = NestedDict.get(metadata, ("ffprobe", "Streams", "Video"))
    if ffprobe_Streams_Video:
        original_video_str = f"codec: {ffprobe_Streams_Video.get('codec_name')}"
        original_video_bitrate = ffprobe_Streams_Video.get('bit_rate')
        if original_video_bitrate:
            try:
                original_video_bitrate = int(original_video_bitrate)
                if   original_video_bitrate >= 1e9: original_video_str += f"; bitrate: {original_video_bitrate/1e9:.3g}Gbps"
                elif original_video_bitrate >= 1e6: original_video_str += f"; bitrate: {original_video_bitrate/1e6:.3g}Mbps"
                elif original_video_bitrate >= 1e3: original_video_str += f"; bitrate: {original_video_bitrate/1e3:.3g}kbps"
                else:                               original_video_str += f"; bitrate: {original_video_bitrate}bps"
            except ValueError:
                pass
        original_video_str += f"; res: {ffprobe_Streams_Video.get('width')}x{ffprobe_Streams_Video.get('height')}"
        original_video_fps = ffprobe_Streams_Video.get('avg_frame_rate')
        try:
            if isinstance(original_video_fps, (int, float)):
                original_video_fps_numerator = None
                original_video_fps_denominator = None
            elif isinstance(original_video_fps, str):
                if "/" in original_video_fps:
                    original_video_fps_numerator, original_video_fps_denominator = original_video_fps.split("/")
                    original_video_fps_numerator = int(original_video_fps_numerator.strip())
                    original_video_fps_denominator = int(original_video_fps_denominator.strip())
                    original_video_fps = original_video_fps_numerator / original_video_fps_denominator
                else:
                    original_video_fps = float(original_video_fps.strip())
            else:
                raise ValueError
            original_video_str += f"; fps: {original_video_fps:.2f}"
            if original_video_fps_numerator and original_video_fps_denominator:
                original_video_str += f" ({original_video_fps_numerator}/{original_video_fps_denominator})"
        except ValueError:
            pass
        original_video_str += f"; pixfmt: {ffprobe_Streams_Video.get('pix_fmt')}"
        original_video_str += f"; range: {ffprobe_Streams_Video.get('color_range')}"
        original_video_str += f"; color: spc={ffprobe_Streams_Video.get('color_space')}, trf={ffprobe_Streams_Video.get('color_transfer')}, pri={ffprobe_Streams_Video.get('color_primaries')}"
        NestedDict.set(result, ("Source", "Video"), original_video_str)

    #Source -> Audio
    ffprobe_Streams_Audio = NestedDict.get(metadata, ("ffprobe", "Streams", "Audio"))
    if ffprobe_Streams_Audio:
        original_audio_str = f"codec: {ffprobe_Streams_Audio.get('codec_name')}"
        original_audio_bitrate = ffprobe_Streams_Audio.get('bit_rate')
        if original_audio_bitrate:
            try:
                original_audio_bitrate = int(original_audio_bitrate)
                original_audio_str += f"; bitrate: {original_audio_bitrate/1e3:.4g}kbps"
            except ValueError:
                pass
        original_audio_channels = ffprobe_Streams_Audio.get('channels')
        if original_audio_channels:
            original_audio_str += f"; channels: {original_audio_channels}"
        original_audio_samplerate = ffprobe_Streams_Audio.get('sample_rate')
        if original_audio_samplerate:
            try:
                original_audio_samplerate = int(original_audio_samplerate)
                original_audio_str += f"; samplerate: {original_audio_samplerate/1e3:.6g}kHz"
            except ValueError:
                pass
        NestedDict.set(result, ("Source", "Audio"), original_audio_str)

    #Source -> Metadata
    NestedDict.set(result, ("Source", "Metadata"), "Full source video file metadata is in the attached ZIP archive.")

    return result


def main():
    #parse call arguments
    parser = argparse.ArgumentParser(description=f"video-reencode-tools:metadata-carrier, v.{_module_date:%Y-%m-%d} by {_module_designer}.")
    parser.add_argument("inputs",       nargs="+", type=Path,                                 help="Input files (drag & drop supported)")
    parser.add_argument("--exiftool",              type=Path, default=None, metavar="<file>", help="Path to exiftool.")
    parser.add_argument("--ffprobe",               type=Path, default=None, metavar="<file>", help="Path to ffprobe.")
    parser.add_argument("--mkvpropedit",           type=Path, default=None, metavar="<file>", help="Path to mkvpropedit.")
    parser.add_argument("--mkvextract",            type=Path, default=None, metavar="<file>", help="Path to mkvextract.")
    parser.add_argument('--nohalt',                action='store_true',                       help='Do not halt terminal when finished')
    args = parser.parse_args()

    inputs = [f.resolve() for f in args.inputs]
    if args.nohalt: 
        global _halt_on_exit
        _halt_on_exit = False

    #detect mode of operation
    input_extensions = {f.suffix.lower() for f in inputs}
    opmode_extract = (".mp4" in input_extensions or  ".json" in input_extensions)
    opmode_insert  = (".mkv" in input_extensions and ".xml"  in input_extensions and ".zip" in input_extensions)

    if opmode_extract and opmode_insert:
        raise ValueError("Input contains files belonging to both extraction and insertion mode.")
    
    if opmode_extract:
        #metadata extraction mode
        input_extensions_allowed = {".mp4", ".json"}
        invalid = [
            ext for ext in input_extensions
            if ext not in input_extensions_allowed
        ]
        if invalid:
            raise ValueError(f"Invalid file types in extraction mode: {invalid}")
        
        global exiftool_exe, ffprobe_exe
        exiftool_exe = find_exe("exiftool", args.exiftool)
        ffprobe_exe  = find_exe("ffprobe",  args.ffprobe)
        print(f"Exiftool: {exiftool_exe}")
        print(f"ffprobe:  {ffprobe_exe}")
        print("")

        for file in inputs:
            print(f"Processing: {file}")
            file_suffix = file.suffix.lower()
            metadata_dict = {}
            if file_suffix == ".mp4":
                metadata_header_bin  = metadada_get_binary(file)
                metadata_dict["ExifTool"] = metadata_decode_exiftool_stdout(file)
                metadata_dict["ffprobe"]  = metadata_decode_ffprobe_stdout(file)
            elif file_suffix == ".json":
                print(f"{CMD_INDENT}Working with exiftool JSON output. No original header data will be available.")
                metadata_header_bin  = None
                metadata_dict["ExifTool"] = metadata_decode_exiftool_file(file)
            else:
                print(f"{CMD_INDENT}Unsupported file type. Operation may be limited. Manually check the result.")
                metadata_header_bin  = None
                metadata_dict["ExifTool"] = metadata_decode_exiftool_stdout(file)
                metadata_dict["ffprobe"]  = metadata_decode_ffprobe_stdout(file)

            metadata_dict = metadata_refactor(metadata_dict)
            composite_dict = composite_build(metadata_dict)

            metadata_json = metadata_encode_json(metadata_dict)
            composite_xml = metadata_encode_mkvxml(composite_dict)

            metadata_files = {}
            if metadata_header_bin is not None:
                metadata_files[file.with_name(file.name + ".header")] = metadata_header_bin
            if metadata_json is not None:
                metadata_files[file.with_name(file.name + ".json")] = metadata_json
            metadata_save(metadata_files, zipfile.ZIP_LZMA, file.with_name(file.stem + "_metadata.zip"))

            composite_files = {file.with_name(file.stem + "_metadata.xml"): composite_xml}
            metadata_save(composite_files, None)
            
            print("")

        print("Done.")

    elif opmode_insert:
        #metadata insertion mode
        #check input
        input_extensions_allowed = {".mkv", ".xml", ".zip"}
        invalid = [
            ext for ext in input_extensions
            if ext not in input_extensions_allowed
        ]
        if invalid:
            raise ValueError(f"Invalid file types in insertion mode: {invalid}")

        #group files
        groups = {}
        for file in inputs:
            ext = file.suffix.lower()
            stem = str(file.parent) + "\\" + file.stem[:8]
            if stem in groups:
                if ext in groups[stem]:
                    raise ValueError(f"Multiple '{ext}' files found for '{stem}'")
                else:
                    groups[stem][ext] = file
            else:
                groups[stem] = {ext: file}

        #validate groups
        for stem, group in groups.items():
            missing = []
            for required in [".mkv", ".xml", ".zip"]:
                if required not in group:
                    missing.append(required)
            if missing:
                raise ValueError(f"Group '{stem}' is missing: {', '.join(missing)}")

        #insert metadata
        global mkvpropedit_exe, mkvextract_exe
        mkvpropedit_exe = find_exe("mkvpropedit", args.mkvpropedit)
        mkvextract_exe  = find_exe("mkvextract",  args.mkvextract)
        print(f"mkvpropedit: {mkvpropedit_exe}")
        print(f"mkvextract:  {mkvextract_exe}")
        print("")

        for stem, group in groups.items():
            print(f"Processing: {group['.mkv'].stem}")
            print(f"{CMD_INDENT}MKV: {group['.mkv']}")
            print(f"{CMD_INDENT}XML: {group['.xml']}")
            print(f"{CMD_INDENT}ZIP: {group['.zip']}")
            #read tags that already exist in MKV file and discard generic Matroska tags
            metadata_mkv = metadata_decode_mkvxml_stdout(group[".mkv"])
            metadata_old = {}
            for tag, value in metadata_mkv.items():
                if not tag.isupper() and isinstance(value, dict):
                    metadata_old[tag] = value
            #read tags that exist in XML file
            metadata_new = metadata_decode_mkvxml_file(group[".xml"])
            #merge metadata
            metadata = metadata_old | metadata_new
            #save it to new temporary XML file
            metadata_file = group[".xml"].with_suffix(".tmp")
            metadata_save({metadata_file: metadata_encode_mkvxml(metadata)}, None)
            #insert merged metadata into MKV file
            metadata_insert_mkv(group[".mkv"], metadata_file, group[".zip"])
            #delete temporary XML file
            metadata_file.unlink(missing_ok=True)
            print("")
        print("Done.")


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