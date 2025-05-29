import streamlit as st
import requests
import time
import moviepy.editor as mpe
import os
import tempfile
import re

st.title("🎬 Multi-Agent AI Video Creator (Replicate)")

replicate_api = st.text_input("🔑 Enter Replicate API Key", type="password")
topic = st.text_input("🎯 Enter your video topic", placeholder="e.g., why the earth rotates")

def poll_prediction(prediction_url, headers, max_wait=300):
    """Poll Replicate prediction until completion"""
    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(prediction_url, headers=headers)
            if response.status_code != 200:
                st.error(f"❌ API Error: {response.status_code} - {response.text}")
                return None
            
            prediction = response.json()
            status = prediction.get("status")
            
            st.write(f"Status: {status}")  # Debug info
            
            if status == "succeeded":
                return prediction.get("output")
            elif status == "failed":
                error_msg = prediction.get("error", "Unknown error")
                st.error(f"❌ Prediction failed: {error_msg}")
                return None
            elif status in ["starting", "processing"]:
                st.write(f"⏳ {status.title()}...")
            
            time.sleep(3)
        except Exception as e:
            st.error(f"❌ Polling error: {str(e)}")
            return None
    
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
            script_prompt = f"""Write a short 20-second video script about '{topic}'. 
            Break it into exactly 4 short sentences, each representing a 5-second segment. 
            Format as a numbered list:
            1. [First sentence]
            2. [Second sentence] 
            3. [Third sentence]
            4. [Fourth sentence]
            
            Keep each sentence under 15 words and focused on visual descriptions."""
            
            # Updated Llama model version
            script_response = requests.post(
                "https://api.replicate.com/v1/predictions",
                headers=headers,
                json={
                    "version": "meta/meta-llama-3-8b-instruct",  # Updated model reference
                    "input": {
                        "prompt": script_prompt,
                        "max_new_tokens": 200,
                        "temperature": 0.7
                    }
                }
            )
            
            st.write(f"Script API Response Status: {script_response.status_code}")  # Debug
            
            if script_response.status_code != 201:
                st.error(f"❌ Script generation failed: {script_response.status_code}")
                st.write("Response:", script_response.text)  # Debug
                st.stop()
            
            prediction = script_response.json()
            st.write("Prediction object:", prediction)  # Debug
            
            script_output = poll_prediction(prediction["urls"]["get"], headers)
            
            if not script_output:
                st.error("❌ Script generation failed.")
                st.stop()
            
            st.write("Raw script output:", script_output)  # Debug
            
            # Extract script text from output
            if isinstance(script_output, list):
                script_text = "".join(script_output)
            else:
                script_text = str(script_output)
            
            st.write("Processed script text:", script_text)  # Debug
            
            # Parse the script into sections with better regex
            sections = []
            
            # Try different parsing methods
            # Method 1: Look for numbered lists
            numbered_pattern = r'(\d+\.?\s*)(.*?)(?=\d+\.|\Z)'
            matches = re.findall(numbered_pattern, script_text, re.DOTALL)
            
            if matches:
                for _, content in matches:
                    clean_content = content.strip().replace('\n', ' ')
                    if len(clean_content) > 5:
                        sections.append(clean_content)
            
            # Method 2: Split by sentences if numbered parsing fails
            if len(sections) < 4:
                sentences = re.split(r'[.!?]+', script_text)
                sections = [s.strip() for s in sentences if len(s.strip()) > 10][:4]
            
            # Method 3: Fallback to topic-based sections
            if len(sections) < 4:
                sections = [
                    f"Introduction to {topic} and its basic concept",
                    f"The main mechanisms behind {topic}",
                    f"Key factors that influence {topic}",
                    f"The importance and impact of {topic}"
                ]
            
            # Ensure we have exactly 4 sections
            sections = sections[:4]
            while len(sections) < 4:
                sections.append(f"Additional aspects of {topic}")
            
            st.success("✅ Script generated!")

        st.write("### Generated Script:")
        for i, line in enumerate(sections):
            st.markdown(f"**Part {i+1}**: {line}")

        # Create temporary directory for files
        temp_dir = tempfile.mkdtemp()
        video_paths = []
        
        # Step 2: Generate 4 videos
        for i, section in enumerate(sections):
            with st.spinner(f"🎥 Generating video {i+1}/4..."):
                video_prompt = f"A cinematic shot illustrating: {section}. High quality, professional lighting, smooth camera movement, detailed visual."
                
                video_response = requests.post(
                    "https://api.replicate.com/v1/predictions",
                    headers=headers,
                    json={
                        "version": "runwayml/gen-3-alpha-turbo",  # Updated model reference
                        "input": {
                            "prompt": video_prompt,
                            "duration": 5,
                            "aspect_ratio": "16:9"
                        }
                    }
                )
                
                if video_response.status_code != 201:
                    st.error(f"❌ Video {i+1} generation failed: {video_response.text}")
                    continue
                
                prediction = video_response.json()
                video_url = poll_prediction(prediction["urls"]["get"], headers, max_wait=600)
                
                if video_url:
                    # Handle different response formats
                    if isinstance(video_url, dict) and 'mp4' in video_url:
                        video_url = video_url['mp4']
                    elif isinstance(video_url, list) and len(video_url) > 0:
                        video_url = video_url[0]
                    
                    try:
                        video_path = os.path.join(temp_dir, f"video_part_{i}.mp4")
                        video_content = requests.get(video_url)
                        if video_content.status_code == 200:
                            with open(video_path, "wb") as f:
                                f.write(video_content.content)
                            video_paths.append(video_path)
                            st.success(f"✅ Video {i+1} completed!")
                        else:
                            st.error(f"❌ Failed to download video {i+1}")
                    except Exception as e:
                        st.error(f"❌ Error saving video {i+1}: {str(e)}")
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
                    try:
                        clip = mpe.VideoFileClip(path)
                        clips.append(clip)
                    except Exception as e:
                        st.warning(f"⚠️ Could not load video clip: {str(e)}")
            
            if clips:
                final_video = mpe.concatenate_videoclips(clips, method="compose")
                final_video_path = os.path.join(temp_dir, "final_video.mp4")
                final_video.write_videofile(
                    final_video_path, 
                    codec="libx264", 
                    audio_codec="aac",
                    temp_audiofile=os.path.join(temp_dir, "temp_audio.m4a"),
                    verbose=False,
                    logger=None
                )
                
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
                    "version": "elevenlabs/eleven-multilingual-v2",  # Updated model reference
                    "input": {
                        "text": full_script,
                        "voice": "Chris",
                        "model_id": "eleven_multilingual_v2"
                    }
                }
            )
            
            voice_path = None
            if voice_response.status_code == 201:
                prediction = voice_response.json()
                voice_url = poll_prediction(prediction["urls"]["get"], headers)
                
                if voice_url:
                    try:
                        voice_path = os.path.join(temp_dir, "voiceover.mp3")
                        voice_content = requests.get(voice_url)
                        if voice_content.status_code == 200:
                            with open(voice_path, "wb") as f:
                                f.write(voice_content.content)
                            st.success("✅ Voiceover generated!")
                        else:
                            st.warning("⚠️ Failed to download voiceover")
                    except Exception as e:
                        st.warning(f"⚠️ Voiceover error: {str(e)}")
                else:
                    st.warning("⚠️ Voiceover generation failed")
            else:
                st.warning("⚠️ Voiceover API call failed")

        # Step 5: Generate background music
        with st.spinner("🎵 Generating background music..."):
            music_response = requests.post(
                "https://api.replicate.com/v1/predictions",
                headers=headers,
                json={
                    "version": "meta/musicgen-melody",  # Updated model reference
                    "input": {
                        "prompt": f"Cinematic background music for {topic}, instrumental, ambient, calm",
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
                    try:
                        music_path = os.path.join(temp_dir, "music.wav")
                        music_content = requests.get(music_url)
                        if music_content.status_code == 200:
                            with open(music_path, "wb") as f:
                                f.write(music_content.content)
                            st.success("✅ Background music generated!")
                        else:
                            st.warning("⚠️ Failed to download music")
                    except Exception as e:
                        st.warning(f"⚠️ Music error: {str(e)}")
                else:
                    st.warning("⚠️ Music generation failed")
            else:
                st.warning("⚠️ Music API call failed")

        # Step 6: Combine everything
        with st.spinner("🎬 Finalizing video..."):
            video = mpe.VideoFileClip(final_video_path)
            audio_clips = []
            
            # Add voiceover if available
            if voice_path and os.path.exists(voice_path):
                try:
                    voice_audio = mpe.AudioFileClip(voice_path)
                    # Adjust voice duration to match video
                    if voice_audio.duration > video.duration:
                        voice_audio = voice_audio.subclip(0, video.duration)
                    audio_clips.append(voice_audio.volumex(1.0))
                except Exception as e:
                    st.warning(f"⚠️ Could not process voiceover: {str(e)}")
            
            # Add background music if available
            if music_path and os.path.exists(music_path):
                try:
                    music_audio = mpe.AudioFileClip(music_path)
                    # Loop or trim music to match video duration
                    if music_audio.duration < video.duration:
                        music_audio = music_audio.loop(duration=video.duration)
                    else:
                        music_audio = music_audio.subclip(0, video.duration)
                    audio_clips.append(music_audio.volumex(0.3))
                except Exception as e:
                    st.warning(f"⚠️ Could not process music: {str(e)}")
            
            # Combine audio
            if audio_clips:
                try:
                    final_audio = mpe.CompositeAudioClip(audio_clips)
                    video = video.set_audio(final_audio)
                except Exception as e:
                    st.warning(f"⚠️ Could not combine audio: {str(e)}")
            
            final_output_path = os.path.join(temp_dir, "final_output.mp4")
            video.write_videofile(
                final_output_path, 
                codec="libx264", 
                audio_codec="aac",
                temp_audiofile=os.path.join(temp_dir, "temp_final_audio.m4a"),
                verbose=False,
                logger=None
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
        import traceback
        st.write("Full error:", traceback.format_exc())  # Debug info
        
    finally:
        # Clean up temporary files
        try:
            if 'temp_dir' in locals():
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass
