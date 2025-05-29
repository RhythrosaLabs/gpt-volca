import streamlit as st
import requests
import time
import moviepy.editor as mpe
import os
import tempfile

st.title("🎬 Multi-Agent AI Video Creator (Replicate)")

replicate_api = st.text_input("🔑 Enter Replicate API Key", type="password")
topic = st.text_input("🎯 Enter your video topic", placeholder="e.g., why the earth rotates")

def poll_prediction(prediction_url, headers, max_wait=300):
    """Poll Replicate prediction until completion"""
    start_time = time.time()
    while time.time() - start_time < max_wait:
        response = requests.get(prediction_url, headers=headers)
        if response.status_code != 200:
            return None
        
        prediction = response.json()
        status = prediction.get("status")
        
        if status == "succeeded":
            return prediction.get("output")
        elif status == "failed":
            st.error(f"❌ Prediction failed: {prediction.get('error', 'Unknown error')}")
            return None
        
        time.sleep(3)
    
    st.error("❌ Prediction timed out")
    return None

if replicate_api and topic and st.button("Generate Video"):
    headers = {
        "Authorization": f"Token {replicate_api}",
        "Content-Type": "application/json"
    }

    try:
        # Step 1: Generate script
        with st.spinner("📝 Writing script..."):
            script_prompt = f"Write a short 20-second video script about '{topic}'. Break it into exactly 4 short sentences, each representing a 5-second segment. Format as numbered list: 1. [sentence] 2. [sentence] 3. [sentence] 4. [sentence]"
            
            script_response = requests.post(
                "https://api.replicate.com/v1/predictions",
                headers=headers,
                json={
                    "version": "35042c9a33ac8fd5e29e27fb3197f33aa483f72c2ce3b0b9d201155c7fd2a287",  # Meta Llama 3.1 405B
                    "input": {
                        "prompt": script_prompt,
                        "max_tokens": 200
                    }
                }
            )
            
            if script_response.status_code != 201:
                st.error(f"❌ Script generation failed: {script_response.text}")
                st.stop()
            
            prediction = script_response.json()
            script_output = poll_prediction(prediction["urls"]["get"], headers)
            
            if not script_output:
                st.error("❌ Script generation failed.")
                st.stop()
            
            # Extract script text from output
            if isinstance(script_output, list):
                script_text = "".join(script_output)
            else:
                script_text = str(script_output)
            
            # Parse the script into sections
            lines = script_text.split('\n')
            sections = []
            for line in lines:
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                    # Remove numbering and clean up
                    clean_line = line.split('.', 1)[-1].strip() if '.' in line else line
                    clean_line = clean_line.lstrip('-•').strip()
                    if len(clean_line) > 10:  # Ensure meaningful content
                        sections.append(clean_line)
            
            # Fallback if parsing fails
            if len(sections) < 4:
                sections = [
                    f"Introduction to {topic}",
                    f"Key aspects of {topic}",
                    f"Important details about {topic}",
                    f"Conclusion about {topic}"
                ]
            
            sections = sections[:4]  # Take only first 4
            st.success("✅ Script generated!")

        st.write("### Script:")
        for i, line in enumerate(sections):
            st.markdown(f"**Part {i+1}**: {line}")

        # Create temporary directory for files
        temp_dir = tempfile.mkdtemp()
        video_paths = []
        
        # Step 2: Generate 4 videos
        for i, section in enumerate(sections):
            with st.spinner(f"🎥 Generating video {i+1}/4..."):
                video_prompt = f"A cinematic shot illustrating: {section}. High quality, professional lighting, smooth camera movement."
                
                video_response = requests.post(
                    "https://api.replicate.com/v1/predictions",
                    headers=headers,
                    json={
                        "version": "1cec0b7267a4a9c30ba58e6f7ffc7d5d848e9a2c87d4dc56e7a7e04d77733a5c",  # Runway Gen-3 Alpha Turbo
                        "input": {
                            "prompt": video_prompt,
                            "duration": 5,
                            "ratio": "16:9"
                        }
                    }
                )
                
                if video_response.status_code != 201:
                    st.error(f"❌ Video {i+1} generation failed: {video_response.text}")
                    continue
                
                prediction = video_response.json()
                video_url = poll_prediction(prediction["urls"]["get"], headers, max_wait=600)
                
                if video_url:
                    video_path = os.path.join(temp_dir, f"video_part_{i}.mp4")
                    with open(video_path, "wb") as f:
                        video_content = requests.get(video_url)
                        f.write(video_content.content)
                    video_paths.append(video_path)
                    st.success(f"✅ Video {i+1} completed!")
                else:
                    st.error(f"❌ Video part {i+1} failed")

        if len(video_paths) == 0:
            st.error("❌ No videos were generated successfully.")
            st.stop()

        # Step 3: Concatenate videos
        with st.spinner("📽️ Concatenating videos..."):
            clips = []
            for path in video_paths:
                if os.path.exists(path):
                    clip = mpe.VideoFileClip(path)
                    clips.append(clip)
            
            if clips:
                final_video = mpe.concatenate_videoclips(clips, method="compose")
                final_video_path = os.path.join(temp_dir, "final_video.mp4")
                final_video.write_videofile(final_video_path, codec="libx264", audio_codec="aac", temp_audiofile=os.path.join(temp_dir, "temp_audio.m4a"))
                
                # Close clips to free memory
                for clip in clips:
                    clip.close()
                final_video.close()
                st.success("✅ Videos concatenated!")

        # Step 4: Generate voiceover
        with st.spinner("🎙️ Generating voiceover..."):
            full_script = ". ".join(sections)
            
            voice_response = requests.post(
                "https://api.replicate.com/v1/predictions",
                headers=headers,
                json={
                    "version": "aefca5a3d99d4c509ffa117e15d00bf0cee5c86b1a6b67ee3d5b39f15e77e4a3",  # ElevenLabs TTS
                    "input": {
                        "text": full_script,
                        "voice": "chris"
                    }
                }
            )
            
            if voice_response.status_code == 201:
                prediction = voice_response.json()
                voice_url = poll_prediction(prediction["urls"]["get"], headers)
                
                if voice_url:
                    voice_path = os.path.join(temp_dir, "voiceover.mp3")
                    with open(voice_path, "wb") as f:
                        voice_content = requests.get(voice_url)
                        f.write(voice_content.content)
                    st.success("✅ Voiceover generated!")
                else:
                    voice_path = None
                    st.warning("⚠️ Voiceover generation failed, continuing without it.")
            else:
                voice_path = None
                st.warning("⚠️ Voiceover generation failed, continuing without it.")

        # Step 5: Generate background music
        with st.spinner("🎵 Generating background music..."):
            music_response = requests.post(
                "https://api.replicate.com/v1/predictions",
                headers=headers,
                json={
                    "version": "b05b1dff1d8c6dc63d14b0cdb42135378dcb87f6373b0d3d341ede46e59e2b38",  # MusicGen
                    "input": {
                        "prompt": f"Cinematic background music for {topic}, instrumental, ambient",
                        "duration": 20,
                        "continuation": False
                    }
                }
            )
            
            music_path = None
            if music_response.status_code == 201:
                prediction = music_response.json()
                music_url = poll_prediction(prediction["urls"]["get"], headers)
                
                if music_url:
                    music_path = os.path.join(temp_dir, "music.wav")
                    with open(music_path, "wb") as f:
                        music_content = requests.get(music_url)
                        f.write(music_content.content)
                    st.success("✅ Background music generated!")
                else:
                    st.warning("⚠️ Music generation failed, continuing without it.")
            else:
                st.warning("⚠️ Music generation failed, continuing without it.")

        # Step 6: Combine everything
        with st.spinner("🎬 Finalizing video..."):
            video = mpe.VideoFileClip(final_video_path)
            audio_clips = []
            
            # Add voiceover if available
            if voice_path and os.path.exists(voice_path):
                voice_audio = mpe.AudioFileClip(voice_path)
                # Adjust voice duration to match video
                if voice_audio.duration > video.duration:
                    voice_audio = voice_audio.subclip(0, video.duration)
                audio_clips.append(voice_audio.volumex(1.0))
            
            # Add background music if available
            if music_path and os.path.exists(music_path):
                music_audio = mpe.AudioFileClip(music_path)
                # Loop or trim music to match video duration
                if music_audio.duration < video.duration:
                    music_audio = music_audio.loop(duration=video.duration)
                else:
                    music_audio = music_audio.subclip(0, video.duration)
                audio_clips.append(music_audio.volumex(0.3))
            
            # Combine audio
            if audio_clips:
                final_audio = mpe.CompositeAudioClip(audio_clips)
                video = video.set_audio(final_audio)
            
            final_output_path = os.path.join(temp_dir, "final_output.mp4")
            video.write_videofile(
                final_output_path, 
                codec="libx264", 
                audio_codec="aac",
                temp_audiofile=os.path.join(temp_dir, "temp_final_audio.m4a")
            )
            video.close()
            
            # Clean up audio clips
            for clip in audio_clips:
                clip.close()

        st.success("✅ Your video is ready!")
        
        # Display the video
        if os.path.exists(final_output_path):
            st.video(final_output_path)
            
            # Offer download
            with open(final_output_path, "rb") as f:
                st.download_button(
                    label="📥 Download Video",
                    data=f.read(),
                    file_name="ai_generated_video.mp4",
                    mime="video/mp4"
                )

    except Exception as e:
        st.error(f"❌ An error occurred: {str(e)}")
        
    finally:
        # Clean up temporary files
        try:
            if 'temp_dir' in locals():
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass
