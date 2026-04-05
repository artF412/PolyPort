"""
PolyPort – Core conversion logic
Supported inputs : PLY, ABC, BLEND, MA, MB, MAX, C4D
Supported outputs: OBJ, FBX (ASCII 7.4.0), ABC
Handles          : Meshes, Point Clouds, 3D Gaussian Splatting (3DGS) files
"""

import os
import re
import shutil
import subprocess
import tempfile
import platform
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


# ── Software detection ───────────────────────────────────────────────────────

def find_blender():
    """Return path to Blender executable, or None if not found."""
    blender = shutil.which("blender")
    if blender:
        return blender
    if platform.system() == "Windows":
        base = Path("C:/Program Files/Blender Foundation")
        if base.exists():
            for vdir in sorted(base.glob("Blender*"), reverse=True):
                exe = vdir / "blender.exe"
                if exe.exists():
                    return str(exe)
    elif platform.system() == "Darwin":
        mac = Path("/Applications/Blender.app/Contents/MacOS/Blender")
        if mac.exists():
            return str(mac)
    return None


def find_maya():
    """Return path to Maya executable, or None if not found."""
    maya = shutil.which("maya")
    if maya:
        return maya
    if platform.system() == "Windows":
        base = Path("C:/Program Files/Autodesk")
        if base.exists():
            for vdir in sorted(base.glob("Maya*"), reverse=True):
                exe = vdir / "bin" / "maya.exe"
                if exe.exists():
                    return str(exe)
    elif platform.system() == "Darwin":
        base = Path("/Applications/Autodesk")
        if base.exists():
            for vdir in sorted(base.glob("maya*"), reverse=True):
                exe = vdir / "Maya.app/Contents/MacOS/Maya"
                if exe.exists():
                    return str(exe)
    return None


def find_3dsmax():
    """Return path to 3ds Max executable, or None if not found."""
    if platform.system() == "Windows":
        base = Path("C:/Program Files/Autodesk")
        if base.exists():
            for vdir in sorted(base.glob("3ds Max*"), reverse=True):
                exe = vdir / "3dsmax.exe"
                if exe.exists():
                    return str(exe)
    return None


def find_c4d():
    """Return path to Cinema 4D executable, or None if not found."""
    if platform.system() == "Windows":
        for base_str in ["C:/Program Files/Maxon Cinema 4D",
                         "C:/Program Files/Maxon"]:
            base = Path(base_str)
            if not base.exists():
                continue
            exe = base / "Cinema 4D.exe"
            if exe.exists():
                return str(exe)
            for vdir in sorted(base.glob("Cinema 4D*"), reverse=True):
                exe = vdir / "Cinema 4D.exe"
                if exe.exists():
                    return str(exe)
    elif platform.system() == "Darwin":
        for p in ["/Applications/Cinema 4D.app/Contents/MacOS/Cinema 4D"]:
            if Path(p).exists():
                return p
    return None


# ── Blender headless conversion ──────────────────────────────────────────────

