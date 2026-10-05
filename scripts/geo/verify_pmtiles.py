#!/usr/bin/env python3
"""Smoke-check a PMTiles v3 archive header — the CodeBuild tiles lane
(buildspec-tiles.yml) gates the S3 publish on this. Prints a summary
and exits non-zero on anything that would make /tiles lie.

  python3 verify_pmtiles.py /path/to/delhi.pmtiles
"""
import os
import struct
import sys


def main(path: str) -> int:
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        h = f.read(127)
    assert len(h) == 127, "file shorter than the 127-byte header"
    assert h[:7] == b"PMTiles", "missing PMTiles magic"
    assert h[7] == 3, f"PMTiles spec version {h[7]} != 3"
    u = struct.unpack_from
    (root_off, root_len, meta_off, meta_len, leaf_off, leaf_len,
     tile_off, tile_len, n_tiles, n_entries,
     n_contents) = u("<11Q", h, 8)
    (clustered, int_comp, tile_comp, tile_type,
     minz, maxz) = u("<6B", h, 96)
    bounds = [v / 1e7 for v in u("<4i", h, 102)]
    assert tile_off + tile_len <= size, "tile section runs past EOF"
    assert tile_type == 1, f"tile_type {tile_type} != mvt(1)"
    assert maxz >= 14, f"max_zoom {maxz} below street level"
    assert n_tiles > 1000, f"suspiciously few tiles: {n_tiles}"
    # NCR sanity — Connaught Place (77.2167, 28.6315) inside the bbox
    assert bounds[0] <= 77.2167 <= bounds[2] \
        and bounds[1] <= 28.6315 <= bounds[3], \
        f"CP outside declared bounds {bounds}"
    print("SMOKE-OK pmtiles z%d-%d bounds=%s tiles=%d entries=%d "
          "tile_bytes=%d file_mb=%.1f"
          % (minz, maxz, bounds, n_tiles, n_entries, tile_len,
             size / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
