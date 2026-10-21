import struct
import zlib
import os

def generate_png(width, height, path):
    """
    Generates a valid PNG icon using standard Python (zlib, struct)
    with zero external dependencies.
    Renders a purple rounded square with an inner document symbol.
    """
    raw_data = bytearray()
    
    for y in range(height):
        raw_data.append(0)  # filter type 0 (None)
        for x in range(width):
            # Normalized coordinates [0, 1]
            nx = x / width
            ny = y / height
            
            # Rounded border box
            border_dist = min(nx, 1 - nx, ny, 1 - ny)
            if border_dist < 0.05:
                # Transparent or anti-aliased edge
                raw_data.extend([0, 0, 0, 0])
            else:
                # Check if inside document icon (center area)
                if 0.28 <= nx <= 0.72 and 0.20 <= ny <= 0.80:
                    # Inside document body
                    # Check for simulated text lines
                    is_line = (
                        (0.35 <= ny <= 0.40 and 0.35 <= nx <= 0.65) or
                        (0.46 <= ny <= 0.51 and 0.35 <= nx <= 0.65) or
                        (0.57 <= ny <= 0.62 and 0.35 <= nx <= 0.55) or
                        (0.68 <= ny <= 0.73 and 0.35 <= nx <= 0.60)
                    )
                    if is_line:
                        # Purple line
                        raw_data.extend([99, 102, 241, 255])
                    else:
                        # White document paper
                        raw_data.extend([248, 250, 252, 255])
                else:
                    # Background gradient: Indigo / Violet (#6366f1 to #8b5cf6)
                    r = int(99 + (139 - 99) * ny)
                    g = int(102 + (92 - 102) * ny)
                    b = int(241 + (246 - 241) * ny)
                    raw_data.extend([r, g, b, 255])

    # PNG File Structure
    png = bytearray(b"\x89PNG\r\n\x1a\n")
    
    # IHDR chunk
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data)
    png.extend(struct.pack(">I", len(ihdr_data)))
    png.extend(b"IHDR")
    png.extend(ihdr_data)
    png.extend(struct.pack(">I", ihdr_crc))
    
    # IDAT chunk
    compressed = zlib.compress(bytes(raw_data), 9)
    idat_crc = zlib.crc32(b"IDAT" + compressed)
    png.extend(struct.pack(">I", len(compressed)))
    png.extend(b"IDAT")
    png.extend(compressed)
    png.extend(struct.pack(">I", idat_crc))
    
    # IEND chunk
    iend_crc = zlib.crc32(b"IEND")
    png.extend(struct.pack(">I", 0))
    png.extend(b"IEND")
    png.extend(struct.pack(">I", iend_crc))
    
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)

if __name__ == "__main__":
    generate_png(16, 16, "extension/icons/icon16.png")
    generate_png(48, 48, "extension/icons/icon48.png")
    generate_png(128, 128, "extension/icons/icon128.png")
    print("Zero-dependency PNG icons generated successfully!")
