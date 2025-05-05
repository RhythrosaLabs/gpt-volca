import streamlit as st
import json
import requests
import zipfile
import os
import time
from io import BytesIO
from PIL import Image

# OpenAI and DALL-E setup
CHAT_API_URL = "https://api.openai.com/v1/chat/completions"
DALLE_API_URL = "https://api.openai.com/v1/images/generations"
API_KEY_FILE = "api_key.json"

def load_api_key():
    """Load API key from file if it exists"""
    if os.path.exists(API_KEY_FILE):
        try:
            with open(API_KEY_FILE, 'r') as file:
                data = json.load(file)
                return data.get('api_key')
        except Exception:
            return None
    return None

def save_api_key(api_key):
    """Save API key to file"""
    with open(API_KEY_FILE, 'w') as file:
        json.dump({"api_key": api_key}, file)

def generate_content(api_key, prompt, action):
    """Generate text content using GPT-4"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": f"You are a helpful assistant specializing in {action}."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = requests.post(CHAT_API_URL, headers=headers, json=data)
        response.raise_for_status()
        response_data = response.json()
        if "choices" not in response_data:
            error_message = response_data.get("error", {}).get("message", "Unknown error")
            return f"Error: {error_message}"

        content_text = response_data["choices"][0]["message"]["content"]
        return content_text

    except requests.RequestException as e:
        return f"Error: Unable to communicate with the OpenAI API. {str(e)}"

def generate_image(api_key, prompt, size="1024x1024"):
    """Generate image using DALL-E"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "dall-e-3",
        "prompt": prompt,
        "n": 1,
        "size": size,
        "quality": "hd",
        "style": "vivid",
        "response_format": "url"
    }
    
    try:
        response = requests.post(DALLE_API_URL, headers=headers, json=data)
        response.raise_for_status()
        response_data = response.json()
        image_url = response_data['data'][0]['url']
        return image_url
    except requests.RequestException as e:
        st.error(f"Error generating image: {str(e)}")
        return None

def download_image(image_url):
    """Download image from URL"""
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        st.error(f"Error downloading image: {str(e)}")
        return None

def create_master_document(comic_book):
    """Create a master document summarizing the comic book contents"""
    master_doc = "# Comic Book Master Document\n\n"
    for key, value in comic_book.items():
        if key == "character_designs" or key == "comic_panels" or key == "cover_page":
            master_doc += f"## {key.replace('_', ' ').title()}\n"
            master_doc += "See attached images.\n\n"
        else:
            master_doc += f"## {key.replace('_', ' ').title()}\n"
            if isinstance(value, str):
                master_doc += f"{value}\n\n"
            else:
                master_doc += "See attached document.\n\n"
    return master_doc

def create_zip(content_dict):
    """Create a ZIP file containing all comic book assets"""
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for key, value in content_dict.items():
            if isinstance(value, str):
                zip_file.writestr(f"{key}.txt", value)
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, bytes):
                        zip_file.writestr(f"{key}/{sub_key}", sub_value)

    zip_buffer.seek(0)
    return zip_buffer.read()

