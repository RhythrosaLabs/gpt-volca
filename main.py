import streamlit as st
import replicate
import tempfile
import os
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip, CompositeAudioClip

st.title("AI Multi-Agent Video Creator")

# Input: Replicate API key and video topic
replicate_api_key = st.text_input("Enter your Replicate API Key", type="password")
video_topic = st.text_input("Enter a video topic (e.g., 'Why the earth rotates')")

if replicate_api_key and video_topic and st.button("Generate 20s Video"):
    replicate_client = replicate.Client(api_token=replicate_api_key)

    def run_replicate(model_path, input_data):
        return replicate_client.run(model_path, input=input_data)

    st.info("Step 1: Writing full script")
    full_script = run_replicate("anthropic/claude-4-sonnet", {
        "prompt": f"Write a precise, vivid, emotionally engaging narration for a 20 second video on the topic: '{video_topic}', broken into four 5-second segments clearly marked as 1, 2, 3, 4. Keep timing and pacing in mind."
    })

    st.success("Script written successfully")

    # Extract 4 sections from script
    script_parts = full_script.split("\n")
    script_segments = [s.strip() for s in script_parts if s.strip()][:4]

    temp_video_paths = []

    for i, segment in enumerate(script_segments):
        st.info(f"Step 2.{i+1}: Generating video for segment {i+1}")
        video_uri = run_replicate("luma/ray-flash-2-540p", {
            "prompt": segment,
            "num_frames": 120,  # 5 seconds * 24fps
            "fps": 24
        })
        
        video_url = video_uri  # assume it's a direct URL
        video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
        os.system(f"curl -o {video_path} '{video_url}'")
        temp_video_paths.append(video_path)

    st.info("Step 3: Concatenating videos")
    clips = [VideoFileClip(path) for path in temp_video_paths]
    final_video = concatenate_videoclips(clips)
    final_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    final_video.write_videofile(final_video_path, codec="libx264")

    st.success("20-second video created")

    st.info("Step 4: Generating voiceover")
    voiceover_uri = run_replicate("minimax/speech-02-hd", {
        "text": " ".join(script_segments),
        "voice": "default"
    })
    voice_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
    os.system(f"curl -o {voice_path} '{voiceover_uri}'")

    st.info("Step 5: Generating music")
    music_uri = run_replicate("google/lyria-2", {
        "prompt": f"Generate background music suitable for a {video_topic} video lasting 20 seconds."
    })
    music_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
    os.system(f"curl -o {music_path} '{music_uri}'")

    st.info("Step 6: Merging audio")
    video_clip = VideoFileClip(final_video_path)
    voice_clip = AudioFileClip(voice_path).subclip(0, video_clip.duration)
    music_clip = AudioFileClip(music_path).volumex(0.3).subclip(0, video_clip.duration)
    final_audio = CompositeAudioClip([voice_clip, music_clip])
    video_clip = video_clip.set_audio(final_audio)

    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    video_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")

    st.success("Final video with music and voiceover ready")
    st.video(output_path)

    # Cleanup (optional)
    for path in temp_video_paths:
        os.remove(path)
    os.remove(voice_path)
    os.remove(music_path)
    os.remove(final_video_path)
