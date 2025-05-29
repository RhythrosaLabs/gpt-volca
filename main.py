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

# Voice selection dropdown
voice_options = {
    "Wise Woman": "Wise_Woman",
    "Friendly Person": "Friendly_Person", 
    "Inspirational Girl": "Inspirational_girl",
    "Deep Voice Man": "Deep_Voice_Man",
    "Calm Woman": "Calm_Woman",
    "Casual Guy": "Casual_Guy",
    "Lively Girl": "Lively_Girl",
    "Patient Man": "Patient_Man",
    "Young Knight": "Young_Knight",
    "Determined Man": "Determined_Man",
    "Lovely Girl": "Lovely_Girl",
    "Decent Boy": "Decent_Boy",
    "Imposing Manner": "Imposing_Manner",
    "Elegant Man": "Elegant_Man",
    "Abbess": "Abbess",
    "Sweet Girl 2": "Sweet_Girl_2",
    "Exuberant Girl": "Exuberant_Girl"
}

# Video quality settings
st.subheader("Video Settings")
col1, col2 = st.columns(2)

with col1:
    video_style = st.selectbox(
        "Video Style:",
        ["Documentary", "Cinematic", "Educational", "Modern", "Nature", "Scientific"],
        help="Choose the visual style for your video"
    )
    
    num_frames = st.selectbox(
        "Video Quality:",
        [("Standard (120 frames)", 120), ("High (200 frames)", 200)],
        format_func=lambda x: x[0]
    )[1]

with col2:
    selected_voice = st.selectbox(
        "Choose a voice for your voiceover:",
        options=list(voice_options.keys()),
        index=0,
        help="Select the voice that will narrate your video"
    )
    
    selected_emotion = st.selectbox(
        "Voice emotion:",
        options=emotion_options,
        index=0,
        help="Select the emotional tone for the voiceover"
    )

if replicate_api_key and video_topic and st.button("Generate 20s Video"):
    replicate_client = replicate.Client(api_token=replicate_api_key)

    def run_replicate(model_path, input_data):
        return replicate_client.run(model_path, input=input_data)

    st.info("Step 1: Writing cohesive script for full video")
    full_script = run_replicate(
        "anthropic/claude-4-sonnet",
        {
            "prompt": (
                f"You are an expert video scriptwriter. Write a clear, engaging, thematically consistent voiceover script for a 20-second educational video titled '{video_topic}'. "
                "The video will be 20 seconds long; divide your script into 4 segments of approximately 5 seconds each. "
                "Each segment should be 8-12 words (about 1.5-2 seconds of speech per segment, allowing for pacing). "
                "Make sure the 4 segments tell a cohesive, progressive story that builds toward a compelling conclusion. "
                "Use vivid, concrete language that translates well to visuals. Include specific details, numbers, or comparisons when relevant. "
                "Label each section clearly as '1:', '2:', '3:', and '4:'. "
                "Write in an engaging, conversational tone that keeps viewers hooked. Avoid generic statements."
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
        # Create more detailed, cinematic prompts
        if i == 0:
            shot_type = "establishing wide shot"
        elif i == 1:
            shot_type = "medium shot with focus on key elements"
        elif i == 2:
            shot_type = "close-up shot showing important details"
        else:
            shot_type = "dynamic concluding shot"
            
        video_prompt = f"Cinematic {shot_type} for educational video about '{video_topic}'. Visual content: {segment}. Style: clean, professional, well-lit, documentary quality. Camera movement: smooth, purposeful. No text overlays."
        try:
            video_uri = run_replicate(
                "luma/ray-flash-2-540p",
                {
                    "prompt": video_prompt, 
                    "num_frames": num_frames, 
                    "fps": 24,
                    "guidance": 3.0,  # Higher guidance for better prompt adherence
                    "num_inference_steps": 30  # More steps for better quality
                },
            )
            video_path = download_to_file(video_uri, suffix=".mp4")
            temp_video_paths.append(video_path)

            # Ensure 5s per segment for a total of 20s
            clip = VideoFileClip(video_path).subclip(0, 5)
            segment_clips.append(clip)

            st.video(video_path)
            st.download_button(f"🎥 Download Segment {i+1}", video_path, f"segment_{i+1}.mp4")
        except Exception as e:
            st.error(f"Failed to generate or download segment {i+1} video: {e}")
            st.stop()

    # Step 4: Generate voiceover with selected voice
    st.info(f"Step 4: Generating voiceover narration with {selected_voice} voice")
    full_narration = " ".join(script_segments)
    try:
        voiceover_uri = run_replicate(
            "minimax/speech-02-hd",
            {
                "text": full_narration, 
                "voice_id": voice_options[selected_voice],
                "emotion": selected_emotion,
                "speed": 1,
                "pitch": 0,
                "volume": 1,
                "bitrate": 128000,
                "channel": "mono",
                "sample_rate": 32000,
                "language_boost": "English",
                "english_normalization": True
            },
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
        # Ensure the final video duration is exactly 20 seconds
        final_video = final_video.set_duration(20)
        final_duration = final_video.duration

        voice_clip = AudioFileClip(voice_path)
        music_clip = AudioFileClip(music_path).volumex(0.3)

        # Center the voiceover and music within the 20-second video
        # Calculate padding needed
        voice_padding = max(0, (final_duration - voice_clip.duration) / 2)
        music_padding = max(0, (final_duration - music_clip.duration) / 2)

        # Apply padding and ensure audio clips are exactly 20 seconds
        voice_clip = voice_clip.set_start(voice_padding).set_duration(final_duration)
        music_clip = music_clip.set_start(music_padding).set_duration(final_duration)

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