# Script executed by Blender's Python interpreter (NOT an f-string)
_BLENDER_SCRIPT = """\
import bpy, sys, pathlib

argv = sys.argv
try:
    sep = argv.index("--")
    args = argv[sep + 1:]
except ValueError:
    print("ERROR:No -- separator")
    sys.exit(1)

input_file  = args[0]
output_file = args[1]
in_ext  = pathlib.Path(input_file).suffix.lower()
out_ext = pathlib.Path(output_file).suffix.lower()

if in_ext != ".blend":
    bpy.ops.wm.read_factory_settings(use_empty=True)

try:
    if in_ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=input_file)
    elif in_ext == ".abc":
        bpy.ops.wm.alembic_import(filepath=input_file)
    elif in_ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=input_file)
    elif in_ext == ".obj":
        try:
            bpy.ops.wm.obj_import(filepath=input_file)
        except AttributeError:
            bpy.ops.import_scene.obj(filepath=input_file)
    elif in_ext == ".ply":
        try:
            bpy.ops.wm.ply_import(filepath=input_file)
        except AttributeError:
            bpy.ops.import_mesh.ply(filepath=input_file)
    else:
        print("ERROR:Unsupported input: " + in_ext)
        sys.exit(1)
except Exception as e:
    print("ERROR:Import failed: " + str(e))
    sys.exit(1)

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
if not meshes:
    print("ERROR:No mesh objects found in file")
    sys.exit(1)

print("INFO:Found " + str(len(meshes)) + " mesh object(s)")

bpy.ops.object.select_all(action="DESELECT")
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()

# Apply scale so the exported geometry has correct world-space size
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

import math, mathutils
obj = bpy.context.view_layer.objects.active
if in_ext == ".blend":
    # Blender is Z-up; rotate -90 deg X to produce Y-up PLY output
    rot = mathutils.Matrix.Rotation(math.radians(-90), 4, "X")
    obj.data.transform(rot)
    obj.data.update()
elif in_ext == ".ply" and out_ext == ".abc":
    # PLY data is Y-up; rotate +90 deg X so Blender sees Z-up,
    # then alembic_export's own Z-up→Y-up conversion produces correct output
    rot = mathutils.Matrix.Rotation(math.radians(90), 4, "X")
    obj.data.transform(rot)
    obj.data.update()

try:
    if out_ext == ".ply":
        try:
            bpy.ops.wm.ply_export(
                filepath=output_file,
                export_selected_objects=True,
                export_normals=True,
                export_colors="NONE",
            )
        except (AttributeError, TypeError):
            bpy.ops.export_mesh.ply(filepath=output_file, use_normals=True)
    elif out_ext == ".abc":
        try:
            bpy.ops.wm.alembic_export(
                filepath=output_file,
                selected=True,
                flatten=True,
                export_normals=True,
            )
        except TypeError:
            bpy.ops.wm.alembic_export(
                filepath=output_file,
                selected=True,
                flatten=True,
            )
    print("SUCCESS:Exported to " + output_file)
except Exception as e:
    print("ERROR:Export failed: " + str(e))
    sys.exit(1)
"""


def _blender_convert(input_path, output_path, callback=None, label=None):
    """
    Use Blender headlessly to convert between 3D formats.
    Raises RuntimeError if Blender is not installed or conversion fails.
    """
    blender = find_blender()
    if not blender:
        raise RuntimeError(
            "Blender not found.\n"
            "Install Blender from https://www.blender.org/ or add it to PATH.\n"
            "Blender is required for .blend and .abc formats."
        )

    input_path  = Path(input_path)
    output_path = Path(output_path)

    script_fd, script_path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(script_fd, "w", encoding="utf-8") as sf:
            sf.write(_BLENDER_SCRIPT)

        if callback:
            callback(
                label or f"  Running Blender: {input_path.name} → {output_path.name}",
                progress=5,
            )

        result = subprocess.run(
            [blender, "--background", "--python", script_path,
             "--", str(input_path), str(output_path)],
            capture_output=True, text=True, timeout=300,
        )

        combined = result.stdout + "\n" + result.stderr
        for line in combined.splitlines():
            if line.startswith("ERROR:"):
                raise RuntimeError(line[6:].strip())

        if result.returncode not in (0, 1):
            tail = "\n".join(combined.splitlines()[-20:])
            raise RuntimeError(
                f"Blender exited with code {result.returncode}.\n{tail}"
            )

        if not output_path.exists():
            tail = "\n".join(combined.splitlines()[-20:])
            raise RuntimeError(f"Blender produced no output.\n{tail}")

        if callback:
            callback("  Blender conversion complete.", progress=30)

    finally:
        Path(script_path).unlink(missing_ok=True)

    return output_path


# ── PLY reader (original) ────────────────────────────────────────────────────

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
        if np.any(norms != 0):
            normals = norms
            if callback:
                callback("Loaded vertex normals")

    # --- Colors ---
    colors = None
    is_3dgs = False

    if "red" in props and "green" in props and "blue" in props:
        r = np.array(vertex_el["red"],   dtype=np.float32) / 255.0
        g = np.array(vertex_el["green"], dtype=np.float32) / 255.0
        b = np.array(vertex_el["blue"],  dtype=np.float32) / 255.0
        colors = np.column_stack([r, g, b])
        if callback:
            callback("Loaded vertex colors (RGB)")

    elif "f_dc_0" in props and "f_dc_1" in props and "f_dc_2" in props:
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
                faces = raw_faces
                n_faces = len(faces)
                if callback:
                    callback(f"Loaded {n_faces:,} polygon faces")

    return {
        "vertices":   vertices,
        "normals":    normals,
        "colors":     colors,
        "faces":      faces,
        "is_3dgs":    is_3dgs,
        "n_vertices": n_vertices,
        "n_faces":    n_faces,
    }


# ── New format readers ───────────────────────────────────────────────────────

