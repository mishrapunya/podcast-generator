import streamlit as st
import os
import re
import tempfile
import base64
from gtts import gTTS
from pydub import AudioSegment
from pydub.generators import Sine
import io

st.set_page_config(page_title="Podcast Generator", page_icon="🎙️")

st.title("Podcast Transcript to Audio Converter")
st.markdown("Upload your podcast transcript and convert it to a multi-voice audio file.")

def transcript_to_podcast(transcript_text):
    """
    Convert a podcast transcript with multiple speakers into an audio file with different voices.
    
    Parameters:
    transcript_text (str): The podcast transcript text
    
    Returns:
    bytes: The final audio file as bytes
    """
    # Parse the transcript to identify speakers and their lines
    pattern = r'([A-Za-z]+):\s*((?:.+?)(?=\n[A-Za-z]+:|$|\[))'
    speaker_turns = re.findall(pattern, transcript_text, re.DOTALL)
    
    # Also find music/sound cues in square brackets
    sound_cues = re.findall(r'\[(.*?)\]', transcript_text)
    
    # Extract unique speakers
    speakers = list(set([turn[0].strip() for turn in speaker_turns]))
    st.write(f"Found {len(speakers)} speakers: {', '.join(speakers)}")
    st.write(f"Found {len(sound_cues)} sound cues")
    
    # Assign specific voices based on demographics:
    # - Priyal and Arpita are Indian women
    # - Karina is an American woman
    # - Bret is an American man
    
    # Define voice settings
    indian_female = {'lang': 'en-in', 'tld': 'co.in'}     # Indian English
    american_female = {'lang': 'en-us', 'tld': 'com'}     # American English female
    american_male = {'lang': 'en-us', 'tld': 'com'}       # American English male
    
    # Unfortunately, gTTS doesn't have gender-specific voices, but we'll note them for reference
    
    # Directly assign appropriate voices to each speaker
    speaker_voices = {
        'Priyal': indian_female,
        'Arpita': indian_female,
        'Karina': american_female,
        'Bret': american_male,
    }
    
    # For any other speakers that might be in the transcript
    default_voice = {'lang': 'en-us', 'tld': 'com'}
    for speaker in speakers:
        if speaker not in speaker_voices:
            speaker_voices[speaker] = default_voice
    
    # Create temporary directory for audio segments
    temp_dir = tempfile.mkdtemp()
    segments = []
    
    # Create intro music
    intro_music = generate_music(5000, "intro")  # 5 seconds of intro music
    intro_music = intro_music.fade_in(1000).fade_out(2000)
    segments.append(intro_music)
    
    # Process each dialogue turn and sound cue in order
    all_elements = []
    
    # First, rebuild the script in order with both dialogue and sound cues
    # Extract positions of sound cues
    cue_positions = [(m.start(), m.group()) for m in re.finditer(r'\[(.*?)\]', transcript_text)]
    
    # Extract positions of speaker turns
    turn_positions = []
    for match in re.finditer(r'([A-Za-z]+):\s*', transcript_text):
        speaker = match.group(1)
        start_pos = match.end()
        
        # Find the end of this turn (next speaker or end of text)
        next_speaker_match = re.search(r'\n[A-Za-z]+:', transcript_text[start_pos:])
        next_cue_match = re.search(r'\[', transcript_text[start_pos:])
        
        end_pos = len(transcript_text)
        if next_speaker_match:
            candidate_end = start_pos + next_speaker_match.start()
            if candidate_end < end_pos:
                end_pos = candidate_end
        if next_cue_match:
            candidate_end = start_pos + next_cue_match.start()
            if candidate_end < end_pos:
                end_pos = candidate_end
        
        turn_positions.append((match.start(), (speaker, transcript_text[start_pos:end_pos].strip())))
    
    # Combine and sort all elements by position
    all_elements = cue_positions + turn_positions
    all_elements.sort(key=lambda x: x[0])
    
    # Create progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Process each element in order
    for i, (_, element) in enumerate(all_elements):
        # Update progress
        progress = int((i / len(all_elements)) * 100)
        progress_bar.progress(progress)
        
        if isinstance(element, tuple):  # Speaker turn
            speaker, text = element
            if not text:
                continue
                
            status_text.text(f"Converting {speaker}'s dialogue...")
            
            # Create TTS audio
            segment_file = os.path.join(temp_dir, f"segment_{len(segments)}.mp3")
            voice = speaker_voices[speaker]
            tts = gTTS(text=text, lang=voice['lang'], tld=voice['tld'], slow=False)
            tts.save(segment_file)
            
            # Add a short pause after each speaker (300ms)
            speaker_audio = AudioSegment.from_file(segment_file)
            pause = AudioSegment.silent(duration=300)
            segments.append(speaker_audio)
            segments.append(pause)
            
        else:  # Sound cue
            cue_text = element.strip('[]').lower()
            status_text.text(f"Processing sound cue: {cue_text}")
            
            if "music" in cue_text and "fade" in cue_text:
                if "in" in cue_text:
                    music = generate_music(3000, "background").fade_in(1500)
                    segments.append(music)
                elif "out" in cue_text:
                    music = generate_music(3000, "outro").fade_out(2000)
                    segments.append(music)
            elif "all:" in cue_text.lower():
                # Create "See you next time" with mixed voices
                all_segment_file = os.path.join(temp_dir, "all_voices.mp3")
                text = cue_text.split(":", 1)[1].strip()
                
                # Create a combined audio of all voices saying the same thing
                all_voices = AudioSegment.silent(duration=0)
                for i, speaker in enumerate(speakers):
                    voice = speaker_voices[speaker]
                    temp_file = os.path.join(temp_dir, f"all_voice_{i}.mp3")
                    tts = gTTS(text=text, lang=voice['lang'], tld=voice['tld'], slow=False)
                    tts.save(temp_file)
                    voice_segment = AudioSegment.from_file(temp_file)
                    all_voices = all_voices.overlay(voice_segment, position=i*100)  # Slightly staggered
                
                segments.append(all_voices)
    
    # Combine all segments into final audio
    if segments:
        status_text.text("Combining audio segments...")
        final_audio = segments[0]
        for segment in segments[1:]:
            final_audio += segment
            
        # Export the final podcast to a BytesIO object
        audio_bytes = io.BytesIO()
        final_audio.export(audio_bytes, format="mp3")
        audio_bytes.seek(0)
        
        status_text.text("Podcast generation complete!")
        progress_bar.progress(100)
        
        return audio_bytes.getvalue()
    else:
        st.error("No audio segments were created.")
        return None

