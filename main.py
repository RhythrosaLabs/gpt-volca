import streamlit as st
import replicate
import tempfile
import os
import requests
from moviepy.editor import (
    VideoFileClip,
    concatenate_videoclips,
    AudioFileClip,
    CompositeAudioClip,
)

st.title("AI Multi-Agent Video Creator")

# Input: Replicate API key and video topic
replicate_api_key = st.text_input("Enter your Replicate API Key", type="password")
video_topic = st.text_input("Enter a video topic (e.g., 'Why the earth rotates')")

if replicate_api_key and video_topic and st.button("Generate 20s Video"):
    replicate_client = replicate.Client(api_token=replicate_api_key)

    def run_replicate(model_path, input_data):
        return replicate_client.run(model_path, input=input_data)

    st.info("Step 1: Writing full script")
    full_script = run_replicate(
        "anthropic/claude-4-sonnet",
        {
            "prompt": (
                f"Write a precise, vivid, emotionally engaging narration for a 20 second "
                f"video on the topic: '{video_topic}', broken into four 5-second segments "
                "clearly marked as 1, 2, 3, 4. Keep timing and pacing in mind."
            )
        },
    )

    # Safely convert output to string
    script_text = "".join(full_script) if isinstance(full_script, list) else full_script
    script_parts = script_text.split("\n")
    script_segments = [s.strip() for s in script_parts if s.strip()][:4]

    st.success("Script written successfully")

    temp_video_paths = []

    # helper to download a URL into a temp file
    def download_to_file(url: str, suffix: str):
        resp = requests.get(url, stream=True)
        resp.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        with open(tmp.name, "wb") as f:
            for chunk in resp.iter_content(1024 * 32):
                f.write(chunk)
        return tmp.name

    # Generate segment videos
    for i, segment in enumerate(script_segments):
        st.info(f"Step 2.{i+1}: Generating video for segment {i+1}")
        video_uri = run_replicate(
            "luma/ray-flash-2-540p",
            {"prompt": segment, "num_frames": 120, "fps": 24},
        )
        try:
            video_path = download_to_file(video_uri, suffix=".mp4")
        except Exception as e:
            st.error(f"Failed to download segment {i+1} video: {e}")
            st.stop()
        temp_video_paths.append(video_path)

    st.info("Step 3: Concatenating videos")
    clips = [VideoFileClip(path) for path in temp_video_paths]
    # ensure same size/fps
    final_video = concatenate_videoclips(clips, method="compose")
    final_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    final_video.write_videofile(final_video_path, codec="libx264", audio=False)
    st.success("20-second video created")

    st.info("Step 4: Generating voiceover")
    voiceover_uri = run_replicate(
        "minimax/speech-02-hd",
        {"text": " ".join(script_segments), "voice": "default"},
    )
    try:
        voice_path = download_to_file(voiceover_uri, suffix=".mp3")
    except Exception as e:
        st.error(f"Failed to download voiceover: {e}")
        st.stop()

    st.info("Step 5: Generating music")
    music_uri = run_replicate(
        "google/lyria-2",
        {"prompt": f"Generate background music suitable for a {video_topic} video lasting 20 seconds."},
    )
    try:
        music_path = download_to_file(music_uri, suffix=".mp3")
    except Exception as e:
        st.error(f"Failed to download music: {e}")
        st.stop()

    st.info("Step 6: Merging audio")
    # reload the silent video
    video_clip = VideoFileClip(final_video_path)
    duration = video_clip.duration

    # load audio clips and force duration to match video
    voice_clip = AudioFileClip(voice_path).subclip(0, duration).set_duration(duration)
    music_clip = AudioFileClip(music_path).subclip(0, duration).set_duration(duration).volumex(0.3)

    final_audio = CompositeAudioClip([voice_clip, music_clip])
    video_with_audio = video_clip.set_audio(final_audio)

    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    try:
        video_with_audio.write_videofile(
            output_path, codec="libx264", audio_codec="aac", temp_audiofile="temp-audio.m4a", remove_temp=True
        )
    except Exception as e:
        st.error(f"Error writing final video: {e}")
        st.stop()

    st.success("Final video with music and voiceover ready")
    st.video(output_path)

    # Cleanup temp files
    for path in (*temp_video_paths, final_video_path, voice_path, music_path):
        try:
            os.remove(path)
        except OSError:
            pass