def read_abc(filepath, callback=None):
    """Read Alembic .abc file via Blender → intermediate PLY."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_ply = Path(tmpdir) / "converted.ply"
        _blender_convert(filepath, tmp_ply, callback=callback,
                         label=f"  Reading {Path(filepath).name} via Blender...")
        return read_ply(tmp_ply, callback=callback)


def read_blend(filepath, callback=None):
    """Read Blender .blend file via Blender → intermediate PLY."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_ply = Path(tmpdir) / "converted.ply"
        _blender_convert(filepath, tmp_ply, callback=callback,
                         label=f"  Reading {Path(filepath).name} via Blender...")
        return read_ply(tmp_ply, callback=callback)


def _read_maya_ascii(filepath, callback=None):
    """
    Parse a Maya ASCII (.ma) file to extract vertices and polygon faces.
    Face topology is reconstructed from the edge table.
    Complex scenes or constraints may only yield vertex data.
    """
    if callback:
        callback(f"Parsing Maya ASCII: {filepath}")

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # ── Vertices ─────────────────────────────────────────────────────
    # setAttr [-s N] ".vt[0:M]" x0 y0 z0 ...;
    vt_re = re.compile(
        r'setAttr\s+(?:-s\s+\d+\s+)?"\.[^"]*vt\[[\d:]+\]"\s+'
        r'([\d\s.\-e+]+);',
        re.IGNORECASE,
    )
    all_verts = []
    for m in vt_re.finditer(content):
        nums = re.findall(r"-?[\d]+\.?[\d]*(?:[eE][+\-]?\d+)?", m.group(1))
        for i in range(0, len(nums) - 2, 3):
            try:
                all_verts.append(
                    [float(nums[i]), float(nums[i + 1]), float(nums[i + 2])]
                )
            except (ValueError, IndexError):
                break

    if not all_verts:
        raise RuntimeError(
            "No vertex data found in .ma file.\n"
            "Export the mesh to OBJ or FBX from Maya for reliable conversion."
        )

    # ── Edges (stride-3: v0, v1, smooth_flag) ────────────────────────
    # setAttr -s N ".ed[0:M]" v0 v1 s  v0 v1 s ...;
    ed_re = re.compile(
        r'setAttr\s+(?:-s\s+\d+\s+)?"\.[^"]*ed\[[\d:]+\]"\s+'
        r'([\d\s]+);',
        re.IGNORECASE,
    )
    edges = []
    for m in ed_re.finditer(content):
        nums = re.findall(r"\d+", m.group(1))
        for i in range(0, len(nums) - 2, 3):
            try:
                edges.append((int(nums[i]), int(nums[i + 1])))
            except (ValueError, IndexError):
                break

    # ── Faces (polyFaces) ─────────────────────────────────────────────
    # Convention: ei >= 0 → edge[ei][0];  ei < 0 → edge[-ei-1][1]
    fc_re = re.compile(
        r'setAttr\s+(?:-s\s+\d+\s+)?"\.[^"]*fc\[[\d:]+\]"\s+'
        r'-type\s+"polyFaces"\s+(.*?);',
        re.DOTALL | re.IGNORECASE,
    )
    all_faces = []
    for m in fc_re.finditer(content):
        block = m.group(1)
        for fm in re.finditer(r"\bf\s+(\d+)((?:\s+-?\d+)+)", block):
            n = int(fm.group(1))
            edge_idxs = [int(x) for x in fm.group(2).split()][:n]
            if not edges:
                all_faces.append(edge_idxs)
                continue
            verts = []
            valid = True
            for ei in edge_idxs:
                if ei >= 0:
                    if ei >= len(edges):
                        valid = False
                        break
                    verts.append(edges[ei][0])
                else:
                    idx = -ei - 1
                    if idx >= len(edges):
                        valid = False
                        break
                    verts.append(edges[idx][1])
            if valid and len(verts) >= 3:
                all_faces.append(verts)

    if callback:
        callback(
            f"Loaded {len(all_verts):,} vertices, "
            f"{len(all_faces):,} faces from Maya ASCII"
        )

    return {
        "vertices":   np.array(all_verts, dtype=np.float32),
        "normals":    None,
        "colors":     None,
        "faces":      all_faces or None,
        "is_3dgs":    False,
        "n_vertices": len(all_verts),
        "n_faces":    len(all_faces),
    }


