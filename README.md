# AudioCutter

A function to cut audio and generate chapters and qpfiles based on your video trimming, for vapoursynth.

## API

### Functions
    **__init__(self)**
        Bog standard initialization. There are no possible arguments.

    **cut_audio(self, outfile, video_source=None, audio_source=None)**
        Cuts the supplied audio file, based on trims from AudioCutter.split()

        video_source is intended for use with a video type where you've either manually
        demuxed an audio track to the same name as your source (e.g. tsmuxer + LSMASHSource),
        or generated an index file that demuxes the audio in a very similar way 
        (e.g dgindex + d2v.Source). It will search for filenames that begin with the video name,
        but have an aac or ac3 extension, as these are the most likely output from those types
        of sources (DVDs/Transport streams). It always uses the largest available file, so don't
        use this option if for some reason you have ac3 and aac files that are similar to your
        source name, unless you're sure you want the ac3, as it will be bigger. This is mutually
        exclusive with audio_source.

        audio_source simply takes an audio file name, in case your audio isn't so strictly named
        like your video. This is mutually exclusive with video_source.

        outfile should be fairly straightforward.

    **ready_qp_and_chapters(self, vid)**
        Populates qp_lines and chapters based on frames passed to split()

        This function is kept separate from split() in case of framerate change.
        The obvious use case is after inverse telecine, where this must be called
        after decimation. 

        The chapters created will be bog standard OGM chapters format, defaulting to
        Chapter NN for the names if chapter_names has not been set. Also, if there are
        more split points than names supplied, it will exhaust the list first and then
        start using the defaults.

        The chapter timecodes are converted back from the qpfile cut frames, rather than
        separately like vfr.py used to for avisynth, largely because I don't even know
        how those timecodes came about, but also because this ensures a chapter jump will
        go to the exact spot with a forced IDR point. While this may not always be perfectly
        frame accurate in an ivtc context, having them match and be off by one is better than
        potentially having the chapter IDR point one frame later than the chapter start 
        timecode.

    **split(self, vid, trims)**
        Takes a list of 2-tuples of frame numbers and returns the trimmed/spliced video.

        The 2-tuples must have positive frame numbers, and the second member must be greater
        than the first. The end frame number is inclusive, like avisynth, but unlike standard
        slicing in vapoursynth. As a result, avisynth's:
            trim(9536,22662)++trim(25360,36238)++trim(38038,47896)
        is exactly analagous to:
            split(video_in, [(9536,22662),(25360,36238),(38038,47896)]

        Fancy list slicing, inverse stride, skipping frames, and other similar tricks you can
        trivially pull with vapoursynth directly don't make much sense in this context, so they
        simply will not work.

    **write_chapters(self, outfile)**
        Writes chapters to outfile.

        Obviously, this is of limited use if you have not run ready_qp_and_chapters(),
        as the default is an empty string, but that operation should succeed.

    **write_qpfile(self, outfile)**
        Writes qp_lines to outfile.

        Obviously, this is of limited use if you have not run ready_qp_and_chapters(),
        as the default is an empty string, but that operation should succeed.

### Instance variables
    ------------------
    chapter_names

    chapters
        A string containing the lines for a chapter file.

    cut_cmd
        The mkvmerge command(s) that will be called, to show the timecodes.

        Do note that the actual cutting method modifies this further, though not
        the timecodes. If you just want to ensure that it's cutting in the right
        spot, this is fine after cut_audio()

        Note that this command will come with two format string variables, 
        {0} for the input filename, and {1} for the output. cut_audio() handles
        this for you though.

    qp_lines 
