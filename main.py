import streamlit as st
import replicate
import os
import requests
import zipfile
import io
from datetime import datetime

# Set page config
st.set_page_config(page_title="AI Video Generator", page_icon="🎬", layout="wide")

def download_video(url, filename):
    """Download video from URL"""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        st.error(f"Error downloading {filename}: {str(e)}")
        return False

def create_zip_file(video_files):
    """Create a zip file containing all videos"""
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for video_file in video_files:
            if os.path.exists(video_file):
                zip_file.write(video_file, os.path.basename(video_file))
    
    zip_buffer.seek(0)
    return zip_buffer

def generate_video_with_model(prompt, model_name, model_identifier, duration=None):
    """Generate video using specified model"""
    try:
        st.write(f"🎬 Generating video with {model_name}...")
        
        # Different input parameters for different models
        if "runway" in model_identifier.lower():
            input_params = {
                "prompt": prompt,
            }
            if duration:
                input_params["duration"] = duration
        elif "zeroscope" in model_identifier.lower():
            input_params = {
                "prompt": prompt,
                "num_frames": 24 if duration and duration <= 3 else 40,
                "num_inference_steps": 50
            }
        elif "stable-video" in model_identifier.lower():
            input_params = {
                "input": prompt,  # Some models use 'input' instead of 'prompt'
            }
            if duration:
                input_params["video_length"] = duration
        else:
            # Generic parameters
            input_params = {
                "prompt": prompt,
            }
            if duration:
                input_params["duration"] = duration
        
        output = replicate.run(model_identifier, input=input_params)
        
        # Handle different output formats
        if isinstance(output, list) and len(output) > 0:
            video_url = output[0] if isinstance(output[0], str) else str(output[0])
        elif isinstance(output, str):
            video_url = output
        elif hasattr(output, 'url'):
            video_url = output.url
        else:
            video_url = str(output)
        
        return video_url
        
    except Exception as e:
        error_msg = str(e)
        st.error(f"❌ {model_name} generation failed: {error_msg}")
        return None

# Available models with their correct identifiers
AVAILABLE_MODELS = {
    "Zeroscope V2 XL": "anotherjesse/zeroscope-v2-xl",
    "Stable Video Diffusion": "stability-ai/stable-video-diffusion",
    "Text2Video Zero": "cjwbw/text2video-zero",
    "Runway ML": "runwayml/stable-video-diffusion"  # Check if this is available
}

# Streamlit UI
st.title("🎬 AI Video Generator")
st.write("Generate multiple videos simultaneously using different AI models!")

# API Key input
api_key = st.text_input("Enter your Replicate API Token:", type="password")

if api_key:
    os.environ["REPLICATE_API_TOKEN"] = api_key
    
    # Input section
    col1, col2 = st.columns([2, 1])
    
    with col1:
        prompt = st.text_area(
            "Video Prompt:", 
            placeholder="Describe the video you want to generate...",
            height=100
        )
    
    with col2:
        st.write("**Settings:**")
        
        # Model selection
        selected_models = st.multiselect(
            "Select Models:",
            options=list(AVAILABLE_MODELS.keys()),
            default=["Zeroscope V2 XL", "Stable Video Diffusion"]
        )
        
        duration = st.selectbox(
            "Video Duration (seconds):",
            options=[3, 5, 8, 10],
            index=0
        )
        
        num_videos = st.slider(
            "Number of variations per model:",
            min_value=1,
            max_value=3,
            value=1
        )
    
    # Generate button
    if st.button("🎬 Generate Videos", type="primary"):
        if not prompt.strip():
            st.error("Please enter a video prompt!")
        elif not selected_models:
            st.error("Please select at least one model!")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_videos = len(selected_models) * num_videos
            current_video = 0
            
            video_results = []
            successful_videos = []
            
            # Create columns for video display
            if total_videos <= 2:
                video_cols = st.columns(total_videos)
            else:
                video_cols = st.columns(3)
            
            for model_idx, model_name in enumerate(selected_models):
                model_identifier = AVAILABLE_MODELS[model_name]
                
                for variation in range(num_videos):
                    current_video += 1
                    progress = current_video / total_videos
                    progress_bar.progress(progress)
                    status_text.text(f"Generating video {current_video}/{total_videos} - {model_name} (Variation {variation + 1})")
                    
                    # Generate video
                    video_url = generate_video_with_model(prompt, model_name, model_identifier, duration)
                    
                    if video_url:
                        video_results.append({
                            'model': model_name,
                            'variation': variation + 1,
                            'url': video_url,
                            'filename': f"{model_name.replace(' ', '_')}_v{variation + 1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                        })
                        
                        # Display video in appropriate column
                        col_idx = (current_video - 1) % len(video_cols)
                        with video_cols[col_idx]:
                            st.write(f"**{model_name} - Variation {variation + 1}**")
                            st.video(video_url)
                            
                            # Download button for individual video
                            if st.button(f"📥 Download", key=f"download_{current_video}"):
                                if download_video(video_url, video_results[-1]['filename']):
                                    st.success(f"Downloaded: {video_results[-1]['filename']}")
            
            progress_bar.progress(1.0)
            status_text.text("✅ Generation complete!")
            
            # Results summary
            if video_results:
                st.success(f"🎉 Successfully generated {len(video_results)} videos!")
                
                # Download all videos button
                st.write("### 📦 Download All Videos")
                
                if st.button("📥 Download All as ZIP"):
                    with st.spinner("Preparing download..."):
                        # Download all videos
                        downloaded_files = []
                        for result in video_results:
                            if download_video(result['url'], result['filename']):
                                downloaded_files.append(result['filename'])
                        
                        if downloaded_files:
                            # Create ZIP file
                            zip_buffer = create_zip_file(downloaded_files)
                            
                            # Provide download button
                            st.download_button(
                                label="📦 Download ZIP File",
                                data=zip_buffer.getvalue(),
                                file_name=f"ai_videos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                                mime="application/zip"
                            )
                            
                            # Clean up individual files
                            for file in downloaded_files:
                                try:
                                    os.remove(file)
                                except:
                                    pass
                        else:
                            st.error("Failed to download videos for ZIP creation.")
                
                # Display generation details
                with st.expander("📊 Generation Details"):
                    for result in video_results:
                        st.write(f"- **{result['model']}** (Variation {result['variation']}): [View Video]({result['url']})")
            
            else:
                st.error("❌ No videos were generated successfully. Please check your API token and try again.")

else:
    st.info("👆 Please enter your Replicate API token to get started!")
    
    with st.expander("ℹ️ How to get your Replicate API Token"):
        st.write("""
        1. Go to [Replicate.com](https://replicate.com)
        2. Sign up or log in to your account
        3. Go to your account settings
        4. Find the "API Tokens" section
        5. Copy your token and paste it above
        """)

# Footer
st.markdown("---")
st.markdown("🎬 **AI Video Generator** - Generate amazing videos with AI!")