def generate_comic_book(api_key, user_prompt, progress_placeholder):
    """Generate a complete comic book based on user prompt"""
    comic_book = {}
    
    # Update progress bar
    progress_bar = progress_placeholder.progress(0)
    status_text = st.empty()
    
    try:
        # Step 1: Generate comic book concept
        status_text.text("Generating comic book concept...")
        progress_bar.progress(10)
        comic_concept = generate_content(api_key, f"Create a detailed comic book concept based on the following prompt: {user_prompt}.", "comic book concept creation")
        comic_book['comic_concept'] = comic_concept
        
        # Step 2: Generate detailed plot
        status_text.text("Generating detailed plot...")
        progress_bar.progress(20)
        comic_book['plot'] = generate_content(api_key, f"Create a detailed plot for the comic book: {comic_concept}", "comic book plot development")
        
        # Step 3: Generate character designs
        status_text.text("Generating character designs...")
        progress_bar.progress(30)
        character_designs = {}
        
        character_prompt = f"Full-body character design for the comic book, based on the following description: {comic_concept}"
        image_url = generate_image(api_key, character_prompt)
        if image_url:
            image_data = download_image(image_url)
            if image_data:
                character_designs["character_1.png"] = image_data
        
        character_prompt_2 = f"Another full-body character design for the comic book, based on the following description: {comic_concept}"
        image_url = generate_image(api_key, character_prompt_2)
        if image_url:
            image_data = download_image(image_url)
            if image_data:
                character_designs["character_2.png"] = image_data
                
        comic_book['character_designs'] = character_designs
        
        # Step 4: Generate comic panels
        status_text.text("Generating comic panels...")
        progress_bar.progress(50)
        comic_panels = {}
        
        panel_prompt_1 = f"Comic panel illustrating a key scene from the comic book, based on the following description: {comic_concept}"
        image_url = generate_image(api_key, panel_prompt_1)
        if image_url:
            image_data = download_image(image_url)
            if image_data:
                comic_panels["panel_1.png"] = image_data
        
        panel_prompt_2 = f"Comic panel illustrating another key scene from the comic book, based on the following description: {comic_concept}"
        image_url = generate_image(api_key, panel_prompt_2)
        if image_url:
            image_data = download_image(image_url)
            if image_data:
                comic_panels["panel_2.png"] = image_data
                
        comic_book['comic_panels'] = comic_panels
        
        # Step 5: Generate cover page
        status_text.text("Generating cover page...")
        progress_bar.progress(70)
        cover_page = {}
        
        cover_prompt = f"Cover page for the comic book, based on the following description: {comic_concept}"
        image_url = generate_image(api_key, cover_prompt)
        if image_url:
            image_data = download_image(image_url)
            if image_data:
                cover_page["cover.png"] = image_data
                
        comic_book['cover_page'] = cover_page
        
        # Step 6: Generate recap
        status_text.text("Generating recap...")
        progress_bar.progress(80)
        comic_book['recap'] = generate_content(api_key, f"Recap the comic book content: {comic_concept}", "comic book recap")
        
        # Step 7: Generate master document
        status_text.text("Generating master document...")
        progress_bar.progress(90)
        comic_book['master_document'] = create_master_document(comic_book)
        
        # Step 8: Package into ZIP
        status_text.text("Packaging into ZIP...")
        progress_bar.progress(95)
        
        status_text.text("Comic book generation complete!")
        progress_bar.progress(100)
        
        return comic_book
        
    except Exception as e:
        status_text.text(f"Error: {str(e)}")
        progress_bar.progress(100)
        return None

def main():
    st.set_page_config(
        page_title="Comic Book Creator",
        page_icon="📚",
        layout="wide",
    )
    
    st.title("Comic Book Creator")
    st.markdown("Generate custom comic books using AI!")
    
    # API Key setup
    api_key = load_api_key()
    
    with st.sidebar:
        st.header("Settings")
        saved_api_key = st.text_input("OpenAI API Key", value=api_key if api_key else "", type="password")
        if st.button("Save API Key"):
            save_api_key(saved_api_key)
            st.success("API key saved!")
            api_key = saved_api_key
    
    # Main content
    prompt = st.text_input("Enter your comic book idea:", placeholder="e.g., A superhero who can control time but ages faster when using powers")
    
    if st.button("Generate Comic Book"):
        if not api_key:
            st.error("Please enter an OpenAI API key in the settings panel.")
        elif not prompt:
            st.warning("Please enter a comic book idea.")
        else:
            with st.expander("Generation Progress", expanded=True):
                progress_placeholder = st.empty()
                comic_book = generate_comic_book(api_key, prompt, progress_placeholder)
                
                if comic_book:
                    # Show preview
                    st.header("Comic Book Preview")
                    
                    st.subheader("Comic Concept")
                    st.write(comic_book['comic_concept'])
                    
                    st.subheader("Plot")
                    st.write(comic_book['plot'])
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("Cover Page")
                        if comic_book['cover_page']:
                            cover_image = comic_book['cover_page'].get('cover.png')
                            if cover_image:
                                st.image(Image.open(BytesIO(cover_image)), width=300)
                    
                    with col2:
                        st.subheader("Characters")
                        if comic_book['character_designs']:
                            character_images = list(comic_book['character_designs'].values())
                            if character_images:
                                for i, img_data in enumerate(character_images):
                                    st.image(Image.open(BytesIO(img_data)), width=250, caption=f"Character {i+1}")
                    
                    st.subheader("Comic Panels")
                    if comic_book['comic_panels']:
                        panel_images = list(comic_book['comic_panels'].values())
                        cols = st.columns(len(panel_images))
                        for i, (col, img_data) in enumerate(zip(cols, panel_images)):
                            with col:
                                st.image(Image.open(BytesIO(img_data)), width=350, caption=f"Panel {i+1}")
                    
                    st.subheader("Recap")
                    st.write(comic_book['recap'])
                    
                    # Download button
                    zip_data = create_zip(comic_book)
                    st.download_button(
                        label="Download Comic Book ZIP",
                        data=zip_data,
                        file_name=f"comic_book_{int(time.time())}.zip",
                        mime="application/zip"
                    )

if __name__ == "__main__":
    main()
