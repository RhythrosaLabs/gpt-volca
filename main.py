import streamlit as st
import requests
import time
import moviepy.editor as mpe
import os

st.title("🎬 Multi-Agent AI Video Creator (Replicate)")

replicate_api = st.text_input("🔑 Enter Replicate API Key", type="password")
topic = st.text_input("🎯 Enter your video topic", placeholder="e.g., why the earth rotates")

if replicate_api and topic and st.button("Generate Video"):
    headers = {
        "Authorization": f"Token {replicate_api}",
        "Content-Type": "application/json"
    }

    # Step 1: Generate script
    with st.spinner("📝 Writing script..."):
        script_prompt = f"Write a short 20-second video script about '{topic}', broken into 4 short lines. Each line represents a 5-second segment."
        script_response = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers=headers,
            json={
                "version": "5050b99e78aa0fcfb6e9fb366c47f32b211f7c5a46f12de334e52893762c1b30",  # Claude 4 Sonnet
                "input": {"prompt": script_prompt}
            }
        )
        script_text = script_response.json().get("output", "").strip() if script_response.ok else ""

        if not script_text:
            st.error("❌ Script generation failed.")
            st.stop()

        sections = [s.strip() for s in script_text.split("\n") if len(s.strip()) >= 3][:4]
        while len(sections) < 4:
            sections.append(f"This part continues the topic: {topic}")
        st.success("✅ Script generated!")

    st.write("### Script:")
    for i, line in enumerate(sections):
        st.markdown(f"**Part {i+1}**: {line}")

    # Step 2: Generate 4 videos
    video_paths = []
    for i, section in enumerate(sections):
        with st.spinner(f"🎥 Generating video {i+1}/4..."):
            video_response = requests.post(
                "https://api.replicate.com/v1/predictions",
                headers=headers,
                json={
                    "version": "9c08c0b33d8174a8588b4ac289d9a20345f1fc3912c6524f31f53ccfa37e17e1",  # Luma Ray Flash
                    "input": {
                        "prompt": section,
                        "fps": 30,
                        "num_frames": 150
                    }
                }
            )
            prediction = video_response.json()
            status = prediction.get("status")
            prediction_url = prediction.get("urls", {}).get("get")

            if not prediction_url:
                st.error("❌ Failed to start video generation.")
                st.stop()

            # Poll for completion
            while status not in ["succeeded", "failed"]:
                time.sleep(2)
                poll_response = requests.get(prediction_url, headers=headers)
                prediction = poll_response.json()
                status = prediction.get("status")

            if status == "succeeded":
                video_url = prediction["output"]
                video_path = f"video_part_{i}.mp4"
                with open(video_path, "wb") as f:
                    f.write(requests.get(video_url).content)
                video_paths.append(video_path)
            else:
                st.error(f"❌ Video part {i+1} failed: {prediction.get('error', 'Unknown error')}")
                st.stop()

    # Step 3: Concatenate all video parts
    with st.spinner("📽️ Concatenating videos..."):
        clips = [mpe.VideoFileClip(path) for path in video_paths]
        final_video = mpe.concatenate_videoclips(clips)
        final_video_path = "final_video.mp4"
        final_video.write_videofile(final_video_path, codec="libx264")
        [clip.close() for clip in clips]

    # Step 4: Generate VoiceOver
    with st.spinner("🎙️ Generating voiceover..."):
        voice_input = {"text": " ".join(sections)}
        voice_response = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers=headers,
            json={
                "version": "bc1f13760386b1360d82898a379c71c273b94df4b73389c66ef4e4ccaa1d3fd6",  # Minimax Speech 02 HD
                "input": voice_input
            }
        )
        voice_url = voice_response.json().get("output")
        if not voice_url:
            st.error("❌ Voice generation failed.")
            st.stop()
        voice_path = "voiceover.mp3"
        with open(voice_path, "wb") as f:
            f.write(requests.get(voice_url).content)

    # Step 5: Generate music
    with st.spinner("🎵 Generating background music..."):
        music_input = {"prompt": f"Background cinematic music for a video about {topic}", "duration": 20}
        music_response = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers=headers,
            json={
                "version": "9a4b6f857ca96d772a0cdfe952515c2c9fc291e3df812d66cc7c09ebd7ac221c",  # Google Lyria 2
                "input": music_input
            }
        )
        music_url = music_response.json().get("output")
        if not music_url:
            st.error("❌ Music generation failed.")
            st.stop()
        music_path = "music.mp3"
        with open(music_path, "wb") as f:
            f.write(requests.get(music_url).content)

    # Step 6: Combine video + voice + music
    with st.spinner("🎬 Finalizing video..."):
        video = mpe.VideoFileClip(final_video_path)
        voice_audio = mpe.AudioFileClip(voice_path).volumex(1.0)
        music_audio = mpe.AudioFileClip(music_path).volumex(0.2)
        final_audio = mpe.CompositeAudioClip([voice_audio, music_audio])
        video = video.set_audio(final_audio)
        final_output_path = "final_output.mp4"
        video.write_videofile(final_output_path, codec="libx264", audio_codec="aac")
        video.close()

    st.success("✅ Your video is ready!")
    st.video(final_output_path)

    # Clean up temporary files
    for path in video_paths + [final_video_path, voice_path, music_path]:
        os.remove(path)
