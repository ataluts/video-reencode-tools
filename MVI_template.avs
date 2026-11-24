# Define constants ============================================================================================================
type_video   = 0
type_audio   = 1
type_image   = 2
type_fill    = 3
type_unknown = -1
type_extensions = []
type_extensions = ArrayIns(type_extensions, ["3gp", "asf", "avi", "flv", "m2ts", "m4v", "mkv", "mov", "mp4", "mts", "ogv", "rmvb", "ts", "vob", "webm", "wmv"], type_video)
type_extensions = ArrayIns(type_extensions, ["aac", "ac3", "amr", "dts", "dtshd", "eac3", "flac", "m4a", "mka", "mp2", "mp3", "ogg", "opus", "pcm", "wav", "wma"], type_audio)
type_extensions = ArrayIns(type_extensions, ["bmp", "dds", "exr", "gif", "hdr", "jpg", "jpeg", "pbm", "pcx", "pgm", "png", "ppm", "psd", "tga", "tif", "tiff", "webp"], type_image)
align_bottomleft   = 1
align_bottomcenter = 2
align_bottomright  = 3
align_middleleft   = 4
align_middlecenter = 5
align_middleright  = 6
align_topleft      = 7
align_topcenter    = 8
align_topright     = 9

# Change these values only if you know what you are doing or there is no primary video/audio source
global None = -2147483648                   # signify absence of a value (like in python), use IsNone() function to check for this
global project_video_framerate  = None      # float
global project_audio_channels   = None      # int
global project_audio_samplerate = None      # int
global project_audio_format     = None      # string {8bit|16bit|24bit|32bit|float}

# User defined settings
prefetch_threads = None                     # threads argument for Prefetch(), use None for default one.
prefetch_frames  = None                     # frames  argument for Prefetch(), use None for default one.


# Define source files =========================================================================================================
# Format:
#   inputs = [<clip>, ...]
#   clip   = [<track:video>, <track:audio>] | <path:str> | None
#   track  = [<path:str>, <type:enum>, <params:str>] | [<path:str>, <type:enum>] | [<path:str>, <params:str>] | [<type:enum>, <params:str>] | <path:str>
# Use None as a clip to disable it and preserve per-clip arguments indexes at the same time. Use None as a track or its components to define their absence explicitly.
# Use track types from enum constants. If type for a track is not specified it is determined from file extension.
# Functions used: type_video - LWLibavVideoSource(), type_audio - LWLibavAudioSource(), type_image - ImageSource(), type_fill - BlankClip()
# They are called via Eval() so you can use functions/expressions in their params, for example for type_fill: length=SecToFrames(1.0), color_yuv=Color_RGBToYUV($000000, "709:f").
# To delay audio use 'delay' param for audio track with value in seconds.
inputs = []
inputs = ArrayAdd(inputs, "MVI_0000.MP4")
inputs_count = ArraySize(inputs) - 1


# Define filter parameters ====================================================================================================
# Filters are applied in the same order as their parameters are listed here (except convert_audio which is applied last). This is hardcoded, so there will be no effect when changing params order.
# Due to usage of Eval() function for most calls you can use functions/expressions as an argument values. Clip variable name at the moment of a call is 'c'.
# Set default filter parameters in the '*_default' variable and its overrides in '*_perclip' array for each clip. This array must be fully initialized to work properly, though can contain only empty strings.
# Some additional/special arguments are added to the parameters string which are stripped away before passing arguments to the filter. For example 'enabled'.
# Positional arguments can be defined by argument named 'positional' with value as is for a single argument and as an array for multiple arguments.
# If you need to add another filter into the pipeline add its code into the 'Regular pass' loop.

# Convert video [ConvertTo*] --------------------------------------------------------------------------------------------------
convert_video_default = """ enabled=false, format=YUV420, matrix="709:f" """ # format=* from ConvertTo* function (without quotes!)
convert_video_perclip = []
for (i = 0, inputs_count) { convert_video_perclip = ArrayAdd(convert_video_perclip, "") }
#convert_video_perclip = ArraySet(convert_video_perclip, """ enabled=true """, 0)

# Convert audio [ConvertToMono + MergeChannels + SSRC + Normalize + AmplifydB + ConvertAudioTo*] ------------------------------
# It is better to kill audio with 'channels=0' on encoding, otherwise it can hinder multithreading substantially
# Arguments: enabled=<bool>, format=* (from ConvertAudioTo* function without quotes!), samplerate=<int>, channels=<int>, normalize=<bool>, amplify_db=<float>
convert_audio_default = """ enabled=false, channels=1 """
convert_audio_perclip = []
for (i = 0, inputs_count) { convert_audio_perclip = ArrayAdd(convert_audio_perclip, "") }
#convert_audio_perclip = ArraySet(convert_audio_perclip, """ enabled=true """, 0)

# Stabilize [DePanEstimate + DePanStabilize] ----------------------------------------------------------------------------------
# If estimate is enabled the script will run in special single-threaded pass where only DePanEstimate will be queued and store its motion data in a log files.
# DePanStabilize uses motion data from a log files created by DePanEstimate. Do not specify log files in parameters because this is handled by the script.
# Extra arguments for DePanEstimate:
#   crop={int|[<left>,<top>,<width>,<height>]} - define area of a clip where motion will be estimated, either single value or array
# Extra arguments for DePanStabilize:
#   mirror={int|[<left/right>,<top/bottom>]|[<left>,<top>,<right>,<bottom>]} - single values from 0...15 use filter built-in mirror function, other single values or array value use MirrorEdges function
stab_estimate_default  = """ enabled=false, range=0, trust=4.0, dxmax=-1, dymax=-1, stab=1.0, zoommax=1.0, crop=[0, 0, 0, 0] """
stab_stabilize_default = """ enabled=false, cutoff=1.0, damping=1.0, initzoom=1.00, addzoom=false, prev=0, next=0, mirror=[RoundToMultiple(c.Width/16, 2, "ceil"), RoundToMultiple(c.Height/16, 2, "ceil")], blur=16, dxmax=RoundToMultiple(c.Width/16, 2, "ceil"), dymax=RoundToMultiple(c.Height/16, 2, "ceil"), rotmax=60.0, zoommax=1.0, subpixel=2, method=0 """
stab_estimate_perclip  = []
stab_stabilize_perclip = []
for (i = 0, inputs_count) { stab_estimate_perclip  = ArrayAdd(stab_estimate_perclip, "") }
for (i = 0, inputs_count) { stab_stabilize_perclip = ArrayAdd(stab_stabilize_perclip, "") }
#stab_stabilize_perclip = ArraySet(stab_stabilize_perclip, """ enabled=true """, 0)

# Crop [Crop] -----------------------------------------------------------------------------------------------------------------
# preview={true|false} - marks cropped area on the source image instead of actually cropping it
# pv_mode={"overlay"|"outline"|"all"} - selects marking mode: "overlay" - croppped-out area is overlayed with 'pv_overlay_color' and 'pv_overlay_opacity' between 0.0 and 1.0; "outline" - border is drawn around cropped-in area with 'pv_outline_color' and 'pv_outline_thickness' in pixels; "all" - all options together
crop_default = """ enabled=false, positional=[128, 72, -128, -72], preview=false, pv_mode="outline", pv_outline_color=color_yellow, pv_outline_thickness=2, pv_overlay_color=color_black, pv_overlay_opacity=0.5 """
crop_perclip = []
for (i = 0, inputs_count) { crop_perclip = ArrayAdd(crop_perclip, "") }
#crop_perclip = ArraySet(crop_perclip, """ enabled=true """, 0)

# Denoise [TemporalDegrain2] --------------------------------------------------------------------------------------------------
# Occasionally TD2 may refuse to work on certain inputs. In these cases try to slightly change resolution via Crop and it may solve the problem.
denoise_default = """ enabled=false, degrainTR=0, grainLevel=1, postFFT=3, postSigma=2.0, fftThreads=8, limitFFT=2 """
denoise_perclip = []
for (i = 0, inputs_count) { denoise_perclip = ArrayAdd(denoise_perclip, "") }
#denoise_perclip = ArraySet(denoise_perclip, """ enabled=true """, 0)

# Resize [Spline36Resize] -----------------------------------------------------------------------------------------------------
resize_default = """ enabled=true, positional=[1920, 1080] """
resize_perclip = []
for (i = 0, inputs_count) { resize_perclip = ArrayAdd(resize_perclip, "") }
#resize_perclip = ArraySet(resize_perclip, """  """, 0)

# White Balance [Color_WBToUV + ColorYUV] -------------------------------------------------------------------------------------
# Custom White Balance correction via Temperature and Tint values approximated to Adobe Camera RAW values
whitebalance_default = """ enabled=false, temp=-8.0, tint=8.0, matrix="709:f", affect_luma=true """
whitebalance_perclip = []
for (i = 0, inputs_count) { whitebalance_perclip = ArrayAdd(whitebalance_perclip, "") }
#whitebalance_perclip = ArraySet(whitebalance_perclip, """ enabled=true """, 0)

# Exposure [SmoothLevels] -----------------------------------------------------------------------------------------------------
smoothlevels_default = """ enabled=false, input_low=0, gamma=1.05, input_high=224, output_low=0, output_high=255, limiter=0, TVrange=false, Lmode=2, brightSTR=144, Ecurve=1 """
smoothlevels_perclip = []
for (i = 0, inputs_count) { smoothlevels_perclip = ArrayAdd(smoothlevels_perclip, "") }
#smoothlevels_perclip = ArraySet(smoothlevels_perclip, """ enabled=true """, 0)

# Color [SmoothTweak] ---------------------------------------------------------------------------------------------------------
smoothtweak_default = """ enabled=false, brightness=0, contrast=1.0, saturation=1.0, hue1=0, hue2=0, limiter=false, TVrange=false, Lmode=2, limitSTR=32, Ecurve=1 """
smoothtweak_perclip = []
for (i = 0, inputs_count) { smoothtweak_perclip = ArrayAdd(smoothtweak_perclip, "") }
#smoothtweak_perclip = ArraySet(smoothtweak_perclip, """ enabled=true """, 0)

# Color [ColorYUV] ------------------------------------------------------------------------------------------------------------
coloryuv_default = """ enabled=false, gain_y=0.0, off_y=0.0, gamma_y=1.0, cont_y=0.0, gain_u=0.0, off_u=0.0, gamma_u=0.0, cont_u=0.0, gain_v=0.0, off_v=0.0, gamma_v=0.0, cont_v=0.0, levels="", opt="", showyuv=false, analyze=false, autowhite=false, autogain=false, conditional=false, bits=8, showyuv_fullrange=false, f2c=false, condvarsuffix="" """
coloryuv_perclip = []
for (i = 0, inputs_count) { coloryuv_perclip = ArrayAdd(coloryuv_perclip, "") }
#coloryuv_perclip = ArraySet(coloryuv_perclip, """  """, 0)

# Sharpen [LSFmod]-------------------------------------------------------------------------------------------------------------
sharpen_default = """ enabled=false, strength=100, defaults="slow" """
sharpen_perclip = []
for (i = 0, inputs_count) { sharpen_perclip = ArrayAdd(sharpen_perclip, "") }
#sharpen_perclip = ArraySet(sharpen_perclip, """ enabled=true """, 0)

