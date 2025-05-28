import streamlit as st
import requests
import tempfile
import os
from moviepy.editor import concatenate_videoclips, AudioFileClip, VideoFileClip

# Set up the Streamlit interface
st.title("AI-Powered 20s Video Creator")
st.markdown("Enter your Replicate API key and a topic to generate a 20-second video with script, visuals, music, and voiceover.")

api_key = st.text_input("Replicate API Key", type="password")
topic = st.text_input("Video Topic")

if st.button("Generate Video"):
    if not api_key or not topic:
        st.error("Please enter both API Key and a topic.")
    else:
        headers = {"Authorization": f"Token {api_key}"}

        # Step 1: Script writing
        st.info("Generating script...")
        script_prompt = f"Write a 20 second educational video script for this topic: {topic}. Break it into 4 parts of 5 seconds each."
        script_response = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers=headers,
            json={
                "version": "anthropic/claude-4-sonnet",
                "input": {"prompt": script_prompt}
            }
        )
        script_text = script_response.json().get("output", "").strip()
        sections = script_text.split("\n")[:4]  # assume each section is on a new line

        st.success("Script generated:")
        for idx, sec in enumerate(sections):
            st.markdown(f"**Part {idx+1}:** {sec}")

        # Step 2: Generate video for each section
        video_clips = []
        st.info("Generating video clips...")
        for idx, sec in enumerate(sections):
            video_input = f"Create a 5 second cinematic video about: {sec}"
            vid_resp = requests.post(
                "https://api.replicate.com/v1/predictions",
                headers=headers,
                json={
                    "version": "luma/ray-flash-2-540p",
                    "input": {"prompt": video_input}
                }
            )
            vid_url = vid_resp.json().get("output", "")
            vid_path = tempfile.mktemp(suffix=".mp4")
            with open(vid_path, "wb") as f:
                f.write(requests.get(vid_url).content)
            video_clips.append(VideoFileClip(vid_path))

        final_video = concatenate_videoclips(video_clips)
        final_video_path = tempfile.mktemp(suffix="_final.mp4")
        final_video.write_videofile(final_video_path)

        # Step 3: Voiceover
        st.info("Generating voiceover...")
        voice_prompt = " ".join(sections)
        voice_resp = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers=headers,
            json={
                "version": "minimax/speech-02-hd",
                "input": {"text": voice_prompt, "language": "en"}
            }
        )
        voice_url = voice_resp.json().get("output", "")
        voice_path = tempfile.mktemp(suffix=".mp3")
        with open(voice_path, "wb") as f:
            f.write(requests.get(voice_url).content)

        # Step 4: Music
        st.info("Generating background music...")
        music_prompt = f"Background music for a {topic} educational video. 20 seconds."
        music_resp = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers=headers,
            json={
                "version": "google/lyria-2",
                "input": {"prompt": music_prompt}
            }
        )
        music_url = music_resp.json().get("output", "")
        music_path = tempfile.mktemp(suffix=".mp3")
        with open(music_path, "wb") as f:
            f.write(requests.get(music_url).content)

        # Combine audio and video
        st.info("Combining everything into final video...")
        video_clip = VideoFileClip(final_video_path)
        voice_audio = AudioFileClip(voice_path).volumex(1.0)
        music_audio = AudioFileClip(music_path).volumex(0.3)
        final_audio = voice_audio.audio_fadein(1).set_duration(video_clip.duration).fx(lambda clip: clip.set_audio(music_audio))
        video_clip = video_clip.set_audio(voice_audio.set_duration(video_clip.duration))

        output_path = tempfile.mktemp(suffix="_output.mp4")
        video_clip.write_videofile(output_path)

        st.success("Video creation complete!")
        st.video(output_path)

        # Cleanup
        for path in [voice_path, music_path, final_video_path] + [clip.filename for clip in video_clips]:
            os.remove(path)
