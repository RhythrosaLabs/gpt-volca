import streamlit as st
import openai
import json

st.set_page_config(page_title="Volca Sequencer AI", layout="centered")

st.title("🎛️ Volca Sequencer AI")
st.markdown("Describe your beat idea, and AI will generate a Volca-ready pattern.")

# Secure per-session API key
api_key = st.text_input("🔐 Enter your OpenAI API Key", type="password")
if not api_key:
    st.warning("Please enter your API key to continue.")
    st.stop()

openai.api_key = api_key

# Prompt input
user_prompt = st.text_area("📝 What kind of beat would you like to create?", placeholder="e.g. Glitchy IDM loop with panned hats and polyrhythms")

if st.button("🎵 Generate Pattern") and user_prompt:
    system_prompt = """
You are a world-class MIDI sequencing AI designed to control Korg Volca Drum and Volca Sample via MIDI. 
You deeply understand:

🎵 MUSIC THEORY
- Rhythmic structures: 4/4, 3/4, polyrhythm, polymeter
- Groove, swing, quantization
- Song structure: loop, intro, fill, drop
- Instrument roles: kick, snare, hi-hat, bass, percussion

🎚️ MIDI PROGRAMMING
- CC automation (modulation, pitch, decay, pan)
- Note velocity and mapping to MIDI notes
- Use of step patterns (0–15 for 16 steps)
- Creating humanized patterns with randomness, swing

🎧 GENRE CHARACTERISTICS
- Techno: 4-on-the-floor, dark, driving
- IDM: Glitchy, non-repetitive, complex rhythms
- Hip-hop: Boom bap, swing-heavy, sample focus
- DnB: Fast BPM, rolling snares, syncopation
- Ambient: Sparse, slow, textured
- Experimental: Asymmetric patterns, wild CC mod

🎛️ VOLCA SPECIFICS
- Volca Drum/Sample uses 6 parts
- MIDI note range for parts: 36–51
- Useful CCs: pitch (40), mod amount (41), decay (43), pan (47), bitcrush (52), waveguide (58)
- Parameter values range 0–127
- Always return JSON with: bpm, steps, and per-step note/cc data

📘 FORMAT
Respond ONLY with valid JSON:
{
  "bpm": 125,
  "steps": [
    {
      "note": 36,
      "pattern": [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0],
      "cc": { "pan": 30, "pitch": 90 }
    },
    {
      "note": 38,
      "pattern": [0,0,1,0,0,0,1,0,0,1,0,0,1,0,0,0],
      "cc": { "bitcrush": 100 }
    }
  ]
}

🎯 GOAL
Translate user prompts into high-quality, playable Volca patterns.
Always match genre expectations and musicality. Prioritize musical coherence, not randomness.
Respond with JSON only.
    """

    try:
        with st.spinner("Generating pattern..."):
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )

            content = response['choices'][0]['message']['content']
            pattern_data = json.loads(content)  # Validate it's JSON
            st.success("✅ Pattern generated!")

            st.json(pattern_data)
            st.download_button("💾 Download JSON", json.dumps(pattern_data, indent=2), file_name="volca_pattern.json")

    except json.JSONDecodeError:
        st.error("⚠️ GPT did not return valid JSON. Try a simpler prompt.")
    except Exception as e:
        st.error(f"Error: {e}")
