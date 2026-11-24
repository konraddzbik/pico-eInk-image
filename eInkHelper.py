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
import struct


class eInk213(EPD_2in13_V4_Portrait):

    def display_bmp(self, filename, invert=False):
        try:
            with open(filename, "rb") as f:
                w, h, top_down, offset = self._parse_bmp_header(f)
                f.seek(offset)
                rows = self._read_pixel_data(f, w, h, top_down)
        except ValueError as e:
            print(f"BMP error: {e}")
            return False

        display_portrait = self.height > self.width
        image_portrait = h >= w
        if display_portrait != image_portrait:
            rows, w, h = self._rotate_90cw(rows, w, h)

        buf = self._scale_to_display(rows, w, h, invert)
        self.fill(0xff)
        self.displayPartial(buf)
        print(f"BMP: {filename} -> {self.width}x{self.height}")
        return True

    @staticmethod
    def _parse_bmp_header(f):
        file_hdr = f.read(14)
        if len(file_hdr) < 14 or file_hdr[0:2] != b'BM':
            raise ValueError("Not a valid BMP file")

        offset = int.from_bytes(file_hdr[10:14], 'little')
        dib_hdr = f.read(40)
        if len(dib_hdr) < 40:
            raise ValueError("Invalid DIB header")

        w = struct.unpack('<i', dib_hdr[4:8])[0]
        h_signed = struct.unpack('<i', dib_hdr[8:12])[0]
        top_down = h_signed < 0
        h = -h_signed if top_down else h_signed

        bpp = int.from_bytes(dib_hdr[14:16], 'little')
        if bpp != 1:
            raise ValueError(f"Unsupported bpp: {bpp}")
        compression = int.from_bytes(dib_hdr[16:20], 'little')
        if compression != 0:
            raise ValueError(f"Compression not supported: {compression}")

        return w, h, top_down, offset

    @staticmethod
    def _read_pixel_data(f, w, h, top_down):
        row_bytes = (w + 7) // 8
        padded_row = ((w + 31) // 32) * 4
        padding = padded_row - row_bytes

        rows = []
        for _ in range(h):
            data = f.read(row_bytes)
            if len(data) < row_bytes:
                raise ValueError("Unexpected end of file")
            rows.append(bytearray(data))
            if padding:
                f.read(padding)

        if not top_down:
            rows.reverse()
        return rows

    @staticmethod
    def _rotate_90cw(rows, w, h):
        new_w, new_h = h, w
        new_row_bytes = (new_w + 7) // 8
        new_rows = []
        for x in range(w):
            row = bytearray(new_row_bytes)
            for i in range(h):
                if (rows[h - 1 - i][x >> 3] >> (7 - (x & 7))) & 1:
                    row[i >> 3] |= 1 << (7 - (i & 7))
            new_rows.append(row)
        return new_rows, new_w, new_h

    def _scale_to_display(self, rows, w, h, invert):
        dw, dh = self.width, self.height
        # Integer math avoids float on Cortex-M0+ (no FPU)
        col_src = [min(x * w // dw, w - 1) for x in range(dw)]
        row_src = [min(y * h // dh, h - 1) for y in range(dh)]
        col_byte = [col_src[x] >> 3 for x in range(dw)]
        col_shift = [7 - (col_src[x] & 7) for x in range(dw)]

        stride = dw // 8
        buf = bytearray(dh * stride)
        xor = 0xFF if invert else 0x00

        for dy in range(dh):
            src = rows[row_src[dy]]
            base = dy * stride
            for bi in range(stride):
                val = 0
                bx = bi << 3
                for bit in range(8):
                    px = bx + bit
                    val = (val << 1) | ((src[col_byte[px]] >> col_shift[px]) & 1)
                buf[base + bi] = val ^ xor

        return buf


if __name__ == "__main__":
    epd = eInk213()
    epd.display_bmp("example.bmp")