# Subtitle [Subtitle]----------------------------------------------------------------------------------------------------------
subtitle_default = """ enabled=false, positional=e"text", x=c.Width/2, y=c.Height/2, font="Arial", size=96, bold=true, italic=false, text_color=color_white, halo_color=color_black, align=align_middlecenter """
subtitle_perclip = []
for (i = 0, inputs_count) { subtitle_perclip = ArrayAdd(subtitle_perclip, [""]) }
#subtitle_set = []
#subtitle_set = ArrayAdd(subtitle_set, """ enabled=true, positional=e"text", first_frame=SecToFrames(1.0), last_frame=SecToFrames(2.0) """)
#subtitle_perclip = ArraySet(subtitle_perclip, subtitle_set, 0)

# Trim [Trim] -----------------------------------------------------------------------------------------------------------------
trim_default = """ enabled=false, positional=[0, 0] """
trim_perclip = []
for (i = 0, inputs_count) { trim_perclip = ArrayAdd(trim_perclip, "") }
#trim_perclip = ArraySet(trim_perclip, """ enabled=true, positional=[0, 0] """, 0)

# Fade [FadeIn + FadeOut] -----------------------------------------------------------------------------------------------------
# Arguments: in_* is passed to FadiIn(), out_* is passed to FadeOut() with prefix srtripped
fade_default = """ enabled=false, in_positional=SecToFrames(0.5), in_color_yuv=Color_RGBToYUV($000000, "709:f"), out_positional=SecToFrames(0.5), out_color_yuv=Color_RGBToYUV($000000, "709:f") """
fade_perclip = []
for (i = 0, inputs_count) { fade_perclip = ArrayAdd(fade_perclip, "") }
#fade_perclip = ArraySet(fade_perclip, """ enabled=true """, 0)


# Define preview parameters ===================================================================================================
# Compare [Crop + StackHorizontal + StackVertical + Subtract + Levels] --------------------------------------------------------
# Displays two versions of the image - before and after the filters
# mode={"split"|"stack"|"crop"} - select comparison mode: "split" - single full image is split in half; "stack" - both full images are displayed as is; "crop" - identical areas of both images are displayed but cropped to maintain original size
# orientation={"h"|"v"} - orientation in which images are stacked
# align={1...9} - crop alignment, value is the same as in Subtitle
# swap={true|false} - swap images sides
# diff={true|false} - show difference between images
# diff_levels=[input_low,input_high,output_low,output_high] - arguments for Levels filter to make difference more obvious
compare = """ enabled=false, mode="split", orientation="h", align=align_middlecenter, swap=false, diff=false, diff_levels=[64, 192, 0, 255] """

# Info [ScriptClip + Subtitle]-------------------------------------------------------------------------------------------------
# Displays clip index, timestamp and frame number
info_default = """ enabled=false, x=0, y=0, font="Consolas", size=28, bold=false, italic=false, text_color=color_yellow, halo_color=color_black, align=align_topleft """
info_perclip = []
for (i = 0, inputs_count) { info_perclip = ArrayAdd(info_perclip, "") }
#info_perclip = ArraySet(info_perclip, """  """, 0)

# Range fix [ColorYUV + SubTitle] -----------------------------------------------------------------------------------------------
# Convert levels from PC to TV range.
# This is a workaround to correctly display full range image in those players which assume limited range by default.
# Enable only for preview in a player, ffmpeg determines range correctly.
rangefix = """ enabled=false, warning=true, text="RANGE", x=-5, y=0, font="Consolas", size=28, bold=false, italic=false, text_color=color_yellow, halo_color=color_black, align=align_topright """


# Set filter modes ============================================================================================================
# Multithreading
SetFilterMTMode("TemporalDegrain2", MT_MULTI_INSTANCE)
SetFilterMTMode("SmoothLevels", MT_NICE_FILTER)
SetFilterMTMode("SmoothTweak", MT_NICE_FILTER)
SetFilterMTMode("LSFmod", MT_MULTI_INSTANCE)

# Frame properties (fix frame properties loss)
SetFilterPropPassthrough("DePanStabilize")
SetFilterPropPassthrough("FastBlur")


# Custom functions ============================================================================================================
# Check that value is None
function IsNone(val value) {
    if(IsInt(value) && value == None) { return true }
    return false
}

# Return the index of the first element in array which matches or -1 if not found
function Array_IndexOf(val array, val value) {
    for (i = 0, ArraySize(array) - 1) {
        if (array[i] == value) {
            return i
        }
    }
    return -1
}

# Get extension from file path
function Path_GetExtension(string path) {
    lastDot = 0
    for (i = 1, StrLen(path)) {
        char = MidStr(path, i, 1)
        if (char == "." || char == "/" || char == "\\") {
            lastDot = char == "." ? i : 0
        }
    }
    return lastDot > 0 ? LCase(MidStr(path, lastDot + 1)) : ""
}

# Get type from extension
function Path_GetExtType(string ext, val extensions) {
    for(i = 0, ArraySize(extensions) - 1) {
        for(j = 0, ArraySize(extensions[i]) - 1) {
            if(ext == extensions[i][j]) {
                return i
            }
        }
    }
    return -1
}

# Convert object to string
function ToString(val obj) {
    if(IsNone(obj))   { return "None" }
    if(IsString(obj)) { return Chr(34) + obj + Chr(34) }
    
    result = ""
    if(IsArray(obj)) {
        result = result + "["
        array_size = ArraySize(obj)
        if(array_size > 0) {
            for(i = 0, ArraySize(obj) - 1) {
                result = result + ToString(obj[i]) + ", "
            }
            result = LeftStr(result, StrLen(result) - 2)
        }
        result = result + "]"
    } else {
        return String(obj)
    }
    return result
}

# Remove surrounding quotes from string
function String_Unquote(string s) {
    length = StrLen(s)
    if (length >= 2) {
        first_char = LeftStr(s, 1)
        last_char = RightStr(s, 1)
        if (first_char == Chr(34) && last_char == Chr(34)) {
            s = MidStr(s, 2, length - 2)
        }
    }
    return s
}

# Convert string to bool
function String_ToBool(string s) {
    s = LCase(TrimAll(s))
    if(s == "true" || s == "1" || s == "yes") {
        return true
    } else if(s == "false" || s == "0" || s == "no") {
        return false
    } else {
        Assert(false, "Invalid boolean string: " + s)
    }
}

# Convert string to integer
function String_ToInt(string s) {
    s = TrimAll(s)
    if (LeftStr(s, 1) == "$") {
        return HexValue(MidStr(s, 2))
    } else if (LCase(LeftStr(s, 6)) == "color_") {
        return Eval(s)
    }
    return Int(Value(s))
}

# Convert string to float
function String_ToFloat(string s) {
    return Float(Value(s))
}

# Parse argument value into a scalar or an array
function Argument_Parse_Value(string value) {
    if (Findstr(value, ";") == 0) {
        return value
    }
    result = []
    start = 1
    for (i = 1, StrLen(value) + 1) {
        if (i > StrLen(value) || MidStr(value, i, 1) == ";") {
            item = TrimAll(MidStr(value, start, i - start))
            Assert(item != "", "Invalid argument value: " + value)
            result = ArrayAdd(result, item)
            start = i + 1
        }
    }
    return result
}

# Parse "name=value" into [name, value]
function Argument_Parse(string s) {
    p = Findstr(s, "=")
    Assert(p > 1, "Invalid function argument: " + s)

    name = TrimAll(LeftStr(s, p - 1))
    value = TrimAll(MidStr(s, p + 1))

    if (StrLen(value) >= 2 && LeftStr(value, 1) == "[" && RightStr(value, 1) == "]") {
        array = []
        s = MidStr(value, 2, StrLen(value) - 2)
        start = 1
        inQuotes = false
        depth = 0

        for (i = 1, StrLen(s)) {
            char = MidStr(s, i, 1)

            if (char == Chr(34)) {
                inQuotes = !inQuotes
            } else if (!inQuotes) {
                if (char == "(") {
                    depth = depth + 1
                } else if (char == ")") {
                    depth = depth - 1
                    Assert(depth >= 0, "Unexpected closing parenthesis in array: " + value)
                } else if (char == "," && depth == 0) {
                    item = TrimAll(MidStr(s, start, i - start))
                    if (item != "") {
                        array = ArrayAdd(array, item)
                    }
                    start = i + 1
                }
            }
        }

        item = TrimAll(MidStr(s, start, StrLen(s) - start + 1))
        if (item != "") {
            array = ArrayAdd(array, item)
        }

        Assert(!inQuotes, "Unclosed quotation mark in array: " + value)
        Assert(depth == 0, "Unclosed parenthesis in array: " + value)

        value = array
    }

    return [name, value]
}

# Parse arguments string "name0=value0, name1=value1, ..." into arguments array [[name0, value0], [name1, value1], ...]
function Arguments_Parse(string s) {
    result = []
    start = 1
    inQuotes = false
    depth = 0
    inArray = false

    for (i = 1, StrLen(s)) {
        char = MidStr(s, i, 1)

        if (char == Chr(34)) {
            inQuotes = !inQuotes
        } else if (!inQuotes) {
            if (char == "[") {
                Assert(!inArray, "Nested arrays are not supported: " + s)
                inArray = true
            } else if (char == "]") {
                Assert(inArray, "Unexpected closing bracket in settings: " + s)
                inArray = false
            } else if (char == "(") {
                depth = depth + 1
            } else if (char == ")") {
                depth = depth - 1
                Assert(depth >= 0, "Unexpected closing parenthesis in settings: " + s)
            } else if (char == "," && depth == 0 && !inArray) {
                item = TrimAll(MidStr(s, start, i - start))
                if (item != "") {
                    result = ArrayAdd(result, Argument_Parse(item))
                }
                start = i + 1
            }
        }
    }

    item = TrimAll(MidStr(s, start, StrLen(s) - start + 1))
    if (item != "") {
        result = ArrayAdd(result, Argument_Parse(item))
    }

    Assert(!inQuotes, "Unclosed quotation mark in settings: " + s)
    Assert(!inArray, "Unclosed array bracket in settings: " + s)
    Assert(depth == 0, "Unclosed parenthesis in settings: " + s)

    return result
}

# Build function arguments string from an array of [name, value]
function Arguments_Build(val arguments) {
    result = ""
    for (i = 0, ArraySize(arguments) - 1) {
        name = arguments[i][0]
        value = arguments[i][1]
        if (LCase(name) == "positional") {
            if (IsArray(value)) {
                for (j = 0, ArraySize(value) - 1) {
                    result = result + (result == "" ? "" : ", ") + value[j]
                }
            } else {
                result = result + (result == "" ? "" : ", ") + value
            }
        } else {
            result = result + (result == "" ? "" : ", ") + name + "=" + value
        }
    }
    return result
}

# Set argument value in arguments array, if argument is absent it is appended
function Argument_Set(val arguments, string name, val value) {
    found = false
    for (i = 0, ArraySize(arguments) - 1) {
        if (LCase(arguments[i][0]) == LCase(name)) {
            arguments = ArraySet(arguments, [name, value], i)
            found = true
            break
        }
    }
    if (!found) {
        arguments = ArrayAdd(arguments, [name, value])
    }

    return arguments
}

