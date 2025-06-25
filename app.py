import gradio as gr
import edge_tts
import asyncio
import tempfile
import os
import json
import datetime
import re
import io


async def get_voices():
    voices = await edge_tts.list_voices()
    return {
        f"{v['ShortName']} - {v['Locale']} ({v['Gender']})": v["ShortName"]
        for v in voices
    }


def format_time(milliseconds):
    """Convert milliseconds to SRT time format (HH:MM:SS,mmm)"""
    # Ensure milliseconds is an integer
    milliseconds = int(milliseconds)
    seconds, milliseconds = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def time_to_ms(time_str):
    """Convert SRT time format (HH:MM:SS,mmm) to milliseconds"""
    hours, minutes, rest = time_str.split(':')
    seconds, milliseconds = rest.split(',')
    return int(hours) * 3600000 + int(minutes) * 60000 + int(seconds) * 1000 + int(milliseconds)


def parse_srt_content(content):
    """Parse SRT file content and extract text and timing data"""
    lines = content.split('\n')
    timing_data = []
    text_only = []
    
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
            
        # Check if this is a subtitle number line
        if lines[i].strip().isdigit():
            subtitle_num = int(lines[i].strip())
            i += 1
            if i >= len(lines):
                break
                
            # Parse timestamp line
            timestamp_match = re.search(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', lines[i])
            if timestamp_match:
                start_time = timestamp_match.group(1)
                end_time = timestamp_match.group(2)
                
                # Convert to milliseconds
                start_ms = time_to_ms(start_time)
                end_ms = time_to_ms(end_time)
                
                i += 1
                subtitle_text = ""
                
                # Collect all text lines until empty line or end of file
                while i < len(lines) and lines[i].strip():
                    subtitle_text += lines[i] + " "
                    i += 1
                
                subtitle_text = subtitle_text.strip()
                text_only.append(subtitle_text)
                timing_data.append({
                    'text': subtitle_text,
                    'start': start_ms,
                    'end': end_ms
                })
        else:
            i += 1
    
    return " ".join(text_only), timing_data


async def process_uploaded_file(file):
    """Process uploaded file and detect if it's SRT or plain text"""
    if file is None:
        return None, None, False, None
    
    try:
        file_path = file.name if hasattr(file, 'name') else file
        file_extension = os.path.splitext(file_path)[1].lower()
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if it's an SRT file
        is_subtitle = False
        timing_data = None
        
        if file_extension == '.srt' or re.search(r'^\d+\s*\n\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}', content, re.MULTILINE):
            is_subtitle = True
            text_content, timing_data = parse_srt_content(content)
            # Return original content for display
            return text_content, timing_data, is_subtitle, content
        else:
            # Treat as plain text
            text_content = content
        
        return text_content, timing_data, is_subtitle, content
    except Exception as e:
        return f"Error processing file: {str(e)}", None, False, None


async def update_text_from_file(file):
    """Callback function to update text area when file is uploaded"""
    if file is None:
        return "", None
    
    text_content, timing_data, is_subtitle, original_content = await process_uploaded_file(file)
    if original_content is not None:
        # Return the original content to preserve formatting
        return original_content, None
    return "", gr.Warning("Failed to process the file")


async def text_to_speech(text, voice, rate, pitch, generate_subtitles=False, uploaded_file=None):
    """Convert text to speech, handling both direct text input and uploaded files"""
    if not text.strip() and uploaded_file is None:
        return None, None, "Please enter text or upload a file to convert."
    if not voice:
        return None, None, "Please select a voice."

    # First, determine if the text is SRT format
    is_srt_format = bool(re.search(r'^\d+\s*\n\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}', text, re.MULTILINE))
    
    # If the text is in SRT format, parse it directly
    if is_srt_format:
        text_content, timing_data = parse_srt_content(text)
        is_subtitle = True
    else:
        # Process uploaded file if provided
        timing_data = None
        is_subtitle = False
        
        if uploaded_file is not None:
            file_text, file_timing_data, file_is_subtitle, _ = await process_uploaded_file(uploaded_file)
            if isinstance(file_text, str) and file_text.strip():
                if file_is_subtitle:
                    text = file_text
                    timing_data = file_timing_data
                    is_subtitle = file_is_subtitle

    voice_short_name = voice.split(" - ")[0]
    rate_str = f"{rate:+d}%"
    pitch_str = f"{pitch:+d}Hz"
    
    # Create temporary file for audio
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
        audio_path = tmp_file.name
    
    subtitle_path = None
    
    # Handle SRT-formatted text or subtitle files differently for audio generation
    if is_srt_format or (is_subtitle and timing_data):
        # Create separate audio files for each subtitle entry and then combine them
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_segments = []
            max_end_time = 0
            
            # If we don't have timing data but have SRT format text, parse it
            if not timing_data and is_srt_format:
                _, timing_data = parse_srt_content(text)
            
            # Process each subtitle entry separately
            for i, entry in enumerate(timing_data):
                segment_text = entry['text']
                start_time = entry['start']
                end_time = entry['end']
                max_end_time = max(max_end_time, end_time)
                
                # Create temporary file for this segment
                segment_file = os.path.join(temp_dir, f"segment_{i}.mp3")
                
                # Generate audio for this segment
                communicate = edge_tts.Communicate(segment_text, voice_short_name, rate=rate_str, pitch=pitch_str)
                await communicate.save(segment_file)
                
                audio_segments.append({
                    'file': segment_file,
                    'start': start_time,
                    'end': end_time,
                    'text': segment_text
                })
            
            # Combine audio segments with proper timing
            import wave
            import audioop
            from pydub import AudioSegment
            
            # Initialize final audio
            final_audio = AudioSegment.silent(duration=max_end_time + 1000)  # Add 1 second buffer
            
            # Add each segment at its proper time
            for segment in audio_segments:
                segment_audio = AudioSegment.from_file(segment['file'])
                final_audio = final_audio.overlay(segment_audio, position=segment['start'])
            
            # Export the combined audio
            final_audio.export(audio_path, format="mp3")
            
            # Generate subtitles if requested
            if generate_subtitles:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".srt") as srt_file:
                    subtitle_path = srt_file.name
                    with open(subtitle_path, "w", encoding="utf-8") as f:
                        for i, entry in enumerate(timing_data):
                            f.write(f"{i+1}\n")
                            f.write(f"{format_time(entry['start'])} --> {format_time(entry['end'])}\n")
                            f.write(f"{entry['text']}\n\n")
    else:
        # Use the existing approach for regular text
        communicate = edge_tts.Communicate(text, voice_short_name, rate=rate_str, pitch=pitch_str)
        if not generate_subtitles:
            await communicate.save(audio_path)
        if generate_subtitles:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".srt") as srt_file:
                subtitle_path = srt_file.name
                
            # Generate audio and collect word boundary data
            async def process_audio():
                word_boundaries = []
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        with open(audio_path, "ab") as audio_file:
                            audio_file.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        word_boundaries.append(chunk)
                return word_boundaries
            
            word_boundaries = await process_audio()
            
            # Group words into sensible phrases/sentences for subtitles
            phrases = []
            current_phrase = []
            current_text = ""
            phrase_start = 0
            
            for i, boundary in enumerate(word_boundaries):
                word = boundary["text"]
                start_time = boundary["offset"] / 10000
                duration = boundary["duration"] / 10000
                end_time = start_time + duration
                
                if not current_phrase:
                    phrase_start = start_time
                    
                current_phrase.append(boundary)
                
                if word in ['.', ',', '!', '?', ':', ';'] or word.startswith(('.', ',', '!', '?', ':', ';')):
                    current_text = current_text.rstrip() + word + " "
                else:
                    current_text += word + " "
                
                # Determine if we should end this phrase and start a new one
                should_break = False
                
                # Break on punctuation
                if word.endswith(('.', '!', '?', ':', ';', ',')) or i == len(word_boundaries) - 1:
                    should_break = True
                    
                # Break after a certain number of words (4-5 is typical for subtitles)
                elif len(current_phrase) >= 5:
                    should_break = True
                    
                # Break on long pause (more than 300ms between words)
                elif i < len(word_boundaries) - 1:
                    next_start = word_boundaries[i + 1]["offset"] / 10000
                    if next_start - end_time > 300:
                        should_break = True
            
                if should_break or i == len(word_boundaries) - 1:
                    if current_phrase:
                        last_boundary = current_phrase[-1]
                        phrase_end = (last_boundary["offset"] + last_boundary["duration"]) / 10000
                        phrases.append({
                            "text": current_text.strip(),
                            "start": phrase_start,
                            "end": phrase_end
                        })
                        current_phrase = []
                        current_text = ""
            
            # Write phrases to SRT file
            with open(subtitle_path, "w", encoding="utf-8") as srt_file:
                for i, phrase in enumerate(phrases):
                    # Write SRT entry
                    srt_file.write(f"{i+1}\n")
                    srt_file.write(f"{format_time(phrase['start'])} --> {format_time(phrase['end'])}\n")
                    srt_file.write(f"{phrase['text']}\n\n")
    
    return audio_path, subtitle_path, None


async def tts_interface(text, voice, rate, pitch, generate_subtitles, uploaded_file=None):
    audio, subtitle, warning = await text_to_speech(text, voice, rate, pitch, generate_subtitles, uploaded_file)
    if warning:
        return audio, subtitle, gr.Warning(warning)
    return audio, subtitle, None


async def parse_multi_speaker_text(text):
    """Parse text containing speaker designations like 'Speaker1: Hello'"""
    lines = text.split('\n')
    speaker_segments = []
    current_speaker = None
    current_text = []
    
    speaker_pattern = re.compile(r'^(Speaker\s*\d+|S\d+)\s*:\s*(.*)$', re.IGNORECASE)
    
    for line in lines:
        match = speaker_pattern.match(line.strip())
        if match:
            # If collecting text for a previous speaker, save it
            if current_speaker and current_text:
                speaker_segments.append({
                    'speaker': current_speaker,
                    'text': ' '.join(current_text).strip()
                })
                current_text = []
            
            # Set the new current speaker and start collecting their text
            current_speaker = match.group(1).strip()
            if match.group(2).strip():  # If there's text after the speaker designation
                current_text.append(match.group(2).strip())
        elif line.strip() and current_speaker:  # Continue with the current speaker
            current_text.append(line.strip())
    
    # Add the last speaker's text if any
    if current_speaker and current_text:
        speaker_segments.append({
            'speaker': current_speaker,
            'text': ' '.join(current_text).strip()
        })
    
    return speaker_segments

