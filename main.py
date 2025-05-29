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
    ColorClip,
)

st.title("AI Multi-Agent Ad Creator")

replicate_api_key = st.text_input("Enter your Replicate API Key", type="password")

# Ad-specific inputs
col1, col2 = st.columns(2)
with col1:
    product_name = st.text_input("Product/Service Name", placeholder="e.g., 'EcoClean Detergent'")
    target_audience = st.selectbox("Target Audience", [
        "Young Adults (18-35)", 
        "Families with Children", 
        "Professionals", 
        "Seniors (55+)", 
        "Tech Enthusiasts",
        "Health & Fitness"
    ])

with col2:
    ad_tone = st.selectbox("Ad Tone", [
        "Exciting & Energetic",
        "Warm & Friendly", 
        "Professional & Trustworthy",
        "Fun & Playful",
        "Luxury & Premium",
        "Urgent & Action-Driven"
    ])
    call_to_action = st.text_input("Call to Action", placeholder="e.g., 'Visit our website today!'")

key_benefits = st.text_area("Key Benefits/Features (1-3 main points)", 
                           placeholder="e.g., '99% effective cleaning, eco-friendly, saves time'")

if replicate_api_key and product_name and key_benefits and st.button("Generate 20s Ad"):
    replicate_client = replicate.Client(api_token=replicate_api_key)

    def run_replicate(model_path, input_data):
        return replicate_client.run(model_path, input=input_data)

    st.info("Step 1: Writing compelling ad script")
    
    # Enhanced ad script prompt
    ad_script_prompt = f"""You are an expert advertising copywriter. Write a compelling, persuasive 20-second video ad script for '{product_name}'.

Target Audience: {target_audience}
Tone: {ad_tone}
Key Benefits: {key_benefits}
Call to Action: {call_to_action}

Create a 4-segment script (5 seconds each) that follows this structure:
1: Hook/Problem - Grab attention with a relatable problem or exciting opening
2: Solution - Introduce the product as the perfect solution
3: Benefits - Highlight the key benefits that matter to the target audience
4: Call to Action - Strong, compelling call to action with urgency

Keep each segment to 6-8 words maximum for clear delivery. Make it persuasive and memorable.
Label each section as '1:', '2:', '3:', and '4:'."""

    full_script = run_replicate(
        "anthropic/claude-4-sonnet",
        {"prompt": ad_script_prompt}
    )

    script_text = "".join(full_script) if isinstance(full_script, list) else full_script
    script_segments = re.findall(r"\d+:\s*(.+)", script_text)

    if len(script_segments) < 4:
        st.error("Failed to extract 4 clear script segments. Try adjusting your inputs.")
        st.stop()

    st.success("Ad script written successfully")
    st.write("**Generated Script:**")
    for i, segment in enumerate(script_segments):
        st.write(f"**Segment {i+1}:** {segment}")
    
    script_file_path = tempfile.NamedTemporaryFile(delete=False, suffix=".txt").name
    with open(script_file_path, "w") as f:
        f.write(f"Ad Script for: {product_name}\n")
        f.write(f"Target: {target_audience}\n")
        f.write(f"Tone: {ad_tone}\n\n")
        f.write("\n\n".join([f"Segment {i+1}: {seg}" for i, seg in enumerate(script_segments)]))
    st.download_button("📜 Download Ad Script", script_file_path, "ad_script.txt")

    temp_video_paths = []

    def download_to_file(url: str, suffix: str):
        resp = requests.get(url, stream=True)
        resp.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        with open(tmp.name, "wb") as f:
            for chunk in resp.iter_content(1024 * 32):
                f.write(chunk)
        return tmp.name

    def safe_audio_resize(audio_clip, target_duration):
        """Safely resize audio clip to target duration"""
        try:
            if audio_clip.duration >= target_duration:
                # If audio is longer, trim it
                return audio_clip.subclip(0, target_duration)
            else:
                # If audio is shorter, loop it to reach target duration
                loops_needed = int(target_duration / audio_clip.duration) + 1
                looped_audio = audio_clip
                for _ in range(loops_needed - 1):
                    looped_audio = CompositeAudioClip([looped_audio, audio_clip.set_start(looped_audio.duration)])
                return looped_audio.subclip(0, target_duration)
        except Exception as e:
            st.warning(f"Audio processing warning: {e}")
            # Return a silent audio clip as fallback
            return AudioFileClip(None).set_duration(target_duration)

    def safe_video_resize(video_clip, target_duration):
        """Safely resize video clip to target duration"""
        try:
            if video_clip.duration >= target_duration:
                return video_clip.subclip(0, target_duration)
            else:
                # If video is shorter, create a filler clip and concatenate
                remaining_time = target_duration - video_clip.duration
                filler = ColorClip(size=video_clip.size, color=(0,0,0), duration=remaining_time)
                return concatenate_videoclips([video_clip, filler])
        except Exception as e:
            st.warning(f"Video processing warning: {e}")
            # Return the original clip if processing fails
            return video_clip

    segment_clips = []

    # Step 2: Generate ad visuals with commercial style
    visual_styles = {
        "Exciting & Energetic": "dynamic, high-energy, vibrant colors, fast-paced",
        "Warm & Friendly": "warm lighting, friendly faces, cozy atmosphere",
        "Professional & Trustworthy": "clean, professional, modern office setting",
        "Fun & Playful": "bright, colorful, animated, joyful expressions",
        "Luxury & Premium": "elegant, sophisticated, high-end materials, golden lighting",
        "Urgent & Action-Driven": "dramatic, bold, intense, action-packed"
    }
    
    style_description = visual_styles.get(ad_tone, "professional, appealing")

    for i, segment in enumerate(script_segments):
        st.info(f"Step 2.{i+1}: Generating commercial visuals for segment {i+1}")
        
        # Ad-specific visual prompts
        if i == 0:  # Hook/Problem
            video_prompt = f"Commercial ad opening scene: {style_description}. Scene showing the problem or hook for {product_name}. {segment}"
        elif i == 1:  # Solution  
            video_prompt = f"Commercial ad scene: {style_description}. Product showcase for {product_name}, revealing the solution. {segment}"
        elif i == 2:  # Benefits
            video_prompt = f"Commercial ad scene: {style_description}. Demonstrating benefits of {product_name} in action. {segment}"
        else:  # Call to Action
            video_prompt = f"Commercial ad finale: {style_description}. Strong call-to-action scene for {product_name}. {segment}"
            
        try:
            video_uri = run_replicate(
                "luma/ray-flash-2-540p",
                {"prompt": video_prompt, "num_frames": 120, "fps": 24},
            )
            video_path = download_to_file(video_uri, suffix=".mp4")
            temp_video_paths.append(video_path)

            # Ensure exactly 5s per segment with safe resizing
            raw_clip = VideoFileClip(video_path)
            clip = safe_video_resize(raw_clip, 5.0)
            segment_clips.append(clip)
            raw_clip.close()  # Free memory

            st.video(video_path)
            st.download_button(f"🎥 Download Segment {i+1}", video_path, f"ad_segment_{i+1}.mp4")
        except Exception as e:
            st.error(f"Failed to generate segment {i+1} visuals: {e}")
            st.stop()

    # Step 4: Generate professional voiceover
    st.info("Step 4: Generating professional ad voiceover")
    full_narration = " ".join(script_segments)
    
    # Add voiceover direction based on tone
    voice_direction = {
        "Exciting & Energetic": "enthusiastic, high-energy",
        "Warm & Friendly": "warm, conversational", 
        "Professional & Trustworthy": "authoritative, confident",
        "Fun & Playful": "upbeat, cheerful",
        "Luxury & Premium": "sophisticated, smooth",
        "Urgent & Action-Driven": "urgent, compelling"
    }.get(ad_tone, "professional")
    
    voice_path = None
    try:
        voiceover_uri = run_replicate(
            "minimax/speech-02-hd",
            {
                "text": f"[{voice_direction} tone] {full_narration}",
                "voice": "default"
            },
        )
        voice_path = download_to_file(voiceover_uri, suffix=".mp3")
        st.audio(voice_path)
        st.download_button("🎙 Download Ad Voiceover", voice_path, "ad_voiceover.mp3")
    except Exception as e:
        st.error(f"Failed to generate voiceover: {e}")
        st.stop()

    # Step 5: Generate commercial background music
    st.info("Step 5: Creating commercial background music")
    
    music_styles = {
        "Exciting & Energetic": "upbeat electronic, driving beat, energetic",
        "Warm & Friendly": "acoustic, warm, feel-good melody",
        "Professional & Trustworthy": "corporate, inspiring, confidence-building",
        "Fun & Playful": "upbeat, playful, catchy melody",
        "Luxury & Premium": "elegant orchestral, sophisticated, premium",
        "Urgent & Action-Driven": "dramatic, intense, building tension"
    }
    
    music_style = music_styles.get(ad_tone, "commercial, professional")
    
    music_path = None
    try:
        music_uri = run_replicate(
            "google/lyria-2",
            {
                "prompt": f"Commercial ad background music: {music_style}. 20-second instrumental track for {product_name} advertisement. Professional quality, suitable for TV commercial."
            },
        )
        music_path = download_to_file(music_uri, suffix=".mp3")
        st.audio(music_path)
        st.download_button("🎵 Download Ad Music", music_path, "ad_background_music.mp3")
    except Exception as e:
        st.error(f"Failed to generate background music: {e}")
        st.stop()

    # Step 6: Create final commercial with robust audio handling
    st.info("Step 6: Assembling final commercial")
    try:
        # Concatenate video clips
        final_video = concatenate_videoclips(segment_clips, method="compose")
        final_duration = final_video.duration  # Should be 20s
        st.write(f"Final video duration: {final_duration:.2f} seconds")

        # Process audio with safe duration handling
        audio_clips = []
        
        if voice_path and os.path.exists(voice_path):
            try:
                voice_raw = AudioFileClip(voice_path)
                st.write(f"Original voice duration: {voice_raw.duration:.2f} seconds")
                voice_clip = safe_audio_resize(voice_raw, final_duration)
                audio_clips.append(voice_clip)
                voice_raw.close()  # Free memory
            except Exception as e:
                st.warning(f"Voice audio processing failed: {e}")
        
        if music_path and os.path.exists(music_path):
            try:
                music_raw = AudioFileClip(music_path)
                st.write(f"Original music duration: {music_raw.duration:.2f} seconds")
                music_clip = safe_audio_resize(music_raw, final_duration)
                music_clip = music_clip.volumex(0.25)  # Lower music volume for ads
                audio_clips.append(music_clip)
                music_raw.close()  # Free memory
            except Exception as e:
                st.warning(f"Music audio processing failed: {e}")

        # Combine audio tracks
        if audio_clips:
            try:
                final_audio = CompositeAudioClip(audio_clips)
                final_video = final_video.set_audio(final_audio)
            except Exception as e:
                st.warning(f"Audio composition failed: {e}. Proceeding with video only.")

        output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
        
        # Write video with error handling
        try:
            final_video.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac" if final_video.audio is not None else None,
                temp_audiofile="temp-audio.m4a",
                remove_temp=True,
                fps=24,
                bitrate="5000k",  # Higher quality for commercial use
                verbose=False,
                logger=None  # Suppress moviepy logs
            )
        except Exception as e:
            st.error(f"Video writing failed: {e}")
            # Try writing without audio as fallback
            try:
                final_video_no_audio = final_video.without_audio()
                final_video_no_audio.write_videofile(
                    output_path,
                    codec="libx264",
                    fps=24,
                    bitrate="5000k",
                    verbose=False,
                    logger=None
                )
                st.warning("Created video without audio due to audio processing issues.")
            except Exception as e2:
                st.error(f"Fallback video creation also failed: {e2}")
                st.stop()

        st.success("🎬 Your 20-second commercial is ready!")
        st.video(output_path)
        
        # Summary of created ad
        st.write("**Ad Summary:**")
        st.write(f"**Product:** {product_name}")
        st.write(f"**Target Audience:** {target_audience}")
        st.write(f"**Tone:** {ad_tone}")
        st.write(f"**Key Message:** {key_benefits}")
        
        st.download_button("📽 Download Final Commercial", output_path, f"{product_name.replace(' ', '_')}_ad.mp4")

        # Close video clips to free memory
        final_video.close()
        for clip in segment_clips:
            clip.close()

    except Exception as e:
        st.warning("Final commercial assembly failed, but you can still download individual components.")
        st.error(f"Error creating final video: {e}")
        
        # Close clips even if assembly failed
        try:
            for clip in segment_clips:
                clip.close()
        except:
            pass

    # Cleanup temporary files
    cleanup_paths = [*temp_video_paths, script_file_path]
    if voice_path:
        cleanup_paths.append(voice_path)
    if music_path:
        cleanup_paths.append(music_path)
        
    for path in cleanup_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

# Add helpful tips section
with st.expander("💡 Tips for Better Ads"):
    st.write("""
    **Script Tips:**
    - Keep benefits customer-focused (what's in it for them?)
    - Use action words and emotional triggers
    - Make your call-to-action specific and urgent
    
    **Visual Tips:**
    - Show the product in use, not just static shots
    - Include people who represent your target audience
    - Use consistent branding colors and style
    
    **Audio Tips:**
    - Match voice tone to your brand personality
    - Keep music volume low enough that narration is clear
    - End with a memorable audio signature if possible
    
    **Troubleshooting:**
    - If audio issues occur, the app will automatically create video-only versions
    - Generated audio may be shorter than expected - the app will loop it safely
    - All individual components are available for download even if final assembly fails
    """)
