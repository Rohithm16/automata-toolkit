python -m venv .venv
.venv\Scripts\Activate.ps1
cd automata_toolkit
python -m pip install -r requirements.txt
python -m uvicorn automata_toolkit.app:app --reload