def _read_obj_simple(filepath, callback=None):
    """Minimal Wavefront OBJ reader (geometry + normals only, no UVs/materials)."""
    if callback:
        callback(f"Reading OBJ: {filepath}")

    vertices = []
    normals  = []
    faces    = []

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("v "):
                parts = line.split()
                vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif line.startswith("vn "):
                parts = line.split()
                normals.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif line.startswith("f "):
                parts = line.split()[1:]
                idxs = []
                for p in parts:
                    vi = int(p.split("/")[0])
                    idxs.append(vi - 1 if vi > 0 else len(vertices) + vi)
                if len(idxs) >= 3:
                    faces.append(idxs)

    if not vertices:
        raise RuntimeError("No vertex data found in intermediate OBJ file.")

    if callback:
        callback(f"Loaded {len(vertices):,} vertices, {len(faces):,} faces")

    return {
        "vertices":   np.array(vertices, dtype=np.float32),
        "normals":    np.array(normals, dtype=np.float32) if normals else None,
        "colors":     None,
        "faces":      faces if faces else None,
        "is_3dgs":    False,
        "n_vertices": len(vertices),
        "n_faces":    len(faces),
    }


def read_maya(filepath, callback=None):
    """Read Maya .ma (ASCII parsed) or .mb (requires Maya or Blender FBX path)."""
    ext = Path(filepath).suffix.lower()
    if ext == ".ma":
        return _read_maya_ascii(filepath, callback=callback)

    # .mb is binary – need Maya
    maya = find_maya()
    if not maya:
        raise RuntimeError(
            "Maya Binary (.mb) requires Autodesk Maya to be installed.\n"
            "Open the file in Maya and export as .ma, .obj, or .fbx first."
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_obj = Path(tmpdir) / "converted.obj"
        if callback:
            callback("  Running Maya batch export...")
        fp = str(filepath).replace("\\", "/")
        tp = str(tmp_obj).replace("\\", "/")
        mel = (
            f'file -f -o "{fp}"; '
            f'file -force -type "OBJexport" -pr -ea "{tp}"; '
            f'quit -f;'
        )
        result = subprocess.run(
            [maya, "-batch", "-command", mel],
            capture_output=True, text=True, timeout=120,
        )
        if not tmp_obj.exists():
            raise RuntimeError(
                f"Maya export failed (exit {result.returncode}).\n"
                f"{result.stderr[-400:]}"
            )
        return _read_obj_simple(tmp_obj, callback=callback)


def read_max(filepath, callback=None):
    """Read 3ds Max .max file (requires 3ds Max to be installed)."""
    max_exe = find_3dsmax()
    if not max_exe:
        raise RuntimeError(
            "3ds Max .max files require Autodesk 3ds Max to be installed.\n"
            "Open in 3ds Max and export as .obj or .fbx first."
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_obj = Path(tmpdir) / "converted.obj"
        fp = str(filepath).replace("\\", "\\\\")
        tp = str(tmp_obj).replace("\\", "\\\\")
        script = (
            f'loadMaxFile @"{fp}" quiet:true; '
            f'exportFile @"{tp}" #noPrompt using:IOBJEXP; '
            f'quitMax #noPrompt'
        )
        if callback:
            callback("  Running 3ds Max export...")
        result = subprocess.run(
            [max_exe, "-q", "-silent", "-mxs", script],
            capture_output=True, text=True, timeout=180,
        )
        if not tmp_obj.exists():
            raise RuntimeError(
                f"3ds Max export failed (exit {result.returncode}).\n"
                "Tip: export manually as OBJ or FBX from 3ds Max."
            )
        return _read_obj_simple(tmp_obj, callback=callback)


def read_c4d(filepath, callback=None):
    """Read Cinema 4D .c4d file (requires Cinema 4D to be installed)."""
    c4d_exe = find_c4d()
    if not c4d_exe:
        raise RuntimeError(
            "Cinema 4D .c4d files require Maxon Cinema 4D to be installed.\n"
            "Open in Cinema 4D and export as .obj or .fbx first."
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_obj = Path(tmpdir) / "converted.obj"
        fp = str(filepath).replace("\\", "\\\\")
        tp = str(tmp_obj).replace("\\", "\\\\")
        c4d_py = (
            "import c4d\n"
            "def main():\n"
            f'    doc = c4d.documents.LoadDocument(r"{fp}",\n'
            "        c4d.SCENEFILTER_OBJECTS | c4d.SCENEFILTER_MATERIALS)\n"
            "    if not doc:\n"
            '        print("ERROR:Could not load document")\n'
            "        return\n"
            "    c4d.documents.InsertBaseDocument(doc)\n"
            "    c4d.documents.SetActiveDocument(doc)\n"
            "    c4d.documents.SaveDocument(\n"
            f'        doc, r"{tp}",\n'
            "        c4d.SAVEDOCUMENTFLAGS_DONTADDTORECENTLIST,\n"
            "        c4d.FORMAT_OBJ2EXPORT)\n"
            "main()\n"
        )
        script_fd, script_path = tempfile.mkstemp(suffix=".py")
        try:
            with os.fdopen(script_fd, "w", encoding="utf-8") as sf:
                sf.write(c4d_py)
            if callback:
                callback("  Running Cinema 4D export...")
            result = subprocess.run(
                [c4d_exe, "-nogui", "-python", script_path, str(filepath)],
                capture_output=True, text=True, timeout=180,
            )
        finally:
            Path(script_path).unlink(missing_ok=True)

        if not tmp_obj.exists():
            raise RuntimeError(
                f"Cinema 4D export failed (exit {result.returncode}).\n"
                "Tip: export manually as OBJ or FBX from Cinema 4D."
            )
        return _read_obj_simple(tmp_obj, callback=callback)


def read_file(filepath, callback=None):
    """Dispatch to the correct reader based on file extension."""
    ext = Path(filepath).suffix.lower()
    readers = {
        ".ply":   read_ply,
        ".abc":   read_abc,
        ".blend": read_blend,
        ".ma":    read_maya,
        ".mb":    read_maya,
        ".max":   read_max,
        ".c4d":   read_c4d,
    }
    if ext not in readers:
        raise ValueError(f"Unsupported input format: {ext}")
    return readers[ext](filepath, callback=callback)


# ── OBJ Export ───────────────────────────────────────────────────────────────

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
    CHUNK = 50_000

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# PolyPort – Wavefront OBJ\n")
        f.write(f"# Vertices: {n:,}\n")
        if has_faces:
            f.write(f"# Faces: {len(faces):,}\n")
        f.write(f"g {stem}\n\n")

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


# ── FBX ASCII 7.4.0 Export ───────────────────────────────────────────────────

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
        poly_indices = [-(i + 1) for i in range(n_verts)]
        if callback:
            callback("  Point cloud mode: generating point polygons", progress=10)

    verts_flat  = vertices.flatten().tolist()
    norms_flat  = normals.flatten().tolist() if has_normals else []
    if has_colors:
        rgba = np.hstack([colors, np.ones((len(colors), 1), dtype=np.float32)])
        colors_flat = rgba.flatten().tolist()
    else:
        colors_flat = []

    with open(output_path, "w", encoding="utf-8") as f:

        f.write("; FBX 7.4.0 project file\n")
        f.write("; Created by PolyPort\n")
        f.write("; ----------------------------------------------------\n\n")

        f.write("FBXHeaderExtension:  {\n")
        f.write("\tFBXHeaderVersion: 1003\n")
        f.write("\tFBXVersion: 7400\n")
        f.write('\tCreator: "PolyPort 1.0"\n')
        f.write("}\n\n")

        f.write("GlobalSettings:  {\n")
        f.write("\tVersion: 1000\n")
        f.write("\tProperties70:  {\n")
        f.write('\t\tP: "UpAxis", "int", "Integer", "",1\n')
        f.write('\t\tP: "UpAxisSign", "int", "Integer", "",1\n')
        f.write('\t\tP: "FrontAxis", "int", "Integer", "",2\n')
        f.write('\t\tP: "FrontAxisSign", "int", "Integer", "",1\n')
        f.write('\t\tP: "CoordAxis", "int", "Integer", "",0\n')
        f.write('\t\tP: "CoordAxisSign", "int", "Integer", "",1\n')
        f.write('\t\tP: "UnitScaleFactor", "double", "Number", "",100\n')
        f.write("\t}\n}\n\n")

        f.write("Documents:  {\n")
        f.write("\tCount: 1\n")
        f.write('\tDocument: 999999999, "", "Scene" {\n')
        f.write("\t\tRootNode: 0\n")
        f.write("\t}\n}\n\n")

        f.write("References:  {\n}\n\n")

        f.write("Definitions:  {\n")
        f.write("\tVersion: 100\n")
        f.write("\tCount: 2\n")
        f.write('\tObjectType: "Model" {\n\t\tCount: 1\n\t}\n')
        f.write('\tObjectType: "Geometry" {\n\t\tCount: 1\n\t}\n')
        f.write("}\n\n")

        if callback:
            callback("  Header written", progress=15)

        f.write("Objects:  {\n")

        f.write(f'\tGeometry: {_GEOM_ID}, "Geometry::{stem}", "Mesh" {{\n')
        f.write("\t\tGeometryVersion: 124\n")

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

        f.write('\t}\n')

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

        f.write("}\n\n")

        f.write("Connections:  {\n")
        f.write(f"\tC: \"OO\",{_GEOM_ID},{_MODEL_ID}\n")
        f.write(f"\tC: \"OO\",{_MODEL_ID},0\n")
        f.write("}\n")

    if callback:
        size_mb = Path(output_path).stat().st_size / 1_048_576
        callback(f"FBX saved ({size_mb:.1f} MB)", progress=100)

    return output_path


# ── Alembic Export ───────────────────────────────────────────────────────────

def _write_ply_temp(data, output_path):
    """Write a temporary PLY from mesh data, used as Blender input for ABC export."""
    from plyfile import PlyData, PlyElement

    vertices = data["vertices"]
    normals  = data["normals"]
    faces    = data["faces"]
    n = len(vertices)

    if normals is not None:
        verts_np = np.zeros(n, dtype=[
            ("x", "f4"), ("y", "f4"), ("z", "f4"),
            ("nx", "f4"), ("ny", "f4"), ("nz", "f4"),
        ])
        verts_np["nx"] = normals[:, 0]
        verts_np["ny"] = normals[:, 1]
        verts_np["nz"] = normals[:, 2]
    else:
        verts_np = np.zeros(n, dtype=[
            ("x", "f4"), ("y", "f4"), ("z", "f4"),
        ])

    verts_np["x"] = vertices[:, 0]
    verts_np["y"] = vertices[:, 1]
    verts_np["z"] = vertices[:, 2]

    elements = [PlyElement.describe(verts_np, "vertex")]

    if faces is not None and len(faces) > 0:
        faces_list = faces if isinstance(faces, list) else faces.tolist()
        face_dtype = np.dtype([("vertex_indices", "O")])
        face_np = np.empty(len(faces_list), dtype=face_dtype)
        for i, face in enumerate(faces_list):
            face_np[i] = (np.array(face, dtype=np.int32),)
        elements.append(PlyElement.describe(face_np, "face"))

    PlyData(elements).write(str(output_path))


def export_abc(data, output_path, callback=None):
    """
    Export mesh/point-cloud data to Alembic .abc via Blender subprocess.
    Requires Blender to be installed.
    """
    blender = find_blender()
    if not blender:
        raise RuntimeError(
            "Alembic (.abc) export requires Blender to be installed.\n"
            "Download from https://www.blender.org/ and add to PATH."
        )

    if callback:
        callback(f"Writing ABC: {output_path}", progress=5)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_ply = Path(tmpdir) / "temp_mesh.ply"

        if callback:
            callback("  Preparing intermediate PLY...", progress=10)
        _write_ply_temp(data, tmp_ply)

        _blender_convert(tmp_ply, Path(output_path), callback=callback)

    if callback:
        size_mb = Path(output_path).stat().st_size / 1_048_576
        callback(f"ABC saved ({size_mb:.1f} MB)", progress=100)

    return output_path


# ── Unified entry point ───────────────────────────────────────────────────────

class PLYConverter:
    def __init__(self, callback=None):
        self._raw_callback = callback

    def _cb(self, msg, progress=None):
        if self._raw_callback:
            self._raw_callback(msg, progress=progress)

    def convert(self, input_path, output_dir, fmt):
        """Convert a 3D file to OBJ, FBX, or ABC. Returns output path string."""
        fmt = fmt.lower().strip()
        if fmt not in ("obj", "fbx", "abc"):
            raise ValueError(f"Unsupported output format: {fmt}")

        input_path = Path(input_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{input_path.stem}.{fmt}"

        data = read_file(input_path, callback=self._cb)
        self._cb(
            f"File info: {data['n_vertices']:,} vertices, "
            f"{data['n_faces']:,} faces, "
            f"colors={'yes' if data['colors'] is not None else 'no'}, "
            f"normals={'yes' if data['normals'] is not None else 'no'}"
        )

        if fmt == "obj":
            export_obj(data, output_path, callback=self._cb)
        elif fmt == "fbx":
            export_fbx(data, output_path, callback=self._cb)
        else:
            export_abc(data, output_path, callback=self._cb)

        return str(output_path)
