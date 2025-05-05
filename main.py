import streamlit as st
import json
import requests
import zipfile
import os
import time
from io import BytesIO
from PIL import Image

# OpenRouter setup
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
IMAGE_API_URL = "https://api.openai.com/v1/images/generations"  # Keep DALL-E for images
API_KEY_FILE = "api_key.json"

# Available models on OpenRouter
OPENROUTER_MODELS = {
    "OpenAI": [
        {"id": "openai/gpt-4-turbo", "name": "GPT-4 Turbo"},
        {"id": "openai/gpt-4", "name": "GPT-4"},
        {"id": "openai/gpt-3.5-turbo", "name": "GPT-3.5 Turbo"}
    ],
    "Anthropic": [
        {"id": "anthropic/claude-3-opus", "name": "Claude 3 Opus"},
        {"id": "anthropic/claude-3-sonnet", "name": "Claude 3 Sonnet"},
        {"id": "anthropic/claude-3-haiku", "name": "Claude 3 Haiku"},
        {"id": "anthropic/claude-2", "name": "Claude 2"}
    ],
    "Meta": [
        {"id": "meta-llama/llama-3-70b-instruct", "name": "Llama 3 70B Instruct"},
        {"id": "meta-llama/llama-3-8b-instruct", "name": "Llama 3 8B Instruct"},
        {"id": "meta-llama/llama-2-70b-chat", "name": "Llama 2 70B Chat"}
    ],
    "Mistral": [
        {"id": "mistralai/mistral-large", "name": "Mistral Large"},
        {"id": "mistralai/mistral-7b-instruct", "name": "Mistral 7B Instruct"},
        {"id": "mistralai/mixtral-8x7b-instruct", "name": "Mixtral 8x7B Instruct"}
    ],
    "DeepSeek": [
        {"id": "deepseek/deepseek-coder", "name": "DeepSeek Coder"},
        {"id": "deepseek/deepseek-llm-67b-chat", "name": "DeepSeek LLM 67B Chat"}
    ],
    "Google": [
        {"id": "google/gemini-pro", "name": "Gemini Pro"}
    ],
    "Other": [
        {"id": "cohere/command-r-plus", "name": "Cohere Command R+"},
        {"id": "perplexity/sonar-small-online", "name": "Perplexity Sonar Small"},
        {"id": "phind/phind-codellama-34b", "name": "Phind CodeLlama 34B"}
    ]
}

# Image generation models
IMAGE_MODELS = [
    {"id": "dall-e-3", "name": "DALL-E 3"},
    {"id": "dall-e-2", "name": "DALL-E 2"},
    {"id": "sdxl", "name": "Stable Diffusion XL"}
]

def load_api_keys():
    """Load API keys from file if it exists"""
    if os.path.exists(API_KEY_FILE):
        try:
            with open(API_KEY_FILE, 'r') as file:
                data = json.load(file)
                return {
                    "openrouter_api_key": data.get('openrouter_api_key', ''),
                    "dalle_api_key": data.get('dalle_api_key', '')
                }
        except Exception:
            return {"openrouter_api_key": "", "dalle_api_key": ""}
    return {"openrouter_api_key": "", "dalle_api_key": ""}

def save_api_keys(openrouter_api_key, dalle_api_key):
    """Save API keys to file"""
    with open(API_KEY_FILE, 'w') as file:
        json.dump({
            "openrouter_api_key": openrouter_api_key,
            "dalle_api_key": dalle_api_key
        }, file)

def generate_content(api_key, prompt, action, model):
    """Generate text content using OpenRouter"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://comic-book-creator.streamlit.app",  # Replace with your domain
        "X-Title": "Comic Book Creator"
    }
    
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": f"You are a helpful assistant specializing in {action}."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=data)
        response.raise_for_status()
        response_data = response.json()
        if "choices" not in response_data:
            error_message = response_data.get("error", {}).get("message", "Unknown error")
            return f"Error: {error_message}"

        content_text = response_data["choices"][0]["message"]["content"]
        return content_text

    except requests.RequestException as e:
        return f"Error: Unable to communicate with OpenRouter API. {str(e)}"

def generate_image(api_key, prompt, image_model="dall-e-3", size="1024x1024"):
    """Generate image using selected image model"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": image_model,
        "prompt": prompt,
        "n": 1,
        "size": size,
        "quality": "hd" if image_model == "dall-e-3" else "standard",
        "style": "vivid" if image_model in ["dall-e-3", "dall-e-2"] else None,
        "response_format": "url"
    }
    
    # Remove None values from data
    data = {k: v for k, v in data.items() if v is not None}
    
    try:
        response = requests.post(IMAGE_API_URL, headers=headers, json=data)
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

