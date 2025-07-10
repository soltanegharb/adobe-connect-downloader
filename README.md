
---
# Adobe Connect Downloader (Hardware Accelerated)

A robust, user-friendly Python script to download Adobe Connect recordings. It intelligently uses your computer's hardware to merge the video and audio streams into a high-quality MP4 file, faster and more reliably than ever.

This project uses a universal bootstrapper, so there's **no need to manually create virtual environments or install packages**. Just run the script, and it handles everything for you.

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Platforms](https://img.shields.io/badge/platform-windows%20%7C%20macos%20%7C%20linux-lightgrey.svg)](https://shields.io/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)

## Key Features

-   **One-Command Execution**: A smart bootstrap script creates a local Python environment (`.venv`) and installs dependencies automatically. No `pip install` needed!
-   **Batch Downloading**: Process hundreds of links automatically from a single text file.
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
2.  **FFmpeg**: This is the only manual dependency. This guide will help you install it.

---

### FFmpeg Installation Guide

This is the most important dependency. Follow the guide for your operating system.

#### 🪟 For Windows

Installing FFmpeg on Windows requires downloading it and adding it to the system's PATH.

1.  **Download FFmpeg**:
    *   Go to the **[FFmpeg for Windows builds page (gyan.dev)](https://www.gyan.dev/ffmpeg/builds/)**.
    *   Scroll down to the "release" builds section.
    *   Download the `ffmpeg-release-full.7z` archive. You will need a tool like [7-Zip](https://www.7-zip.org/) to extract it.

2.  **Extract the Files**:
    *   Extract the downloaded `.7z` file.
    *   You will get a folder like `ffmpeg-7.0-full_build`. For simplicity, rename it to `ffmpeg`.
    *   Move this `ffmpeg` folder to a permanent location, for example, directly on your `C:\` drive, so the path is `C:\ffmpeg`.

3.  **Add FFmpeg to the Windows PATH**:
    *   Press the **Windows Key**, type `env`, and select **"Edit the system environment variables"**.
    *   In the System Properties window that opens, click the **"Environment Variables..."** button.
    *   In the top box ("User variables"), find the variable named `Path` and double-click it.
    *   Click **"New"** and paste the path to the `bin` folder inside your FFmpeg directory. If you followed the example above, this would be: `C:\ffmpeg\bin`
    *   Click **OK** on all the windows to close them.

4.  **Verify the Installation** (see below).

#### 🍎 For macOS

The easiest way to install FFmpeg on macOS is with [Homebrew](https://brew.sh/).

1.  **Install Homebrew** (if you don't have it already):
    *   Open your Terminal and paste this command:
        ```bash
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        ```

2.  **Install FFmpeg**:
    *   In the same Terminal, run:
        ```bash
        brew install ffmpeg
        ```
    *   Homebrew will automatically handle the rest.

3.  **Verify the Installation** (see below).

#### 🐧 For Linux

Use your distribution's package manager to install FFmpeg.

*   **For Debian / Ubuntu / Mint:**
    ```bash
    sudo apt update && sudo apt install ffmpeg
    ```

*   **For Fedora / CentOS / RHEL:**
    ```bash
    sudo dnf install ffmpeg
    ```

*   **For Arch Linux:**
    ```bash
    sudo pacman -S ffmpeg
    ```

3.  **Verify the Installation** (see below).

---

### ✅ Verify FFmpeg Installation (All Platforms)

After installing, you **must** verify that your system can find FFmpeg.

1.  **Open a NEW terminal window.** (This is important, as existing terminals won't know about the new PATH on Windows).
2.  Type the following command and press Enter:
    ```bash
    ffmpeg -version
    ```
3.  **If it's successful**, you will see version information, like `ffmpeg version 7.1.1...`.
4.  **If it fails**, you will see an error like `ffmpeg: command not found`. This means something went wrong with the installation or the PATH was not set correctly. Please review the steps for your OS.

---

## How to Use

1.  **Get the Project Files:**
    Download all the project files from this repository and place them into a new, empty directory.

2.  **Run from Your Terminal:**
    Open your terminal or command prompt and `cd` into the directory where you saved the files.

### Option A: Download a Single Video

Run the script with the recording URL.

```bash
python adobe_downloader.py "YOUR_ADOBE_CONNECT_URL_HERE"
```

**Example:**
```bash
python adobe_downloader.py "https://my-university.adobeconnect.com/p1a2b3c4d5e6/"
```

### Option B: Batch Downloading from a File

1.  Create a text file named `list.csv` (or any name you prefer).
2.  Add your links to the file, one per line. The format is `URL,OPTIONAL_FILENAME`.

    **`list.csv` Example:**
    ```csv
    https://my-uni.adobeconnect.com/p123/,Lecture 01 - Intro.mp4
    https://my-uni.adobeconnect.com/p456/,Lecture 02 - Advanced Topics
    https://my-uni.adobeconnect.com/p789/
    ```
    *Note: If the filename is omitted, a default name will be used.*

3.  Run the script using the `-f` or `--file` flag.

    ```bash
    python adobe_downloader.py --file list.csv
    ```

The script will loop through each link, download it, and save the final video to a folder named `Adobe_Downloader` inside your system's **Downloads** directory.

### Command-Line Options

You can customize the output filename and quality.

**Specify an output filename (single URL mode only):**
```bash
python adobe_downloader.py "YOUR_URL_HERE" -o "My Awesome Lecture.mp4"
```

**Set the encoding quality (applies to all downloads):**
The `--quality` flag accepts `fast`, `medium` (default), `high`, or `ultra`. Higher quality results in a larger file size.
```bash
python adobe_downloader.py "YOUR_URL_HERE" --quality high
```
```bash
python adobe_downloader.py --file list.csv --quality fast
```

## How It Works

1.  **Bootstrap Environment**: Running `adobe_downloader.py` first triggers `bootstrap.py`. It checks for a `.venv`, installs packages from `requirements.txt` if needed, and re-launches the main script inside the new environment.
2.  **Process Input**: The script checks if you provided a single URL or a batch file with the `--file` flag.
3.  **Loop & Download**: For each URL, it fetches the recording's web page to find its unique ID. It uses this ID to construct a direct URL to a `.zip` archive and downloads it with a progress bar into a temporary sub-folder.
4.  **Extract & Prepare**: The `.zip` file is extracted. The script finds the screen share (`screenshare.flv`) and camera/voice (`cameravoip.flv`) streams.
5.  **Encoder Validation**: The script takes a small sample of the video and runs a quick test encode with every potential hardware and software encoder to find the best one. If all tests fail (due to a corrupt file), it intelligently falls back to a robust CPU-only mode.
6.  **Merge & Finalize**: Using the best encoder, it merges the streams, fixes A/V sync, and encodes the final `MP4` file.
7.  **Organize & Clean Up**: The final video is moved to the main `Adobe_Downloader` directory, and the temporary sub-folder with all the raw files is deleted.