# Get argument value from arguments array, if argument is absent default value is returned
function Argument_Get(val arguments, string name, val default) {
    for (i = 0, ArraySize(arguments) - 1) {
        if (LCase(arguments[i][0]) == LCase(name)) {
            return arguments[i][1]
        }
    }
    return default
}

# Get argument value from arguments array and remove it from the array, if argument is absent default value is returned
function Argument_Pop(val arguments, string name, val default) {
    value = default
    for (i = 0, ArraySize(arguments) - 1) {
        if (LCase(arguments[i][0]) == LCase(name)) {
            value = arguments[i][1]
            arguments = ArrayDel(arguments, i)
            break
        }
    }
    return [arguments, value]
}

# Delete argument from arguments array
function Argument_Delete(val arguments, string name) {
    for (i = 0, ArraySize(arguments) - 1) {
        if (LCase(arguments[i][0]) == LCase(name)) {
            arguments = ArrayDel(arguments, i)
            break
        }
    }
    return arguments
}

# Check if arguments block is enabled
function Arguments_IsEnabled(val arguments, string "name", bool "default") {
    name = Default(name, "enabled")
    default = Default(default, false)
    return String_ToBool(Argument_Get(arguments, name, String(default)))
}

# Merge default arguments with override ones
function Arguments_Merge(val defaults, val overrides) {
    result = defaults
    for (i = 0, ArraySize(overrides) - 1) {
        result = Argument_Set(result, overrides[i][0], overrides[i][1])
    }

    return result
}

# Resolve defaults and per clip string arguments line into per clip arguments array
function Arguments_Resolve(string default, val "perclip") {
    defaultArgs = Arguments_Parse(default)
    if (!Defined(perclip)) { return defaultArgs }
    if (IsString(perclip)) { return Arguments_Merge(defaultArgs, Arguments_Parse(perclip)) }
    result = []
    for (i = 0, ArraySize(perclip) - 1) {
        result = ArrayAdd(result, Arguments_Resolve(default, perclip[i]))
    }
    return result
}

# Execute function with merged default and override arguments
function Function_Execute(clip c, string functionName, val arguments, bool "force") {
    # Extract enabled argument
    result = Argument_Pop(arguments, "enabled", "false")
    arguments = result[0]
    enabled = String_ToBool(result[1])
    
    force = Default(force, false)
    if (force) { enabled = true }

    if (enabled) {
        args = Arguments_Build(arguments)
        return Eval(functionName + "(c" + (args == "" ? "" : ", " + args) + ")")
    } else {
        return c
    }
}

# Get allowed width/height modulo for a clip
function Clip_SizeModulo(clip c) {
    width = 1
    height = 1
    if (c.IsYV12() || c.IsYV16() || c.IsYUY2()) { width = 2 }
    if (c.IsYV411()) { width = 4 }
    if (c.IsYV12()) { height = 2 }
    return [width, height]
}

# Mirrors edges of a clip, negative edge values imply percentage of a clip
function MirrorEdges(clip c, int "left", int "top", int "right", int "bottom", float "blur", float "threads") {
    left    = Default(left, -10)
    right   = Default(right, left)
    top     = Default(top, left)
    bottom  = Default(bottom, top)
    blur    = Default(blur, 0)
    threads = Default(threads, -1)
    Assert (left >= -100 && left <= c.Width && right >= -100 && right <= c.Width && top >= -100 && top <= c.Height && bottom >= -100 && bottom <= c.Height,  "Invalid edge size!")
    Assert (blur >= 0,  "Invalid blur radius!")
    
    if(left   < 0) { left   = (-left   * c.Width)  / 100 }
    if(right  < 0) { right  = (-right  * c.Width)  / 100 }
    if(top    < 0) { top    = (-top    * c.Height) / 100 }
    if(bottom < 0) { bottom = (-bottom * c.Height) / 100 }
    
    horizontal = c
    if(left > 0) {
        c_left = c.Crop(0, 0, left, 0).FlipHorizontal()
        horizontal = StackHorizontal(c_left, horizontal)
        if(blur > 0) { c_left = c_left.FastBlur(blur, threads=threads) }
    }
    if(right > 0) {
        c_right = c.Crop(c.Width - right, 0, right, 0).FlipHorizontal()
        horizontal = StackHorizontal(horizontal, c_right)
        if(blur > 0) { c_right = c_right.FastBlur(blur, threads=threads) }
    }
    if(top > 0) {
        c_top = horizontal.Crop(0, 0, 0, top).FlipVertical()
        if(blur > 0) { c_top = c_top.FastBlur(blur, threads=threads) }
    }
    if(bottom > 0) {
        c_bottom = horizontal.Crop(0, c.Height - bottom, 0, bottom).FlipVertical()
        if(blur > 0) { c_bottom = c_bottom.FastBlur(blur, threads=threads) }
    }
    
    result = c
    if(left   > 0) { result = StackHorizontal(c_left, result)  }
    if(right  > 0) { result = StackHorizontal(result, c_right) }
    if(top    > 0) { result = StackVertical(c_top, result)     }
    if(bottom > 0) { result = StackVertical(result, c_bottom)  }

    return result
}

# Preview crop area
function Crop_Preview(clip c, int left, int top, int width, int height, string "mode", int "outline_color", int "outline_thickness", int "overlay_color", float "overlay_opacity") {
    mode = Default(mode, "overlay")
    outline_color = Default(outline_color, color_yellow)
    outline_thickness = Default(outline_thickness, 2)
    overlay_color = Default(overlay_color, color_black)
    overlay_opacity = Default(overlay_opacity, 0.5)

    # Resolve dimensions
    clip_width  = c.Width
    clip_height = c.Height
    crop_left   = left
    crop_top    = top
    crop_width  = (width > 0) ? width : clip_width - crop_left + width
    crop_height = (height > 0) ? height : clip_height - crop_top + height
    crop_right  = clip_width - crop_left - crop_width
    crop_bottom = clip_height - crop_top - crop_height

    # Validate parameters
    Assert(mode == "outline" || mode == "overlay" || mode == "all", "Crop_Preview: invalid mode")
    Assert(outline_thickness > 0, "Crop_Preview: outline_thickness must be positive")
    Assert(overlay_opacity >= 0.0 && overlay_opacity <= 1.0, "Crop_Preview: overlay_opacity must be between 0 and 1")
    Assert(crop_left >= 0 && crop_top >= 0 && crop_right >= 0 && crop_bottom >= 0, "Crop_Preview: crop offsets must be non-negative")
    Assert(crop_width > 0 && crop_height > 0, "Crop_Preview: resulting dimensions must be positive")
    Assert(crop_left + crop_width <= clip_width && crop_top + crop_height <= clip_height, "Crop_Preview: crop rectangle exceeds source dimensions")

    # Validate chroma subsampling restrictions
    subsample_mod = Clip_SizeModulo(c)
    subsample_mod_width = subsample_mod[0]
    subsample_mod_height = subsample_mod[1]
    Assert(crop_left % subsample_mod_width == 0 && crop_width % subsample_mod_width == 0, "Crop_Preview: horizontal crop coordinates and dimensions violate chroma subsampling")
    Assert(crop_top % subsample_mod_height == 0 && crop_height % subsample_mod_height == 0, "Crop_Preview: vertical crop coordinates and dimensions violate chroma subsampling")

    # Validate outline alignment
    Assert(outline_thickness % subsample_mod_width == 0 && outline_thickness % subsample_mod_height == 0, "Crop_Preview: outline_thickness violates chroma subsampling")

    result = c

    # Darken everything outside crop area
    if (mode == "overlay" || mode == "all") {
        overlay_layer = BlankClip(c, color=overlay_color)
        overlay_mask = BlankClip(c, pixel_type="Y8", color=$000000)
        overlay_mask = Letterbox(overlay_mask, crop_top, crop_bottom, crop_left, crop_right, color=$FFFFFF)
        overlay_mask = ColorYUV(overlay_mask, levels="TV->PC")
        result = Overlay(result, overlay_layer, mask=overlay_mask, opacity=overlay_opacity, use444=false)
    }

    # Draw outline outside crop area
    if (mode == "outline" || mode == "all") {
        outline_width = crop_width + 2 * outline_thickness
        outline_height = crop_height + 2 * outline_thickness
        outline_layer = BlankClip(c, width=outline_width, height=outline_height, color=outline_color)
        outline_mask = BlankClip(c, width=outline_width, height=outline_height, pixel_type="Y8", color=$000000)
        outline_mask = Letterbox(outline_mask, outline_thickness, outline_thickness, outline_thickness, outline_thickness, color=$FFFFFF)
        outline_mask = ColorYUV(outline_mask, levels="TV->PC")
        result = Overlay(result, outline_layer, x=crop_left-outline_thickness, y=crop_top-outline_thickness, mask=outline_mask, use444=false)
    }

    return result
}

# Convert RGB color into YUV color with specified matrix
function Color_RGBToYUV(int color, string matrix) {
    r = (color / 65536) % 256
    g = (color / 256) % 256
    b = color % 256

    matrix = LCase(matrix)
    p = FindStr(matrix, ":")
    range = p > 0 ? MidStr(matrix, p + 1) : "auto"
    matrix = p > 0 ? LeftStr(matrix, p - 1) : matrix

    if (matrix == "709") {
        kr = 0.2126
        kb = 0.0722
    } else if (matrix == "470bg" || matrix == "601" || matrix == "170m") {
        kr = 0.299
        kb = 0.114
    } else if (matrix == "240m") {
        kr = 0.212
        kb = 0.087
    } else if (matrix == "2020" || matrix == "2020ncl" || matrix == "2020cl") {
        kr = 0.2627
        kb = 0.0593
    } else {
        Assert(false, "Unsupported color matrix: " + matrix)
    }

    kg = 1.0 - kr - kb
    y = kr * r + kg * g + kb * b
    u = (b - y) / (2.0 * (1.0 - kb)) + 128
    v = (r - y) / (2.0 * (1.0 - kr)) + 128

    if (range == "l" || range == "limited") {
        y = 16 + y * 219 / 255
        u = 128 + (u - 128) * 224 / 255
        v = 128 + (v - 128) * 224 / 255
    } else if (range != "f" && range != "full" && range != "auto" && range != "same") {
        Assert(false, "Unsupported color range: " + range)
    }

    y = Max(0, Min(255, Round(y)))
    u = Max(0, Min(255, Round(u)))
    v = Max(0, Min(255, Round(v)))

    return y * 65536 + u * 256 + v
}

