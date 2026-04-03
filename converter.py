"""
PLY Converter - Core conversion logic
Supports: PLY → OBJ, PLY → FBX (ASCII 7.4.0)
Handles: Meshes, Point Clouds, 3D Gaussian Splatting (3DGS) files
"""

import numpy as np
from pathlib import Path
import math


# Spherical Harmonic DC constant: 1 / (2 * sqrt(pi))
SH_C0 = 0.28209479177387814


def check_dependencies():
    """Return list of missing required packages."""
    missing = []
    try:
        import numpy
    except ImportError:
        missing.append("numpy")
    try:
        import plyfile
    except ImportError:
        missing.append("plyfile")
    return missing


def read_ply(filepath, callback=None):
    """
    Read a PLY file and return a mesh/point-cloud data dict.

    Returns dict with keys:
      vertices  : ndarray (N, 3) float32
      normals   : ndarray (N, 3) float32  or None
      colors    : ndarray (N, 3) float32 in [0,1]  or None
      faces     : ndarray (F, K) int  or None
      is_3dgs   : bool – True when file has 3DGS Gaussian attributes
      n_vertices: int
      n_faces   : int
    """
    from plyfile import PlyData

    if callback:
        callback(f"Reading: {filepath}")

    plydata = PlyData.read(filepath)
    vertex_el = plydata["vertex"]
    props = set(p.name for p in vertex_el.properties)

    # --- Positions ---
    x = np.array(vertex_el["x"], dtype=np.float32)
    y = np.array(vertex_el["y"], dtype=np.float32)
    z = np.array(vertex_el["z"], dtype=np.float32)
    vertices = np.column_stack([x, y, z])

    n_vertices = len(vertices)
    if callback:
        callback(f"Loaded {n_vertices:,} vertices")

    # --- Normals ---
    normals = None
    if "nx" in props and "ny" in props and "nz" in props:
        nx = np.array(vertex_el["nx"], dtype=np.float32)
        ny = np.array(vertex_el["ny"], dtype=np.float32)
        nz = np.array(vertex_el["nz"], dtype=np.float32)
        norms = np.column_stack([nx, ny, nz])
        # Only keep normals if they're not all zero
        if np.any(norms != 0):
            normals = norms
            if callback:
                callback("Loaded vertex normals")

    # --- Colors ---
    colors = None
    is_3dgs = False

    if "red" in props and "green" in props and "blue" in props:
        # Standard uint8 vertex colors
        r = np.array(vertex_el["red"], dtype=np.float32) / 255.0
        g = np.array(vertex_el["green"], dtype=np.float32) / 255.0
        b = np.array(vertex_el["blue"], dtype=np.float32) / 255.0
        colors = np.column_stack([r, g, b])
        if callback:
            callback("Loaded vertex colors (RGB)")

    elif "f_dc_0" in props and "f_dc_1" in props and "f_dc_2" in props:
        # 3DGS Spherical Harmonic DC coefficients → diffuse color
        is_3dgs = True
        dc0 = np.array(vertex_el["f_dc_0"], dtype=np.float32)
        dc1 = np.array(vertex_el["f_dc_1"], dtype=np.float32)
        dc2 = np.array(vertex_el["f_dc_2"], dtype=np.float32)
        r = np.clip(0.5 + SH_C0 * dc0, 0.0, 1.0)
        g = np.clip(0.5 + SH_C0 * dc1, 0.0, 1.0)
        b = np.clip(0.5 + SH_C0 * dc2, 0.0, 1.0)
        colors = np.column_stack([r, g, b])
        if callback:
            callback("Detected 3DGS format – converted SH coefficients to RGB colors")

    # --- Faces ---
    faces = None
    n_faces = 0
    if "face" in plydata:
        face_el = plydata["face"]
        raw_faces = [f[0] for f in face_el.data]
        if len(raw_faces) > 0:
            try:
                faces = np.array(raw_faces, dtype=np.int32)
                n_faces = len(faces)
                if callback:
                    callback(f"Loaded {n_faces:,} faces")
            except Exception:
                # Faces have mixed sizes (polygon soup) – store as list
                faces = raw_faces
                n_faces = len(faces)
                if callback:
                    callback(f"Loaded {n_faces:,} polygon faces")

    return {
        "vertices": vertices,
        "normals": normals,
        "colors": colors,
        "faces": faces,
        "is_3dgs": is_3dgs,
        "n_vertices": n_vertices,
        "n_faces": n_faces,
    }


# ---------------------------------------------------------------------------
# OBJ Export
# ---------------------------------------------------------------------------

