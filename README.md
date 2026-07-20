# video-reencode-tools
A collection of scripts for reencoding camera footage. Designed for creating archival encodes while preserving metadata and automating common encoding workflows.

## tools
- [**_metadata-carrier.py_**](#metadata-carrier) - a Python utility for preserving camera metadata when transcoding camera-original MP4 files into MKV files;
- [**_encoder.py_**](#encoder) - a Python utility for automating encoding process using FFmpeg;
- [**_abav1-crfprobe.py_**](#abav1-crfprobe) - a Python utility for getting sample-encode scores for multiple crf values using ab-av1 tool;
- [**_compare.avs_**](#compare) - AviSynth script to compare several video files side-by-side while maintaining resolution of original file.

---

<a name="metadata-carrier"></a>
## metadata-carrier.py

A Python utility for preserving camera metadata when transcoding camera-original MP4 files into MKV (Matroska) files. Designed for my Canon EOS R7. Other similar Canon cameras should work too.

When transcoding camera originals, most camera-specific metadata is lost. This script extracts metadata from the original MP4 using ExifTool and FFprobe, filters and consolidates useful information, and transfers it into the final MKV as native Matroska tags and binary attachments.

### Workflow
Script contains 2 mode of operation: metadata extraction mode and metadata insertion mode. Mode of operation is determined by extension of the input files.

Extraction mode:
- User drops original MP4 file(s) onto the script.
- Camera shooting metadata is exctracted using *ExifTool*.
- Stream properties are exctracted using *FFprobe*.
- The whole MP4 header (everything before the first `mdat` atom) is extracted in binary form.
- *ExifTool* and *FFprobe* data is merged into a single metadata dictionary.
- This dictionary is refactored to fix known issues, move data into proper tags and drop useless data. Also user is asked for missing/additional information which can be taken from stored location and lens presets.
- Dictionary with consolidated tag values for MKV container is build from metadata dictionary.
- Metadata dictionary is encoded into JSON file and with binary MP4 header is compressed into ZIP-archive.
- Tag dictionary is saved into XML file.

Insertion mode:
- User drops final MKV file(s) along with XML tag file(s) and any attachment files onto the script.
- Input files are grouped by first 8 characters in their filenames (parent directory must match too).
- For each group container, tags and attachment files are determined by their extensions and suffixes.
- Tags and attachments are inserted into container using *mkvpropedit* from *MKVToolNix*.

---

<a name="encoder"></a>
## encoder.py

A Python utility for automating encoding process using FFmpeg.

Encoding parameters are defined in encoder presets at the beginning of the script. Value of any argument can be defined as to be asked from the user at a runtime. Multiple arguments with multiple values can be defined. In this case the product of all combinations of argument values is added to the job queue. Also filename variables can be used in argument values. If output container is MKV, encoder arguments and version are added in it as global tags. Encoder arguments stored can be filtered via corresponding tuple so arguments containing irrelevant information or file paths can be excluded. 

### Workflow
- User drops file(s) to be encoded onto the script.
- User is asked the name of encoder preset to be used.
- Variable arguments values are asked for each file (if defined in a preset).
- Product of all combinations of specified arguments is added to the job queue.
- Encoding process is performed for each job in a queue.
- Metadata about encoding is inserted into final files (if container is MKV).

---

<a name="abav1-crfprobe"></a>
## abav1-crfprobe.py

A Python utility for getting sample-encode scores for multiple crf values using ab-av1 tool. 

You can drop a bunch of files onto the script, enter crf values you are interested in for each file and go mind your business. After script finishes it's job you get a report for each file containing scores for crfs you have selected.

### Workflow
- User drops file(s) to be sample-encoded onto the script.
- User is asked for crf values to be tested, sample number and sample duration for each file.
- Each crf value is sample-encoded using ab-av1.
- Report for each file containing score for each crf value is stored in a corresponding text file.

---

<a name="compare"></a>
## compare.avs

AviSynth script to compare several video files side-by-side while maintaining resolution of original file (output image is cropped accordingly).

Define files to be compared in the `files` array at the beginning of the script. Each file will be cropped and stacked side-by-side so that the resulting resolution will be the same as the single file resolution. If `diff_show` is set to `True`, the second row will appear (cropping files again) containing difference between the first file and every other one. If `diff_levels` is set to `True`, difference will be amplified be `Levels` to be more visible.