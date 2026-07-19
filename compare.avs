# Define files ----------------------------------------------------------------------------------------------------------------
files = ["MVI_0000_lossless.mkv", "MVI_0000_av1-crf35.mkv", "MVI_0000_av1-crf40.mkv"]
diff_show   = false
diff_levels = true
filesCount = ArraySize(files)-1


# Open files ------------------------------------------------------------------------------------------------------------------
clips = []
for(i=0, filesCount) {
    video = LWLibavVideoSource(files[i])
    audio = LWLibavAudioSource(files[i])
    clips = ArrayAdd(clips, AudioDub(video, audio))
}


# Calculate crop dimentions ---------------------------------------------------------------------------------------------------
clip_width  = clips[0].Width
clip_height = clips[0].Height
rows = 1
if(diff_show) {rows = 2}
cols = filesCount+1
crop_offset_x = round(0.0 * clip_width)
crop_offset_y = round(0.0 * clip_height)
crop_width  = round(clip_width / cols)
crop_height = round(clip_height / rows)
crop_left   = round((clip_width - crop_width) / 2) + crop_offset_x
crop_top    = round((clip_height - crop_height) / 2) + crop_offset_y


# Crop clips ------------------------------------------------------------------------------------------------------------------
for(i=0, filesCount) {
    clips = ArraySet(clips, clips[i].Crop(crop_left, crop_top, crop_width, crop_height), i)
}


# Get difference from source --------------------------------------------------------------------------------------------------
if(diff_show) {
    diffs = []
    for(i=0, filesCount) {
        diff = Subtract(clips[0], clips[i])
        if(diff_levels) {
            diff = diff.Levels(112, 1, 144, 0, 255)
        }
        diffs = ArrayAdd(diffs, diff)
    }
}


# Stack clips -----------------------------------------------------------------------------------------------------------------
clips_stacked = clips[0]
for(i=1, filesCount) {
    clips_stacked = StackHorizontal(clips_stacked, clips[i])
}
if(diff_show) {
    diffs_stacked = diffs[0]
    for(i=1, filesCount) {
        diffs_stacked = StackHorizontal(diffs_stacked, diffs[i])
    }
    clips_stacked = StackVertical(clips_stacked, diffs_stacked)
}
clips_stacked


#!!!PREVIEW ONLY!!! Convert levels for preview in videoplayer
ColorYUV(levels="PC->TV")