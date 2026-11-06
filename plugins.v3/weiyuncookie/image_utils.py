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


def _segment_bounds(
    start: int,
    end: int,
    dark_row_ranges: "list[tuple[int, int]]",
    width: int,
) -> "tuple[int, int, int, int]":
    """返回指定行段内深色像素的外接框 (min_x, max_x, min_y, max_y)。"""
    min_x, max_x = width, -1
    min_y, max_y = start, end
    for offset, (row_min_x, row_max_x) in enumerate(dark_row_ranges[start:end + 1]):
        if row_max_x >= row_min_x:
            if max_x < 0:
                min_y = start + offset
            min_x = min(min_x, row_min_x)
            max_x = max(max_x, row_max_x)
            max_y = start + offset
    return min_x, max_x, min_y, max_y


def _segment_squareness(segment: "tuple[int, int]", dark_row_ranges: "list[tuple[int, int]]") -> float:
    """
    估算一个行段的「方形程度」，越接近 1 越像二维码。

    二维码是宽高接近的方形深色块；登录框文字、图标这类长条区域宽高比偏离很大，
    只按最长行取段会把它们当成二维码，这正是半边残码的来源。
    """
    width = dark_row_ranges[0][0] if False else None
    min_x = None
    max_x = -1
    for row_min_x, row_max_x in dark_row_ranges[segment[0]:segment[1] + 1]:
        if row_max_x >= row_min_x:
            min_x = row_min_x if min_x is None else min(min_x, row_min_x)
            max_x = max(max_x, row_max_x)
    if min_x is None or max_x < min_x:
        return 0.0
    span_w = max_x - min_x + 1
    span_h = segment[1] - segment[0] + 1
    return min(span_w, span_h) / max(span_w, span_h)


def _fit_axis(start: int, side: int, limit: int, low: int, high: int) -> "int | None":
    """
    在单一轴上平移方框，返回合法起点；无法在不切掉二维码的前提下放下时返回 None。

    limit 是该轴允许的最大起点（图像尺寸 - 边长）。越界只允许容差范围内的平移，
    即二维码距边界很近（贴边截图）时把方框推向边界，而不是把二维码切掉。
    """
    if side <= 0 or limit < 0:
        return None
    if 0 <= start <= limit:
        return start
    if start < 0:
        return 0 if low >= 0 else None
    # start > limit：向左/向上推到底
    return limit if high <= limit + side - 1 else None


def _fit_square_in_image(
    left: int,
    top: int,
    side: int,
    width: int,
    height: int,
    min_x: int,
    max_x: int,
    min_y: int,
    max_y: int,
    tolerance: int,
) -> "tuple[int | None, int | None]":
    """
    把正方形裁剪框平移进图片范围内，同时保证二维码深色区域不被切掉。

    以二维码居中为起点；某一轴越界时沿该轴平移方框（而不是直接放弃裁剪），
    这样贴边的二维码也能收紧成正方形，又不会把二维码本体切掉。
    无法满足时返回 (None, None)，由调用方保留原图。
    """
    new_left = _fit_axis(left, side, width - side, min_x, max_x)
    new_top = _fit_axis(top, side, height - side, min_y, max_y)
    if new_left is None or new_top is None:
        return None, None
    # 平移后仍需完整包住二维码深色区域，并保留最小静区
    if new_left > min_x or new_top > min_y:
        return None, None
    if new_left + side - 1 < max_x or new_top + side - 1 < max_y:
        return None, None
    if min(min_x - new_left, min_y - new_top) < tolerance:
        return None, None
    return new_left, new_top


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
        # 二维码本体必须是正方形：按「方形程度」选段，而不是只看行数最长。
        # 截图里常混有登录框文字、图标等长条深色块，只取最长行会框到非二维码区域，
        # 进而把整块方形裁成半张（实测出现过 164x102 的残码）。
        anchor_y, anchor_bottom = max(
            segments,
            key=lambda seg: (
                _segment_squareness(seg, dark_row_ranges),
                (
                    (seg[1] - seg[0] + 1)
                    * sum(
                        (mx - mn + 1) if mx >= mn else 0
                        for mn, mx in dark_row_ranges[seg[0]:seg[1] + 1]
                    )
                ),
            ),
        )
        min_x, max_x, min_y, max_y = _segment_bounds(anchor_y, anchor_bottom, dark_row_ranges, width)
        if max_x < min_x or max_y < min_y:
            return data
        # 方形化：以对角线方向较长边为准，把外接框扩成正方形。
        square_side = max(max_x - min_x + 1, max_y - min_y + 1) + padding * 2
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        edge_tolerance = max(2, padding // 2)
        # 自适应平移：二维码上方紧邻截图边缘（典型如 iframe 全框截图）时，
        # 居中会顶出边界；此时沿该轴平移方框，只要不把二维码切掉就接受。
        shifted_x, shifted_y = _fit_square_in_image(
            int(round(center_x - square_side / 2)),
            int(round(center_y - square_side / 2)),
            square_side, width, height, min_x, max_x, min_y, max_y, edge_tolerance,
        )
        if shifted_x is None:
            if logger:
                logger.debug(
                    "微云 Cookie 助手二维码贴边且无法完整框入，保留原图：二维码 %s-%s/%s-%s，截图 %sx%s",
                    min_x, max_x, min_y, max_y, width, height,
                )
            return data
        left, top = shifted_x, shifted_y
        right = left + square_side - 1
        bottom = top + square_side - 1
        if square_side > min(width, height):
            if logger:
                logger.debug(
                    "微云 Cookie 助手二维码裁剪区域过大，保留原图：需要 %s，截图仅 %sx%s",
                    square_side, width, height,
                )
            return data
        if left == 0 and top == 0 and right == width - 1 and bottom == height - 1:
            return data
        crop_width = right - left + 1
        crop_height = bottom - top + 1
        # 半张残码就是从这里的正方形被破坏开始的，所以裁出来必须是正方形。
        if crop_width < 64 or crop_height < 64 or crop_width != crop_height:
            if logger:
                logger.debug(
                    "微云 Cookie 助手二维码裁剪结果不合格，保留原图：%sx%s",
                    crop_width, crop_height,
                )
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
