# VTF (Valve Texture Format) Parser for Python/Blender
# Based on Source Engine VTF specification

import struct
from enum import IntEnum
from typing import Optional, Tuple
import os


class VtfImageFormat(IntEnum):
    """VTF image format enum"""
    NONE = -1
    RGBA8888 = 0
    ABGR8888 = 1
    RGB888 = 2
    BGR888 = 3
    RGB565 = 4
    I8 = 5
    IA88 = 6
    P8 = 7
    A8 = 8
    RGB888_BLUESCREEN = 9
    BGR888_BLUESCREEN = 10
    ARGB8888 = 11
    BGRA8888 = 12
    DXT1 = 13
    DXT3 = 14
    DXT5 = 15
    BGRX8888 = 16
    BGR565 = 17
    BGRX5551 = 18
    BGRA4444 = 19
    DXT1_ONEBITALPHA = 20
    BGRA5551 = 21
    UV88 = 22
    UVWQ8888 = 23
    RGBA16161616F = 24
    RGBA16161616 = 25
    UVLX8888 = 26


class VtfFile:
    """VTF file parser and converter"""
    
    # VTF signature "VTF\0"
    VTF_SIGNATURE = 0x00465456
    
    def __init__(self):
        self.signature = 0
        self.version_major = 0
        self.version_minor = 0
        self.header_size = 0
        self.width = 0
        self.height = 0
        self.flags = 0
        self.frames = 1
        self.first_frame = 0
        self.reflectivity = (0.0, 0.0, 0.0)
        self.bump_scale = 1.0
        self.high_res_format = VtfImageFormat.NONE
        self.mip_count = 0
        self.low_res_format = VtfImageFormat.NONE
        self.low_res_width = 0
        self.low_res_height = 0
        self.depth = 1
        self.num_resources = 0
        
        self.mip_data = []
        self.thumbnail_data = None
    
    @staticmethod
    def load(filepath: str) -> Optional['VtfFile']:
        """Load a VTF file from disk"""
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            return VtfFile.parse(data)
        except Exception as e:
            print(f"[VTF] Failed to load {filepath}: {e}")
            return None
    
    @staticmethod
    def parse(data: bytes) -> Optional['VtfFile']:
        """Parse VTF data from bytes"""
        if len(data) < 80:
            print("[VTF] File too small")
            return None
        
        vtf = VtfFile()
        
        # Read header (64 bytes minimum for 7.2)
        vtf.signature = struct.unpack_from('<I', data, 0)[0]
        
        if vtf.signature != VtfFile.VTF_SIGNATURE:
            print(f"[VTF] Invalid signature: 0x{vtf.signature:08X}")
            return None
        
        vtf.version_major = struct.unpack_from('<I', data, 4)[0]
        vtf.version_minor = struct.unpack_from('<I', data, 8)[0]
        vtf.header_size = struct.unpack_from('<I', data, 12)[0]
        vtf.width = struct.unpack_from('<H', data, 16)[0]
        vtf.height = struct.unpack_from('<H', data, 18)[0]
        vtf.flags = struct.unpack_from('<I', data, 20)[0]
        vtf.frames = struct.unpack_from('<H', data, 24)[0]
        vtf.first_frame = struct.unpack_from('<H', data, 26)[0]
        # padding 4 bytes at 28
        vtf.reflectivity = struct.unpack_from('<fff', data, 32)
        # padding 4 bytes at 44
        vtf.bump_scale = struct.unpack_from('<f', data, 48)[0]
        vtf.high_res_format = VtfImageFormat(struct.unpack_from('<i', data, 52)[0])
        vtf.mip_count = struct.unpack_from('<B', data, 56)[0]
        vtf.low_res_format = VtfImageFormat(struct.unpack_from('<i', data, 57)[0])
        vtf.low_res_width = struct.unpack_from('<B', data, 61)[0]
        vtf.low_res_height = struct.unpack_from('<B', data, 62)[0]
        
        # Version 7.2+ has depth
        if vtf.version_major >= 7 and vtf.version_minor >= 2:
            vtf.depth = struct.unpack_from('<H', data, 63)[0]
        
        print(f"[VTF] Loaded: {vtf.width}x{vtf.height}, format={vtf.high_res_format.name}, mips={vtf.mip_count}")
        
        # Calculate data offsets
        data_offset = vtf.header_size
        
        # Read low-res thumbnail if present
        if vtf.low_res_format != VtfImageFormat.NONE and vtf.low_res_width > 0 and vtf.low_res_height > 0:
            thumb_size = VtfFile.calculate_image_size(vtf.low_res_format, vtf.low_res_width, vtf.low_res_height)
            vtf.thumbnail_data = data[data_offset:data_offset + thumb_size]
            data_offset += thumb_size
        
        # Read mip levels (stored smallest to largest, from end of file)
        vtf.mip_data = [None] * vtf.mip_count
        current_offset = len(data)
        
        frame_count = max(1, vtf.frames)
        
        for mip in range(vtf.mip_count):
            mip_width = max(1, vtf.width >> mip)
            mip_height = max(1, vtf.height >> mip)
            mip_size = VtfFile.calculate_image_size(vtf.high_res_format, mip_width, mip_height)
            mip_size *= frame_count  # Multiply by frame count for animated textures
            
            current_offset -= mip_size
            if current_offset >= 0:
                vtf.mip_data[mip] = data[current_offset:current_offset + mip_size]
        
        return vtf
    
    @staticmethod
    def calculate_image_size(format: VtfImageFormat, width: int, height: int) -> int:
        """Calculate the size in bytes for an image in a given format"""
        # Ensure minimum dimensions for block-compressed formats
        if format in (VtfImageFormat.DXT1, VtfImageFormat.DXT1_ONEBITALPHA,
                      VtfImageFormat.DXT3, VtfImageFormat.DXT5):
            width = max(4, width)
            height = max(4, height)
        
        size_map = {
            VtfImageFormat.RGBA8888: width * height * 4,
            VtfImageFormat.ABGR8888: width * height * 4,
            VtfImageFormat.RGB888: width * height * 3,
            VtfImageFormat.BGR888: width * height * 3,
            VtfImageFormat.RGB565: width * height * 2,
            VtfImageFormat.I8: width * height,
            VtfImageFormat.IA88: width * height * 2,
            VtfImageFormat.P8: width * height,
            VtfImageFormat.A8: width * height,
            VtfImageFormat.ARGB8888: width * height * 4,
            VtfImageFormat.BGRA8888: width * height * 4,
            VtfImageFormat.DXT1: ((width + 3) // 4) * ((height + 3) // 4) * 8,
            VtfImageFormat.DXT1_ONEBITALPHA: ((width + 3) // 4) * ((height + 3) // 4) * 8,
            VtfImageFormat.DXT3: ((width + 3) // 4) * ((height + 3) // 4) * 16,
            VtfImageFormat.DXT5: ((width + 3) // 4) * ((height + 3) // 4) * 16,
            VtfImageFormat.BGRX8888: width * height * 4,
            VtfImageFormat.BGR565: width * height * 2,
            VtfImageFormat.BGRX5551: width * height * 2,
            VtfImageFormat.BGRA4444: width * height * 2,
            VtfImageFormat.BGRA5551: width * height * 2,
            VtfImageFormat.UV88: width * height * 2,
            VtfImageFormat.UVWQ8888: width * height * 4,
            VtfImageFormat.RGBA16161616F: width * height * 8,
            VtfImageFormat.RGBA16161616: width * height * 8,
            VtfImageFormat.UVLX8888: width * height * 4,
        }
        
        return size_map.get(format, width * height * 4)
    
    def get_largest_mip_data(self) -> Optional[bytes]:
        """Get the largest mip level data (highest resolution)"""
        if not self.mip_data or len(self.mip_data) == 0:
            return None
        return self.mip_data[0]
    
    def convert_to_rgba(self, force_opaque_alpha: bool = False) -> Optional[bytes]:
        """Convert to RGBA8888 format"""
        data = self.get_largest_mip_data()
        if data is None:
            return None
        
        rgba = self._convert_format_to_rgba(data, self.width, self.height, self.high_res_format)
        
        # Force alpha to 255 if requested
        if force_opaque_alpha and rgba:
            rgba = bytearray(rgba)
            for i in range(3, len(rgba), 4):
                rgba[i] = 255
            rgba = bytes(rgba)
        
        return rgba
    
    def _convert_format_to_rgba(self, data: bytes, width: int, height: int, format: VtfImageFormat) -> bytes:
        """Convert image data to RGBA8888 format"""
        rgba = bytearray(width * height * 4)
        
        if format == VtfImageFormat.RGBA8888:
            rgba[:min(len(data), len(rgba))] = data[:min(len(data), len(rgba))]
        
        elif format == VtfImageFormat.BGRA8888:
            for i in range(width * height):
                if i * 4 + 3 >= len(data):
                    break
                rgba[i * 4 + 0] = data[i * 4 + 2]  # R
                rgba[i * 4 + 1] = data[i * 4 + 1]  # G
                rgba[i * 4 + 2] = data[i * 4 + 0]  # B
                rgba[i * 4 + 3] = data[i * 4 + 3]  # A
        
        elif format == VtfImageFormat.RGB888:
            for i in range(width * height):
                if i * 3 + 2 >= len(data):
                    break
                rgba[i * 4 + 0] = data[i * 3 + 0]  # R
                rgba[i * 4 + 1] = data[i * 3 + 1]  # G
                rgba[i * 4 + 2] = data[i * 3 + 2]  # B
                rgba[i * 4 + 3] = 255              # A
        
        elif format == VtfImageFormat.BGR888:
            for i in range(width * height):
                if i * 3 + 2 >= len(data):
                    break
                rgba[i * 4 + 0] = data[i * 3 + 2]  # R
                rgba[i * 4 + 1] = data[i * 3 + 1]  # G
                rgba[i * 4 + 2] = data[i * 3 + 0]  # B
                rgba[i * 4 + 3] = 255              # A
        
        elif format in (VtfImageFormat.DXT1, VtfImageFormat.DXT1_ONEBITALPHA):
            self._decompress_dxt1(data, rgba, width, height)
        
        elif format == VtfImageFormat.DXT3:
            self._decompress_dxt3(data, rgba, width, height)
        
        elif format == VtfImageFormat.DXT5:
            self._decompress_dxt5(data, rgba, width, height)
        
        elif format == VtfImageFormat.I8:
            for i in range(width * height):
                if i >= len(data):
                    break
                rgba[i * 4 + 0] = data[i]
                rgba[i * 4 + 1] = data[i]
                rgba[i * 4 + 2] = data[i]
                rgba[i * 4 + 3] = 255
        
        elif format == VtfImageFormat.A8:
            for i in range(width * height):
                if i >= len(data):
                    break
                rgba[i * 4 + 0] = 255
                rgba[i * 4 + 1] = 255
                rgba[i * 4 + 2] = 255
                rgba[i * 4 + 3] = data[i]
        
        elif format == VtfImageFormat.ARGB8888:
            for i in range(width * height):
                if i * 4 + 3 >= len(data):
                    break
                rgba[i * 4 + 0] = data[i * 4 + 1]  # R
                rgba[i * 4 + 1] = data[i * 4 + 2]  # G
                rgba[i * 4 + 2] = data[i * 4 + 3]  # B
                rgba[i * 4 + 3] = data[i * 4 + 0]  # A
        
        else:
            print(f"[VTF] Unsupported format: {format.name}, filling with gray")
            for i in range(0, len(rgba), 4):
                rgba[i] = 128
                rgba[i + 1] = 128
                rgba[i + 2] = 128
                rgba[i + 3] = 255
        
        return bytes(rgba)
    
    @staticmethod
    def _decode_rgb565(color: int) -> Tuple[int, int, int]:
        """Decode RGB565 color to RGB components"""
        r = ((color >> 11) & 0x1F) * 255 // 31
        g = ((color >> 5) & 0x3F) * 255 // 63
        b = (color & 0x1F) * 255 // 31
        return r, g, b
    
    def _decompress_dxt1(self, compressed: bytes, output: bytearray, width: int, height: int):
        """Decompress DXT1 block-compressed data"""
        block_width = (width + 3) // 4
        block_height = (height + 3) // 4
        block_index = 0
        
        for by in range(block_height):
            for bx in range(block_width):
                block_offset = block_index * 8
                if block_offset + 8 > len(compressed):
                    break
                
                # Read color endpoints
                c0 = compressed[block_offset] | (compressed[block_offset + 1] << 8)
                c1 = compressed[block_offset + 2] | (compressed[block_offset + 3] << 8)
                
                # Decode colors
                colors = [0] * 16
                r0, g0, b0 = self._decode_rgb565(c0)
                r1, g1, b1 = self._decode_rgb565(c1)
                
                colors[0:4] = [r0, g0, b0, 255]
                colors[4:8] = [r1, g1, b1, 255]
                
                if c0 > c1:
                    colors[8:12] = [
                        (2 * r0 + r1) // 3,
                        (2 * g0 + g1) // 3,
                        (2 * b0 + b1) // 3,
                        255
                    ]
                    colors[12:16] = [
                        (r0 + 2 * r1) // 3,
                        (g0 + 2 * g1) // 3,
                        (b0 + 2 * b1) // 3,
                        255
                    ]
                else:
                    colors[8:12] = [
                        (r0 + r1) // 2,
                        (g0 + g1) // 2,
                        (b0 + b1) // 2,
                        255
                    ]
                    colors[12:16] = [0, 0, 0, 0]  # Transparent
                
                # Read indices
                indices = (compressed[block_offset + 4] |
                          (compressed[block_offset + 5] << 8) |
                          (compressed[block_offset + 6] << 16) |
                          (compressed[block_offset + 7] << 24))
                
                # Write pixels
                for py in range(4):
                    for px in range(4):
                        x = bx * 4 + px
                        y = by * 4 + py
                        if x >= width or y >= height:
                            continue
                        
                        color_index = (indices >> ((py * 4 + px) * 2)) & 0x3
                        out_offset = (y * width + x) * 4
                        output[out_offset:out_offset + 4] = bytes(colors[color_index * 4:(color_index + 1) * 4])
                
                block_index += 1
    
    def _decompress_dxt3(self, compressed: bytes, output: bytearray, width: int, height: int):
        """Decompress DXT3 block-compressed data"""
        block_width = (width + 3) // 4
        block_height = (height + 3) // 4
        block_index = 0
        
        for by in range(block_height):
            for bx in range(block_width):
                block_offset = block_index * 16
                if block_offset + 16 > len(compressed):
                    break
                
                # Read alpha values (first 8 bytes)
                alphas = 0
                for i in range(8):
                    alphas |= compressed[block_offset + i] << (i * 8)
                
                # Read color data
                c0 = compressed[block_offset + 8] | (compressed[block_offset + 9] << 8)
                c1 = compressed[block_offset + 10] | (compressed[block_offset + 11] << 8)
                
                r0, g0, b0 = self._decode_rgb565(c0)
                r1, g1, b1 = self._decode_rgb565(c1)
                
                colors = [
                    r0, g0, b0,
                    r1, g1, b1,
                    (2 * r0 + r1) // 3, (2 * g0 + g1) // 3, (2 * b0 + b1) // 3,
                    (r0 + 2 * r1) // 3, (g0 + 2 * g1) // 3, (b0 + 2 * b1) // 3
                ]
                
                indices = (compressed[block_offset + 12] |
                          (compressed[block_offset + 13] << 8) |
                          (compressed[block_offset + 14] << 16) |
                          (compressed[block_offset + 15] << 24))
                
                for py in range(4):
                    for px in range(4):
                        x = bx * 4 + px
                        y = by * 4 + py
                        if x >= width or y >= height:
                            continue
                        
                        color_index = (indices >> ((py * 4 + px) * 2)) & 0x3
                        alpha_index = py * 4 + px
                        alpha = ((alphas >> (alpha_index * 4)) & 0xF) * 17
                        
                        out_offset = (y * width + x) * 4
                        output[out_offset + 0] = colors[color_index * 3 + 0]
                        output[out_offset + 1] = colors[color_index * 3 + 1]
                        output[out_offset + 2] = colors[color_index * 3 + 2]
                        output[out_offset + 3] = alpha
                
                block_index += 1
    
    def _decompress_dxt5(self, compressed: bytes, output: bytearray, width: int, height: int):
        """Decompress DXT5 block-compressed data"""
        block_width = (width + 3) // 4
        block_height = (height + 3) // 4
        block_index = 0
        
        for by in range(block_height):
            for bx in range(block_width):
                block_offset = block_index * 16
                if block_offset + 16 > len(compressed):
                    break
                
                # Read alpha endpoints
                a0 = compressed[block_offset]
                a1 = compressed[block_offset + 1]
                
                # Read alpha indices (48 bits = 6 bytes)
                alpha_indices = 0
                for i in range(6):
                    alpha_indices |= compressed[block_offset + 2 + i] << (i * 8)
                
                # Calculate alpha palette
                alpha_palette = [0] * 8
                alpha_palette[0] = a0
                alpha_palette[1] = a1
                if a0 > a1:
                    alpha_palette[2] = (6 * a0 + 1 * a1) // 7
                    alpha_palette[3] = (5 * a0 + 2 * a1) // 7
                    alpha_palette[4] = (4 * a0 + 3 * a1) // 7
                    alpha_palette[5] = (3 * a0 + 4 * a1) // 7
                    alpha_palette[6] = (2 * a0 + 5 * a1) // 7
                    alpha_palette[7] = (1 * a0 + 6 * a1) // 7
                else:
                    alpha_palette[2] = (4 * a0 + 1 * a1) // 5
                    alpha_palette[3] = (3 * a0 + 2 * a1) // 5
                    alpha_palette[4] = (2 * a0 + 3 * a1) // 5
                    alpha_palette[5] = (1 * a0 + 4 * a1) // 5
                    alpha_palette[6] = 0
                    alpha_palette[7] = 255
                
                # Read color data
                c0 = compressed[block_offset + 8] | (compressed[block_offset + 9] << 8)
                c1 = compressed[block_offset + 10] | (compressed[block_offset + 11] << 8)
                
                r0, g0, b0 = self._decode_rgb565(c0)
                r1, g1, b1 = self._decode_rgb565(c1)
                
                colors = [
                    r0, g0, b0,
                    r1, g1, b1,
                    (2 * r0 + r1) // 3, (2 * g0 + g1) // 3, (2 * b0 + b1) // 3,
                    (r0 + 2 * r1) // 3, (g0 + 2 * g1) // 3, (b0 + 2 * b1) // 3
                ]
                
                indices = (compressed[block_offset + 12] |
                          (compressed[block_offset + 13] << 8) |
                          (compressed[block_offset + 14] << 16) |
                          (compressed[block_offset + 15] << 24))
                
                for py in range(4):
                    for px in range(4):
                        x = bx * 4 + px
                        y = by * 4 + py
                        if x >= width or y >= height:
                            continue
                        
                        color_index = (indices >> ((py * 4 + px) * 2)) & 0x3
                        alpha_idx = (alpha_indices >> ((py * 4 + px) * 3)) & 0x7
                        
                        out_offset = (y * width + x) * 4
                        output[out_offset + 0] = colors[color_index * 3 + 0]
                        output[out_offset + 1] = colors[color_index * 3 + 1]
                        output[out_offset + 2] = colors[color_index * 3 + 2]
                        output[out_offset + 3] = alpha_palette[alpha_idx]
                
                block_index += 1


def convert_vtf_to_png(vtf_path: str, output_path: str = None) -> Optional[str]:
    """
    Convert a VTF file to PNG format.
    
    Args:
        vtf_path: Path to the VTF file
        output_path: Output path for PNG (defaults to same name with .png extension)
    
    Returns:
        Path to the created PNG file, or None on failure
    """
    try:
        # Try to import PIL for PNG saving
        try:
            from PIL import Image
            has_pil = True
        except ImportError:
            has_pil = False
        
        vtf = VtfFile.load(vtf_path)
        if vtf is None:
            return None
        
        rgba_data = vtf.convert_to_rgba()
        if rgba_data is None:
            print(f"[VTF] Failed to convert {vtf_path} to RGBA")
            return None
        
        if output_path is None:
            output_path = os.path.splitext(vtf_path)[0] + '.png'
        
        if has_pil:
            # Use PIL for proper PNG saving
            img = Image.frombytes('RGBA', (vtf.width, vtf.height), rgba_data)
            # VTF images are often stored flipped
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
            img.save(output_path, 'PNG')
        else:
            # Fallback: save as raw TGA (simpler format)
            output_path = os.path.splitext(output_path)[0] + '.tga'
            save_tga(output_path, vtf.width, vtf.height, rgba_data)
        
        print(f"[VTF] Converted: {vtf_path} -> {output_path}")
        return output_path
        
    except Exception as e:
        print(f"[VTF] Error converting {vtf_path}: {e}")
        import traceback
        traceback.print_exc()
        return None


def save_tga(filepath: str, width: int, height: int, rgba_data: bytes):
    """Save RGBA data as a TGA file (simple uncompressed format)"""
    with open(filepath, 'wb') as f:
        # TGA header (18 bytes)
        header = bytearray(18)
        header[2] = 2  # Uncompressed true-color image
        header[12] = width & 0xFF
        header[13] = (width >> 8) & 0xFF
        header[14] = height & 0xFF
        header[15] = (height >> 8) & 0xFF
        header[16] = 32  # Bits per pixel
        header[17] = 0x28  # Image descriptor (top-left origin + 8 alpha bits)
        f.write(header)
        
        # Convert RGBA to BGRA (TGA format)
        bgra = bytearray(len(rgba_data))
        for i in range(0, len(rgba_data), 4):
            bgra[i + 0] = rgba_data[i + 2]  # B
            bgra[i + 1] = rgba_data[i + 1]  # G
            bgra[i + 2] = rgba_data[i + 0]  # R
            bgra[i + 3] = rgba_data[i + 3]  # A
        
        f.write(bgra)


def load_vtf_as_blender_image(vtf_path: str, image_name: str = None):
    """
    Load a VTF file directly into Blender as an image.
    
    Args:
        vtf_path: Path to the VTF file
        image_name: Name for the Blender image (defaults to filename)
    
    Returns:
        Blender image object, or None on failure
    """
    try:
        import bpy
        
        vtf = VtfFile.load(vtf_path)
        if vtf is None:
            return None
        
        rgba_data = vtf.convert_to_rgba()
        if rgba_data is None:
            return None
        
        if image_name is None:
            image_name = os.path.basename(vtf_path)
        
        # Create Blender image
        img = bpy.data.images.new(image_name, vtf.width, vtf.height, alpha=True)
        
        # Convert bytes to float pixels (Blender uses 0-1 range)
        pixels = []
        for i in range(0, len(rgba_data), 4):
            pixels.extend([
                rgba_data[i + 0] / 255.0,  # R
                rgba_data[i + 1] / 255.0,  # G
                rgba_data[i + 2] / 255.0,  # B
                rgba_data[i + 3] / 255.0   # A
            ])
        
        # VTF images are stored bottom-to-top, need to flip
        flipped_pixels = []
        for y in range(vtf.height - 1, -1, -1):
            row_start = y * vtf.width * 4
            flipped_pixels.extend(pixels[row_start:row_start + vtf.width * 4])
        
        img.pixels = flipped_pixels
        img.pack()
        
        print(f"[VTF] Loaded into Blender: {image_name} ({vtf.width}x{vtf.height})")
        return img
        
    except Exception as e:
        print(f"[VTF] Error loading {vtf_path} into Blender: {e}")
        import traceback
        traceback.print_exc()
        return None
