import sys
import os
import struct
import types
import unittest
import tempfile
import io


class MockEPD:
    def __init__(self):
        self.width = 128
        self.height = 250
        self.buffer = bytearray(self.width * self.height // 8)
        self.last_partial = None

    def fill(self, val):
        for i in range(len(self.buffer)):
            self.buffer[i] = val

    def displayPartial(self, buf):
        self.last_partial = bytes(buf)


mock_lib = types.ModuleType('lib')
mock_epaper = types.ModuleType('lib.ePaper')
mock_213v4 = types.ModuleType('lib.ePaper.ePaper213v4')
mock_213v4.EPD_2in13_V4_Portrait = MockEPD
mock_lib.ePaper = mock_epaper
mock_epaper.ePaper213v4 = mock_213v4
sys.modules['lib'] = mock_lib
sys.modules['lib.ePaper'] = mock_epaper
sys.modules['lib.ePaper.ePaper213v4'] = mock_213v4

from eInkHelper import eInk213


def make_bmp_bytes(width, height, rows_data, top_down=False):
    """Build a minimal 1-bit BMP. rows_data is top-to-bottom order."""
    row_bytes = (width + 7) // 8
    padded_row = ((width + 31) // 32) * 4
    padding = padded_row - row_bytes

    stored = rows_data if top_down else list(reversed(rows_data))
    pixel_data = bytearray()
    for row in stored:
        pixel_data.extend(row[:row_bytes])
        pixel_data.extend(b'\x00' * padding)

    color_table = b'\x00\x00\x00\x00' + b'\xFF\xFF\xFF\x00'
    offset = 14 + 40 + len(color_table)
    h_val = -height if top_down else height

    bmp = bytearray()
    bmp.extend(b'BM')
    bmp.extend(struct.pack('<I', offset + len(pixel_data)))
    bmp.extend(b'\x00\x00\x00\x00')
    bmp.extend(struct.pack('<I', offset))
    bmp.extend(struct.pack('<I', 40))
    bmp.extend(struct.pack('<i', width))
    bmp.extend(struct.pack('<i', h_val))
    bmp.extend(struct.pack('<HH', 1, 1))
    bmp.extend(struct.pack('<I', 0))
    bmp.extend(b'\x00' * 20)
    bmp.extend(color_table)
    bmp.extend(pixel_data)
    return bytes(bmp)


class TestParseBmpHeader(unittest.TestCase):

    def test_valid_bottom_up(self):
        rows = [bytearray([0xFF]), bytearray([0x00])]
        f = io.BytesIO(make_bmp_bytes(8, 2, rows))
        w, h, top_down, offset = eInk213._parse_bmp_header(f)
        self.assertEqual(w, 8)
        self.assertEqual(h, 2)
        self.assertFalse(top_down)

    def test_valid_top_down(self):
        rows = [bytearray([0xFF]), bytearray([0x00])]
        f = io.BytesIO(make_bmp_bytes(8, 2, rows, top_down=True))
        w, h, top_down, offset = eInk213._parse_bmp_header(f)
        self.assertEqual(w, 8)
        self.assertEqual(h, 2)
        self.assertTrue(top_down)

    def test_invalid_magic(self):
        f = io.BytesIO(b'XX' + b'\x00' * 52)
        with self.assertRaises(ValueError):
            eInk213._parse_bmp_header(f)

    def test_truncated_file_header(self):
        f = io.BytesIO(b'BM\x00\x00')
        with self.assertRaises(ValueError):
            eInk213._parse_bmp_header(f)

    def test_non_1bit_rejected(self):
        data = bytearray(make_bmp_bytes(8, 2, [bytearray([0xFF])] * 2))
        struct.pack_into('<H', data, 28, 24)
        with self.assertRaises(ValueError):
            eInk213._parse_bmp_header(io.BytesIO(bytes(data)))

    def test_compressed_rejected(self):
        data = bytearray(make_bmp_bytes(8, 2, [bytearray([0xFF])] * 2))
        struct.pack_into('<I', data, 30, 1)
        with self.assertRaises(ValueError):
            eInk213._parse_bmp_header(io.BytesIO(bytes(data)))


class TestReadPixelData(unittest.TestCase):

    def test_bottom_up_reversal(self):
        row0 = bytearray([0xFF])
        row1 = bytearray([0x00])
        data = make_bmp_bytes(8, 2, [row0, row1], top_down=False)
        f = io.BytesIO(data)
        w, h, top_down, offset = eInk213._parse_bmp_header(f)
        f.seek(offset)
        rows = eInk213._read_pixel_data(f, w, h, top_down)
        self.assertEqual(rows[0], bytearray([0xFF]))
        self.assertEqual(rows[1], bytearray([0x00]))

    def test_top_down_order_preserved(self):
        row0 = bytearray([0xFF])
        row1 = bytearray([0x00])
        data = make_bmp_bytes(8, 2, [row0, row1], top_down=True)
        f = io.BytesIO(data)
        w, h, top_down, offset = eInk213._parse_bmp_header(f)
        f.seek(offset)
        rows = eInk213._read_pixel_data(f, w, h, top_down)
        self.assertEqual(rows[0], bytearray([0xFF]))
        self.assertEqual(rows[1], bytearray([0x00]))

    def test_row_padding_consumed(self):
        row = bytearray([0xFF, 0xF0])
        data = make_bmp_bytes(12, 1, [row])
        f = io.BytesIO(data)
        w, h, top_down, offset = eInk213._parse_bmp_header(f)
        f.seek(offset)
        rows = eInk213._read_pixel_data(f, w, h, top_down)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], bytearray([0xFF, 0xF0]))

    def test_truncated_pixel_data(self):
        data = bytearray(make_bmp_bytes(8, 2, [bytearray([0xFF])] * 2))
        # Remove enough to cut into the second row's pixel byte, not just padding
        data = data[:-4]
        f = io.BytesIO(bytes(data))
        w, h, top_down, offset = eInk213._parse_bmp_header(f)
        f.seek(offset)
        with self.assertRaises(ValueError):
            eInk213._read_pixel_data(f, w, h, top_down)