async def multi_speaker_tts(text, speaker_settings, generate_subtitles=False):
    """Process multi-speaker text and generate audio with different voices and settings"""
    if not text.strip():
        return None, None, "Please enter text to convert."
    
    # Parse the multi-speaker text
    speaker_segments = await parse_multi_speaker_text(text)
    if not speaker_segments:
        return None, None, "No valid speaker segments found in the text."
    
    # Create temporary file for final audio
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
        final_audio_path = tmp_file.name
    
    subtitle_path = None
    if generate_subtitles:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".srt") as srt_file:
            subtitle_path = srt_file.name
    
    # Process each speaker segment with the corresponding voice
    with tempfile.TemporaryDirectory() as temp_dir:
        audio_segments = []
        subtitle_entries = []
        current_offset = 0  # Track the time offset in milliseconds
        
        for i, segment in enumerate(speaker_segments):
            speaker = segment['speaker']
            text = segment['text']
            
            # Get the voice for this speaker
            speaker_num = int(re.search(r'\d+', speaker).group()) if re.search(r'\d+', speaker) else 1
            speaker_idx = min(speaker_num - 1, len(speaker_settings) - 1)  # Ensure we don't go out of bounds
            
            if speaker_idx < 0 or speaker_idx >= len(speaker_settings) or not speaker_settings[speaker_idx]['voice']:
                return None, None, f"No voice selected for {speaker}."
            
            # Get voice, rate, and pitch for this speaker
            voice_short_name = speaker_settings[speaker_idx]['voice'].split(" - ")[0]
            rate_str = f"{speaker_settings[speaker_idx]['rate']:+d}%"
            pitch_str = f"{speaker_settings[speaker_idx]['pitch']:+d}Hz"
            
            # Create temporary file for this segment
            segment_file = os.path.join(temp_dir, f"segment_{i}.mp3")
            
            # Generate audio for this segment with speaker-specific settings
            communicate = edge_tts.Communicate(text, voice_short_name, rate=rate_str, pitch=pitch_str)
            
            # For subtitle generation, we need word boundaries
            if generate_subtitles:
                word_boundaries = []
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        with open(segment_file, "ab") as audio_file:
                            audio_file.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        # Adjust offset to account for previous segments
                        adjusted_chunk = chunk.copy()
                        adjusted_chunk["offset"] += current_offset * 10000  # Convert ms to 100ns units
                        word_boundaries.append(adjusted_chunk)
                
                # Process word boundaries for subtitles
                if word_boundaries:
                    # Group words into phrases for subtitles
                    phrases = []
                    current_phrase = []
                    current_text = ""
                    phrase_start = 0
                    
                    for j, boundary in enumerate(word_boundaries):
                        word = boundary["text"]
                        start_time = boundary["offset"] / 10000
                        duration = boundary["duration"] / 10000
                        end_time = start_time + duration
                        
                        if not current_phrase:
                            phrase_start = start_time
                            
                        current_phrase.append(boundary)
                        
                        if word in ['.', ',', '!', '?', ':', ';'] or word.startswith(('.', ',', '!', '?', ':', ';')):
                            current_text = current_text.rstrip() + word + " "
                        else:
                            current_text += word + " "
                        
                        # Determine if we should end this phrase
                        should_break = False
                        
                        if word.endswith(('.', '!', '?', ':', ';', ',')) or j == len(word_boundaries) - 1:
                            should_break = True
                        elif len(current_phrase) >= 5:
                            should_break = True
                        elif j < len(word_boundaries) - 1:
                            next_start = word_boundaries[j + 1]["offset"] / 10000
                            if next_start - end_time > 300:
                                should_break = True
                    
                        if should_break or j == len(word_boundaries) - 1:
                            if current_phrase:
                                last_boundary = current_phrase[-1]
                                phrase_end = (last_boundary["offset"] + last_boundary["duration"]) / 10000
                                phrases.append({
                                    "text": f"[{speaker}] {current_text.strip()}",
                                    "start": phrase_start,
                                    "end": phrase_end
                                })
                                subtitle_entries.extend(phrases)
                                current_phrase = []
                                current_text = ""
            else:
                # Simple audio generation without subtitles
                await communicate.save(segment_file)
            
            # Get duration of the generated audio
            from pydub import AudioSegment
            audio = AudioSegment.from_file(segment_file)
            duration = len(audio)
            
            audio_segments.append({
                'file': segment_file,
                'duration': duration
            })
            
            # Update the current offset for the next segment
            current_offset += duration
        
        # Combine all audio segments
        from pydub import AudioSegment
        
        combined = AudioSegment.empty()
        for segment in audio_segments:
            audio = AudioSegment.from_file(segment['file'])
            combined += audio
        
        combined.export(final_audio_path, format="mp3")
        
        # Generate subtitles file if requested
        if generate_subtitles and subtitle_path:
            with open(subtitle_path, "w", encoding="utf-8") as f:
                for i, entry in enumerate(subtitle_entries):
                    f.write(f"{i+1}\n")
                    f.write(f"{format_time(entry['start'])} --> {format_time(entry['end'])}\n")
                    f.write(f"{entry['text']}\n\n")
    
    return final_audio_path, subtitle_path, None

