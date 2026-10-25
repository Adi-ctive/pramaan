# Large public-dataset evaluation

Mode FULL, run 25 Oct 2026, 8,013 real files in total. Fetched by scripts/fetch_public_data.py, kept in realdata/public/ (gitignored).
Tamper rule is the engine's: TAMPER_INDICATOR when the noise residual is suspicious, ELA and copy-move run when the noise score is borderline.

## RVL-CDIP: 5,600 real scanned documents, 16 types, none tampered

- Tamper flags raised on genuine scans: 1,425 (25.4% false-alarm rate).
- Forensics time: 178.5 ms per document per CPU worker (6 workers).

| Type | Docs | Flagged | Rate |
|---|---|---|---|
| advertisement | 350 | 162 | 46.3% |
| budget | 350 | 66 | 18.9% |
| email | 350 | 25 | 7.1% |
| file folder | 350 | 114 | 32.6% |
| form | 350 | 90 | 25.7% |
| handwritten | 350 | 193 | 55.1% |
| invoice | 350 | 125 | 35.7% |
| letter | 350 | 84 | 24.0% |
| memo | 350 | 64 | 18.3% |
| news article | 350 | 98 | 28.0% |
| presentation | 350 | 44 | 12.6% |
| questionnaire | 350 | 83 | 23.7% |
| resume | 350 | 24 | 6.9% |
| scientific publication | 350 | 58 | 16.6% |
| scientific report | 350 | 97 | 27.7% |
| specification | 350 | 98 | 28.0% |

OCR Model on 1,000 pages: 277.4 ms per page, 114.7 words per page, 24 pages with no text read. RVL-CDIP has no text truth, so this is throughput and coverage only.

## SROIE and T-SROIE: real receipts, genuine and with tampered text

- Files: 973 genuine, 986 tampered.
- Tamper indicator: precision 50.8%, recall 75.9%, F1 0.609, false-alarm rate on genuine 74.3%.
- Receipt dates our date parser understands: 968 of 973.
- OCR Model on 973 genuine receipts: total read 98.2%, date read 95.3%, company name CER 17.0%, 352.0 ms per receipt.

## SIFTA: real and forged document images

- Files: 96 genuine, 96 tampered.
- Tamper indicator: precision 61.9%, recall 76.0%, F1 0.682, false-alarm rate on genuine 46.9%.

## CubiCasa5K: 262 real floor plans

- Room recall 22.2%, precision 51.6% (1,443 found, 3,325 true). Rooms matched by box overlap (IoU >= 0.5). No scale in these images, so areas in m² are not measured.

## Licences

RVL-CDIP (IIT-CDIP / UCSF terms), SROIE (ICDAR 2019), T-SROIE (MIT), SIFTA (Hugging Face, no licence stated), photo forgery set (Apache-2.0 tag; CASIA, COCO and Paris sources), MIT Indoor 67, CubiCasa5K, IIIT-HW-Dev: research use, cited, never redistributed.
