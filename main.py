# === FILE 1: voice_controlled_volca.py ===
import mido
import openai
import time
import json
import streamlit as st
import speech_recognition as sr
from collections import defaultdict

openai.api_key = 'YOUR_OPENAI_API_KEY'

# Update this to the name of your MIDI output port (use mido.get_output_names())
MIDI_PORT = mido.open_output(mido.get_output_names()[0])

loop_layers = defaultdict(list)

device_map = {
    "drum": {
        "notes": list(range(36, 46)),
        "cc": {
            "pitch": 40, "mod_amount": 41, "mod_rate": 42, "decay": 43, "attack": 44,
            "wave_guide": 46, "pan": 47, "level": 48, "drive": 49, "overdrive": 50,
            "rate": 51, "bitcrush": 52, "wavefold": 53, "reverb": 54, "delay": 55,
            "distortion": 56, "feedback": 57, "lfo_depth": 58, "lfo_rate": 59,
            "transpose": 60, "glide": 61, "cutoff": 62, "resonance": 63, "grain": 64,
            "formant": 65, "shimmer": 66, "blur": 67, "gate": 68, "fx_mix": 69
        }
    },
    "sample": {
        "notes": list(range(0, 10)),
        "cc": {
            "level": 7, "start_point": 39, "length": 40, "hi_cut": 41, "speed": 42,
            "pitch_eg_int": 43, "attack": 44, "decay": 45, "sample_select": 46
        }
    }
}

device_type = st.radio("Select Volca device", ["drum", "sample"])
current_device = device_map[device_type]

GPT_SYSTEM_PROMPT = f"""
You are an expert MIDI programmer controlling a Korg Volca {device_type.capitalize()} using Python and mido.

### DEVICE OVERVIEW
- You can send NOTE ON/OFF messages on channel 0.
- You can send CONTROL CHANGE (CC) messages using the following parameter map:
  {json.dumps(current_device['cc'], indent=2)}
- You can trigger parts using these MIDI note numbers:
  {current_device['notes']}

### BEHAVIOR GUIDELINES
- You understand rhythmic structures and genres (e.g. techno, house, IDM, trap, ambient, glitch).
- You can generate polyrhythmic and polymetric loops.
- You understand dynamics and transitions (intro, build, drop, fill, breakdown).
- You can vary velocity/intensity and CC automation for expressive sequences.
- You can build on existing patterns by merging new layers.
- You can respond to text or voice commands like:
  - "clear all loops"
  - "play all loops"
  - "create a new techno loop with reverb"
  - "add a glitchy snare fill"
  - "modulate pitch and pan every 2 steps"

### OUTPUT FORMAT
Always respond with JSON formatted like this:
{{
  "bpm": 120,
  "steps": [
    {{
      "note": 36,
      "pattern": [1,0,1,0,1,0,1,0],
      "cc": {{
        "pitch": 64,
        "pan": 100
      }}
    }},
    {{
      "note": 38,
      "pattern": [0,0,1,0,0,1,0,1]
    }}
  ]
}}

Or respond with a command:
- `{{"command": "clear_loops"}}`
- `{{"command": "play_loops"}}`

Be creative, musical, and always follow the format.
"""


def query_gpt(text):
    messages = [
        {"role": "system", "content": GPT_SYSTEM_PROMPT},
        {"role": "user", "content": text}
    ]
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages
    )
    return response["choices"][0]["message"]["content"]

def record_loop(note, pattern):
    loop_layers[note].append(pattern)

def clear_loops():
    loop_layers.clear()

def play_all_loops():
    max_len = max(len(p) for patterns in loop_layers.values() for p in patterns)
    for i in range(max_len):
        for note, layers in loop_layers.items():
            active = any(p[i % len(p)] for p in layers)
            msg_type = 'note_on' if active else 'note_off'
            MIDI_PORT.send(mido.Message(msg_type, note=note, velocity=127 if active else 0, channel=0))
        time.sleep(0.1)

def merge_patterns(base, new):
    return [max(b, n) for b, n in zip(base, new)]

def send_to_volca(data):
    for step in data.get("steps", []):
        note = step["note"]
        pattern = step["pattern"]
        existing = loop_layers[note][-1] if loop_layers[note] else []
        merged = merge_patterns(existing, pattern) if existing else pattern
        record_loop(note, merged)

        for i in range(len(pattern)):
            msg_type = 'note_on' if pattern[i] == 1 else 'note_off'
            MIDI_PORT.send(mido.Message(msg_type, note=note, velocity=127 if pattern[i] == 1 else 0))
            time.sleep(0.1)

        for cc, val in step.get("cc", {}).items():
            if cc in current_device["cc"]:
                MIDI_PORT.send(mido.Message('control_change', control=current_device["cc"][cc], value=val))
                time.sleep(0.05)

def recognize_speech():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.info("Listening for voice input...")
        audio = recognizer.listen(source)
        try:
            text = recognizer.recognize_google(audio)
            st.success(f"You said: {text}")
            return text
        except sr.UnknownValueError:
            st.error("Could not understand audio")
        except sr.RequestError as e:
            st.error(f"Speech recognition error: {e}")
    return ""

# === STREAMLIT UI ===
st.title("GPT-Controlled Volca")
user_input = st.text_input("Describe a beat, sequence, or modulation pattern:")

if st.button("Use Voice Input"):
    voice_input = recognize_speech()
    if voice_input:
        user_input = voice_input

if st.button("Send to Volca"):
    if user_input:
        with st.spinner("Generating sequence with GPT..."):
            try:
                gpt_response = query_gpt(user_input)
                parsed = json.loads(gpt_response)
                if parsed.get("command") == "clear_loops":
                    clear_loops()
                    st.success("Cleared all loops.")
                elif parsed.get("command") == "play_loops":
                    play_all_loops()
                    st.success("Playing all loops.")
                else:
                    send_to_volca(parsed)
                    st.success("Sequence sent to Volca!")
            except Exception as e:
                st.error(f"Error: {e}")
