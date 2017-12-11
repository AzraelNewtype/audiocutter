# AudioCutter

A tool to cut audio and generate associated chapters/qpfiles for vapoursynth.

## Getting Started

### Prerequisites
- [Python 3](http://python.org) which is actually already a requirement for
- [Vapoursynth](http://vapoursynth.com) Obviously.
- [MKVToolNix](https://mkvtoolnix.download) - Needs to be new enough to handle `--split parts:`, though not necessarily up to date

### "Installation"

You can safely put `audiocutter.py` anywhere in your python path, though I recommend creating a `scripts` folder next
to your plugins32 and plugins64 folders, so you can keep the python in the same vicinity as the the compiled plugins
you use. You can look at `example.vpy` to see how you can easily leverage this on windows, though the same principle
applies for Linux/OSX with a different path.

**Note:** Before you leave wherever you're putting the script, check if you can execute `mkvmerge` from your command
line. If you can't, you should edit `self.__mkvmerge` in `__init__` to match the path to your mkvmerge executable. If
you're on windows, you should use forward slashes as path delimiters.

## API

### Functions
**\_\_init\_\_(self)**

Bog standard initialization. There are no possible arguments. _If mkvmerge isn't in your path, though, this function has the line you need to edit._

**cut\_audio(self, outfile, video\_source=None, audio\_source=None)**

Cuts the supplied audio file, based on trims from AudioCutter.split()

`video_source` is intended for use with a video type where you've either manually
demuxed an audio track to the same name as your source (e.g. tsmuxer + LSMASHSource),
or generated an index file that demuxes the audio in a very similar way 
(e.g dgindex + d2v.Source). It will search for filenames that begin with the video name,
but have an aac or ac3 extension, as these are the most likely output from those types
of sources (DVDs/Transport streams). It always uses the largest available file, so don't
use this option if for some reason you have ac3 and aac files that are similar to your
source name, unless you're sure you want the ac3, as it will be bigger. This is mutually
exclusive with audio_source.

`audio_source` simply takes an audio file name, in case your audio isn't so strictly named
like your video. This is mutually exclusive with video_source.

`outfile` should be fairly straightforward.

**ready\_qp\_and\_chapters(self, vid)**

Populates qp_lines and chapters based on frames passed to split()

This function is kept separate from split() in case of framerate change.
The obvious use case is after inverse telecine, where this must be called
after decimation. 

The chapters created will be bog standard OGM chapters format, defaulting to
Chapter NN for the names if chapter_names has not been set. Also, if there are
more split points than names supplied, it will exhaust the list first and then
start using the defaults. If any of the entries are None or otherwise evaluate
to False, it will also use the default.

The chapter timecodes are converted back from the qpfile cut frames, rather than
separately like `vfr.py` used to for avisynth, largely because I don't even know
how those timecodes came about, but also because this ensures a chapter jump will
go to the exact spot with a forced IDR point. While this may not always be perfectly
frame accurate in an ivtc context, having them match and be off by one is better than
potentially having the chapter IDR point one frame later than the chapter start 
timecode.

**split(self, vid, trims[, doublecheck=False, join=True])**

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

Optionally, the user can supply a 3-tuple (or list, it honestly doesn't enforce tuple,
with the third element being the chapter name. When done this way, setting chapter_names
manually is redundant, though you can override the list with it if you really want to.
Either method entirely overrides the other. There is no ability to partially override,
so make your decision which way you like it. Any chapter without a name set will enter
`chapter_names` as `None`, which will render a default name at `ready_qp_and_chapters` time.

If you desire a quick view of your cut points without commenting the `split()` call out and
manually checking numbers, set `doublecheck=True`. There each start/end frame from the supplied
list will be sandwiched with the frames that come before/after them, and labeled with the chapter
name if given. Using this, you can ensure that you're starting a cut after the commercials or
whatever are over, and ending before a new set starts, just for example.

If join is set to true, it will join the segments immediately. If it is not, the segments
will remain in their array, waiting for you to process further. This would allow you to perform
per-segment filtering, such as fancy IVTC tricks. Also, by allowing IVTC to be performed before
joining, there shouldn't be any estimation of frame count changes for chapters.

**join(self[, update_framerate=False])**

Joins a delayed split.

As this allows per-segment filtering rather than scene filtering, it is probably only
really useful for IVTC pattern changes. If you are performing IVTC before joining, you
probably want to set update_framerate to True here. Doing so will take __clip_holder[0]'s
framerate and update the internal holders to it, so that ready_qp_and_chapters() multiplies
in a 1 at framerate scale time, rather than adjusting to the decimated rate.

This won't work with vfr, but I'm not sure the chapters would even with default handling.

**write_chapters(self, outfile)**

Writes chapters to outfile.

Obviously, this is of limited use if you have not run `ready_qp_and_chapters()`,
as the default is an empty string, but that operation should succeed.

**write_qpfile(self, outfile)**

Writes qp_lines to outfile.

Obviously, this is of limited use if you have not run `ready_qp_and_chapters()`,
as the default is an empty string, but that operation should succeed.

***get_segment(self, idx)***

Returns the split segment at index `idx`. Allows filtering prior to joining.
    
***write_segment(self, idx, new_segment)***
        
Overwrites the split segment at index `idx` with a clip supplied to `new_segment`. Allows filtering prior to joining.

### Instance variables
**chapter\_names** - The list of names to populate the NAME field in your chapters file. Optional, and can be set
by simply adding the names to the tuples passed to split.

**chapters** - A string containing the lines for a chapter file. Of limited value given `write_chapters()`

**cut\_cmd** - The mkvmerge command(s) that will be called, to show the timecodes.

>Do note that the actual cutting method modifies this further, though not
>the timecodes. If you just want to ensure that it's cutting in the right
>spot, this is fine after cut_audio()

>Note that this command will come with two format string variables, 
>`{0}` for the input filename, and `{1}` for the output. `cut_audio()` handles
>this for you though.

**qp\_lines** - A string containing the lines for a qpfile. Of limited value given `write_qpfile()`

## Acknowledgments

- [Vfr.py](https://github.com/wiiaboo/vfr) Lifted some of the timecode related code directly from here
- [split_aud.pl](http://mod16.org/hurfdurf/?p=33) the original big daddy we both descended from for ease of trim->cut audio
- Some anti-acknowledgments to the writer of vapoursynth's `sam` (Split Audio Module), which appears to have done most of what this code did, but it was only hosted on a pastebin that is now lost to the aether, leading to me having to reinvent this wheel in the first place. I don't believe it handled chapters/qpfiles, so there's at least some novel functionality here, but please, if you're going to create utilities that fill the gap between Avisynth and Vapoursynth, don't let them disappear so easily.
