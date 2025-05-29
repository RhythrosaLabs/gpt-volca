import streamlit as st
import replicate
import tempfile
import os
import requests
import re
from moviepy.editor import (
    VideoFileClip,
    concatenate_videoclips,
    AudioFileClip,
    CompositeAudioClip,
)

st.title("AI Multi-Agent Video Creator")

replicate_api_key = st.text_input("Enter your Replicate API Key", type="password")
video_topic = st.text_input("Enter a video topic (e.g., 'Why the Earth rotates')")

if replicate_api_key and video_topic and st.button("Generate 20s Video"):
    replicate_client = replicate.Client(api_token=replicate_api_key)

    def run_replicate(model_path, input_data):
        return replicate_client.run(model_path, input=input_data)

    st.info("Step 1: Writing cohesive script for full video")
    full_script = run_replicate(
        "anthropic/claude-4-sonnet",
        {
            "prompt": (
                f"You are an expert video scriptwriter. Write a clear, engaging, thematically consistent voiceover script for a 10 second short educational video titled '{video_topic}'. "
                "The video will be 10 seconds long, so divide your script into 4 segments, each segment being 5 seconds. "
                "Make sure the 4 segments tell a cohesive, progressive mini-story or explanation that builds toward a final point. "
                "Label each section clearly as '1:', '2:', '3:', and '4:'. "
                "Avoid generic breathing or meditation cues. Stay strictly on-topic."
            )
        },
    )

    script_text = "".join(full_script) if isinstance(full_script, list) else full_script
    script_segments = re.findall(r"\d+:\s*(.+)", script_text)

    if len(script_segments) < 4:
        st.error("Failed to extract 4 clear script segments. Try adjusting your topic or refining the prompt.")
        st.stop()

    st.success("Script written successfully")
    script_file_path = tempfile.NamedTemporaryFile(delete=False, suffix=".txt").name
    with open(script_file_path, "w") as f:
        f.write("\n\n".join(script_segments))
    st.download_button("📜 Download Script", script_file_path, "script.txt")

    temp_video_paths = []

    def download_to_file(url: str, suffix: str):
        resp = requests.get(url, stream=True)
        resp.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        with open(tmp.name, "wb") as f:
            for chunk in resp.iter_content(1024 * 32):
                f.write(chunk)
        return tmp.name

    segment_clips = []

    # Step 2: Generate segment visuals
    for i, segment in enumerate(script_segments):
        st.info(f"Step 2.{i+1}: Generating visuals for segment {i+1}")
        video_prompt = f"Scene for a video about '{video_topic}'. This part should illustrate: {segment}"
        try:
            video_uri = run_replicate(
                "luma/ray-flash-2-540p",
                {"prompt": video_prompt, "num_frames": 120, "fps": 24},
            )
            video_path = download_to_file(video_uri, suffix=".mp4")
            temp_video_paths.append(video_path)

            # Ensure 5s per segment
            clip = VideoFileClip(video_path).subclip(0, 5)
            segment_clips.append(clip)

            st.video(video_path)
            st.download_button(f"🎥 Download Segment {i+1}", video_path, f"segment_{i+1}.mp4")
        except Exception as e:
            st.error(f"Failed to generate or download segment {i+1} video: {e}")
            st.stop()

    # Step 4: Generate voiceover
    st.info("Step 4: Generating voiceover narration")
    full_narration = " ".join(script_segments)
    try:
        voiceover_uri = run_replicate(
            "minimax/speech-02-hd",
            {"text": full_narration, "voice": "default"},
        )
        voice_path = download_to_file(voiceover_uri, suffix=".mp3")
        st.audio(voice_path)
        st.download_button("🎙 Download Voiceover", voice_path, "voiceover.mp3")
    except Exception as e:
        st.error(f"Failed to generate or download voiceover: {e}")
        st.stop()

    # Step 5: Generate background music
    st.info("Step 5: Creating background music")
    try:
        music_uri = run_replicate(
            "google/lyria-2",
            {"prompt": f"Background music for a cohesive, 20-second educational video about {video_topic}. Light, non-distracting, slightly cinematic tone."},
        )
        music_path = download_to_file(music_uri, suffix=".mp3")
        st.audio(music_path)
        st.download_button("🎵 Download Background Music", music_path, "background_music.mp3")
    except Exception as e:
        st.error(f"Failed to generate or download music: {e}")
        st.stop()

    # Step 6: Merge audio and video
    st.info("Step 6: Merging final audio and video")
    try:
        # Concatenate video clips
        final_video = concatenate_videoclips(segment_clips, method="compose")
        final_duration = final_video.duration  # Should be 20s

        voice_clip = AudioFileClip(voice_path).subclip(0, final_duration).set_duration(final_duration)
        music_clip = AudioFileClip(music_path).subclip(0, final_duration).set_duration(final_duration).volumex(0.3)
        final_audio = CompositeAudioClip([voice_clip, music_clip])

        final_video = final_video.set_audio(final_audio)

        output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
        final_video.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile="temp-audio.m4a",
            remove_temp=True,
            fps=24
        )

        st.success("🎬 Final video with narration and music is ready")
        st.video(output_path)
        st.download_button("📽 Download Final Video", output_path, "final_video.mp4")

    except Exception as e:
        st.warning("Final video merge failed, but you can still download individual assets.")
        st.error(f"Error writing final video: {e}")

    # Cleanup
    for path in (*temp_video_paths, voice_path, music_path, script_file_path):
        try:
            os.remove(path)
        except OSError:
            pass