# Convert Temperature and Tint values (approximated to Adobe Camera RAW) to YUV offset for ColorYUV()
# temp: -Blue / +Yellow [-100 ... +100]; tint: -Green / +Magenta  [-100 ... +100];
function Color_WBToUV(float "temp", float "tint", string "matrix") {
    temp = Default(temp, 0.0)
    tint = Default(tint, 0.0)
    matrix = Default(matrix, "709:f")
    Assert(temp >= -100.0 && temp <= 100.0, "Temperature must be in range -100 ... +100")
    Assert(tint >= -100.0 && tint <= 100.0, "Tint must be in range -100 ... +100")

    # LUT table from Adobe Camera RAW (at RGB=[86,86,86])
    wb_lut_ref = 86.0
    wb_lut = [ \
        [-100,0,82,129,254], [-95,0,66,125,249], [-90,0,50,120,243], [-85,0,33,117,236], [-80,0,16,114,228], [-75,0,4,111,218], [-70,0,3,109,208], [-65,0,9,107,198], [-60,0,21,105,188], [-55,0,32,103,178], [-50,0,42,101,167], [-45,0,50,99,156], [-40,0,56,98,147], [-35,0,62,96,137], [-30,0,68,94,128], [-25,0,72,93,119], [-20,0,76,91,112], [-18,0,77,90,108], [-16,0,78,90,106], [-14,0,79,89,103], [-12,0,80,89,100], [-10,0,81,88,98], [-8,0,82,88,95], [-6,0,83,87,93], [-5,0,84,87,92], [-4,0,84,87,90], [-3,0,85,87,89], [-2,0,85,86,88], [-1,0,86,86,87], \
        [0,0,86,86,86], [1,0,87,87,86], [2,0,89,88,86], [3,0,90,88,86], [4,0,91,89,85], [5,0,93,90,85], [6,0,94,91,85], [8,0,97,92,85], [10,0,100,94,85], [12,0,102,95,84], [14,0,105,97,84], [16,0,108,98,84], [18,0,110,100,83], [20,0,113,101,83], [25,0,119,105,82], [30,0,126,109,82], [35,0,132,112,81], [40,0,138,116,80], [45,0,145,120,79], [50,0,150,123,78], [55,0,156,126,77], [60,0,161,129,76], [65,0,166,132,75], [70,0,170,135,74], [75,0,174,138,73], [80,0,178,140,73], [85,0,182,142,72], [90,0,185,144,71], [95,0,188,146,71], [100,0,190,147,70], \
        [0,-100,48,150,75], [0,-95,58,144,76], [0,-90,66,139,77], [0,-85,71,134,78], [0,-80,75,129,79], [0,-75,78,125,80], [0,-70,81,121,81], [0,-65,83,117,81], [0,-60,84,114,82], [0,-55,85,110,82], [0,-50,86,107,83], [0,-45,86,104,83], [0,-40,87,102,84], [0,-35,87,99,84], [0,-30,87,97,84], [0,-25,87,95,85], [0,-20,87,93,85], [0,-15,87,91,85], [0,-10,86,89,86], [0,-5,86,88,86], \
        [0,5,87,86,87], [0,10,88,86,89], [0,15,89,85,91], [0,20,90,85,93], [0,25,92,85,95], [0,30,93,85,97], [0,35,95,84,100], [0,40,96,84,103], [0,45,98,84,106], [0,50,99,83,110], [0,55,101,83,113], [0,60,103,83,118], [0,65,105,82,122], [0,70,106,82,128], [0,75,108,81,133], [0,80,110,80,140], [0,85,112,79,147], [0,90,113,78,154], [0,95,115,78,163], [0,100,116,77,172], \
        [-100,-100,0,167,106], [-100,-80,0,155,130], [-100,-65,0,149,152], [-100,-50,0,142,177], [-100,-35,0,134,202], [-100,-20,0,128,228], [-100,-10,40,127,243], [-100,-5,65,128,248], [-100,5,84,129,254], [-100,10,73,127,249], [-100,20,0,128,177], [-100,35,47,126,0], [-100,50,55,123,0], [-100,65,81,119,0], [-100,80,66,115,0], [-100,100,72,109,0], \
        [-80,-100,0,153,96], [-80,-80,0,141,117], [-80,-65,0,135,134], [-80,-50,0,130,155], [-80,-35,0,124,178], [-80,-20,0,118,200], [-80,-10,0,116,214], [-80,-5,0,115,221], [-80,5,35,114,234], [-80,10,51,114,241], [-80,20,76,115,252], [-80,35,22,112,177], [-80,50,72,110,0], [-80,65,75,106,0], [-80,80,78,102,0], [-80,100,81,87,0], \
        [-65,-100,0,144,88], [-65,-80,0,132,106], [-65,-65,0,126,121], [-65,-50,0,121,138], [-65,-35,0,117,157], [-65,-20,0,112,175], [-65,-10,0,109,187], [-65,-5,0,108,193], [-65,5,19,106,204], [-65,10,27,105,210], [-65,20,43,103,226], [-65,35,73,105,251], [-65,50,69,102,104], [-65,65,81,98,0], [-65,80,83,94,0], [-65,100,85,89,0], \
        [-50,-100,0,138,81], [-50,-80,0,125,96], [-50,-65,25,118,108], [-50,-50,35,113,120], [-50,-35,38,109,135], [-50,-20,40,106,149], [-50,-10,41,103,158], [-50,-5,42,102,162], [-50,5,43,100,171], [-50,10,44,99,176], [-50,20,46,97,188], [-50,35,52,93,213], [-50,50,71,94,249], [-50,65,75,89,152], [-50,80,86,87,0], [-50,100,92,86,0], \
        [-35,-100,0,140,78], [-35,-80,33,121,87], [-35,-65,49,113,96], [-35,-50,56,108,105], [-35,-35,60,103,115], [-35,-20,61,100,125], [-35,-10,62,98,131], [-35,-5,62,97,134], [-35,5,62,95,140], [-35,10,63,94,143], [-35,20,63,92,152], [-35,35,63,88,169], [-35,50,64,83,194], [-35,65,70,83,233], [-35,80,78,83,234], [-35,100,100,86,0], \
        [-20,-100,9,144,77], [-20,-80,53,121,81], [-20,-65,62,109,85], [-20,-50,68,103,92], [-20,-35,72,98,98], [-20,-20,74,95,104], [-20,-10,75,93,108], [-20,-5,75,92,110], [-20,5,76,90,113], [-20,10,76,89,115], [-20,20,77,87,120], [-20,35,79,85,132], [-20,50,82,83,151], [-20,65,85,81,177], [-20,80,87,80,212], [-20,100,93,87,249], \
        [-10,-100,34,147,76], [-10,-80,65,125,80], [-10,-65,72,112,82], [-10,-50,74,101,84], [-10,-35,77,96,88], [-10,-20,80,92,93], [-10,-10,81,90,95], [-10,-5,81,89,97], [-10,5,82,87,99], [-10,10,82,87,100], [-10,20,84,86,105], [-10,35,88,85,114], [-10,50,92,83,128], [-10,65,96,82,146], [-10,80,100,79,172], [-10,100,101,79,219], \
        [-5,-100,41,148,75], [-5,-80,70,127,80], [-5,-65,77,115,82], [-5,-50,80,104,83], [-5,-35,81,96,85], [-5,-20,82,91,87], [-5,-10,83,89,90], [-5,-5,83,88,91], [-5,5,84,86,92], [-5,10,85,86,94], [-5,20,87,85,98], [-5,35,91,85,107], [-5,50,96,83,118], [-5,65,101,82,133], [-5,80,105,80,154], [-5,100,109,77,193], \
        [5,-100,53,152,74], [5,-80,80,132,78], [5,-65,88,120,81], [5,-50,91,110,82], [5,-35,93,102,83], [5,-20,93,96,84], [5,-10,93,93,85], [5,-5,93,91,85], [5,5,93,89,86], [5,10,92,87,86], [5,20,93,85,88], [5,35,98,84,94], [5,50,102,83,102], [5,65,108,82,113], [5,80,114,81,127], [5,100,122,77,153], \
        [10,-100,58,153,74], [10,-80,85,134,78], [10,-65,93,123,80], [10,-50,97,113,82], [10,-35,99,106,83], [10,-20,99,100,84], [10,-10,100,96,84], [10,-5,100,95,84], [10,5,99,92,85], [10,10,99,91,85], [10,20,99,88,85], [10,35,101,84,88], [10,50,106,83,95], [10,65,111,82,104], [10,80,117,81,116], [10,100,126,78,137], \
        [20,-100,66,157,72], [20,-80,93,139,76], [20,-65,102,128,79], [20,-50,107,120,80], [20,-35,110,112,81], [20,-20,112,107,82], [20,-10,112,104,83], [20,-5,113,102,83], [20,5,113,100,83], [20,10,113,99,84], [20,20,113,96,84], [20,35,114,91,85], [20,50,113,85,85], [20,65,117,82,90], [20,80,124,80,99], [20,100,133,78,113], \
        [35,-100,76,163,71], [35,-80,105,147,74], [35,-65,116,137,76], [35,-50,122,129,78], [35,-35,127,122,79], [35,-20,130,117,80], [35,-10,131,115,80], [35,-5,132,113,81], [35,5,133,111,81], [35,10,133,110,81], [35,20,134,108,81], [35,35,136,103,82], [35,50,138,98,83], [35,65,139,92,83], [35,80,140,85,84], [35,100,144,78,88], \
        [50,-100,84,169,69], [50,-80,115,155,72], [50,-65,128,146,74], [50,-50,136,138,75], [50,-35,142,132,77], [50,-20,147,128,77], [50,-10,149,125,78], [50,-5,150,124,78], [50,5,151,122,78], [50,10,152,121,78], [50,20,154,119,78], [50,35,157,114,79], [50,50,161,110,79], [50,65,164,104,80], [50,80,167,98,81], [50,100,171,89,82], \
        [65,-100,90,175,67], [65,-80,123,162,70], [65,-65,138,154,72], [65,-50,148,147,73], [65,-35,155,141,74], [65,-20,161,137,75], [65,-10,164,134,75], [65,-5,165,133,75], [65,5,167,131,75], [65,10,168,130,75], [65,20,171,128,75], [65,35,175,124,76], [65,50,179,119,76], [65,65,184,114,77], [65,80,189,108,77], [65,100,196,100,78], \
        [80,-100,95,180,65], [80,-80,130,168,68], [80,-65,146,160,69], [80,-50,158,154,71], [80,-35,166,148,72], [80,-20,172,144,72], [80,-10,176,142,72], [80,-5,177,141,73], [80,5,180,139,73], [80,10,181,138,73], [80,20,184,136,73], [80,35,189,132,73], [80,50,194,127,74], [80,65,200,122,74], [80,80,206,116,75], [80,100,215,108,76], \
        [100,-100,99,186,63], [100,-80,137,175,65], [100,-65,154,167,67], [100,-50,167,161,68], [100,-35,176,156,69], [100,-20,183,152,70], [100,-10,187,149,70], [100,-5,189,148,70], [100,5,192,146,70], [100,10,193,145,70], [100,20,197,143,70], [100,35,202,139,71], [100,50,208,134,71], [100,65,215,129,72], [100,80,222,124,73], [100,100,233,115,74] \
    ]

    # Determine color matrix
    matrix = LCase(matrix)
    p = FindStr(matrix, ":")
    range = p > 0 ? MidStr(matrix, p + 1) : "auto"
    matrix = p > 0 ? LeftStr(matrix, p - 1) : matrix
    if (matrix == "709") {
        kr = 0.2126
        kb = 0.0722
    } else if (matrix == "470bg" || matrix == "601" || matrix == "170m") {
        kr = 0.299
        kb = 0.114
    } else if (matrix == "240m") {
        kr = 0.212
        kb = 0.087
    } else if (matrix == "2020" || matrix == "2020ncl") {
        kr = 0.2627
        kb = 0.0593
    } else {
        Assert(false, "Unsupported color matrix: " + matrix)
    }

    # Determine color range
    yblack = 0.0
    yscale = 1.0
    cscale = 1.0
    if (range == "l" || range == "limited") {
        yblack = 16.0
        yscale = 219.0 / 255.0
        cscale = 224.0 / 255.0
    } else if (range != "f" && range != "full" && range != "auto" && range != "same") {
        Assert(false, "Unsupported color range: " + range)
    }

    # Interpolation on the Temperature axis: PCHIP
    if (tint == 0.0) {
        xs = []
        ys_r = []
        ys_g = []
        ys_b = []
        for (i = 0, ArraySize(wb_lut) - 1) {
            if (wb_lut[i, 1] == 0.0) {
                xs = ArrayAdd(xs, wb_lut[i, 0])
                ys_r = ArrayAdd(ys_r, wb_lut[i, 2])
                ys_g = ArrayAdd(ys_g, wb_lut[i, 3])
                ys_b = ArrayAdd(ys_b, wb_lut[i, 4])
            }
        }
        n = ArraySize(xs)
        Assert(n >= 3, "Temperature axis requires at least 3 LUT points")
        x = Max(xs[0], Min(xs[n - 1], temp))
        rgb = []
        for (channel = 0, 2) {
            ys = channel == 0 ? ys_r : channel == 1 ? ys_g : ys_b
            if (x <= xs[0]) {
                yout = ys[0]
            } else if (x >= xs[n - 1]) {
                yout = ys[n - 1]
            } else {
                h = []
                delta = []
                for (i = 0, n - 2) {
                    hi = xs[i + 1] - xs[i]
                    h = ArrayAdd(h, hi)
                    delta = ArrayAdd(delta, (ys[i + 1] - ys[i]) / hi)
                }
                d0 = ((2.0 * h[0] + h[1]) * delta[0] - h[0] * delta[1]) / (h[0] + h[1])
                if (d0 * delta[0] <= 0.0) {
                    d0 = 0.0
                } else if (delta[0] * delta[1] < 0.0 && Abs(d0) > Abs(3.0 * delta[0])) {
                    d0 = 3.0 * delta[0]
                }
                last = n - 2
                dn = ((2.0 * h[last] + h[last - 1]) * delta[last] - h[last] * delta[last - 1]) / (h[last] + h[last - 1])
                if (dn * delta[last] <= 0.0) {
                    dn = 0.0
                } else if (delta[last] * delta[last - 1] < 0.0 && Abs(dn) > Abs(3.0 * delta[last])) {
                    dn = 3.0 * delta[last]
                }
                d = [d0]
                for (i = 1, n - 2) {
                    if (delta[i - 1] * delta[i] <= 0.0) {
                        di = 0.0
                    } else {
                        w1 = 2.0 * h[i] + h[i - 1]
                        w2 = h[i] + 2.0 * h[i - 1]
                        di = (w1 + w2) / (w1 / delta[i - 1] + w2 / delta[i])
                    }
                    d = ArrayAdd(d, di)
                }
                d = ArrayAdd(d, dn)
                k = 0
                for (i = 0, n - 2) {
                    if (x >= xs[i] && x <= xs[i + 1]) {
                        k = i
                    }
                }
                hi = h[k]
                t = (x - xs[k]) / hi
                t2 = t * t
                t3 = t2 * t
                h00 = 2.0 * t3 - 3.0 * t2 + 1.0
                h10 = t3 - 2.0 * t2 + t
                h01 = -2.0 * t3 + 3.0 * t2
                h11 = t3 - t2
                yout = h00 * ys[k] + h10 * hi * d[k] + h01 * ys[k + 1] + h11 * hi * d[k + 1]
            }
            rgb = ArrayAdd(rgb, yout)
        }
        r = rgb[0]
        g = rgb[1]
        b = rgb[2]

    # Interpolation on the Tint axis: PCHIP
    } else if (temp == 0.0) {
        xs = []
        ys_r = []
        ys_g = []
        ys_b = []
        for (i = 0, ArraySize(wb_lut) - 1) {
            if (wb_lut[i, 0] == 0.0) {
                xs = ArrayAdd(xs, wb_lut[i, 1])
                ys_r = ArrayAdd(ys_r, wb_lut[i, 2])
                ys_g = ArrayAdd(ys_g, wb_lut[i, 3])
                ys_b = ArrayAdd(ys_b, wb_lut[i, 4])
            }
        }
        n = ArraySize(xs)
        Assert(n >= 3, "Tint axis requires at least 3 LUT points")
        x = Max(xs[0], Min(xs[n - 1], tint))
        rgb = []
        for (channel = 0, 2) {
            ys = channel == 0 ? ys_r : channel == 1 ? ys_g : ys_b
            if (x <= xs[0]) {
                yout = ys[0]
            } else if (x >= xs[n - 1]) {
                yout = ys[n - 1]
            } else {
                h = []
                delta = []
                for (i = 0, n - 2) {
                    hi = xs[i + 1] - xs[i]
                    h = ArrayAdd(h, hi)
                    delta = ArrayAdd(delta, (ys[i + 1] - ys[i]) / hi)
                }
                d0 = ((2.0 * h[0] + h[1]) * delta[0] - h[0] * delta[1]) / (h[0] + h[1])
                if (d0 * delta[0] <= 0.0) {
                    d0 = 0.0
                } else if (delta[0] * delta[1] < 0.0 && Abs(d0) > Abs(3.0 * delta[0])) {
                    d0 = 3.0 * delta[0]
                }
                last = n - 2
                dn = ((2.0 * h[last] + h[last - 1]) * delta[last] - h[last] * delta[last - 1]) / (h[last] + h[last - 1])
                if (dn * delta[last] <= 0.0) {
                    dn = 0.0
                } else if (delta[last] * delta[last - 1] < 0.0 && Abs(dn) > Abs(3.0 * delta[last])) {
                    dn = 3.0 * delta[last]
                }
                d = [d0]
                for (i = 1, n - 2) {
                    if (delta[i - 1] * delta[i] <= 0.0) {
                        di = 0.0
                    } else {
                        w1 = 2.0 * h[i] + h[i - 1]
                        w2 = h[i] + 2.0 * h[i - 1]
                        di = (w1 + w2) / (w1 / delta[i - 1] + w2 / delta[i])
                    }
                    d = ArrayAdd(d, di)
                }
                d = ArrayAdd(d, dn)
                k = 0
                for (i = 0, n - 2) {
                    if (x >= xs[i] && x <= xs[i + 1]) {
                        k = i
                    }
                }
                hi = h[k]
                t = (x - xs[k]) / hi
                t2 = t * t
                t3 = t2 * t
                h00 = 2.0 * t3 - 3.0 * t2 + 1.0
                h10 = t3 - 2.0 * t2 + t
                h01 = -2.0 * t3 + 3.0 * t2
                h11 = t3 - t2
                yout = h00 * ys[k] + h10 * hi * d[k] + h01 * ys[k + 1] + h11 * hi * d[k + 1]
            }
            rgb = ArrayAdd(rgb, yout)
        }
        r = rgb[0]
        g = rgb[1]
        b = rgb[2]

    # Two-dimensional bilinear interpolation
    } else {
        # Extract unique 2D grid coordinates from LUT
        ts = []
        us = []
        for (i = 0, ArraySize(wb_lut) - 1) {
            if (wb_lut[i, 1] == -100.0 && wb_lut[i, 0] != 0.0) {
                ts = ArrayAdd(ts, wb_lut[i, 0])
            }
            if (wb_lut[i, 0] == -100.0 && wb_lut[i, 1] != 0.0) {
                us = ArrayAdd(us, wb_lut[i, 1])
            }
        }

        nt = ArraySize(ts)
        nu = ArraySize(us)
        Assert(nt >= 2 && nu >= 2, "Invalid 2D LUT grid")

        # Find temperature interval
        t0 = ts[0]
        t1 = ts[nt - 1]
        for (i = 0, nt - 1) {
            if (ts[i] <= temp) {
                t0 = ts[i]
            }
            if (ts[i] > temp && t1 == ts[nt - 1]) {
                t1 = ts[i]
            }
        }
        if (t0 == t1) {
            t0 = ts[nt - 2]
        }

        # Find tint interval
        u0 = us[0]
        u1 = us[nu - 1]
        for (i = 0, nu - 1) {
            if (us[i] <= tint) {
                u0 = us[i]
            }
            if (us[i] > tint && u1 == us[nu - 1]) {
                u1 = us[i]
            }
        }
        if (u0 == u1) {
            u0 = us[nu - 2]
        }

        # Calculate interpolation factors
        tx = (temp - t0) / (t1 - t0)
        ty = (tint - u0) / (u1 - u0)

        # Find all four corners in one LUT pass
        found00 = false
        found10 = false
        found01 = false
        found11 = false

        for (i = 0, ArraySize(wb_lut) - 1) {
            lt = wb_lut[i, 0]
            lu = wb_lut[i, 1]

            if (lt == t0 && lu == u0) {
                r00 = wb_lut[i, 2]
                g00 = wb_lut[i, 3]
                b00 = wb_lut[i, 4]
                found00 = true
            }
            if (lt == t1 && lu == u0) {
                r10 = wb_lut[i, 2]
                g10 = wb_lut[i, 3]
                b10 = wb_lut[i, 4]
                found10 = true
            }
            if (lt == t0 && lu == u1) {
                r01 = wb_lut[i, 2]
                g01 = wb_lut[i, 3]
                b01 = wb_lut[i, 4]
                found01 = true
            }
            if (lt == t1 && lu == u1) {
                r11 = wb_lut[i, 2]
                g11 = wb_lut[i, 3]
                b11 = wb_lut[i, 4]
                found11 = true
            }
        }

        Assert(found00 && found10 && found01 && found11, "Missing one or more 2D LUT corner points")

        # Bilinear interpolation
        r0 = r00 * (1.0 - tx) + r10 * tx
        r1 = r01 * (1.0 - tx) + r11 * tx
        r = r0 * (1.0 - ty) + r1 * ty

        g0 = g00 * (1.0 - tx) + g10 * tx
        g1 = g01 * (1.0 - tx) + g11 * tx
        g = g0 * (1.0 - ty) + g1 * ty

        b0 = b00 * (1.0 - tx) + b10 * tx
        b1 = b01 * (1.0 - tx) + b11 * tx
        b = b0 * (1.0 - ty) + b1 * ty
    }

    # RGB(86,86,86) is the neutral reference
    dr = r - wb_lut_ref
    dg = g - wb_lut_ref
    db = b - wb_lut_ref

    # RGB to YUV offsets
    kg = 1.0 - kr - kb
    off_y = (kr * dr + kg * dg + kb * db) * yscale
    off_u = (db - (kr * dr + kg * dg + kb * db)) / (2.0 * (1.0 - kb)) * cscale
    off_v = (dr - (kr * dr + kg * dg + kb * db)) / (2.0 * (1.0 - kr)) * cscale

    gain_y = 256.0 * off_y / (wb_lut_ref - yblack)

    return [gain_y, off_u, off_v]
}

