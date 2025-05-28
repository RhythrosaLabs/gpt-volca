import streamlit as st
import requests
import time
import os
import tempfile
import subprocess
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip, CompositeAudioClip

st.title("AI Video Generator (Replicate)")

replicate_api_key = st.text_input("Enter your Replicate API Key", type="password")
topic = st.text_input("Enter your video topic (e.g. 'deep sea exploration')")

if replicate_api_key and topic:
    headers = {
        "Authorization": f"Token {replicate_api_key}",
        "Content-Type": "application/json"
    }

    def call_replicate(version, input_payload):
        # Create the prediction
        create_resp = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers=headers,
            json={"version": version, "input": input_payload}
        )
        if create_resp.status_code != 201:
            st.error(f"Failed to create prediction: {create_resp.text}")
            st.stop()

        prediction = create_resp.json()
        prediction_id = prediction["id"]

        # Poll until completion
        while prediction["status"] not in ["succeeded", "failed", "canceled"]:
            time.sleep(1)
            poll_resp = requests.get(
                f"https://api.replicate.com/v1/predictions/{prediction_id}",
                headers=headers
            )
            prediction = poll_resp.json()

        if prediction["status"] != "succeeded":
            st.error(f"Prediction failed: {prediction}")
            st.stop()

        return prediction["output"]

    st.info("Generating script...")
    script_prompt = f"Write a 20-second educational video script for the topic: '{topic}'. Break it into 4 parts of 5 seconds each."
    script_text = call_replicate(
        "anthropic/claude-4-sonnet",
        {"prompt": script_prompt}
    )

    if isinstance(script_text, list):
        script_text = script_text[0]

    st.success("Script generated:")
    st.write(script_text)

    sections = [s.strip() for s in script_text.split("\n") if s.strip()][:4]
    
    # Generate 4 video clips
    video_clips = []
    for i, section in enumerate(sections):
        st.info(f"Generating video clip {i+1}...")
        video_url = call_replicate(
            "luma/ray-flash-2-540p",
            {"prompt": section, "num_frames": 150, "fps": 30}  # 5 seconds @ 30 fps
        )
        if isinstance(video_url, list):
            video_url = video_url[0]

        video_path = os.path.join(tempfile.gettempdir(), f"clip_{i}.mp4")
        with open(video_path, "wb") as f:
            f.write(requests.get(video_url).content)
        video_clips.append(VideoFileClip(video_path))

    # Concatenate videos
    st.info("Combining video clips...")
    final_video = concatenate_videoclips(video_clips)
    video_output_path = os.path.join(tempfile.gettempdir(), "final_video.mp4")
    final_video.write_videofile(video_output_path, codec='libx264')

    # Generate VoiceOver
    st.info("Generating voiceover...")
    full_script = " ".join(sections)
    voice_url = call_replicate(
        "minimax/speech-02-hd",
        {"text": full_script, "voice": "en_us_001"}
    )
    if isinstance(voice_url, list):
        voice_url = voice_url[0]

    voice_path = os.path.join(tempfile.gettempdir(), "voice.mp3")
    with open(voice_path, "wb") as f:
        f.write(requests.get(voice_url).content)
    voice_audio = AudioFileClip(voice_path)

    # Generate music
    st.info("Generating background music...")
    music_url = call_replicate(
        "google/lyria-2",
        {"prompt": f"background music for {topic}", "duration": 20}
    )
    if isinstance(music_url, list):
        music_url = music_url[0]

    music_path = os.path.join(tempfile.gettempdir(), "music.mp3")
    with open(music_path, "wb") as f:
        f.write(requests.get(music_url).content)
    music_audio = AudioFileClip(music_path).volumex(0.3)  # Lower music volume

    # Combine audio
    st.info("Combining voice and music...")
    final_audio = CompositeAudioClip([voice_audio, music_audio.set_start(0)])
    final_video = final_video.set_audio(final_audio)

    full_output_path = os.path.join(tempfile.gettempdir(), "final_with_audio.mp4")
    final_video.write_videofile(full_output_path, codec="libx264", audio_codec="aac")

    st.success("Video generation complete!")
    st.video(full_output_path)
    st.download_button("Download Video", open(full_output_path, "rb"), file_name="final_video.mp4")
