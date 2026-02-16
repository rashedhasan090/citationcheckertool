# Citation Checker

Validate citations from papers: check **DOI**, **URL**, **year**, and **author**; detect **suspected fake citations**; get **fix suggestions**. Supports **BibTeX**, **APA**, and unformatted pasted text.

## Features

- **Fake citation detection** — DOI validated against [CrossRef](https://www.crossref.org/); unresolved DOIs flagged as suspected fakes
- **Validation** — DOI, URL (accessibility), publication year, author(s)
- **Fix suggestions** — Actionable suggestions for each issue
- **Format support** — Paste from your paper: **BibTeX**, **APA**, or plain (one per line / numbered)
- **Status display** — Valid / Warning / Suspected fake per citation
- **Export report** — JSON, CSV, or PDF

## Install

```bash
cd citation_checker
pip install -r requirements.txt
```

## Usage

### 1. Python CLI

```bash
# Paste citations (then Ctrl+D / Ctrl+Z to finish)
python cli.py

# From file
python cli.py references.txt

# Export report
python cli.py references.txt -o report.json
python cli.py references.txt -o report.csv
python cli.py references.txt -o report.pdf

# Skip network checks (faster)
python cli.py references.txt --no-doi-check --no-url-check
```

### 2. Desktop GUI (Tkinter)

```bash
python gui_desktop.py
```

Paste citations, click **Check citations**, then **Export report…** to save JSON/CSV/PDF.

### 3. Web app (Streamlit) — local

```bash
streamlit run app.py
```

Open the URL shown in the terminal (e.g. http://localhost:8501).

## Deploy live (free hosting)

### Option A: Streamlit Community Cloud (recommended)

1. **Push this project to GitHub**
   - Create a new repo, e.g. `citation-checker`.
   - Push the contents of the `citation_checker` folder (so that `app.py` and `requirements.txt` are in the repo root, or keep the structure and set the app path in Streamlit Cloud).

2. **Connect to [share.streamlit.io](https://share.streamlit.io)**
   - Sign in with GitHub.
   - **New app** → choose your repo, branch, and set **Main file path** to `app.py` (if `app.py` is in root) or `citation_checker/app.py` if you kept the full repo layout.
   - Set **Working directory** to the folder that contains `app.py` and `requirements.txt` if needed (e.g. `citation_checker`).
   - Deploy. Your app will be live at `https://<your-app>.streamlit.app`.

3. **Repo layout for Streamlit Cloud**
   - Easiest: repo root = this folder, so root has `app.py`, `requirements.txt`, and the `citation_checker` package folder. Then Main file path = `app.py`, no working dir.

### Option B: Render / Railway / Hugging Face Spaces

- **Render**: New Web Service → connect repo → build command `pip install -r requirements.txt`, start command `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`.
- **Hugging Face Spaces**: Create a Space with Streamlit SDK, add `app.py` and `requirements.txt`, then copy the Streamlit app code into the Space’s `app.py`.

## Example input

**BibTeX:**
```bibtex
@article{smith2020,
  author = {Smith, J. and Doe, A.},
  title = {A great paper},
  year = {2020},
  doi = {10.1234/example.2020}
}
```

**APA-style (pasted from paper):**
```
Smith, J., & Doe, A. (2020). A great paper. Journal Name, 1(2), 10–20. https://doi.org/10.1234/example.2020
```

**Unformatted (one per line or numbered):**
```
1. Smith J, Doe A. A great paper. 2020. doi:10.1234/example.2020
2. Another reference (2021). https://example.com/paper
```

## License

MIT.