# White Balance correction using Temperature and Tint values approximated to Adobe Camera RAW
# temp: -Blue / +Yellow [-100 ... +100]; tint: -Green / +Magenta  [-100 ... +100];
function WhiteBalance(clip c, float "temp", float "tint", string "matrix", bool "affect_luma") {
    temp = Default(temp, 0.0)
    tint = Default(tint, 0.0)
    matrix = Default(matrix, "709:f")
    affect_luma = Default(affect_luma, true)
    Assert(temp >= -100.0 && temp <= 100.0, "Temperature must be in range -100 ... +100")
    Assert(tint >= -100.0 && tint <= 100.0, "Tint must be in range -100 ... +100")
    
    offset_yuv = Color_WBToUV(temp, tint, matrix)
    gain_y   = affect_luma ? offset_yuv[0] : 0.0
    offset_u = offset_yuv[1]
    offset_v = offset_yuv[2]
    
    return c.ColorYUV(gain_y=gain_y, off_u=offset_u, off_v=offset_v)
}

# Convert seconds to number of frames
function SecToFrames(float seconds, string "rounding", float "framerate") {
    rounding = LCase(Default(rounding, "round"))
    framerate = Default(framerate, project_video_framerate)
    result = seconds * Float(project_video_framerate)
    if (rounding == "none")  { return result }
    if (rounding == "round") { return Round(result) }
    if (rounding == "floor") { return Floor(result) }
    if (rounding == "none")  { return Ceil(result) }
}

