# Edge TTS Text-to-Speech Converter

## Overview
Edge TTS Text-to-Speech Converter is a Python application that leverages Microsoft Edge TTS for converting text to speech. It features a user-friendly Gradio interface and supports both single and multi-speaker modes, subtitle generation (.srt), and file uploads for text input (TXT or SRT formats). Key functionalities include smart format detection for plain text or SRT subtitle files, and the ability to adjust speech rate and pitch for customized audio output.

## Installation

### Using pip
To install Edge TTS Text-to-Speech Converter using pip, follow these steps:

1. Ensure you have Python 3.7 or higher installed on your system.
2. Clone this repository or download the source code.
3. Navigate to the project directory:
   ```
   cd path/to/EdgeTTS
   ```
4. Create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   venv\Scripts\activate  # On Windows
   # OR
   source venv/bin/activate  # On macOS/Linux
   ```
5. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

### Using Conda
To install Edge TTS Text-to-Speech Converter using Conda, follow these steps:

1. Ensure you have Conda installed on your system. You can download it from [Anaconda](https://www.anaconda.com/products/distribution) or [Miniconda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/).
2. Clone this repository or download the source code.
3. Navigate to the project directory:
   ```
   cd path/to/EdgeTTS
   ```
4. Create a new Conda environment:
   ```
   conda create --name edgetts python=3.11
   conda activate edgetts
   ```
5. Install the required packages:
   ```
   conda install -c conda-forge edge_tts==6.1.12 gradio==5.24.0
   ```
   If the packages are not available in Conda channels, you can use pip within the Conda environment:
   ```
   pip install edge_tts==6.1.12 gradio==5.24.0
   ```

## Features
- **Single & Multi-Speaker Support**: Choose between single speaker or multi-speaker modes for different voice outputs.
- **SRT Subtitle Support**: Upload SRT files or input SRT format text to generate perfectly synchronized speech.
- **SRT Generation**: Create subtitle files alongside your audio for perfect timing.
- **File Upload**: Easily upload TXT or SRT files for conversion.
- **Smart Format Detection**: Automatically detects plain text or SRT subtitle format for seamless processing.

## Usage
To run the Edge TTS Text-to-Speech Converter:

1. Ensure you are in the project directory and your virtual environment (or Conda environment) is activated.
2. Run the application:
   ```
   python app.py
   ```
3. Open the provided URL in your browser to access the Gradio interface (typically `http://127.0.0.1:7860`).
4. Use the interface to:
   - Enter text or upload a TXT/SRT file for conversion in the respective input fields.
   - Select a voice from the available options in the dropdown menu.
   - Adjust speech rate and pitch using sliders if desired for customized audio output.
   - Choose to generate subtitles (.srt) alongside the audio by checking the appropriate box.
   - For multi-speaker mode, switch to the 'Multi Speaker' tab, format text as `Speaker1: text` or `S1: text`, and configure voices for each speaker using the provided dropdowns and sliders.

### Starting the Application with Batch File (Windows)
For Windows users, you can use the provided batch file to automate starting the application:
1. Ensure you have Conda installed and the 'edgetts' environment set up as described in the installation instructions.
2. Double-click the `EdgeTTS.bat` file in the project directory, or run it from the command line:
   ```
   EdgeTTS.bat
   ```
3. The batch file will activate the Conda environment, start the server in a new window titled "EdgeTTS Server", and open the application URL (`http://127.0.0.1:7860`) in your default web browser after a short delay.

## Additional Notes
- **Internet Connection**: Edge TTS is a cloud-based service and requires an active internet connection to function.
- **Subtitle Timing Tip**: When creating SRT files for continuous speech, avoid exact matching timestamps between segments. Create a small overlap (20-30ms) between segments to prevent pauses.
