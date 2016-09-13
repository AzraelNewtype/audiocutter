#!/usr/bin/env python3

import vapoursynth as vs
# I recommend adding the next two lines to your template.vpy on Windows
import sys, os
sys.path.append(os.getenv('APPDATA') + r"\VapourSynth\scripts")
# Keeping this script, as well as things like havsfunc.py in there is much
# cleaner than in site-packages, and you should already be putting plugins
# in %APPDATA%\plugins(32|64) on windows anyway.
import audiocutter


core = vs.get_core()

ts_file = "Some Input.whatever"
ts_in = core.lsmas.LWLibavSource(ts_file) # any source filter will do

ac = audiocutter.AudioCutter()

vid = ac.split(ts_in, [(1159,6910, 'A Chapter'),(6913,9609, 'Another Chapter'),
                       (11862,21298, 'These Names Will be overridden'),(23998,34455),(36255,47523),
                       (47524,49711, 'By the line below'),(49712,50461),(50462,51358, 'So pick a method')])

ac.chapter_names = ['A List', 'Of Chapter Names', 'That Correspond', 'To The',
                    'Trims Above', 'Unnamed Chapters Become', 'Chapter N+1']

# Any processing that you typically perform between trim/splice and anything 
# that affects framerate goes here

# If you need to change framerate (e.g decimate), do it right before:
ac.ready_qp_and_chapters(vid_that_has_the_final_framerate)

# Any processing from this point on had best not affect framerate if you want
# the qpfile and chapters output to work

vid_that_has_the_final_framerate.set_output(0)

# If you run the vpy script by python directly, instead of loading it into 
# VSEdit or VSPipe or the like, these commands will run, letting you handle
# these things only when you want to, rather than every time you try to edit
# or something. It's fun.
if __name__ == "__main__":
    # Do you regularly name your scripts "EPNUM.vpy"?
    # You just grab that filename and never have to remember to adjust your
    # other lines that rely on epnum. Thanks Python!
    prefix = os.path.splitext(__file__)[0]
    # In case the description of video_source in the docs seems confusing,
    # this example should show why I'm into it. Doing the whole thing without
    # updating any filenames but the one input stream. Glorious.
    ac.cut_audio(prefix + '_aud_ac.mka', video_source=ts_file)
    ac.write_qpfile(prefix + "-vsac.qpfile")
    ac.write_chapters(prefix + "-vsac-ch.txt")