# Round value to nearest multiple
function RoundToMultiple(float value, int "divisor", string "mode") {
    divisor = Default(divisor, 2)
    mode = Default(mode, "round")
    Assert(divisor > 0, "RoundToMultiple: divisor must be positive")
    Assert(mode == "floor" || mode == "ceil" || mode == "round", "RoundToMultiple: invalid mode")

    scaled = value / divisor

    if (mode == "floor") {
        result = Floor(scaled) * divisor
    } else if (mode == "ceil") {
        result = Ceil(scaled) * divisor
    } else {
        result = Round(scaled) * divisor
    }

    return result
}


# Open source files ===========================================================================================================
# Resolve inputs into full syntax ---------------------------------------------------------------------------------------------
for (i = 0, inputs_count) {
    clip = inputs[i]
    if (IsNone(clip)) { continue }

    # Normalize clip
    if (IsString(clip)) {
        # Clip is string -> only path specified -> video(+audio) with no params
        clip = [clip, clip]
    }
    # Normalize tracks
    for (j = 0, ArraySize(clip) - 1) {
        track = clip[j]
        if (!IsNone(track)) {
            # Normalize track
            if (IsString(track)) {
                # Track is string -> only path specified -> detect type and no params
                track = [track, None, None]
            }
            if (ArraySize(track) == 2) {
                # Track is array with 2 elements -> detect which elements are present by their datatype
                if (IsInt(track[0])) {
                    # First element is int(enum) -> type and params specified with no path
                    track = [None, track[0], track[1]]
                } else if (IsInt(track[1])) {
                    # Second element is int(enum) -> path and type specified with no params
                    track = [track[0], track[1], None]
                } else {
                    # Both elements are string -> path and params are specified with no type
                    track = [track[0], None, track[1]]
                }
            }
            track_path = track[0]
            track_type = track[1]
            track_params = track[2]
            # Detect track type if it is not set
            if (IsNone(track_type)) { track_type = Path_GetExtType(Path_GetExtension(track_path), type_extensions) }
            # Additional video tracks are treated as audio
            if (j > 0 && track_type == type_video) { track_type = type_audio }

            clip = ArraySet(clip, [track_path, track_type, track_params], j)
        }
    }

    # Arrange tracks order by type
    clip_video = None
    clip_audio = None
    clip_audio_disabled = ArraySize(clip) > 1 && IsNone(clip[1])
    for (j = 0, ArraySize(clip) - 1) {
        track = clip[j]
        if (!IsNone(track)) {
            track_type = track[1]
            if (track_type == type_video || track_type == type_image || track_type == type_fill) {
                clip_video = track
            } else if (track_type == type_audio) {
                clip_audio = track
            }
        }
    }
    # Use video file as audio source if audio is missing
    if (ArraySize(clip) < 2 && !clip_audio_disabled && IsNone(clip_audio) && !IsNone(clip_video) && clip_video[1] == type_video) {
        clip_audio = [clip_video[0], type_audio, None]
    }

    # Check tracks
    if (!IsNone(clip_video)) {
        if (IsString(clip_video[0]) && StrLen(clip_video[0]) == 0) { clip_video = ArraySet(clip_video, None, 0) }
        if (IsString(clip_video[2]) && StrLen(clip_video[2]) == 0) { clip_video = ArraySet(clip_video, None, 2) }
    }
    if (!IsNone(clip_audio)) {
        if (IsString(clip_audio[0]) && StrLen(clip_audio[0]) == 0) {
            clip_audio = None
        } else {
            if (IsString(clip_audio[2]) && StrLen(clip_audio[2]) == 0) { clip_audio = ArraySet(clip_audio, None, 2) }
        }
    }
    Assert(!(IsNone(clip_video[0]) && !(clip_video[1] == type_image || clip_video[1] == type_fill)), Format("Input {:d} has no video source", i))
    Assert(!(IsNone(clip_video[2]) &&  (clip_video[1] == type_image || clip_video[1] == type_fill)), Format("Input {:d} has secondary video source without params", i))

    clip = [clip_video, clip_audio]
    inputs = ArraySet(inputs, clip, i)
}

# Make clips from inputs -----------------------------------------------------------------------------------------------------------
clips = []
# Pass 1: Open primary (file-based) videos and audio as separate instances
for (i = 0, inputs_count) {
    input = inputs[i]
    if (IsNone(input)) {
        clips = ArrayAdd(clips, None)
    } else {
        input_video = input[0]
        input_audio = input[1]
        Assert(!IsNone(input_video), Format("Input {:d} has no video", i))

        # Open audio first
        clip_audio = None
        if (!IsNone(input_audio)) {
            input_audio_path   = input_audio[0]
            input_audio_params = IsNone(input_audio[2]) ? "" : input_audio[2]
            # Prevent delay parameter from passing into function
            tmp = Argument_Pop(Arguments_Parse(input_audio_params), "delay", "0.0")
            input_audio_params = Arguments_Build(tmp[0])
            input_audio_delay = String_ToFloat(tmp[1])
            try {
                clip_audio = [Eval("LWLibavAudioSource(" + Chr(34) + input_audio_path + Chr(34) + (input_audio_params != "" ? ", " + input_audio_params : "") + ")"), input_audio_delay]
            } catch (err_msg) {
                clip_audio = None
            }
        }

        # Open video
        input_video_path   = input_video[0]
        input_video_type   = input_video[1]
        input_video_params = IsNone(input_video[2]) ? "" : input_video[2]
        if (input_video_type == type_video) {
            clip_video = Eval("LWLibavVideoSource(" + Chr(34) + input_video_path + Chr(34) + (input_video_params != "" ? ", " + input_video_params : "") + ")")
        } else {
            # Do not create secondary video on this pass
            clip_video = None
        }

        clips = ArrayAdd(clips, [clip_video, clip_audio])
    }
}

# Find default video format - use first clip with primary video as a template
clip_video_template = None
for (i = 0, inputs_count) {
    clip = clips[i]
    if (!IsNone(clip)) {
        clip_video = clip[0]
        if (!IsNone(clip_video)) {
            clip_video_template = clip_video
            break
        }
    }
}
if (IsNone(project_video_framerate)) {
    Assert(!IsNone(clip_video_template), "No primary video source to determine default video parameters")
    global project_video_framerate = clip_video_template.FrameRate()
}

# Find default audio format - use first clip with primary video which has audio as a template
clip_audio_template = None
for (i = 0, inputs_count) {
    clip = clips[i]
    if (!IsNone(clip)) {
        clip_video = clip[0]
        clip_audio = clip[1]
        if (!IsNone(clip_video)) {
            if (!IsNone(clip_audio)) {
                clip_audio_template = clip_audio[0]
                break
            }
        }
    }
}

# Pass 2: Open secondary (generative) videos (audio have been already open on pass 1)
for (i = 0, inputs_count) {
    clip = clips[i]
    if (!IsNone(clip)) {
        clip_video = clip[0]
        if (IsNone(clip_video)) {
            input = inputs[i]
            input_video = input[0]
            input_video_path   = input_video[0]
            input_video_type   = input_video[1]
            input_video_params = IsNone(input_video[2]) ? "" : input_video[2]
            input_video_params = Arguments_Parse(input_video_params)
            input_video_params = Argument_Set(input_video_params, "fps", "project_video_framerate")
            input_video_params = Arguments_Build(input_video_params)
            if (input_video_type == type_image) {
                clip_video = Eval("ImageSource(" + Chr(34) + input_video_path + Chr(34) + (input_video_params != "" ? ", " + input_video_params : "") + ")")
            } else if (input_video_type == type_fill) {
                clip_video = Eval("BlankClip(" + input_video_params + ")")
                clip_video = clip_video.KillAudio()
            } else {
                Assert(false, Format("Input {:d} has unsupported video type", i))
            }
            tmp = [clip_video]
            for (j = 1, ArraySize(clip) - 1) {
                tmp = ArrayAdd(tmp, clip[j])
            }
            clips = ArraySet(clips, tmp, i)
        }
    }
}

# If default audio format was not found in primary videos try again with all videos - use first audio as a template
if (IsNone(clip_audio_template)) {
    for (i = 0, inputs_count) {
        clip = clips[i]
        if (!IsNone(clip)) {
            clip_audio = clip[1]
            if (!IsNone(clip_audio)) {
                clip_audio_template = clip_audio[0]
                break
            }
        }
    }
}
if (!IsNone(clip_audio_template)) {
    if (IsNone(project_audio_channels)) { global project_audio_channels = AudioChannels(clip_audio_template) }
    if (IsNone(project_audio_samplerate)) { global project_audio_samplerate = AudioRate(clip_audio_template) }
    if (IsNone(project_audio_format)) { global project_audio_format = (IsAudioFloat(clip_audio_template) ? "float" : String(AudioBits(clip_audio_template)) + "bit") }
}

# Pass 3: Combine video and audio into clips
for (i = 0, inputs_count) {
    clip = clips[i]
    if (!IsNone(clip)) {
        clip_video = clip[0]
        clip_audio = clip[1]
        if (IsNone(clip_audio)) {
            if (!IsNone(clip_audio_template)) {
                clip_audio = [BlankClip(clip_video, audio_rate=project_audio_samplerate, channels=project_audio_channels, sample_type=project_audio_format).KillVideo(), 0.0]
            }
        } 
        if (!IsNone(clip_audio)) {
            clip = AudioDub(clip_video, clip_audio[0])
            if(clip_audio[1] != 0.0) {
                clip = clip.DelayAudio(clip_audio[1])
            }
            # Match audio length to video
            clip = clip.Trim(0, FrameCount(clip_video) - 1, pad=true)
        } else {
            clip = clip_video
        }
        clips = ArraySet(clips, clip, i)
    }
}


