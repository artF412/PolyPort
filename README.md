# PolyPort

**3D File Format Converter — PLY → OBJ / FBX**

PolyPort is a lightweight desktop application for converting 3D files between formats, designed to fit seamlessly into Maya and Blender workflows.

---

## Features

- **PLY → OBJ** — Wavefront Object with vertex colors (`v x y z r g b`), compatible with Blender, Maya, and MeshLab
- **PLY → FBX** — ASCII FBX 7.4.0 with vertex colors and normals, compatible with Maya and Blender
- **3D Gaussian Splatting support** — automatically detects 3DGS PLY files and converts Spherical Harmonic (SH) DC coefficients to RGB vertex colors
- **Standard mesh support** — handles meshes with faces, normals, and `uint8` vertex colors
- **Point cloud support** — exports point-only PLY files (no faces)
- **Real-time progress bar and log** — see exactly what is happening during conversion
- **Dark-themed GUI** — clean interface built with Python `tkinter`, no additional UI frameworks required

---

## Screenshots

> *Coming soon*

---

## Requirements

- Python 3.10 or newer
- `numpy`
- `plyfile`

Install dependencies:

```bash
pip install numpy plyfile
```

---

## Usage

```bash
python main.py
```

1. Click **Browse…** next to *Input PLY File* and select your `.ply` file
2. Choose an output directory (defaults to the same folder as the input)
3. Select the export format: **OBJ** or **FBX**
4. Click **Convert & Export**

---

## Supported Input Formats

| Source | Format | Notes |
|--------|--------|-------|
| Standard 3D software | `.ply` mesh | Triangles, quads, polygons |
| 3D Gaussian Splatting | `.ply` (3DGS) | SH coefficients auto-converted to RGB |
| Point cloud tools | `.ply` point cloud | Exported without faces |

---

## Output Formats

| Format | Extension | Colors | Normals | Faces |
|--------|-----------|--------|---------|-------|
| Wavefront OBJ | `.obj` | Yes (extended `v x y z r g b`) | Yes (`vn`) | Yes |
| FBX ASCII 7.4.0 | `.fbx` | Yes (RGBA layer) | Yes (layer) | Yes |

---

## Project Structure

```
PolyPort/
├── main.py          # GUI entry point (tkinter)
├── converter.py     # Conversion logic (read PLY, write OBJ/FBX)
├── requirements.txt
├── LICENSE
└── README.md
```

---

## Roadmap

- [ ] Batch conversion (multiple files at once)
- [ ] More input formats (`.e57`, `.xyz`, `.glb`, `.gltf`)
- [ ] More output formats (`.usd`, `.abc` Alembic)
- [ ] Standalone executable (PyInstaller)
- [ ] Mesh reconstruction from point clouds

---

## License

MIT License — see [LICENSE](LICENSE) for details.
Free to use, modify, and distribute.

---

---

# PolyPort (ภาษาไทย)

**โปรแกรมแปลงไฟล์ 3D — PLY → OBJ / FBX**

PolyPort คือแอปพลิเคชัน Desktop สำหรับแปลงไฟล์ 3D ระหว่างฟอร์แมต ออกแบบมาให้ใช้งานร่วมกับ Maya และ Blender ได้ทันที

---

## ฟีเจอร์หลัก

- **PLY → OBJ** — รูปแบบ Wavefront Object พร้อม vertex colors รองรับ Blender, Maya และ MeshLab
- **PLY → FBX** — ASCII FBX 7.4.0 พร้อม vertex colors และ normals รองรับ Maya และ Blender
- **รองรับ 3D Gaussian Splatting** — ตรวจจับไฟล์ 3DGS อัตโนมัติ แล้วแปลง Spherical Harmonic (SH) coefficients เป็นสี RGB
- **รองรับ mesh ทั่วไป** — รองรับ mesh ที่มี faces, normals และ vertex colors แบบ `uint8`
- **รองรับ point cloud** — export ไฟล์ point-only ได้โดยไม่มี faces
- **Progress bar และ log แบบ real-time** — ติดตามความคืบหน้าระหว่างแปลงไฟล์
- **GUI โทนสีเข้ม** — ใช้ `tkinter` ในตัว ไม่ต้องติดตั้ง UI framework เพิ่ม

---

## ความต้องการของระบบ

- Python 3.10 ขึ้นไป
- `numpy`
- `plyfile`

ติดตั้ง dependencies:

```bash
pip install numpy plyfile
```

---

## วิธีใช้งาน

```bash
python main.py
```

1. กด **Browse…** ถัดจาก *Input PLY File* แล้วเลือกไฟล์ `.ply`
2. เลือก output directory (ค่าเริ่มต้นคือโฟลเดอร์เดียวกับไฟล์ input)
3. เลือกฟอร์แมตที่ต้องการ: **OBJ** หรือ **FBX**
4. กด **Convert & Export**

---

## License

MIT License — ดูรายละเอียดใน [LICENSE](LICENSE)
ใช้งาน ดัดแปลง และแจกจ่ายต่อได้อย่างอิสระ
