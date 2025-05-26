import streamlit as st
import serial
import serial.tools.list_ports
from openai import OpenAI
import time
import platform

st.title("🧠 LED Control Chat via AI")

# Session setup
if 'client' not in st.session_state:
    st.session_state.client = None

# Auto-detect ports
available_ports = [port.device for port in serial.tools.list_ports.comports()]
port = st.selectbox("Select Arduino port:", available_ports) if available_ports else st.text_input("Enter Arduino port manually:")

api_key = st.text_input("Enter OpenAI API Key", type="password")
user_input = st.text_input("Your LED command:", placeholder="e.g., 'Make red blink fast, turn off yellow'")

if st.button("🚀 Send Command"):
    if not api_key or not user_input or not port:
        st.error("Please fill in all fields.")
    else:
        try:
            if st.session_state.client is None or st.session_state.get('api_key') != api_key:
                st.session_state.client = OpenAI(api_key=api_key)
                st.session_state.api_key = api_key

            with st.spinner("🤖 Interpreting command..."):
                response = st.session_state.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Convert natural language to simplified LED control commands. Only output plain commands like: 'red fast blink', 'green off', 'yellow on'. Do not explain."},
                        {"role": "user", "content": user_input},
                    ],
                    max_tokens=50
                )
                led_command = response.choices[0].message.content.strip()
                st.code(led_command, language='text')

            with st.spinner("📡 Sending to Arduino..."):
                arduino = serial.Serial(port, 9600, timeout=3)
                time.sleep(2)
                arduino.write((led_command + "\n").encode('utf-8'))
                time.sleep(1)
                if arduino.in_waiting > 0:
                    arduino_response = arduino.readline().decode('utf-8').strip()
                    st.success(f"Arduino says: {arduino_response}")
                else:
                    st.success("✅ Command sent!")
                arduino.close()

        except Exception as e:
            st.error(f"Error: {e}")