# Resolve parameters ==========================================================================================================
# Resolve arguments from string lines -----------------------------------------------------------------------------------------
convert_video_args  = Arguments_Resolve(convert_video_default, convert_video_perclip)
convert_audio_args  = Arguments_Resolve(convert_audio_default, convert_audio_perclip)
stab_estimate_args  = Arguments_Resolve(stab_estimate_default, stab_estimate_perclip)
stab_stabilize_args = Arguments_Resolve(stab_stabilize_default, stab_stabilize_perclip)
crop_args           = Arguments_Resolve(crop_default, crop_perclip)
denoise_args        = Arguments_Resolve(denoise_default, denoise_perclip)
resize_args         = Arguments_Resolve(resize_default, resize_perclip)
whitebalance_args   = Arguments_Resolve(whitebalance_default, whitebalance_perclip)
smoothlevels_args   = Arguments_Resolve(smoothlevels_default, smoothlevels_perclip)
smoothtweak_args    = Arguments_Resolve(smoothtweak_default, smoothtweak_perclip)
coloryuv_args       = Arguments_Resolve(coloryuv_default, coloryuv_perclip)
sharpen_args        = Arguments_Resolve(sharpen_default, sharpen_perclip)
subtitle_args       = Arguments_Resolve(subtitle_default, subtitle_perclip)
trim_args           = Arguments_Resolve(trim_default, trim_perclip)
fade_args           = Arguments_Resolve(fade_default, fade_perclip)
compare_args        = Arguments_Resolve(compare)
info_args           = Arguments_Resolve(info_default, info_perclip)
rangefix_args       = Arguments_Resolve(rangefix)

# Resolve static parameters ---------------------------------------------------------------------------------------------------
# Check for motion estimation pass
stab_estimate_enabled  = false
for (i = 0, inputs_count) {
    if (Arguments_IsEnabled(stab_estimate_args[i])) {
        stab_estimate_enabled = true
        break
    }
}
# Add motion log to stab functions arguments
for (i = 0, inputs_count) {
    input = inputs[i]
    if (!IsNone(input)) {
        stab_motion_log_suffix = "_motion.log"
        input_video_type = input[0][1]
        if (input_video_type == type_video) {
            stab_motion_log = input[0][0] + stab_motion_log_suffix
        } else {
            stab_motion_log = ScriptFile() + "_" + String(i) + stab_motion_log_suffix
        }
        stab_estimate_args  = ArraySet(stab_estimate_args,  Argument_Set(stab_estimate_args[i],  "log",      Chr(34) + stab_motion_log + Chr(34)), i)
        stab_stabilize_args = ArraySet(stab_stabilize_args, Argument_Set(stab_stabilize_args[i], "inputlog", Chr(34) + stab_motion_log + Chr(34)), i)
    }
}
# Compare
compare_enabled     = Arguments_IsEnabled(compare_args)
compare_mode        = String_Unquote(Argument_Get(compare_args, "mode", "split"))
compare_orientation = String_Unquote(Argument_Get(compare_args, "orientation", "h"))
compare_align       = Eval(Argument_Get(compare_args, "align", "align_middlecenter"))
compare_swap        = Arguments_IsEnabled(compare_args, "swap", false)
compare_diff        = Arguments_IsEnabled(compare_args, "diff", false)
compare_diff_levels = Argument_Get(compare_args, "diff_levels", ["64", "192", "0", "255"])
for (i = 0, ArraySize(compare_diff_levels) - 1) { compare_diff_levels = ArraySet(compare_diff_levels, String_ToInt(compare_diff_levels[i]), i) }
if (compare_mode == "split") { compare_diff = false }


# Process clips ===============================================================================================================
if(stab_estimate_enabled) {
    # Motion estimation pass
    prefetch_threads = 1
    clips_estimated = []
    for(i = 0, inputs_count) {
        if(Arguments_IsEnabled(stab_estimate_args[i])) {
            c = clips[i]
            if (!IsNone(c)) {
                args = stab_estimate_args[i]
                # Get crop area for motion estimation
                tmp = Argument_Pop(args, "crop", "0")
                args = tmp[0]
                stab_estimate_crop = tmp[1]
                if(!IsArray(stab_estimate_crop)) {
                    stab_estimate_crop = [stab_estimate_crop, stab_estimate_crop, stab_estimate_crop, stab_estimate_crop]
                }
                for(j = 0, ArraySize(stab_estimate_crop) - 1) {
                    stab_estimate_crop = ArraySet(stab_estimate_crop, String_ToInt(stab_estimate_crop[j]), j)
                }
                if(stab_estimate_crop[0] != 0 || stab_estimate_crop[1] != 0 || stab_estimate_crop[2] != 0 || stab_estimate_crop[3] != 0) {
                    c = c.Crop(stab_estimate_crop[0], stab_estimate_crop[1], stab_estimate_crop[2], stab_estimate_crop[3])
                }
                # Convert video
                tmp = Argument_Pop(convert_video_args[i], "format", "YUV420")
                c = c.Function_Execute("ConvertTo" + tmp[1], tmp[0])
                # Estimate motion
                c = c.Function_Execute("DePanEstimate", args)
                # Remove audio to avoid processing it on convert stage
                c = c.KillAudio()
                
                c = c.Prefetch(prefetch_threads)
                clips_estimated = ArrayAdd(clips_estimated, c)
            }
        }
    }
    clips = clips_estimated
} else {
    # Regular pass
    for (i = 0, inputs_count) {
        c = clips[i]
        if (!IsNone(c)) {
            # Convert video
            tmp = Argument_Pop(convert_video_args[i], "format", "YUV420")
            c = c.Function_Execute("ConvertTo" + tmp[1], tmp[0])
            # Compare: backup original clip
            if (compare_enabled) { compare_clip = c }
            # Image stabilization
            args = stab_stabilize_args[i]
            if(Arguments_IsEnabled(args)) {
                args = Argument_Set(args, "data", "c") # value "c" is critical and must be the same as clip local variable name in the corresponding function
                stab_stabilize_blur = String_ToInt(Argument_Get(args, "blur", "0"))
                stab_stabilize_mirror = Argument_Get(args, "mirror", "0")
                if(!IsArray(stab_stabilize_mirror)) {
                    stab_stabilize_mirror = Eval(stab_stabilize_mirror)
                    if(stab_stabilize_mirror < 0 || stab_stabilize_mirror > 15) {
                        stab_stabilize_mirror = [stab_stabilize_mirror, stab_stabilize_mirror, stab_stabilize_mirror, stab_stabilize_mirror]
                    }
                } else {
                    for(j = 0, ArraySize(stab_stabilize_mirror) - 1) {
                        stab_stabilize_mirror = ArraySet(stab_stabilize_mirror, Eval(stab_stabilize_mirror[j]), j)
                    }
                    if (ArraySize(stab_stabilize_mirror) == 2) {
                        stab_stabilize_mirror = [stab_stabilize_mirror[0], stab_stabilize_mirror[1], stab_stabilize_mirror[0], stab_stabilize_mirror[1]]
                    }
                }
                if(IsArray(stab_stabilize_mirror)) {
                    # Use MirrorEdges function instead of built-in ones
                    Assert(ArraySize(stab_stabilize_mirror) == 4, "Stabilize: Invalid 'mirror' value")
                    args = Argument_Set(args, "mirror", "0")
                    if(stab_stabilize_mirror[0] < 0) { stab_stabilize_mirror = ArraySet(stab_stabilize_mirror, (-stab_stabilize_mirror[0] * c.Width)  / 100, 0) }
                    if(stab_stabilize_mirror[1] < 0) { stab_stabilize_mirror = ArraySet(stab_stabilize_mirror, (-stab_stabilize_mirror[1] * c.Height) / 100, 1) }
                    if(stab_stabilize_mirror[2] < 0) { stab_stabilize_mirror = ArraySet(stab_stabilize_mirror, (-stab_stabilize_mirror[2] * c.Width)  / 100, 2) }
                    if(stab_stabilize_mirror[3] < 0) { stab_stabilize_mirror = ArraySet(stab_stabilize_mirror, (-stab_stabilize_mirror[3] * c.height) / 100, 3) }
                    c = c.MirrorEdges(left = stab_stabilize_mirror[0], top = stab_stabilize_mirror[1], right = stab_stabilize_mirror[2], bottom = stab_stabilize_mirror[3], blur = stab_stabilize_blur)
                    c = c.Function_Execute("DePanStabilize", args)
                    c = c.Crop(stab_stabilize_mirror[0], stab_stabilize_mirror[1], -stab_stabilize_mirror[2], -stab_stabilize_mirror[3])
                } else {
                    # Use built-in mirror function
                    c = c.Function_Execute("DePanStabilize", args)
                }
            }
            # Crop
            args = crop_args[i]
            if (Arguments_IsEnabled(args)) {
                tmp = Argument_Pop(args, "preview", "false")
                args = tmp[0]
                if (String_ToBool(tmp[1])) {
                    # Strip prefix from preview arguments name
                    for (j = 0, ArraySize(args) - 1) {
                        if (LeftStr(args[j][0], 3) == "pv_") {
                            args = ArraySet(args, [MidStr(args[j][0], 4), args[j][1]], j)
                        }
                    }
                    c = c.Function_Execute("Crop_preview", args)
                } else {
                    # Strip preview arguments
                    args_c = []
                    for (j = 0, ArraySize(args) - 1) {
                        if (LeftStr(args[j][0], 3) != "pv_") { args_c = ArrayAdd(args_c, args[j]) }
                    }
                    c = c.Function_Execute("Crop", args_c)
                }
            }
            # Denoise
            c = c.Function_Execute("TemporalDegrain2", denoise_args[i])
            # Resize
            args = resize_args[i]
            if (Arguments_IsEnabled(args)) {
                c = c.Function_Execute("Spline36Resize", resize_args[i])
                if (compare_enabled) {
                    compare_clip = compare_clip.Function_Execute("Spline36Resize", resize_args[i])
                }
            }
            # WhiteBalance
            c = c.Function_Execute("WhiteBalance", whitebalance_args[i])
            # SmoothLevels
            c = c.Function_Execute("SmoothLevels", smoothlevels_args[i])
            # SmoothTweak
            c = c.Function_Execute("SmoothTweak", smoothtweak_args[i])
            # ColorYUV
            c = c.Function_Execute("ColorYUV", coloryuv_args[i])
            # Sharpen
            c = c.Function_Execute("LSFmod", sharpen_args[i])
            # Subtitle
            for (j = 0, ArraySize(subtitle_args[i]) - 1) {
                c = c.Function_Execute("Subtitle", subtitle_args[i][j])
            }
            # Compare: Combine original and result
            if (compare_enabled) {
                compare_size_mod = Clip_SizeModulo(c)
                compare_size_mod_width = compare_size_mod[0]
                compare_size_mod_height = compare_size_mod[1]
                if (compare_mode == "stack") {
                    compare_crop_source = [0, 0, 0, 0]
                    compare_crop_result = compare_crop_source
                } else if (compare_mode == "split") {
                    if (compare_orientation == "h") {
                        compare_crop_source = [0, 0, RoundToMultiple(c.Width / 2, compare_size_mod_width), 0]
                        compare_crop_result = [c.Width - compare_crop_source[2], 0, 0, 0]
                    } else {
                        compare_crop_source = [0, 0, 0, RoundToMultiple(c.Height / 2, compare_size_mod_height)]
                        compare_crop_result = [0, c.Height - compare_crop_source[3], 0, 0]
                    }
                    if (compare_swap) {
                        tmp = compare_crop_source
                        compare_crop_source = compare_crop_result
                        compare_crop_result = tmp
                    }
                } else if (compare_mode == "crop") {
                    if (compare_orientation == "h") {
                        compare_crop_width = RoundToMultiple(c.Width / 2, compare_size_mod_width)
                        if (compare_diff) { compare_crop_height = RoundToMultiple(c.Height / 2, compare_size_mod_height) }
                        else {              compare_crop_height = c.Height }
                    } else {
                        compare_crop_height = RoundToMultiple(c.Height / 2, compare_size_mod_height)
                        if (compare_diff) { compare_crop_width = RoundToMultiple(c.Width / 2, compare_size_mod_width) }
                        else {              compare_crop_width = c.Width }
                    }
                    if (compare_align == align_topleft || compare_align == align_middleleft || compare_align == align_bottomleft) {
                        compare_crop_left = 0
                    } else if (compare_align == align_topright || compare_align == align_middleright || compare_align == align_bottomright) {
                        compare_crop_left = RoundToMultiple(c.Width - compare_crop_width, compare_size_mod_width)
                    } else {
                        compare_crop_left = RoundToMultiple((c.Width - compare_crop_width) / 2, compare_size_mod_width)
                    }
                    if (compare_align == align_topleft || compare_align == align_topcenter || compare_align == align_topright) {
                        compare_crop_top = 0
                    } else if (compare_align == align_bottomleft || compare_align == align_bottomcenter || compare_align == align_bottomright) {
                        compare_crop_top = RoundToMultiple(c.Height - compare_crop_height, compare_size_mod_height)
                    } else {
                        compare_crop_top = RoundToMultiple((c.Height - compare_crop_height) / 2, compare_size_mod_height)
                    }
                    compare_crop_source = [compare_crop_left, compare_crop_top, compare_crop_width, compare_crop_height]
                    compare_crop_result = compare_crop_source
                }
                compare_clip = compare_clip.Crop(compare_crop_source[0], compare_crop_source[1], compare_crop_source[2], compare_crop_source[3])
                c = c.Crop(compare_crop_result[0], compare_crop_result[1], compare_crop_result[2], compare_crop_result[3])
                if (compare_diff) {
                    compare_clip_diff = Subtract(c, compare_clip)
                    compare_clip_diff_levels = compare_clip_diff.Levels(compare_diff_levels[0], 1.0, compare_diff_levels[1], compare_diff_levels[2], compare_diff_levels[3], coring=false)
                }
                if (compare_orientation == "h") {
                    if (compare_swap) { c = StackHorizontal(c, compare_clip) }
                    else              { c = StackHorizontal(compare_clip, c) }
                    if (compare_diff) {
                        if (compare_swap) { compare_clip_diff = StackHorizontal(compare_clip_diff_levels, compare_clip_diff) }
                        else              { compare_clip_diff = StackHorizontal(compare_clip_diff, compare_clip_diff_levels) }
                        c = StackVertical(c, compare_clip_diff)
                    }
                } else if (compare_orientation == "v") {
                    if (compare_swap) { c = StackVertical(c, compare_clip) }
                    else              { c = StackVertical(compare_clip, c) }
                    if (compare_diff) {
                        if (compare_swap) { compare_clip_diff = StackVertical(compare_clip_diff_levels, compare_clip_diff) }
                        else              { compare_clip_diff = StackVertical(compare_clip_diff, compare_clip_diff_levels) }
                        c = StackHorizontal(c, compare_clip_diff)
                    }
                }
            }
            # Info
            args = info_args[i]
            if (Arguments_IsEnabled(args)) {
                info_frame_count = c.FrameCount()
                info_frame_rate = c.FrameRate()
                info_x = String_ToInt(Argument_Get(args, "x", "0"))
                if(info_x < 0) { info_x = c.Width + info_x }
                info_y = String_ToInt(Argument_Get(args, "y", "0"))
                if(info_y < 0) { info_y = c.Height + info_y }
                info_font = Argument_Get(args, "font", "Consolas")
                info_size = String_ToFloat(Argument_Get(args, "size", "28"))
                info_bold = String_ToBool(Argument_Get(args, "bold", "false"))
                info_italic = String_ToBool(Argument_Get(args, "italic", "false"))
                info_text_color = String_ToInt(Argument_Get(args, "text_color", "color_yellow"))
                info_halo_color = String_ToInt(Argument_Get(args, "halo_color", "color_black"))
                info_align = Eval(Argument_Get(args, "align", "align_topleft"))
                c = c.ScriptClip(function [i, info_frame_count, info_frame_rate, info_x, info_y, info_font, info_size, info_bold, info_italic, info_text_color, info_halo_color, info_align] (clip c) {
                    time = Round(current_frame * 1000.0 / info_frame_rate)
                    text = Format(e"{:02d}*{:02d}:{:02d}:{:02d}.{:03d}\n{:06d} / {:06d}", i, time / 3600000, (time / 60000) % 60, (time / 1000) % 60, time % 1000, current_frame, info_frame_count)
                    return c.Subtitle(text, x=info_x, y=info_y, font=info_font, size=info_size, bold=info_bold, italic=info_italic, text_color=info_text_color, halo_color=info_halo_color, align=info_align)
                })
            }
            # Trim
            c = c.Function_Execute("Trim", trim_args[i])
            # Fade
            args = fade_args[i]
            if(Arguments_IsEnabled(args)) {
                args_in = []
                args_out = []
                for (j = 0, ArraySize(args) - 1) {
                    arg = args[j]
                    if (LeftStr(arg[0], 3) == "in_") { args_in = ArrayAdd(args_in, [MidStr(arg[0], 4), arg[1]]) }
                    else if (LeftStr(arg[0], 4) == "out_") { args_out = ArrayAdd(args_out, [MidStr(arg[0], 5), arg[1]]) }
                }
                fade_in_frames  = Eval(Argument_Get(args_in, "positional",  "0"))
                fade_out_frames = Eval(Argument_Get(args_out, "positional", "0"))
                if(fade_in_frames > 0) {
                    c = c.Function_Execute("FadeIn", args_in, true)
                }
                if(fade_out_frames > 0) {
                    c = c.Function_Execute("FadeOut", args_out, true)
                }
            }
            # Prefetch
            if (IsNone(prefetch_threads)) {
                c = c.Prefetch()
            } else {
                if (IsNone(prefetch_frames)) {
                    c = c.Prefetch(prefetch_threads)
                } else {
                    c = c.Prefetch(prefetch_threads, prefetch_frames)
                }
            }
            
            clips = ArraySet(clips, c, i)
        }
    }
}

