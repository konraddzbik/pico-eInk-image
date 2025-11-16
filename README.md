# eInk213 - E-Paper Driver Extension

This repository provides an extension to the Waveshare EPD_2in13_V4 e-paper display driver for MicroPython. The `eInk213` class inherits from `EPD_2in13_V4_Portrait` and adds a custom `display_bmp` method to load, process, auto-rotate (if needed), scale, and display 1-bit BMP images on the e-paper screen. It handles bottom-up/top-down BMP formats, padding, and simple nearest-neighbor scaling for a better fit.

<img width="1200" height="600" alt="image" src="https://github.com/user-attachments/assets/17d746a4-6377-4dd6-ad08-106af298a197" />

Ideal for projects involving e-paper displays on microcontrollers like Raspberry Pi Pico, where you want to show images alongside text or sensor data.

## Features
- Inherits all functionality from the original EPD_2in13_V4 driver.
- Supports 1-bit monochrome BMP files (no compression).
- Auto-rotates images 90 degrees if needed to match display orientation (portrait/landscape).
- Scales images to fit the display dimensions using nearest-neighbor interpolation.
- Optional inversion of colors.
- Error handling for invalid BMP formats.

## Requirements
- MicroPython environment (tested on Raspberry Pi Pico, and Pi Pico 2W).
- Waveshare e-paper library: Specifically, `lib.ePaper.ePaper213v4` module (download from [Waveshare Wiki](https://www.waveshare.com/wiki/2.13inch_e-Paper_HAT) or their GitHub repo).
- Hardware: 2.13-inch e-Paper display (V4);
- Dependencies: Built-in MicroPython modules (`utime`, `struct`). No external pip-installable packages required.
- 250 x 120 dimensions 

## Installation
1. **Download the Code**:
   - Clone the repository:  
     ```
     git clone https://github.com/konraddzbik/pico-eInk-image.git
     ```
   - Or download as ZIP: Go to the repository page on GitHub, click the green "Code" button, and select "Download ZIP". Extract the files to your project directory.

2. **Set Up Dependencies**:
   - Ensure the Waveshare e-paper library is installed in your MicroPython device's `lib` folder. Copy `ePaper213v4.py` (or similar) from Waveshare's repo to `/lib/ePaper/`.
   - Upload the `eInk213.py` file (from this repo) to your device's root or a suitable directory.

3. **Hardware Setup**:
   - Connect the e-paper display to your microcontroller as per Waveshare's documentation (e.g., RST to GPIO12, BUSY to GPIO13, etc.).
   - Adjust pin constants in the base driver if needed.

## Usage Example
Here's a simple script to initialize the display and show a BMP image. Save this as `main.py` and run it on your device.

```python
from eInkHelper import eInk213  # Import your extended class
import utime

# Initialize the display
epd = eInk213()

# Clear the screen
epd.fill(0xff)  # White background
epd.display(epd.buffer)  # Update display (use displayPartial for partial updates)

# Display a BMP image (place your BMP file on the device, e.g., via Thonny)
epd.display_bmp("example.bmp", invert=False)  # Replace with your file; optional invert=True for color flip

# Add some text overlay (inherited from base class)
epd.text("Hello, e-Paper!", 10, 10, 0x00)  # Black text
epd.display(epd.buffer)

# Sleep mode after use (optional)
utime.sleep(5)  # Wait to view
epd.sleep()
```

### Working example with my own image converted to 1-bit BMP fiel with 250 x 120
<img width="992" height="500" alt="image" src="https://github.com/user-attachments/assets/826b58de-df10-4dce-b930-421275b0c90d" />


### Notes
- BMP files must be 1-bit monochrome and uncompressed. Use tools like GIMP or ImageMagick to convert images.
- For looping displays (e.g., multiple images), wrap the `display_bmp` calls in a `while` loop with `utime.sleep()` to avoid frequent refreshes (e-paper is low-power but slow).
- Debugging: Check console output for errors like "Not a valid BMP file" or scaling info.
- Performance: Scaling large images may be slow on microcontrollers; optimize BMP size beforehand.

## Contributing
Contributions are welcome! Fork the repo, make changes, and submit a pull request. Please follow standard Python coding conventions.

## License
This project is licensed under the MIT License.

## Acknowledgments
- Based on Waveshare's EPD_2in13_V4 driver.
- Thanks to the MicroPython community for hardware support.
