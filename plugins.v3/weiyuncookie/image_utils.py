# -*- coding: utf-8 -*-
"""微云 Cookie 助手的二维码图片处理工具。"""

from __future__ import annotations

import base64
import struct
import zlib
from typing import Optional, Tuple


def decode_data_image(data_image: str) -> Tuple[Optional[bytes], str]:
    """解码 data:image URI，返回图片字节和媒体类型。"""
    if not data_image or not str(data_image).startswith("data:image/"):
        return None, "image/png"
    try:
        header, raw = str(data_image).split(",", 1)
        media_type = "image/png"
        if ":" in header and ";" in header:
            media_type = header.split(":", 1)[1].split(";", 1)[0] or media_type
        return base64.b64decode(raw), media_type
    except Exception:
        return None, "image/png"


def crop_qrcode_png(data: bytes, padding: int = 12, logger=None) -> bytes:
    """按二维码黑色模块裁掉截图空白和提示文字，保留扫码所需的白色静区。"""
    if not data or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data
    try:
        pos = 8
        width = height = bit_depth = color_type = None
        idat = bytearray()
        while pos + 8 <= len(data):
            length = struct.unpack(">I", data[pos:pos + 4])[0]
            chunk_type = data[pos + 4:pos + 8]
            chunk_data = data[pos + 8:pos + 8 + length]
            pos += 12 + length
            if chunk_type == b"IHDR":
                width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", chunk_data)
                if bit_depth != 8 or compression != 0 or filter_method != 0 or interlace != 0:
                    return data
            elif chunk_type == b"IDAT":
                idat.extend(chunk_data)
            elif chunk_type == b"IEND":
                break
        channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color_type)
        if not width or not height or not channels or not idat:
            return data
        row_size = width * channels
        raw = zlib.decompress(bytes(idat))
        rows = []
        dark_row_ranges = []
        prev = bytearray(row_size)
        offset = 0
        for _y in range(height):
            filter_type = raw[offset]
            offset += 1
            scan = bytearray(raw[offset:offset + row_size])
            offset += row_size
            recon = bytearray(row_size)
            for i, value in enumerate(scan):
                left = recon[i - channels] if i >= channels else 0
                up = prev[i]
                up_left = prev[i - channels] if i >= channels else 0
                if filter_type == 0:
                    recon[i] = value
                elif filter_type == 1:
                    recon[i] = (value + left) & 0xFF
                elif filter_type == 2:
                    recon[i] = (value + up) & 0xFF
                elif filter_type == 3:
                    recon[i] = (value + ((left + up) // 2)) & 0xFF
                elif filter_type == 4:
                    p = left + up - up_left
                    pa, pb, pc = abs(p - left), abs(p - up), abs(p - up_left)
                    predictor = left if pa <= pb and pa <= pc else up if pb <= pc else up_left
                    recon[i] = (value + predictor) & 0xFF
                else:
                    return data
            rgba = bytearray(width * 4)
            row_min_x = width
            row_max_x = -1
            for x in range(width):
                idx = x * channels
                out = x * 4
                if color_type == 0:
                    r = g = b = recon[idx]
                    a = 255
                elif color_type == 2:
                    r, g, b = recon[idx], recon[idx + 1], recon[idx + 2]
                    a = 255
                elif color_type == 4:
                    r = g = b = recon[idx]
                    a = recon[idx + 1]
                else:
                    r, g, b, a = recon[idx], recon[idx + 1], recon[idx + 2], recon[idx + 3]
                rgba[out:out + 4] = bytes((r, g, b, a))
                if a > 10 and r <= 120 and g <= 120 and b <= 120:
                    row_min_x = min(row_min_x, x)
                    row_max_x = max(row_max_x, x)
            rows.append(rgba)
            dark_row_ranges.append((row_min_x, row_max_x))
            prev = recon
        min_row_dark = max(3, width // 80)
        max_gap = 8
        segments = []
        start = None
        last_dark = None
        gap = 0
        for y, (row_min_x, row_max_x) in enumerate(dark_row_ranges):
            dark_count = row_max_x - row_min_x + 1 if row_max_x >= row_min_x else 0
            if dark_count >= min_row_dark:
                if start is None:
                    start = y
                last_dark = y
                gap = 0
            elif start is not None:
                gap += 1
                if gap > max_gap:
                    segments.append((start, last_dark))
                    start = None
                    last_dark = None
                    gap = 0
        if start is not None and last_dark is not None:
            segments.append((start, last_dark))
        segments = [seg for seg in segments if seg[1] - seg[0] + 1 >= 32]
        if not segments:
            return data
        min_y, max_y = max(
            segments,
            key=lambda seg: (
                seg[1] - seg[0] + 1,
                sum(
                    (mx - mn + 1) if mx >= mn else 0
                    for mn, mx in dark_row_ranges[seg[0]:seg[1] + 1]
                ),
            ),
        )
        min_x, max_x = width, -1
        for row_min_x, row_max_x in dark_row_ranges[min_y:max_y + 1]:
            if row_max_x >= row_min_x:
                min_x = min(min_x, row_min_x)
                max_x = max(max_x, row_max_x)
        if max_x < min_x or max_y < min_y:
            return data
        left = max(min_x - padding, 0)
        top = max(min_y - padding, 0)
        right = min(max_x + padding, width - 1)
        bottom = min(max_y + padding, height - 1)
        if left == 0 and top == 0 and right == width - 1 and bottom == height - 1:
            return data
        crop_width = right - left + 1
        crop_height = bottom - top + 1
        if crop_width < 64 or crop_height < 64:
            return data
        payload = bytearray()
        for row in rows[top:bottom + 1]:
            payload.append(0)
            payload.extend(row[left * 4:(right + 1) * 4])

        def chunk(kind: bytes, body: bytes) -> bytes:
            """生成 PNG chunk。"""
            return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

        ihdr = struct.pack(">IIBBBBB", crop_width, crop_height, 8, 6, 0, 0, 0)
        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(payload), 9)) + chunk(b"IEND", b"")
    except Exception as err:
        if logger:
            logger.debug("微云 Cookie 助手二维码空白裁剪失败：%s", err)
        return data
