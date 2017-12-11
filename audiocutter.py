import glob
import numbers
import re
import shlex
import sys
import vapoursynth as vs
from fractions import Fraction
from os.path import getsize, splitext


class AudioCutter(object):
    """A tool to cut audio and generate associated chapters/qpfiles for vapoursynth."""

    def __init__(self):
        """Bog standard initialization. There are no possible arguments."""

        # Easy, top of file spot for mkvmerge path. If the binary isn't in your PATH, edit
        # it here.
        self.__mkvmerge = r'mkvmerge'
        self.core = vs.get_core()
        self.__trim_holder = []
        self.__clip_holder = []
        self.__is_ordered = False
        self.__fps_num = 30000
        self.__fps_den = 1001
        self.__cut_cmd = ''
        self.__qp_lines = ''
        self.__chapters = ''
        self.chapter_names = []

    @property
    def chapters(self):
        """A string containing the lines for a chapter file."""
        return self.__chapters

    @property
    def chapter_names(self):
        """A list of strings to be used in the chapter output."""
        return self.__chapter_names

    @chapter_names.setter
    def chapter_names(self, names):
        self.__chapter_names = names

    @property
    def cut_cmd(self):
        """The mkvmerge command(s) that will be called, to show the timecodes.

        Do note that the actual cutting method modifies this further, though not
        the timecodes. If you just want to ensure that it's cutting in the right
        spot, this is fine after cut_audio()

        Note that this command will come with two format string variables,
        {0} for the input filename, and {1} for the output. cut_audio() handles
        this for you though.
        """
        return self.__cut_cmd

    @property
    def qp_lines(self):
        """Returns the lines that would be output to a qpfile."""
        return self.__qp_lines
        
    def get_segment(self, idx):
        return self.__clip_holder[idx]
    
    def write_segment(self, idx, new_segment):
        self.__clip_holder[idx] = new_segment
     
    def split(self, vid, trims, doublecheck=False, join=True):
        """Takes a list of 2-tuples of frame numbers and returns the trimmed/spliced video.

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
        chapter_names as None, which will render a default name at ready_qp_and_chapters time.
        
        If doublecheck is True, the filter will return a series of three frame tryptichs, with
        each being the first frame of a cut flanked by the previous/next frames, and then the last
        frame of a cut in the same way. This feature exists to safeguard against mistyping frame
        numbers.
        
        If join is set to true, it will join the segments immediately. If it is not, the segments
        will remain in their array, waiting for you to process further. This would allow you to perform
        per-segment filtering, such as fancy IVTC tricks. Also, by allowing IVTC to be performed before
        joining, there shouldn't be any estimation of frame count changes for chapters.
        """
        safe, msg = self.__list_of_lists(trims)
        if (not safe):
            return self.core.text.Text(vid, msg)
        max = vid.num_frames
        self.chapter_names = list(map(lambda x: x[2] if len(x) > 2 else None,
                                      trims))
        trims = list(map(lambda x: (x[0], x[1]) if x[1] > 0 else (x[0], max),
                         trims))

        self.__trim_holder = trims
        valid, msg = self.__is_valid()
        if (not valid):
            return self.core.text.Text(vid, msg)

        if doublecheck:
            cut_counter = 0
            for clip in self.__trim_holder:
                if clip[0] > 0:
                    c = self.core.std.StackHorizontal([vid[clip[0]-1], vid[clip[0]], vid[clip[0]+1]])
                else:
                    c = self.core.std.StackHorizontal([vid[clip[0]], vid[clip[0]+1]])
                if self.chapter_names[cut_counter]:
                    cut_name = self.chapter_names[cut_counter] + " Start"
                else:
                    cut_name = "Cut {} Start".format(cut_counter)
                c = self.core.text.Text(c, cut_name, 5)
                self.__clip_holder.append(c)

                if clip[1] < max:
                    c = self.core.std.StackHorizontal([vid[clip[1]-1], vid[clip[1]], vid[clip[1]+1]])
                else:
                    c = self.core.std.StackHorizontal([vid[clip[1]-1], vid[clip[1]]])
                if self.chapter_names[cut_counter]:
                    cut_name = self.chapter_names[cut_counter] + " End"
                else:
                    cut_name = "Cut {} End".format(cut_counter)
                c = self.core.text.Text(c, cut_name, 5)
                self.__clip_holder.append(c)
                cut_counter += 1
        else:
            i = 0
            for clip in self.__trim_holder:
                clp = vid[clip[0]:clip[1]+1]
                clp = self.core.std.SetFrameProp(clp, prop="SegmentIdx", intval=i)
                i += 1
                self.__clip_holder.append(clp)
            self.__fps_num = vid.fps_num
            self.__fps_den = vid.fps_den

            self.__prepare_audio_cut_lines(vid)
        
        if join:
            return self.core.std.Splice(self.__clip_holder)
        else:
            return self.core.text.Text(self.__clip_holder[0], "Not joining, so only returning the "
                                                                   "first segment with this message.", 5)
    
    def join(self, update_framerate=False):
        """Joins a delayed split.
        
        As this allows per-segment filtering rather than scene filtering, it is probably only
        really useful for IVTC pattern changes. If you are performing IVTC before joining, you
        probably want to set update_framerate to True here. Doing so will take __clip_holder[0]'s
        framerate and update the internal holders to it, so that ready_qp_and_chapters() multiplies
        in a 1 at framerate scale time, rather than adjusting to the decimated rate.
        
        This won't work with vfr, but I'm not sure the chapters would even with default handling.
        """
        if update_framerate:
            self.__fps_num = self.__clip_holder[0].fps_num
            self.__fps_den = self.__clip_holder[0].fps_den
        return self.core.std.Splice(self.__clip_holder)
                                                                   
    def cut_audio(self, outfile, video_source=None, audio_source=None):
        """Cuts the supplied audio file, based on trims from AudioCutter.split()

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
        """
        from subprocess import check_output, call

        if video_source is None and audio_source is None:
            exit("You didn't supply any audio to cut")
        elif (video_source is not None) and (audio_source is not None):
            exit("Please supply only one of video_source or audio_source")
        elif video_source is None:
            afile = audio_source
        else:
            aacs = glob.glob("{0}*.aac".format(splitext(video_source)[0]))
            ac3s = glob.glob("{0}*.ac3".format(splitext(video_source)[0]))
            potential_audio = aacs + ac3s
            potential_audio.sort(key=lambda x: getsize(x), reverse=True)
            if len(potential_audio) > 0:
                afile = potential_audio[0]
            else:
                sys.exit('Cannot find audio file that matches given video file name')

        ident = check_output([self.__mkvmerge, "--identify-for-mmg", afile])
        identre = re.compile("Track ID (\d+): audio( \(AAC\) \[aac_is_sbr:true\])?")
        ret = (identre.search(ident.decode(sys.getfilesystemencoding())) if ident
               else None)
        tid = ret.group(1) if ret else '0'
        sbr = ("0:1" if ret.group(2) else "0:0"
               if afile.endswith("aac") else "")

        delre = re.compile('DELAY ([-]?\d+)', flags=re.IGNORECASE)
        ret = delre.search(afile)

        delay = '{0}:{1}'.format(tid, ret.group(1)) if ret else None

        final_cut = self.__cut_cmd
        if delay:
            delay_statement = " --sync {}".format(delay)
        else:
            delay_statement = ''
        if sbr:
            final_cut += " --aac-is-sbr {}".format(sbr)

        

        if self.__is_ordered:
            final_cut += ' -o {1} "{0}"'

            self.__cut_cmd = final_cut
            args = shlex.split(final_cut.format(afile, outfile, delay_statement))
            cutExec = call(args)
        else:
            final_cut = final_cut.format(afile,outfile, delay_statement)
            cmds = final_cut.split('\n')
            for cmd in cmds:
                print(cmd)
                args = shlex.split(cmd)
                cutExec = call(args)
                

        if cutExec == 1:
            print("Mkvmerge exited with warnings: {0:d}".format(cutExec))
        elif cutExec == 2:
            print(args)
            # print(self.__cut_cmd)
            exit("Failed to execute mkvmerge: {0:d}".format(cutExec))

    def ready_qp_and_chapters(self, vid):
        """Populates qp_lines and chapters based on frames passed to split()

        This function is kept separate from split() in case of framerate change.
        The obvious use case is after inverse telecine, where this must be called
        after decimation.

        The chapters created will be bog standard OGM chapters format, defaulting to
        Chapter NN for the names if chapter_names has not been set. Also, if there are
        more split points than names supplied, it will exhaust the list first and then
        start using the defaults. If any of the entries are None or otherwise evaluate
        to False, it will also use the default.

        The chapter timecodes are converted back from the qpfile cut frames, rather than
        separately like vfr.py used to for avisynth, largely because I don't even know
        how those timecodes came about, but also because this ensures a chapter jump will
        go to the exact spot with a forced IDR point. While this may not always be perfectly
        frame accurate in an ivtc context, having them match and be off by one is better than
        potentially having the chapter IDR point one frame later than the chapter start
        timecode.
        """
        # Calculate the scalar value for fps change first
        inverse_source_fps = Fraction(self.__fps_den, self.__fps_num)
        current_fps = Fraction(vid.fps_num, vid.fps_den)
        scalar = inverse_source_fps * current_fps

        # Now update it for the chapter timecodes
        self.__fps_num = current_fps.numerator
        self.__fps_den = current_fps.denominator

        f = [x.num_frames * scalar for x in self.__clip_holder]
        f2 = [f[0]]
        for i in range(1, len(f) - 1):
            f2.append(f2[i-1]+f[i])
        ch_start_frames = [int(x) for x in f2]
        self.__qp_lines = ' K\n'.join(list(map(str, ch_start_frames))) + ' K\n'
        ch_start_frames.insert(0, 0)
        i = 1
        ch_string = ""
        names = self.chapter_names
        for chap in ch_start_frames:
            tc = self.__frame_to_timecode(chap, True)
            ch_string += "CHAPTER{0:02d}={1}\n".format(i, tc)
            fallback_name = "CHAPTER{0:02d}NAME=Chapter {0:02d}\n".format(i)
            try:
                if names[i-1]:
                    ch_string += "CHAPTER{0:02d}NAME={1}\n".format(i, names[i-1])
                else:
                    ch_string += fallback_name
            except IndexError:
                ch_string += fallback_name
            i += 1
        self.__chapters = ch_string

    def write_qpfile(self, outfile):
        """Writes qp_lines to outfile.

        Obviously, this is of limited use if you have not run ready_qp_and_chapters(),
        as the default is an empty string, but that operation should succeed.
        """
        try:
            with open(outfile, 'w') as o:
                o.write(self.qp_lines)
        except IOError:
            print("Error writing to qpfile: {}".format(outfile), file=sys.stderr)
            raise

    def write_chapters(self, outfile):
        """Writes chapters to outfile.

        Obviously, this is of limited use if you have not run ready_qp_and_chapters(),
        as the default is an empty string, but that operation should succeed.
        """
        try:
            with open(outfile, 'w') as o:
                o.write(self.chapters)
        except IOError:
            print("Error writing to chapter file: {}".format(outfile), file=sys.stderr)
            raise

    def __merge_adjacent(self):
        """Merges cuts that are a frame apart into a single cut.

        This may be unnecessary since this tool requires mkvtoolnix to support split parts,
        but since the standard for cutting appears to be to increment end timecodes by one,
        adjacent start and end times would be identical, and that may not actually yield intended
        results. Or it might. It's honestly not worth testing, given how easy this is.
        """
        previous = (-3, -3)
        merged_cuts = []
        for trim in self.__trim_holder:
            if previous[1] + 1 == trim[0]:
                previous = (previous[0], trim[1])
            else:
                merged_cuts.append(previous)
                previous = trim
        merged_cuts.append(previous)
        merged_cuts.pop(0)  # The loop may need that (-3,-3), but the output doesn't
        return merged_cuts

    def __frame_to_timecode(self, fn, msp=False):
        """Takes a frame number and returns a timecode of type HH:MM:SS.nnnnnnnnn

        I'm sure nanosecond precision is never, ever useful, but it's better to round
        as late as possible.
        """
        ts = round(10 ** 9 * fn * Fraction(self.__fps_den, self.__fps_num))
        s = ts / 10 ** 9
        m = s // 60
        s = s % 60
        h = m // 60
        m = m % 60
        if msp:
            return '{:02.0f}:{:02.0f}:{:06.3f}'.format(h, m, round(s, 3))
        else:
            return '{:02.0f}:{:02.0f}:{:012.9f}'.format(h, m, s)

    def __list_of_lists(self, trims):
        """Ensures that the trim list is a list of lists.

        It does not actually enforce that you use a list of tuples, though that is preferred
        just for stylistic reasons. It also doesn't ensure the data inside the sub-lists is
        valid. This could probably be fixed with duck typing more carefully, but this seemed
        easier, especially as pertains to writing the error to the video, so it's obvious what
        has happened.
        """
        if(not isinstance(trims, (list, tuple))):
            return False, "Did not pass a list of lists/tuples to split()"
        else:
            for trim in trims:
                if (not isinstance(trim, (list, tuple))):
                    return False, "One or more trims is not a list/tuple"
        return True, ""

    def __is_valid(self):
        """Ensures that the sub-lists contain two positive integers in ascending order.

        Any subclass of numbers.Integral will do here, in case you need something fancier
        than integer literals. Also, having sub-tuples/sub-lists with more than two elements
        is allowed, as long as the first two elements are what is expected.

        Note that nothing in the library consumes the remaining elements, even optionally,
        but the process will not end because of their existence.
        """
        for trim in self.__trim_holder:
            if (not (isinstance(trim[0], numbers.Integral) and
                     isinstance(trim[1], numbers.Integral))):
                return False, "One or more trims is not a group of two integers"
            if ((trim[1] < trim[0]) or (trim[0] < 0)):
                return False, "One or more trims is either out of order, or negative"
        return True, ""

    def __check_ordered(self):
        """Checks whether the first frame of a trim comes strictly after the last of the previous.

        Out of order cuts are acceptable, and the audio cutting even supports it, unlike
        split_aud.pl or vfr.py, but it is more complicated, so not going down that path is
        encouraged if unnecessary.
        """
        previous = (-3, -3)
        self.__is_ordered = True
        for trim in self.__trim_holder:
            if (previous[1] > trim[0]):
                self.__is_ordered = False
                break
            previous = trim
        return self.__is_ordered

    def __prepare_audio_cut_lines(self, vid):
        self.__check_ordered()
        if self.__is_ordered:
            cmd = self.__mkvmerge + "{2} --split parts:"
            merged_cuts = self.__merge_adjacent()
            for trim in merged_cuts:
                s = self.__frame_to_timecode(trim[0])
                e = self.__frame_to_timecode(trim[1]+1)
                cmd += "{}-{},+".format(s,e)
            cmd = cmd[:-2]
        else:
            cmd = ""
            i = 1
            for trim in self.__trim_holder:
                s = self.__frame_to_timecode(trim[0])
                e = self.__frame_to_timecode(trim[1]+1)
                cmd += '"{}" {{2}} --split parts:{}-{} -o tmp-{:03d}.mka "{{0}}"\n'.format(
                    self.__mkvmerge, s, e, i)
                i += 1
            tmpfiles = '" ")" + "(" "'.join(['tmp-{:03d}.mka'.format(x) for x in range(1, i)])
            cmd += '"{}"  "(" "{}" ")" -o "{{1}}"'.format(self.__mkvmerge, tmpfiles)
            appends = ','.join(['{}:0:{}:0'.format(x+1, x) for x in range(i-2)]) # filenames I 1 indexed, which adds an off-by-one
            cmd += ' --append-to {}'.format(appends)
        self.__cut_cmd = cmd
