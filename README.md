
---
# Adobe Connect Downloader (Hardware Accelerated)

A robust, user-friendly Python script to download Adobe Connect recordings. It intelligently uses your computer's hardware to merge the video and audio streams into a high-quality MP4 file, faster and more reliably than ever.

This project uses a universal bootstrapper, so there's **no need to manually create virtual environments or install packages**. Just run the script, and it handles everything for you.

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Platforms](https://img.shields.io/badge/platform-windows%20%7C%20macos%20%7C%20linux-lightgrey.svg)](https://shields.io/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)

## Key Features

-   **One-Command Execution**: A smart bootstrap script creates a local Python environment (`.venv`) and installs dependencies automatically. No `pip install` needed!
-   **Intelligent Hardware Acceleration**: Automatically detects and uses available GPUs for encoding, supporting:
    -   **NVIDIA (NVENC)**
    -   **Intel & AMD (VAAPI on Linux)**
-   **Smart CPU Fallback**: If GPU encoding is unavailable or fails, it seamlessly switches to the highly compatible `libx264` CPU encoder.
-   **A/V Sync Correction**: Proactively fixes common audio/video synchronization issues often found in screen recordings by standardizing frame and sample rates.
-   **Real-time Progress**: Detailed `tqdm` progress bars show you the status of both the download and the video encoding process.
-   **Customizable Quality**: Use the `--quality` flag to balance file size and video quality.
-   **Portable & Cross-Platform**: Runs on Windows, macOS, and Linux.

## Prerequisites

1.  **Python 3.8+**: Required by the bootstrapper. Check with `python --version` or `python3 --version`.
2.  **FFmpeg**: This is the only manual dependency. It's essential for merging the video and audio.
    -   **Website:** [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
    -   **Installation Tip:** On Windows, download the release build and add the `bin` folder to your system's PATH. On macOS, use Homebrew (`brew install ffmpeg`). On Linux, use your package manager (e.g., `sudo apt install ffmpeg`).
    -   **Verify Installation:** After installing, open a **new** terminal and type `ffmpeg -version`. You must see version information, not a "command not found" error.

## How to Use

1.  **Get the Project Files:**
    Download all the project files from this repository and place them into a new, empty directory.

    Your directory should look like this:
    ```
    my_downloader/
    ├── adobe_downloader.py
    ├── bootstrap.py
    ├── requirements.txt
    ├── ffmpeg_handler.py
    ├── hardware_detector.py
    └── ... (and all other .py files)
    ```

2.  **Run from Your Terminal:**
    Open your terminal or command prompt, `cd` into the directory where you saved the files, and run the script with the recording URL.

    ```bash
    python adobe_downloader.py "YOUR_ADOBE_CONNECT_URL_HERE"
    ```

    **Example:**
    ```bash
    python adobe_downloader.py "https://my-university.adobeconnect.com/p1a2b3c4d5e6/"
    ```

3.  **Let the Magic Happen:**
    The first time you run it, the bootstrapper will set up the environment (this may take a minute). The script will then:
    -   Download the recording data.
    -   Scan for the best video encoder (GPU or CPU).
    -   Merge and encode the final video, showing you its progress.

    A new folder named `adobe_connect_...` will be created in your system's **Downloads** directory. Inside, you will find your final video file, e.g., `recording_1234567.mp4`.

### Command-Line Options

You can customize the output filename and quality.

**Specify an output filename:**
```bash
python adobe_downloader.py "YOUR_URL_HERE" -o "My Awesome Lecture.mp4"
```

**Set the encoding quality:**
The `--quality` flag accepts `fast`, `medium` (default), `high`, or `ultra`. Higher quality results in a larger file size.
```bash
python adobe_downloader.py "YOUR_URL_HERE" --quality high
```

## How It Works

1.  **Bootstrap Environment**: Running `adobe_downloader.py` first triggers `bootstrap.py`. It checks for a `.venv` and the required packages from `requirements.txt`. If missing, it creates the environment, installs the packages, and transparently re-launches the main script inside the new environment.
2.  **Scrape & Download**: The script fetches the recording's web page to find its unique ID. It uses this ID to construct a direct URL to a `.zip` archive containing the raw media streams and downloads it with a progress bar.
3.  **Extract & Prepare**: The `.zip` file is extracted. The script parses the contents to find the screen share (`screenshare.flv`) and camera/voice (`cameravoip.flv`) streams. If the recording is split into multiple parts, they are losslessly concatenated into temporary files.
4.  **Encoder Validation**: This is the key to reliability. The script takes a small sample of the actual video file and runs a quick test encode with every potential hardware and software encoder to see which ones are truly compatible with your specific hardware and drivers.
5.  **Merge & Encode**: Using the best encoder that passed validation, the script calls `ffmpeg` to merge the video and audio streams. During this process, it applies filters to fix A/V sync and encodes the final `MP4` file, showing a real-time progress bar.

---