async def multi_speaker_interface(text, generate_subtitles, speaker1_voice, speaker1_rate, speaker1_pitch, 
                                  speaker2_voice, speaker2_rate, speaker2_pitch):
    """Interface function for multi-speaker TTS"""
    # Create speaker settings from individual parameters
    speaker_settings = []
    
    # Add Speaker 1 if voice is selected
    if speaker1_voice:
        speaker_settings.append({
            'voice': speaker1_voice,
            'rate': speaker1_rate,
            'pitch': speaker1_pitch
        })
    
    # Add Speaker 2 if voice is selected
    if speaker2_voice:
        speaker_settings.append({
            'voice': speaker2_voice,
            'rate': speaker2_rate,
            'pitch': speaker2_pitch
        })
    
    if not speaker_settings:
        return None, None, gr.Warning("Please select at least one speaker voice.")
    
    audio, subtitle, warning = await multi_speaker_tts(text, speaker_settings, generate_subtitles)
    if warning:
        return audio, subtitle, gr.Warning(warning)
    return audio, subtitle, None

async def create_demo():
    voices = await get_voices()

    description = """
    Convert text to speech using Microsoft Edge TTS. Adjust speech rate and pitch: 0 is default, positive values increase, negative values decrease.
    You can also generate subtitle files (.srt) along with the audio.
    
    **Note:** Edge TTS is a cloud-based service and requires an active internet connection."""

    features = """
    ## ✨ Latest Features
    - **Single & Multi-Speaker Support**: Choose between single speaker or multi-speaker modes
    - **SRT Subtitle Support**: Upload SRT files or input SRT format text to generate perfectly synchronized speech
    - **SRT Generation**: Create subtitle files alongside your audio for perfect timing
    - **File Upload**: Easily upload TXT or SRT files for conversion
    - **Smart Format Detection**: Automatically detects plain text or SRT subtitle format
    """

    with gr.Blocks(title="Edge TTS Text-to-Speech", analytics_enabled=False) as demo:
        gr.Markdown("# Edge TTS Text-to-Speech Converter")
        gr.Markdown(description)
        gr.Markdown(features)
        
        with gr.Tabs() as tabs:
            with gr.Tab("Single Speaker"):
                with gr.Row():
                    with gr.Column(scale=3):
                        text_input = gr.Textbox(label="Input Text", lines=5, value="Hello, how are you doing!")
                        file_input = gr.File(label="Or upload a TXT/SRT file", file_types=[".txt", ".srt"])
                    with gr.Column(scale=2):
                        voice_dropdown = gr.Dropdown(
                            choices=[""] + list(voices.keys()),
                            label="Select Voice",
                            value=list(voices.keys())[0] if voices else "",
                        )
                        rate_slider = gr.Slider(
                            minimum=-50,
                            maximum=50,
                            value=0,
                            label="Speech Rate Adjustment (%)",
                            step=1,
                        )
                        pitch_slider = gr.Slider(
                            minimum=-20, maximum=20, value=0, label="Pitch Adjustment (Hz)", step=1
                        )
                        subtitle_checkbox = gr.Checkbox(label="Generate Subtitles (.srt)", value=False)
                        gr.Markdown("""
                            **📝 Subtitle Timing Tip:**
                            
                            When creating SRT files for continuous speech, avoid exact matching timestamps between segments.
                            
                            **For smoother speech flow:**
                            ```
                            1
                            00:00:00,112 --> 00:00:01,647
                            Hello how are you doing
                            
                            2
                            00:00:01,617 --> 00:00:02,000
                            I'm fine
                            ```
                            
                            ✅ Create a small overlap (20-30ms) between segments to prevent pauses
                            ❌ Avoid exact matching timestamps (where end time = next start time) except you want a pause
                        """)
                
                submit_single_btn = gr.Button("Convert to Speech", variant="primary")
                warning_single_md = gr.Markdown(visible=False)
                
                single_outputs = [
                    gr.Audio(label="Generated Audio", type="filepath"),
                    gr.File(label="Generated Subtitles"),
                    warning_single_md
                ]
                
                # Handle file upload to update text
                file_input.change(
                    fn=update_text_from_file,
                    inputs=[file_input],
                    outputs=[text_input, warning_single_md]
                )
                
                # Handle submit button for single speaker
                submit_single_btn.click(
                    fn=tts_interface,
                    api_name="predict",
                    inputs=[text_input, voice_dropdown, rate_slider, pitch_slider, subtitle_checkbox, file_input],
                    outputs=single_outputs
                )
            
            with gr.Tab("Multi Speaker"):
                with gr.Column():
                    multi_text_input = gr.Textbox(
                        label="Multi-Speaker Text (Format: 'Speaker1: text' or 'S1: text')", 
                        lines=8,
                        value="Speaker1: Hello, this is the first speaker.\nSpeaker2: And I'm the second speaker!"
                    )
                    multi_subtitle_checkbox = gr.Checkbox(label="Generate Subtitles (.srt)", value=False)
                    
                    with gr.Row():
                        with gr.Column():
                            speaker1_voice = gr.Dropdown(
                                choices=[""] + list(voices.keys()),
                                label="Speaker 1 Voice",
                                value=list(voices.keys())[0] if voices else "",
                            )
                            speaker1_rate = gr.Slider(
                                minimum=-50,
                                maximum=50,
                                value=0,
                                label="Speaker 1 Rate (%)",
                                step=1,
                            )
                            speaker1_pitch = gr.Slider(
                                minimum=-20,
                                maximum=20,
                                value=0,
                                label="Speaker 1 Pitch (Hz)",
                                step=1,
                            )
                            
                        with gr.Column():
                            speaker2_voice = gr.Dropdown(
                                choices=[""] + list(voices.keys()),
                                label="Speaker 2 Voice",
                                value=list(voices.keys())[10] if len(voices) > 10 else "",
                            )
                            speaker2_rate = gr.Slider(
                                minimum=-50,
                                maximum=50,
                                value=0,
                                label="Speaker 2 Rate (%)",
                                step=1,
                            )
                            speaker2_pitch = gr.Slider(
                                minimum=-20,
                                maximum=20,
                                value=0,
                                label="Speaker 2 Pitch (Hz)",
                                step=1,
                            )
                    
                submit_multi_btn = gr.Button("Convert Multi-Speaker to Speech", variant="primary")
                warning_multi_md = gr.Markdown(visible=False)
                
                multi_outputs = [
                    gr.Audio(label="Generated Audio", type="filepath"),
                    gr.File(label="Generated Subtitles"),
                    warning_multi_md
                ]
                
                # Correctly pass the individual Gradio components to the click function
                submit_multi_btn.click(
                    fn=multi_speaker_interface,
                    api_name="predict_multi",
                    inputs=[
                        multi_text_input, 
                        multi_subtitle_checkbox,
                        speaker1_voice,
                        speaker1_rate,
                        speaker1_pitch,
                        speaker2_voice,
                        speaker2_rate,
                        speaker2_pitch
                    ],
                    outputs=multi_outputs
                )
        
        gr.Markdown("Experience the power of Edge TTS for text-to-speech conversion with support for both single speaker and multi-speaker scenarios!")
    
    return demo


async def main():
    demo = await create_demo()
    demo.queue(default_concurrency_limit=50)
    demo.launch(show_api=True, show_error=True, share=True)


if __name__ == "__main__":
    asyncio.run(main())
                                        