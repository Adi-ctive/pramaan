# realdata/ (private, never committed)

Real documents and photos from our own college, used with permission to see how PRAMAAN does on real files.
Everything in this folder except this README and truth.example.csv is ignored by git and by Vercel.
Scoring runs only on this laptop with an in-memory store. Nothing is sent to MongoDB Atlas, Vercel or any hosted AI.

## Before you add a file
- Get permission from whoever owns the document.
- Mask personal IDs (Aadhaar, PAN), phone numbers and personal addresses. Black boxes are fine.
- Name files plainly: `fire_noc.pdf`, `lab1_photo1.jpg`, `ground_floor_plan.pdf`.

## The truth sheet: truth.csv
Copy `truth.example.csv` to `truth.csv` and add one row per fact you know is true. Columns:

| column | meaning |
|---|---|
| file | file name inside realdata/ |
| doc_type | FIRE_NOC, SOCIETY_REG, LAND_LEASE, BUILDING_COMPLETION, AFFIDAVIT_GENERAL, ACCREDITATION, FEE_RECEIPT, FACULTY_LIST, FLOOR_PLAN or INFRA_PHOTOS |
| field | what the row checks (list below) |
| expected | the true value |
| note | anything useful (optional) |

Fields you can check:
- `doc_type`: does PRAMAAN recognise the document type? (expected = the type)
- any field from the rule pack: `ref_no`, `issued_on`, `valid_to`, `addressee`, `society_name`, `lessee`, `owner`, `institution`, `programme`, `amount`, `payer`, `deponent`
  (dates as DD-MM-YYYY, amounts as plain numbers)
- `computer_count` on a photo: how many computers/monitors are visible
- `area:<ROOM>` on a floor plan, for example `area:COMPUTER_LAB_1`, in square metres
- `expect_flag`: a finding you expect, for example `DOC_EXPIRED` (expected = the code)

## Run it
```bash
python tasks.py eval-real              # CPU checks
set MODE=FULL && python tasks.py eval-real   # adds OCR, handwriting, detector on the GPU
```
The report goes to `docs/EVAL-REAL.md` (also ignored by git).