# Convert Audio ---------------------------------------------------------------------------------------------------------------
# This MUST be AFTER prefetch to not mess with the multithreading because most audio filters work in MT_SERIALIZED mode
if (!stab_estimate_enabled) {
    for(i = 0, inputs_count) {
        args = convert_audio_args[i]
        if(Arguments_IsEnabled(args)) {
            c = clips[i]
            if (!IsNone(c)) {
                # Channels
                audio_channels = String_ToInt(Argument_Get(args, "channels", String(project_audio_channels)))
                if (audio_channels == 0) {
                    c = c.KillAudio()
                } else {
                    Assert(c.HasAudio(), Format("Clip {:d} has no audio", i))
                    if (audio_channels == 1) {
                        c = c.ConvertToMono()
                    } else if (audio_channels == 2) {
                        if (c.AudioChannels() == 1) {
                            c = MergeChannels(c, c)
                        }
                        Assert(audio_channels < 2, Format("Merging of multichannel audio: not implemented", i))
                    }            
                }
                if (c.HasAudio()) {
                    # Sample rate
                    audio_samplerate = String_ToInt(Argument_Get(args, "samplerate", String(project_audio_samplerate)))
                    if (c.AudioRate() != audio_samplerate) {
                        c = c.SSRC(audio_samplerate)
                    }
                    # Format
                    audio_format = Argument_Get(args, "format", project_audio_format)
                    clip_audio_format = (IsAudioFloat(c) ? "Float" : String(AudioBits(c)) + "bit")
                    if (clip_audio_format != audio_format) {
                        Eval("c = c.ConvertAudioTo" + audio_format + "()")
                    }
                    # Normalize + Amplify
                    audio_normalize = String_ToBool(Argument_Get(args, "normalize", "false"))
                    audio_amplify_db = String_ToFloat(Argument_Get(args, "amplify_db", "0.0"))
                    if (audio_normalize) {
                        audio_amplify = Min(1.0, Pow(10.0, audio_amplify_db / 20.0))
                        c = c.Normalize(audio_amplify)
                    }
                    if ((audio_normalize && audio_amplify_db > 0.0) || (!audio_normalize && audio_amplify_db != 0.0)) {
                        c = c.AmplifydB(audio_amplify_db)
                    }
                }
                clips = ArraySet(clips, c, i)
            }
        }
    }
}

# Merge clips array -----------------------------------------------------------------------------------------------------------
output = []
for (i = 0, ArraySize(clips) - 1) {
    if (!IsNone(clips[i])) {
        output = ArrayAdd(output, clips[i])
    }
}
Assert(ArraySize(output) > 0,  "Nothing to output")
result = output[0]
for (i = 1, ArraySize(output) - 1) {
    result = result ++ output[i]
}
result

# Preview levels workaround ---------------------------------------------------------------------------------------------------
if(Arguments_IsEnabled(rangefix_args) && !stab_estimate_enabled) {
    rangefix_args = Argument_Delete(rangefix_args, "enabled")
    ColorYUV(levels="PC->TV")
    if(Arguments_IsEnabled(rangefix_args, "warning", true)) {
        rangefix_args = Argument_Delete(rangefix_args, "warning")
        tmp = Argument_Pop(rangefix_args, "text", "RANGE")
        rangefix_text = tmp[1]
        rangefix_args = tmp[0]
        rangefix_x = String_ToInt(Argument_Get(rangefix_args, "x", "-1"))
        if(rangefix_x < 0) { rangefix_args = Argument_Set(rangefix_args, "x", String(Width + rangefix_x)) }
        rangefix_y = String_ToInt(Argument_Get(rangefix_args, "y", "0"))
        if(rangefix_y < 0) { rangefix_args = Argument_Set(rangefix_args, "y", String(Height + rangefix_y)) }
        rangefix_args = Arguments_Build(rangefix_args)
        Eval("SubTitle(" + rangefix_text + (rangefix_args == "" ? "" : ", " + rangefix_args) + ")")
    }
}