def export_obj(data, output_path, callback=None):
    """
    Export mesh/point-cloud data to Wavefront OBJ.

    Vertex colors are written as 'v x y z r g b' (extended OBJ format
    supported by Blender, MeshLab, and Maya with plugins).
    """
    vertices = data["vertices"]
    normals  = data["normals"]
    colors   = data["colors"]
    faces    = data["faces"]

    stem = Path(output_path).stem
    has_faces   = faces is not None and len(faces) > 0
    has_normals = normals is not None
    has_colors  = colors is not None

    if callback:
        callback(f"Writing OBJ: {output_path}")

    n = len(vertices)
    CHUNK = 50_000  # write in chunks for large files

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# PLY Converter – Wavefront OBJ\n")
        f.write(f"# Vertices: {n:,}\n")
        if has_faces:
            f.write(f"# Faces: {len(faces):,}\n")
        f.write(f"g {stem}\n\n")

        # --- Vertices ---
        for start in range(0, n, CHUNK):
            end = min(start + CHUNK, n)
            chunk_v = vertices[start:end]
            if has_colors:
                chunk_c = colors[start:end]
                lines = [
                    f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}"
                    f" {c[0]:.6f} {c[1]:.6f} {c[2]:.6f}\n"
                    for v, c in zip(chunk_v, chunk_c)
                ]
            else:
                lines = [
                    f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n"
                    for v in chunk_v
                ]
            f.writelines(lines)
            if callback and (start // CHUNK) % 10 == 0:
                pct = int(end / n * 50)
                callback(f"  Writing vertices... {end:,}/{n:,} ({pct}%)", progress=pct)

        # --- Normals ---
        if has_normals:
            for start in range(0, n, CHUNK):
                end = min(start + CHUNK, n)
                chunk_n = normals[start:end]
                lines = [
                    f"vn {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n"
                    for v in chunk_n
                ]
                f.writelines(lines)
            if callback:
                callback("  Vertex normals written", progress=60)

        # --- Faces ---
        if has_faces:
            f.write(f"\no {stem}\n")
            faces_list = faces if isinstance(faces, list) else faces.tolist()
            total_f = len(faces_list)
            for i, face in enumerate(faces_list):
                idxs = [int(x) for x in face]
                if has_normals:
                    indices = " ".join(f"{idx+1}//{idx+1}" for idx in idxs)
                else:
                    indices = " ".join(str(idx + 1) for idx in idxs)
                f.write(f"f {indices}\n")
                if callback and i % CHUNK == 0:
                    pct = 60 + int(i / total_f * 35)
                    callback(f"  Writing faces... {i:,}/{total_f:,}", progress=pct)
        else:
            if callback:
                callback("  Point cloud – no faces to write", progress=85)

    if callback:
        size_mb = Path(output_path).stat().st_size / 1_048_576
        callback(f"OBJ saved ({size_mb:.1f} MB)", progress=100)

    return output_path


# ---------------------------------------------------------------------------
# FBX ASCII 7.4.0 Export
# ---------------------------------------------------------------------------

_GEOM_ID  = 100_000_001
_MODEL_ID = 100_000_002


def _fbx_array(values, label, f, chunk=5000):
    """Write a compact FBX array node: Label: *N { a: v0,v1,... }"""
    n = len(values)
    f.write(f"\t\t{label}: *{n} {{\n")
    f.write(f"\t\t\ta: ")
    for i in range(0, n, chunk):
        seg = values[i:i + chunk]
        if i == 0:
            f.write(",".join(f"{v:.6g}" for v in seg))
        else:
            f.write("," + ",".join(f"{v:.6g}" for v in seg))
    f.write("\n\t\t}\n")


def export_fbx(data, output_path, callback=None):
    """
    Export mesh/point-cloud data to ASCII FBX 7.4.0.
    Compatible with Maya and Blender.
    """
    vertices = data["vertices"]
    normals  = data["normals"]
    colors   = data["colors"]
    faces    = data["faces"]

    stem = Path(output_path).stem
    has_faces   = faces is not None and len(faces) > 0
    has_normals = normals is not None
    has_colors  = colors is not None

    n_verts = len(vertices)

    if callback:
        callback(f"Writing FBX: {output_path}")

    # Build polygon vertex index array (FBX convention:
    # last index per polygon is -(idx+1) )
    poly_indices = []
    if has_faces:
        faces_list = faces if isinstance(faces, list) else faces.tolist()
        for face in faces_list:
            idxs = [int(x) for x in face]
            for k, idx in enumerate(idxs):
                if k == len(idxs) - 1:
                    poly_indices.append(-(idx + 1))
                else:
                    poly_indices.append(idx)
        if callback:
            callback(f"  Built {len(poly_indices):,} polygon indices", progress=10)
    else:
        # Point cloud: single-vertex degenerate polygons
        poly_indices = [-(i + 1) for i in range(n_verts)]
        if callback:
            callback("  Point cloud mode: generating point polygons", progress=10)

    verts_flat   = vertices.flatten().tolist()
    norms_flat   = normals.flatten().tolist() if has_normals else []
    # Colors: FBX vertex color needs RGBA
    if has_colors:
        rgba = np.hstack([colors, np.ones((len(colors), 1), dtype=np.float32)])
        colors_flat = rgba.flatten().tolist()
    else:
        colors_flat = []

    with open(output_path, "w", encoding="utf-8") as f:

        # ---- Header ----
        f.write("; FBX 7.4.0 project file\n")
        f.write("; Created by PLY Converter\n")
        f.write("; ----------------------------------------------------\n\n")

        f.write("FBXHeaderExtension:  {\n")
        f.write("\tFBXHeaderVersion: 1003\n")
        f.write("\tFBXVersion: 7400\n")
        f.write('\tCreator: "PLY Converter 1.0"\n')
        f.write("}\n\n")

        # ---- GlobalSettings ----
        f.write("GlobalSettings:  {\n")
        f.write("\tVersion: 1000\n")
        f.write("\tProperties70:  {\n")
        f.write('\t\tP: "UpAxis", "int", "Integer", "",1\n')
        f.write('\t\tP: "UpAxisSign", "int", "Integer", "",1\n')
        f.write('\t\tP: "FrontAxis", "int", "Integer", "",2\n')
        f.write('\t\tP: "FrontAxisSign", "int", "Integer", "",1\n')
        f.write('\t\tP: "CoordAxis", "int", "Integer", "",0\n')
        f.write('\t\tP: "CoordAxisSign", "int", "Integer", "",1\n')
        f.write('\t\tP: "UnitScaleFactor", "double", "Number", "",1\n')
        f.write("\t}\n}\n\n")

        # ---- Documents ----
        f.write("Documents:  {\n")
        f.write("\tCount: 1\n")
        f.write('\tDocument: 999999999, "", "Scene" {\n')
        f.write("\t\tRootNode: 0\n")
        f.write("\t}\n}\n\n")

        f.write("References:  {\n}\n\n")

        # ---- Definitions ----
        f.write("Definitions:  {\n")
        f.write("\tVersion: 100\n")
        f.write("\tCount: 2\n")
        f.write('\tObjectType: "Model" {\n\t\tCount: 1\n\t}\n')
        f.write('\tObjectType: "Geometry" {\n\t\tCount: 1\n\t}\n')
        f.write("}\n\n")

        if callback:
            callback("  Header written", progress=15)

        # ---- Objects ----
        f.write("Objects:  {\n")

        # Geometry node
        f.write(f'\tGeometry: {_GEOM_ID}, "Geometry::{stem}", "Mesh" {{\n')
        f.write("\t\tGeometryVersion: 124\n")

        # Vertices
        if callback:
            callback(f"  Writing {n_verts:,} vertices...", progress=20)
        f.write(f"\t\tVertices: *{len(verts_flat)} {{\n\t\t\ta: ")
        CHUNK = 10_000
        for i in range(0, len(verts_flat), CHUNK):
            seg = verts_flat[i:i + CHUNK]
            if i == 0:
                f.write(",".join(f"{v:.6g}" for v in seg))
            else:
                f.write("," + ",".join(f"{v:.6g}" for v in seg))
        f.write("\n\t\t}\n")

        if callback:
            callback("  Vertices written", progress=40)

        # Polygon vertex index
        f.write(f"\t\tPolygonVertexIndex: *{len(poly_indices)} {{\n\t\t\ta: ")
        for i in range(0, len(poly_indices), CHUNK):
            seg = poly_indices[i:i + CHUNK]
            if i == 0:
                f.write(",".join(str(v) for v in seg))
            else:
                f.write("," + ",".join(str(v) for v in seg))
        f.write("\n\t\t}\n")

        if callback:
            callback("  Polygon indices written", progress=55)

        # Normals layer
        if has_normals:
            f.write('\t\tLayerElementNormal: 0 {\n')
            f.write('\t\t\tVersion: 101\n')
            f.write('\t\t\tName: ""\n')
            f.write('\t\t\tMappingInformationType: "ByVertice"\n')
            f.write('\t\t\tReferenceInformationType: "Direct"\n')
            f.write(f"\t\t\tNormals: *{len(norms_flat)} {{\n\t\t\t\ta: ")
            for i in range(0, len(norms_flat), CHUNK):
                seg = norms_flat[i:i + CHUNK]
                if i == 0:
                    f.write(",".join(f"{v:.6g}" for v in seg))
                else:
                    f.write("," + ",".join(f"{v:.6g}" for v in seg))
            f.write("\n\t\t\t}\n")
            f.write('\t\t}\n')
            if callback:
                callback("  Normals written", progress=65)

        # Vertex colors layer
        if has_colors:
            f.write('\t\tLayerElementColor: 0 {\n')
            f.write('\t\t\tVersion: 101\n')
            f.write('\t\t\tName: "Col"\n')
            f.write('\t\t\tMappingInformationType: "ByVertice"\n')
            f.write('\t\t\tReferenceInformationType: "Direct"\n')
            f.write(f"\t\t\tColors: *{len(colors_flat)} {{\n\t\t\t\ta: ")
            for i in range(0, len(colors_flat), CHUNK):
                seg = colors_flat[i:i + CHUNK]
                if i == 0:
                    f.write(",".join(f"{v:.6g}" for v in seg))
                else:
                    f.write("," + ",".join(f"{v:.6g}" for v in seg))
            f.write("\n\t\t\t}\n")
            f.write('\t\t}\n')
            if callback:
                callback("  Vertex colors written", progress=75)

        # Layer declaration
        f.write('\t\tLayer: 0 {\n')
        f.write('\t\t\tVersion: 100\n')
        if has_normals:
            f.write('\t\t\tLayerElement:  {\n')
            f.write('\t\t\t\tType: "LayerElementNormal"\n')
            f.write('\t\t\t\tTypedIndex: 0\n')
            f.write('\t\t\t}\n')
        if has_colors:
            f.write('\t\t\tLayerElement:  {\n')
            f.write('\t\t\t\tType: "LayerElementColor"\n')
            f.write('\t\t\t\tTypedIndex: 0\n')
            f.write('\t\t\t}\n')
        f.write('\t\t}\n')

        f.write('\t}\n')  # end Geometry

        # Model node
        f.write(f'\tModel: {_MODEL_ID}, "Model::{stem}", "Mesh" {{\n')
        f.write('\t\tVersion: 232\n')
        f.write('\t\tProperties70:  {\n')
        f.write('\t\t\tP: "DefaultAttributeIndex", "int", "Integer", "",0\n')
        f.write('\t\t\tP: "Lcl Translation", "Lcl Translation", "", "A",0,0,0\n')
        f.write('\t\t\tP: "Lcl Rotation", "Lcl Rotation", "", "A",0,0,0\n')
        f.write('\t\t\tP: "Lcl Scaling", "Lcl Scaling", "", "A",1,1,1\n')
        f.write('\t\t}\n')
        f.write('\t\tShading: T\n')
        f.write('\t\tCulling: "CullingOff"\n')
        f.write('\t}\n')

        f.write("}\n\n")  # end Objects

        # ---- Connections ----
        f.write("Connections:  {\n")
        f.write(f"\tC: \"OO\",{_GEOM_ID},{_MODEL_ID}\n")
        f.write(f"\tC: \"OO\",{_MODEL_ID},0\n")
        f.write("}\n")

    if callback:
        size_mb = Path(output_path).stat().st_size / 1_048_576
        callback(f"FBX saved ({size_mb:.1f} MB)", progress=100)

    return output_path


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

class PLYConverter:
    def __init__(self, callback=None):
        self._raw_callback = callback

    def _cb(self, msg, progress=None):
        if self._raw_callback:
            self._raw_callback(msg, progress=progress)

    def convert(self, input_path, output_dir, fmt):
        """Convert a PLY file to OBJ or FBX. Returns output path string."""
        fmt = fmt.lower().strip()
        if fmt not in ("obj", "fbx"):
            raise ValueError(f"Unsupported format: {fmt}")

        input_path = Path(input_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{input_path.stem}.{fmt}"

        data = read_ply(input_path, callback=self._cb)
        self._cb(
            f"File info: {data['n_vertices']:,} vertices, "
            f"{data['n_faces']:,} faces, "
            f"colors={'yes' if data['colors'] is not None else 'no'}, "
            f"normals={'yes' if data['normals'] is not None else 'no'}"
        )

        if fmt == "obj":
            export_obj(data, output_path, callback=self._cb)
        else:
            export_fbx(data, output_path, callback=self._cb)

        return str(output_path)
