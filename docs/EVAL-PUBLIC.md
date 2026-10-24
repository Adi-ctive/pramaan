# Public-dataset evaluation (FULL mode)

Run took 174 s. Subsets fetched by scripts/fetch_public_data.py.

| Dataset | What it tests | Result |
|---|---|---|
| MIT Indoor 67 (360 real photos) | room type from a photo | 87.5% correct over 6 room types; 'computer lab' precision 79.1%, recall 88.3% |
| CubiCasa5K (60 real floor plans) | finding rooms on raster plans | room recall 22.8%, precision 54.3% (357 found, 833 true) |
| IIIT-HW-Dev (0 handwritten Hindi words) | reading Hindi handwriting | CER n/a, exact n/a (Hindi OCR Model (printed-text model, no Hindi handwriting model)) |

## Room-type confusion (true -> predicted)

- classroom -> classroom: 58
- classroom -> meeting room: 2
- computer lab -> classroom: 6
- computer lab -> computer lab: 53
- computer lab -> meeting room: 1
- corridor -> corridor: 56
- corridor -> library: 1
- corridor -> meeting room: 3
- library -> classroom: 2
- library -> computer lab: 2
- library -> library: 55
- library -> office: 1
- meeting room -> classroom: 1
- meeting room -> meeting room: 59
- office -> classroom: 4
- office -> computer lab: 12
- office -> library: 1
- office -> meeting room: 9
- office -> office: 34

Rooms matched by box overlap (IoU >= 0.5). No scale in these images, so areas in m² are not measured.

Licences: MIT Indoor 67 mirror (Voxel51) tagged MIT; CubiCasa5K and IIIT-HW-Dev for research use, cite the papers. Data stays in realdata/public/.