def generate_music(duration_ms, music_type="background"):
    """Generate simple music tones based on the type needed"""
    if music_type == "intro":
        # Create a simple jingle for intro
        tone1 = Sine(440).to_audio_segment(duration=500).apply_gain(-3)  # A4
        tone2 = Sine(494).to_audio_segment(duration=500).apply_gain(-3)  # B4
        tone3 = Sine(523).to_audio_segment(duration=500).apply_gain(-3)  # C5
        jingle = tone1 + tone2 + tone3 + tone3 + tone2 + tone1
        return jingle * (duration_ms // len(jingle) + 1)
    elif music_type == "outro":
        # Create a simple outro
        tone1 = Sine(523).to_audio_segment(duration=500).apply_gain(-3)  # C5
        tone2 = Sine(494).to_audio_segment(duration=500).apply_gain(-3)  # B4
        tone3 = Sine(440).to_audio_segment(duration=500).apply_gain(-3)  # A4
        jingle = tone1 + tone2 + tone3 + tone3 + tone2 + tone1
        return jingle * (duration_ms // len(jingle) + 1)
    else:
        # Background music - gentle tone
        tone = Sine(392).to_audio_segment(duration=duration_ms).apply_gain(-10)  # G4 at lower volume
        return tone

# File uploader
uploaded_file = st.file_uploader("Upload your transcript file", type=["txt"])

# Text area for direct input
transcript_text = st.text_area("Or paste your transcript here:", height=300)

# Sample data button
if st.button("Use Sample Podcast Script"):
    transcript_text = """PODCAST SCRIPT (5-minute episode)
[INTRO MUSIC FADES IN]

Arpita: Welcome to "Creative Minds: The AI Edition," where we discuss the intersection of artificial intelligence and human creativity. I'm Arpita.

Bret: I'm Bret.

Karina: Karina here.

Priyal: And I'm Priyal. Today, we're reflecting on what we've learned so far in our AI and Creativity course as we approach mid-semester.

Arpita: So, we're about halfway through this fascinating journey exploring how AI can amplify our creative abilities. What's been your biggest takeaway so far?

[OUTRO MUSIC FADES IN]

ALL: See you next time!

[MUSIC FADES OUT]"""

# Process the transcript
if st.button("Generate Podcast Audio"):
    if uploaded_file is not None:
        transcript_text = uploaded_file.getvalue().decode("utf-8")
    
    if transcript_text:
        with st.spinner("Generating podcast audio..."):
            audio_bytes = transcript_to_podcast(transcript_text)
            
            if audio_bytes:
                st.audio(audio_bytes, format="audio/mp3")
                
                # Create download button
                b64 = base64.b64encode(audio_bytes).decode()
                href = f'<a href="data:audio/mp3;base64,{b64}" download="podcast.mp3">Download MP3 File</a>'
                st.markdown(href, unsafe_allow_html=True)
    else:
        st.error("Please upload a transcript file or paste transcript text.")

# Information section
with st.expander("How to Format Your Transcript"):
    st.markdown("""
    ## Formatting Guidelines
    
    1. **Speaker Format**: Each line should begin with the speaker's name followed by a colon:
       ```
       Speaker: Their dialogue goes here.
       ```
    
    2. **Sound Cues**: Put sound effects and music cues in square brackets:
       ```
       [INTRO MUSIC FADES IN]
       ```
    
    3. **Group Speaking**: For lines spoken by everyone, use:
       ```
       ALL: Text spoken by everyone together.
       ```
    """)

st.sidebar.title("About")
st.sidebar.info("""
This app converts podcast transcripts to multi-voice audio files using Google Text-to-Speech.

Features:
- Voice assignment based on demographics
- Automatic sound cue processing
- Multiple speaker support
- One-click download
""")