def generate_comic_book(openrouter_api_key, dalle_api_key, user_prompt, text_model, image_model, progress_placeholder):
    """Generate a complete comic book based on user prompt"""
    comic_book = {}
    
    # Update progress bar
    progress_bar = progress_placeholder.progress(0)
    status_text = st.empty()
    
    try:
        # Step 1: Generate comic book concept
        status_text.text("Generating comic book concept...")
        progress_bar.progress(10)
        comic_concept = generate_content(openrouter_api_key, f"Create a detailed comic book concept based on the following prompt: {user_prompt}.", "comic book concept creation", text_model)
        comic_book['comic_concept'] = comic_concept
        
        # Step 2: Generate detailed plot
        status_text.text("Generating detailed plot...")
        progress_bar.progress(20)
        comic_book['plot'] = generate_content(openrouter_api_key, f"Create a detailed plot for the comic book: {comic_concept}", "comic book plot development", text_model)
        
        # Step 3: Generate character designs
        status_text.text("Generating character designs...")
        progress_bar.progress(30)
        character_designs = {}
        
        character_prompt = f"Full-body character design for the comic book, based on the following description: {comic_concept}"
        image_url = generate_image(dalle_api_key, character_prompt, image_model)
        if image_url:
            image_data = download_image(image_url)
            if image_data:
                character_designs["character_1.png"] = image_data
        
        character_prompt_2 = f"Another full-body character design for the comic book, based on the following description: {comic_concept}"
        image_url = generate_image(dalle_api_key, character_prompt_2, image_model)
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
        image_url = generate_image(dalle_api_key, panel_prompt_1, image_model)
        if image_url:
            image_data = download_image(image_url)
            if image_data:
                comic_panels["panel_1.png"] = image_data
        
        panel_prompt_2 = f"Comic panel illustrating another key scene from the comic book, based on the following description: {comic_concept}"
        image_url = generate_image(dalle_api_key, panel_prompt_2, image_model)
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
        image_url = generate_image(dalle_api_key, cover_prompt, image_model)
        if image_url:
            image_data = download_image(image_url)
            if image_data:
                cover_page["cover.png"] = image_data
                
        comic_book['cover_page'] = cover_page
        
        # Step 6: Generate recap
        status_text.text("Generating recap...")
        progress_bar.progress(80)
        comic_book['recap'] = generate_content(openrouter_api_key, f"Recap the comic book content: {comic_concept}", "comic book recap", text_model)
        
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
    st.markdown("Generate custom comic books using AI with OpenRouter Models!")
    
    # API Key setup
    api_keys = load_api_keys()
    
    with st.sidebar:
        st.header("Settings")
        
        st.subheader("API Keys")
        openrouter_api_key = st.text_input("OpenRouter API Key", 
                                         value=api_keys["openrouter_api_key"] if api_keys["openrouter_api_key"] else "", 
                                         type="password",
                                         help="Get your key at https://openrouter.ai/keys")
        
        dalle_api_key = st.text_input("DALL-E API Key (for images)", 
                                    value=api_keys["dalle_api_key"] if api_keys["dalle_api_key"] else "", 
                                    type="password",
                                    help="Get your key at https://platform.openai.com/api-keys")
        
        if st.button("Save API Keys"):
            save_api_keys(openrouter_api_key, dalle_api_key)
            st.success("API keys saved!")
        
        st.subheader("Model Selection")
        
        # Text model selection
        st.markdown("#### Text Model")
        category = st.selectbox("Provider", options=list(OPENROUTER_MODELS.keys()))
        
        model_options = [(model["id"], model["name"]) for model in OPENROUTER_MODELS[category]]
        text_model = st.selectbox(
            "Text Model",
            options=[model[0] for model in model_options],
            format_func=lambda x: next((model[1] for model in model_options if model[0] == x), x)
        )
        
        # Image model selection
        st.markdown("#### Image Model")
        image_model = st.selectbox(
            "Image Model",
            options=[model["id"] for model in IMAGE_MODELS],
            format_func=lambda x: next((model["name"] for model in IMAGE_MODELS if model["id"] == x), x)
        )
    
    # Main content
    prompt = st.text_input("Enter your comic book idea:", placeholder="e.g., A superhero who can control time but ages faster when using powers")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        generate_button = st.button("Generate Comic Book", type="primary", use_container_width=True)
    
    if generate_button:
        if not openrouter_api_key:
            st.error("Please enter an OpenRouter API key in the settings panel.")
        elif not dalle_api_key:
            st.error("Please enter a DALL-E API key in the settings panel.")
        elif not prompt:
            st.warning("Please enter a comic book idea.")
        else:
            with st.expander("Generation Progress", expanded=True):
                progress_placeholder = st.empty()
                comic_book = generate_comic_book(openrouter_api_key, dalle_api_key, prompt, text_model, image_model, progress_placeholder)
                
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