class TestRotate90CW(unittest.TestCase):

    def test_2x2(self):
        # Original: (0,0)=1 (1,0)=0 / (0,1)=0 (1,1)=1
        # After CW: (0,0)=0 (1,0)=1 / (0,1)=1 (1,1)=0
        rows = [bytearray([0x80]), bytearray([0x40])]
        new_rows, new_w, new_h = eInk213._rotate_90cw(rows, 2, 2)
        self.assertEqual(new_w, 2)
        self.assertEqual(new_h, 2)
        self.assertEqual(new_rows[0], bytearray([0x40]))
        self.assertEqual(new_rows[1], bytearray([0x80]))

    def test_dimensions_swap(self):
        rows = [bytearray([0xFF, 0xFF])] * 2
        new_rows, new_w, new_h = eInk213._rotate_90cw(rows, 16, 2)
        self.assertEqual(new_w, 2)
        self.assertEqual(new_h, 16)
        self.assertEqual(len(new_rows), 16)


class TestScaleToDisplay(unittest.TestCase):

    def test_identity_all_white(self):
        epd = eInk213()
        w, h = epd.width, epd.height
        row_bytes = w // 8
        rows = [bytearray([0xFF] * row_bytes) for _ in range(h)]
        buf = epd._scale_to_display(rows, w, h, invert=False)
        self.assertEqual(len(buf), h * row_bytes)
        self.assertTrue(all(b == 0xFF for b in buf))

    def test_identity_all_black(self):
        epd = eInk213()
        w, h = epd.width, epd.height
        row_bytes = w // 8
        rows = [bytearray([0x00] * row_bytes) for _ in range(h)]
        buf = epd._scale_to_display(rows, w, h, invert=False)
        self.assertTrue(all(b == 0x00 for b in buf))

    def test_invert_flips_all_bits(self):
        epd = eInk213()
        w, h = epd.width, epd.height
        row_bytes = w // 8
        rows = [bytearray([0xFF] * row_bytes) for _ in range(h)]
        buf = epd._scale_to_display(rows, w, h, invert=True)
        self.assertTrue(all(b == 0x00 for b in buf))

    def test_2x_downscale(self):
        epd = eInk213()
        w, h = epd.width * 2, epd.height * 2
        row_bytes = w // 8
        rows = [bytearray([0xAA] * row_bytes) for _ in range(h)]
        buf = epd._scale_to_display(rows, w, h, invert=False)
        self.assertEqual(len(buf), epd.height * (epd.width // 8))


class TestDisplayBmp(unittest.TestCase):

    def test_success_returns_true(self):
        rows = [bytearray([0xFF] * 16) for _ in range(250)]
        data = make_bmp_bytes(128, 250, rows)
        with tempfile.NamedTemporaryFile(suffix='.bmp', delete=False) as tmp:
            tmp.write(data)
            path = tmp.name
        try:
            epd = eInk213()
            self.assertTrue(epd.display_bmp(path))
            self.assertIsNotNone(epd.last_partial)
        finally:
            os.unlink(path)

    def test_invalid_bmp_returns_false(self):
        with tempfile.NamedTemporaryFile(suffix='.bmp', delete=False) as tmp:
            tmp.write(b'NOT A BMP')
            path = tmp.name
        try:
            epd = eInk213()
            self.assertFalse(epd.display_bmp(path))
        finally:
            os.unlink(path)

    def test_missing_file_raises_oserror(self):
        epd = eInk213()
        with self.assertRaises(OSError):
            epd.display_bmp("/nonexistent/file.bmp")

    def test_auto_rotation_triggered(self):
        rows = [bytearray([0xFF] * 32) for _ in range(128)]
        data = make_bmp_bytes(250, 128, rows)
        with tempfile.NamedTemporaryFile(suffix='.bmp', delete=False) as tmp:
            tmp.write(data)
            path = tmp.name
        try:
            epd = eInk213()
            self.assertTrue(epd.display_bmp(path))
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
