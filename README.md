# PolyPort

**3D File Format Converter — Multi-format → OBJ / FBX / ABC**

PolyPort is a lightweight desktop application for converting 3D files between formats, designed to fit seamlessly into Maya and Blender workflows.

---

## Features

- **Multi-format input** — PLY, Alembic (.abc), Blender (.blend), Maya (.ma/.mb), 3ds Max (.max), Cinema 4D (.c4d)
- **Three output formats** — OBJ, FBX (ASCII 7.4.0), Alembic (.abc)
- **3D Gaussian Splatting support** — automatically detects 3DGS PLY files and converts Spherical Harmonic (SH) DC coefficients to RGB vertex colors
- **Standard mesh support** — handles meshes with faces, normals, and vertex colors
- **Point cloud support** — exports point-only files (no faces)
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

### Optional: Blender

[Blender](https://www.blender.org/) is required for:
- Reading `.blend` and `.abc` files
- Exporting to `.abc` (Alembic)

Blender is detected automatically if installed. No extra Python packages needed.

### Optional: Autodesk Maya / 3ds Max / Cinema 4D

Reading `.mb`, `.max`, and `.c4d` files requires the respective application to be installed. `.ma` files are parsed directly without Maya.

---

## Usage

```bash
python main.py
```

1. Click **Browse…** next to *Input File* and select your 3D file
2. Choose an output directory (defaults to the same folder as the input)
3. Select the export format: **OBJ**, **FBX**, or **ABC**
4. Click **Convert & Export**

---

## Supported Input Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| PLY mesh | `.ply` | Triangles, quads, polygons |
| PLY 3DGS | `.ply` (3DGS) | SH coefficients auto-converted to RGB |
| PLY point cloud | `.ply` | Exported without faces |
| Alembic | `.abc` | Requires Blender |
| Blender | `.blend` | Requires Blender |
| Maya ASCII | `.ma` | Parsed directly, no Maya required |
| Maya Binary | `.mb` | Requires Autodesk Maya |
| 3ds Max | `.max` | Requires Autodesk 3ds Max |
| Cinema 4D | `.c4d` | Requires Maxon Cinema 4D |

---

## Output Formats

| Format | Extension | Colors | Normals | Faces | Notes |
|--------|-----------|--------|---------|-------|-------|
| Wavefront OBJ | `.obj` | Yes | Yes | Yes | Extended `v x y z r g b` |
| FBX ASCII 7.4.0 | `.fbx` | Yes | Yes | Yes | Compatible with Maya & Blender |
| Alembic | `.abc` | No | Yes | Yes | Requires Blender |

---

## Project Structure

```
PolyPort/
├── main.py          # GUI entry point (tkinter)
├── converter.py     # Conversion logic (read + write all formats)
├── requirements.txt
├── LICENSE
└── README.md
```

---

## Roadmap

- [ ] Batch conversion (multiple files at once)
- [ ] More output formats (`.usd`, `.glb`)
- [ ] Standalone executable (PyInstaller)
- [ ] Mesh reconstruction from point clouds

---

## License

MIT License — see [LICENSE](LICENSE) for details.
Free to use, modify, and distribute.

---

---

# PolyPort (ภาษาไทย)

**โปรแกรมแปลงไฟล์ 3D — หลายฟอร์แมต → OBJ / FBX / ABC**

PolyPort คือแอปพลิเคชัน Desktop สำหรับแปลงไฟล์ 3D ระหว่างฟอร์แมต ออกแบบมาให้ใช้งานร่วมกับ Maya และ Blender ได้ทันที

---

## ฟีเจอร์หลัก

- **รองรับหลาย input format** — PLY, Alembic (.abc), Blender (.blend), Maya (.ma/.mb), 3ds Max (.max), Cinema 4D (.c4d)
- **3 output format** — OBJ, FBX (ASCII 7.4.0), Alembic (.abc)
- **รองรับ 3D Gaussian Splatting** — ตรวจจับไฟล์ 3DGS อัตโนมัติ แล้วแปลง Spherical Harmonic (SH) coefficients เป็นสี RGB
- **รองรับ mesh ทั่วไป** — รองรับ mesh ที่มี faces, normals และ vertex colors
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

### ตัวเลือกเสริม: Blender

[Blender](https://www.blender.org/) จำเป็นสำหรับ:
- อ่านไฟล์ `.blend` และ `.abc`
- Export เป็น `.abc` (Alembic)

ตรวจจับ Blender อัตโนมัติหากติดตั้งไว้แล้ว ไม่ต้องติดตั้ง Python package เพิ่มเติม

### ตัวเลือกเสริม: Autodesk Maya / 3ds Max / Cinema 4D

การอ่านไฟล์ `.mb`, `.max` และ `.c4d` ต้องติดตั้งโปรแกรมนั้นๆ ไว้ก่อน (ยกเว้น `.ma` ที่อ่านได้โดยตรง)

---

## วิธีใช้งาน

```bash
python main.py
```

1. กด **Browse…** ถัดจาก *Input File* แล้วเลือกไฟล์ 3D
2. เลือก output directory (ค่าเริ่มต้นคือโฟลเดอร์เดียวกับไฟล์ input)
3. เลือกฟอร์แมตที่ต้องการ: **OBJ**, **FBX** หรือ **ABC**
4. กด **Convert & Export**

---

## License

MIT License — ดูรายละเอียดใน [LICENSE](LICENSE)
ใช้งาน ดัดแปลง และแจกจ่ายต่อได้อย่างอิสระ
