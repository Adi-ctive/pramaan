# Large public-dataset evaluation

Mode LITE, run 25 Oct 2026, 7,747 real files in total. Fetched by scripts/fetch_public_data.py, kept in realdata/public/ (gitignored).
Tamper rule is the engine's: TAMPER_INDICATOR when the noise residual is suspicious, ELA and copy-move run when the noise score is borderline.

## RVL-CDIP: 5,334 real scanned documents, 16 types, none tampered

- Tamper flags raised on genuine scans: 5,334 (100.0% false-alarm rate).
- Forensics time: 276.2 ms per document per CPU worker (6 workers).

| Type | Docs | Flagged | Rate |
|---|---|---|---|
| email | 2202 | 2202 | 100.0% |
| file folder | 2527 | 2527 | 100.0% |
| form | 605 | 605 | 100.0% |

## SROIE and T-SROIE: real receipts, genuine and with tampered text

- Files: 973 genuine, 986 tampered.
- Tamper indicator: precision 50.8%, recall 75.9%, F1 0.609, false-alarm rate on genuine 74.3%.
- Receipt dates our date parser understands: 725 of 973.

## SIFTA: real and forged document images

- Files: 96 genuine, 96 tampered.
- Tamper indicator: precision 61.9%, recall 76.0%, F1 0.682, false-alarm rate on genuine 46.9%.

## CubiCasa5K: 262 real floor plans

- Room recall 22.2%, precision 51.6% (1,443 found, 3,325 true). Rooms matched by box overlap (IoU >= 0.5). No scale in these images, so areas in m² are not measured.

## Licences

RVL-CDIP (IIT-CDIP / UCSF terms), SROIE (ICDAR 2019), T-SROIE (MIT), SIFTA (Hugging Face, no licence stated), photo forgery set (Apache-2.0 tag; CASIA, COCO and Paris sources), MIT Indoor 67, CubiCasa5K, IIIT-HW-Dev: research use, cited, never redistributed.
