# Copyright (c) 2025 Konrad Dżbik
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from lib.ePaper.ePaper213v4 import EPD_2in13_V4_Portrait
import utime
import struct  # Added for signed integer unpacking (handles negative BMP heights)

class eInk213(EPD_2in13_V4_Portrait):
    def __init__(self):
        super().__init__()
        
    def display_bmp(self, filename, invert=False):
            try:
                with open(filename, "rb") as f:
                    # Read BMP file header (14 bytes)
                    file_header = f.read(14)
                    if len(file_header) < 14 or file_header[0:2] != b'BM':
                        print("Not a valid BMP file")
                        return
                    # Read offset to pixel data
                    offset = int.from_bytes(file_header[10:14], 'little')
                    # Read DIB header (at least 40 bytes for BITMAPINFOHEADER)
                    dib_header = f.read(40)
                    if len(dib_header) < 40:
                        print("Invalid DIB header")
                        return
                    # Use struct for signed integers (fixes handling of negative height for top-down BMPs)
                    img_width = struct.unpack('<i', dib_header[4:8])[0]
                    height_signed = struct.unpack('<i', dib_header[8:12])[0]
                    # Determine if top-down and get absolute height
                    if height_signed < 0:
                        img_height = -height_signed
                        top_down = True
                    else:
                        img_height = height_signed
                        top_down = False
                    print(f"BMP: {filename} params W:{img_width} H: {img_height} (top_down: {top_down})")
                    bits_per_pixel = int.from_bytes(dib_header[14:16], 'little')
                    compression = int.from_bytes(dib_header[16:20], 'little')
                    if bits_per_pixel != 1:
                        print(f"Unsupported bits per pixel: {bits_per_pixel} (only 1-bit supported)")
                        return
                    if compression != 0:
                        print(f"Compression not supported: {compression}")
                        return
                    # Seek to pixel data
                    f.seek(offset)
                    # Calculate padding per row (to 4-byte boundary)
                    row_size = ((img_width + 31) // 32) * 4  # bytes per row in file
                    # Read pixel data into a 2D list (for easier scaling and rotation)
                    img_data = []
                    for _ in range(img_height):
                        row_data = f.read((img_width + 7) // 8)
                        if len(row_data) < (img_width + 7) // 8:
                            print("Unexpected end of file")
                            return
                        # Skip padding
                        f.read(row_size - len(row_data))
                        # Unpack row to list of bits (0 or 1). BMP 1-bit format: MSB (bit 7) is leftmost pixel.
                        row_bits = []
                        for byte in row_data:
                            for bit in range(7, -1, -1):
                                row_bits.append((byte >> bit) & 1)
                        img_data.append(row_bits[:img_width])  # Trim extra bits
                    # Adjust for bottom-up vs top-down to ensure img_data[0] is always the top row
                    if not top_down:
                        img_data.reverse()  # For bottom-up BMPs, reverse so [0] = top row

                    # New: Auto-rotate logic for better fit on display
                    # If image is landscape (w > h) but display is portrait (w < h), rotate 90 degrees clockwise
                    # Similarly, if image is portrait but display is landscape, rotate (but less common)
                    # This aligns the longer side of the image with the longer side of the display
                    display_is_portrait = self.height > self.width
                    image_is_landscape = img_width > img_height
                    if (image_is_landscape and display_is_portrait) or (not image_is_landscape and not display_is_portrait):
                        # Rotate 90 degrees clockwise: Transpose and reverse each new row
                        new_img_data = []
                        for x in range(img_width):
                            new_row = [img_data[y][x] for y in range(img_height - 1, -1, -1)]  # Reverse y for clockwise
                            new_img_data.append(new_row)
                        img_data = new_img_data
                        # Swap dimensions after rotation
                        img_width, img_height = img_height, img_width
                        print(f"Auto-rotated image 90 degrees to better fit display (new dims: {img_width}x{img_height})")

                    # Now scale the image to display size (self.width x self.height) without unintended rotation
                    # Simple nearest-neighbor scaling for 1-bit images.
                    # Scaling factors: Map display horizontal to image horizontal, vertical to vertical.
                    # This displays in adjusted orientation, stretching to fit (may distort slightly if aspect ratios don't match).
                    # Note: For perfect fit without distortion, you could add letterboxing (black borders) by adjusting scales and offsets.
                    scale_x = self.width / img_width  # Horizontal scaling factor (display width / image width)
                    scale_y = self.height / img_height  # Vertical scaling factor (display height / image height)
                    buffer = bytearray(self.height * self.width // 8)
                    for disp_y in range(self.height):
                        # Map display y (vertical, 0 = top) to image y (0 = top)
                        img_y = int(disp_y / scale_y)
                        img_y = max(0, min(img_height - 1, img_y))  # Clamp to bounds
                        row_bits = img_data[img_y]
                        buf_offset = disp_y * (self.width // 8)
                        byte_index = 0
                        byte_value = 0
                        bit_count = 0
                        for disp_x in range(self.width):
                            # Map display x (horizontal) to image x
                            img_x = int(disp_x / scale_x)
                            img_x = max(0, min(img_width - 1, img_x))  # Clamp to bounds
                            bit = row_bits[img_x]
                            if invert:
                                bit = 1 - bit
                            byte_value = (byte_value << 1) | bit
                            bit_count += 1
                            if bit_count == 8:
                                buffer[buf_offset + byte_index] = byte_value
                                byte_index += 1
                                byte_value = 0
                                bit_count = 0
                        # Fill remaining bits in last byte (shift left if partial byte)
                        if bit_count > 0:
                            byte_value <<= (8 - bit_count)
                            buffer[buf_offset + byte_index] = byte_value
                    # Send to display
                    self.fill(0xff)  # clear before image
                    self.displayPartial(buffer)
                    print(f"BMP displayed: {filename} (scaled from {img_width}x{img_height} to {self.width}x{self.height})")
            except Exception as e:
                print("Error displaying BMP:", e)

# Usage example
if __name__ == "__main__":
    epd = eInk213()
    epd.display_bmp("example.bmp")  # 
    # Display the buffer (assuming you have a display method)
    # epd.display(epd.buffer)

