from flask import Flask, render_template, request, send_file, redirect, flash
from werkzeug.utils import secure_filename
import math
import sys
import subprocess
import os
import shutil
from moviepy.editor import AudioClip, VideoFileClip, concatenate_videoclips

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = set(['mp4'])

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in app.config['ALLOWED_EXTENSIONS']

def find_speaking(audio_clip, window_size=0.1, volume_threshold=0.01, ease_in=0.25):
    # First, iterate over audio to find all silent windows.
    num_windows = math.floor(audio_clip.end/window_size)
    window_is_silent = []
    for i in range(num_windows):
        s = audio_clip.subclip(i * window_size, (i + 1) * window_size)
        v = s.max_volume()
        window_is_silent.append(v < volume_threshold)

    # Find speaking intervals.
    speaking_start = 0
    speaking_end = 0
    speaking_intervals = []
    for i in range(1, len(window_is_silent)):
        e1 = window_is_silent[i - 1]
        e2 = window_is_silent[i]
        # silence -> speaking
        if e1 and not e2:
            speaking_start = i * window_size
        # speaking -> silence, now have a speaking interval
        if not e1 and e2:
            speaking_end = i * window_size
            new_speaking_interval = [speaking_start - ease_in, speaking_end + ease_in]
            # With tiny windows, this can sometimes overlap the previous window, so merge.
            need_to_merge = len(speaking_intervals) > 0 and speaking_intervals[-1][1] > new_speaking_interval[0]
            if need_to_merge:
                merged_interval = [speaking_intervals[-1][0], new_speaking_interval[1]]
                speaking_intervals[-1] = merged_interval
            else:
                speaking_intervals.append(new_speaking_interval)

    return speaking_intervals

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/', methods=['POST'])
def upload_file():
    # check if the post request has the file part
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    file = request.files['file']
    # if user does not select file, browser also
    # submit an empty part without filename
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        input_file = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        vid = VideoFileClip(input_file)
        intervals_to_keep = find_speaking(vid.audio)
        
        keep_clips = [vid.subclip(max(start, 0), end) for [start, end] in intervals_to_keep]
        output_file = os.path.join(app.config['UPLOAD_FOLDER'], 'output.mp4')
        edited_video = concatenate_videoclips(keep_clips)
        edited_video.write_videofile(output_file,
            fps=60,
            preset='ultrafast',
            codec='libx264',
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            audio_codec="aac",
            threads=6
        )

        vid.close()
        
        return send_file(output_file, as_attachment=True)
    else:
        flash('Invalid file format')
        return redirect(request.url)

if __name__ == '__main__':
    app.run(debug=True)


