import streamlit as st

st.set_page_config(page_title="AI Video Creator", layout="centered")

st.title("AI-Powered 20-Second Video Creator")
st.markdown(
    """
    Enter your Replicate API key and a video topic. The app will:
    1. Write a script for a 20-second video on your topic.
    2. Break the script into 4 timed sections.
    3. Generate 4 videos (5 seconds each) using Replicate's Luma Ray Flash.
    4. Concatenate the videos.
    5. Generate a voiceover and music.
    6. Combine everything into a single, cohesive 20-second video.
    """
)

with st.form("video_form"):
    api_key = st.text_input("Replicate API Key", type="password")
    topic = st.text_input("Video Topic", placeholder="e.g. why the earth rotates")
    submitted = st.form_submit_button("Create Video")

import requests
import time
import tempfile
import os
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip, CompositeAudioClip

def call_replicate(api_key, version, input_dict):
    url = f"https://api.replicate.com/v1/predictions"
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "version": version,
        "input": input_dict
    }
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()
    prediction = response.json()
    prediction_id = prediction["id"]

    # Poll for completion
    while prediction["status"] not in ["succeeded", "failed", "canceled"]:
        time.sleep(2)
        poll = requests.get(f"{url}/{prediction_id}", headers=headers)
        poll.raise_for_status()
        prediction = poll.json()
    if prediction["status"] != "succeeded":
        raise Exception(f"Replicate prediction failed: {prediction['status']}")
    return prediction["output"]

def download_file(url, suffix):
    response = requests.get(url)
    response.raise_for_status()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(response.content)
    tmp.close()
    return tmp.name

if submitted:
    if not api_key or not topic:
        st.error("Please provide both your Replicate API key and a video topic.")
    else:
        st.info("Starting multi-agent video creation process...")

        # 1. Script writing (Claude 4 Sonnet)
        st.write("Generating script...")
        try:
            script_output = call_replicate(
                api_key,
                "b8b6b6e8b1e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2",  # Placeholder version
                {
                    "prompt": f"Write a script for a 20 second educational video on: {topic}. The script should be split into 4 sections, each 5 seconds, and clearly indicate the text for each section."
                }
            )
            # Assume output is a string with 4 sections
            script_sections = script_output.split("\n\n")
            if len(script_sections) < 4:
                st.error("Script generation failed to produce 4 sections.")
                st.stop()
        except Exception as e:
            st.error(f"Script generation failed: {e}")
            st.stop()

        st.success("Script generated!")
        for i, section in enumerate(script_sections):
            st.markdown(f"**Section {i+1}:** {section}")

        # 2. Generate 4 videos (Luma Ray Flash 2)
        video_urls = []
        for i, section in enumerate(script_sections):
            st.write(f"Generating video for section {i+1}...")
            try:
                video_url = call_replicate(
                    api_key,
                    "c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3",  # Placeholder version
                    {
                        "prompt": f"Create a 5 second video for: {section}",
                        "duration": 5
                    }
                )
                video_urls.append(video_url)
            except Exception as e:
                st.error(f"Video generation failed for section {i+1}: {e}")
                st.stop()

        # Download and concatenate videos
        st.write("Concatenating videos...")
        video_files = []
        for url in video_urls:
            video_files.append(download_file(url, ".mp4"))
        clips = [VideoFileClip(f) for f in video_files]
        final_video = concatenate_videoclips(clips, method="compose")
        temp_video_path = tempfile.mktemp(suffix=".mp4")
        final_video.write_videofile(temp_video_path, codec="libx264", audio=False, fps=24)
        for clip in clips:
            clip.close()

        # 3. Generate voiceover (Minimax Speech)
        st.write("Generating voiceover...")
        try:
            voiceover_url = call_replicate(
                api_key,
                "d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4",  # Placeholder version
                {
                    "text": "\n".join(script_sections),
                    "duration": 20
                }
            )
            voiceover_file = download_file(voiceover_url, ".mp3")
        except Exception as e:
            st.error(f"Voiceover generation failed: {e}")
            st.stop()

        # 4. Generate music (Google Lyria 2)
        st.write("Generating background music...")
        try:
            music_url = call_replicate(
                api_key,
                "e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5",  # Placeholder version
                {
                    "prompt": f"Background music for a 20 second video about: {topic}",
                    "duration": 20
                }
            )
            music_file = download_file(music_url, ".mp3")
        except Exception as e:
            st.error(f"Music generation failed: {e}")
            st.stop()

        # 5. Combine video, voiceover, and music
        st.write("Combining video, voiceover, and music...")
        try:
            video_clip = VideoFileClip(temp_video_path)
            voiceover_clip = AudioFileClip(voiceover_file)
            music_clip = AudioFileClip(music_file).volumex(0.3)
            composite_audio = CompositeAudioClip([music_clip, voiceover_clip])
            final = video_clip.set_audio(composite_audio)
            final_path = tempfile.mktemp(suffix=".mp4")
            final.write_videofile(final_path, codec="libx264", audio_codec="aac", fps=24)
            video_clip.close()
            voiceover_clip.close()
            music_clip.close()
        except Exception as e:
            st.error(f"Failed to combine video and audio: {e}")
            st.stop()

        st.success("Video creation complete!")
        st.video(final_path)
