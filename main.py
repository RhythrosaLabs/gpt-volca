import streamlit as st
import replicate
import os
import requests
import tempfile
import subprocess
from moviepy.editor import VideoFileClip, CompositeVideoClip, TextClip, AudioFileClip, concatenate_videoclips
import json
import time
from datetime import datetime

# Set page config
st.set_page_config(
    page_title="AI Video Maker",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS for minimal, modern interface
st.markdown("""
<style>
    .main > div {
        padding-top: 2rem;
    }
    .stTextInput > div > div > input {
        border-radius: 25px;
        border: 2px solid #e0e0e0;
        padding: 15px 20px;
        font-size: 16px;
    }
    .stButton > button {
        border-radius: 25px;
        background: linear-gradient(45deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 15px 30px;
        font-size: 16px;
        font-weight: 600;
        width: 100%;
        margin-top: 20px;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
    }
    .video-title {
        text-align: center;
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(45deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2rem;
    }
    .subtitle {
        text-align: center;
        color: #666;
        font-size: 1.2rem;
        margin-bottom: 3rem;
    }
</style>
""", unsafe_allow_html=True)

class AIVideoMaker:
    def __init__(self, api_key):
        self.client = replicate.Client(api_token=api_key)
        self.temp_dir = tempfile.mkdtemp()
    
    def generate_script(self, topic):
        """Generate a 30-second script using Replicate's text generation"""
        try:
            prompt = f"""Write a compelling 30-second video script about '{topic}'. 
            The script should be engaging, informative, and suitable for a short video.
            Format it as natural speech that can be read aloud.
            Make it exactly 30 seconds when read at normal speaking pace (approximately 75-80 words).
            
            Topic: {topic}
            
            Script:"""
            
            output = self.client.run(
                "meta/llama-2-70b-chat:02e509c789964a7ea8736978a43525956ef40397be9033abf9fd2badfe68c9e3",
                input={
                    "prompt": prompt,
                    "max_new_tokens": 200,
                    "temperature": 0.7,
                    "top_p": 0.9,
                }
            )
            
            script = "".join(output).strip()
            return script
            
        except Exception as e:
            st.error(f"Error generating script: {str(e)}")
            return None
    
    def break_script_into_segments(self, script):
        """Break script into 6 segments of ~5 seconds each"""
        words = script.split()
        words_per_segment = len(words) // 6
        
        segments = []
        for i in range(6):
            start_idx = i * words_per_segment
            if i == 5:  # Last segment gets remaining words
                end_idx = len(words)
            else:
                end_idx = (i + 1) * words_per_segment
            
            segment = " ".join(words[start_idx:end_idx])
            segments.append(segment)
        
        return segments
    
    def generate_image_prompt(self, segment, topic):
        """Generate an image prompt based on the script segment"""
        try:
            prompt = f"""Based on this video script segment about '{topic}', create a detailed image prompt for visual representation:

            Script segment: "{segment}"
            Topic: {topic}

            Create a descriptive prompt for a high-quality, cinematic image that visually represents this segment. 
            The prompt should be detailed, specific, and suitable for AI image generation.
            
            Image prompt:"""
            
            output = self.client.run(
                "meta/llama-2-70b-chat:02e509c789964a7ea8736978a43525956ef40397be9033abf9fd2badfe68c9e3",
                input={
                    "prompt": prompt,
                    "max_new_tokens": 150,
                    "temperature": 0.8,
                }
            )
            
            image_prompt = "".join(output).strip()
            return image_prompt
            
        except Exception as e:
            st.error(f"Error generating image prompt: {str(e)}")
            return f"High quality cinematic image about {topic}"
    
    def generate_image(self, prompt, segment_idx):
        """Generate image using Replicate's SDXL"""
        try:
            output = self.client.run(
                "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
                input={
                    "prompt": prompt,
                    "negative_prompt": "blurry, low quality, distorted, ugly, bad anatomy",
                    "width": 1024,
                    "height": 576,
                    "num_outputs": 1,
                    "scheduler": "K_EULER",
                    "num_inference_steps": 30,
                    "guidance_scale": 7.5,
                }
            )
            
            # Download the image
            image_url = output[0]
            response = requests.get(image_url)
            
            image_path = os.path.join(self.temp_dir, f"image_{segment_idx}.png")
            with open(image_path, 'wb') as f:
                f.write(response.content)
            
            return image_path
            
        except Exception as e:
            st.error(f"Error generating image {segment_idx}: {str(e)}")
            return None
    
    def image_to_video(self, image_path, segment_idx):
        """Convert image to 5-second video using Replicate"""
        try:
            with open(image_path, 'rb') as f:
                output = self.client.run(
                    "stability-ai/stable-video-diffusion:3f0457e4619daac51203dedb1a4f3482d9f2ef8d5c25b41b3b2029f5d1baa5b1",
                    input={
                        "cond_aug": 0.02,
                        "decoding_t": 14,
                        "input_image": f,
                        "video_length": "14_frames_with_svd",
                        "sizing_strategy": "maintain_aspect_ratio",
                        "motion_bucket_id": 127,
                        "frames_per_second": 6,
                    }
                )
            
            # Download the video
            video_url = output
            response = requests.get(video_url)
            
            video_path = os.path.join(self.temp_dir, f"video_{segment_idx}.mp4")
            with open(video_path, 'wb') as f:
                f.write(response.content)
            
            # Extend video to exactly 5 seconds using moviepy
            clip = VideoFileClip(video_path)
            if clip.duration < 5.0:
                # Loop the video to make it 5 seconds
                loops_needed = int(5.0 / clip.duration) + 1
                extended_clip = concatenate_videoclips([clip] * loops_needed).subclip(0, 5.0)
                extended_path = os.path.join(self.temp_dir, f"extended_video_{segment_idx}.mp4")
                extended_clip.write_videofile(extended_path, verbose=False, logger=None)
                clip.close()
                extended_clip.close()
                return extended_path
            else:
                return video_path
            
        except Exception as e:
            st.error(f"Error converting image to video {segment_idx}: {str(e)}")
            return None
    
    def generate_voiceover(self, script):
        """Generate voiceover using Replicate's text-to-speech"""
        try:
            output = self.client.run(
                "suno-ai/bark:b76242b40d67c76ab6742e987628a2a9ac019e11d56ab96c4e91ce03b79b2787",
                input={
                    "prompt": script,
                    "text_temp": 0.7,
                    "output_full": False,
                }
            )
            
            # Download the audio
            audio_url = output["audio_out"]
            response = requests.get(audio_url)
            
            audio_path = os.path.join(self.temp_dir, "voiceover.wav")
            with open(audio_path, 'wb') as f:
                f.write(response.content)
            
            return audio_path
            
        except Exception as e:
            st.error(f"Error generating voiceover: {str(e)}")
            return None
    
    def create_final_video(self, video_paths, script_segments, voiceover_path):
        """Combine all videos, add captions and voiceover"""
        try:
            # Load all video clips
            clips = []
            for video_path in video_paths:
                if video_path and os.path.exists(video_path):
                    clip = VideoFileClip(video_path)
                    clips.append(clip)
            
            if not clips:
                st.error("No valid video clips to combine")
                return None
            
            # Concatenate all video clips
            final_video = concatenate_videoclips(clips)
            
            # Add captions
            caption_clips = []
            for i, segment in enumerate(script_segments):
                start_time = i * 5
                end_time = (i + 1) * 5
                
                caption = TextClip(
                    segment,
                    fontsize=24,
                    color='white',
                    font='Arial-Bold',
                    stroke_color='black',
                    stroke_width=2,
                    method='caption',
                    size=(final_video.w * 0.8, None)
                ).set_position(('center', 'bottom')).set_start(start_time).set_end(end_time)
                
                caption_clips.append(caption)
            
            # Composite video with captions
            video_with_captions = CompositeVideoClip([final_video] + caption_clips)
            
            # Add voiceover if available
            if voiceover_path and os.path.exists(voiceover_path):
                audio = AudioFileClip(voiceover_path)
                # Trim or extend audio to match video duration
                if audio.duration > 30:
                    audio = audio.subclip(0, 30)
                video_with_captions = video_with_captions.set_audio(audio)
            
            # Export final video
            final_path = os.path.join(self.temp_dir, "final_video.mp4")
            video_with_captions.write_videofile(
                final_path,
                fps=24,
                verbose=False,
                logger=None,
                codec='libx264',
                audio_codec='aac'
            )
            
            # Clean up
            for clip in clips:
                clip.close()
            video_with_captions.close()
            if voiceover_path:
                audio.close()
            
            return final_path
            
        except Exception as e:
            st.error(f"Error creating final video: {str(e)}")
            return None

def main():
    # Header
    st.markdown('<h1 class="video-title">🎬 AI Video Maker</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Create professional videos with AI in seconds</p>', unsafe_allow_html=True)
    
    # API Key input
    with st.container():
        st.markdown("### 🔑 Setup")
        api_key = st.text_input(
            "Enter your Replicate API key",
            type="password",
            help="Get your API key from https://replicate.com/account/api-tokens"
        )
    
    if not api_key:
        st.info("👆 Please enter your Replicate API key to get started")
        return
    
    # Video topic input
    with st.container():
        st.markdown("### 🎯 Create Your Video")
        topic = st.text_input(
            "What video would you like to create?",
            placeholder="e.g., The importance of nature, Benefits of exercise, Future of AI..."
        )
    
    if not topic:
        st.info("💡 Enter a topic to create your video")
        return
    
    # Generate button
    if st.button("🚀 Generate Video"):
        try:
            video_maker = AIVideoMaker(api_key)
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Step 1: Generate script
            status_text.text("📝 Writing script...")
            progress_bar.progress(10)
            script = video_maker.generate_script(topic)
            
            if not script:
                st.error("Failed to generate script")
                return
            
            st.success("✅ Script generated!")
            with st.expander("📄 View Script"):
                st.write(script)
            
            # Step 2: Break into segments
            status_text.text("✂️ Breaking script into segments...")
            progress_bar.progress(20)
            segments = video_maker.break_script_into_segments(script)
            
            # Step 3-4: Generate images for each segment
            status_text.text("🎨 Generating images...")
            image_paths = []
            
            for i, segment in enumerate(segments):
                progress_bar.progress(20 + (i * 10))
                status_text.text(f"🎨 Generating image {i+1}/6...")
                
                # Generate image prompt
                image_prompt = video_maker.generate_image_prompt(segment, topic)
                
                # Generate image
                image_path = video_maker.generate_image(image_prompt, i)
                image_paths.append(image_path)
                
                time.sleep(1)  # Rate limiting
            
            # Step 5: Convert images to videos
            status_text.text("🎬 Creating video segments...")
            video_paths = []
            
            for i, image_path in enumerate(image_paths):
                if image_path:
                    progress_bar.progress(50 + (i * 5))
                    status_text.text(f"🎬 Creating video segment {i+1}/6...")
                    
                    video_path = video_maker.image_to_video(image_path, i)
                    video_paths.append(video_path)
                    
                    time.sleep(2)  # Rate limiting
            
            # Step 6: Generate voiceover
            status_text.text("🎤 Generating voiceover...")
            progress_bar.progress(85)
            voiceover_path = video_maker.generate_voiceover(script)
            
            # Step 7: Create final video
            status_text.text("🎞️ Assembling final video...")
            progress_bar.progress(95)
            final_video_path = video_maker.create_final_video(video_paths, segments, voiceover_path)
            
            if final_video_path and os.path.exists(final_video_path):
                progress_bar.progress(100)
                status_text.text("✅ Video created successfully!")
                
                # Display video
                st.markdown("### 🎉 Your Video is Ready!")
                
                with open(final_video_path, 'rb') as video_file:
                    video_bytes = video_file.read()
                    st.video(video_bytes)
                
                # Download button
                st.download_button(
                    label="📥 Download Video",
                    data=video_bytes,
                    file_name=f"ai_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4",
                    mime="video/mp4"
                )
                
                # Show segments breakdown
                with st.expander("📋 Video Breakdown"):
                    for i, segment in enumerate(segments):
                        st.write(f"**Segment {i+1} (0:{i*5:02d}-0:{(i+1)*5:02d}):**")
                        st.write(segment)
                        st.write("---")
            
            else:
                st.error("Failed to create final video")
                
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.error("Please check your API key and try again")

    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #666; margin-top: 2rem;'>"
        "Powered by Replicate AI • Made with ❤️ using Streamlit"
        "</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
