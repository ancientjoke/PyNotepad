
<div align="center">

# Notepad+++

<img style="width: 25%; aspect-ratio: 1" src="goose.png">
</div>

<br/>
<br/>
<br/>

.pdf annotation app built with Python + PyQt6.


1) Create & activate venv

```powershell
python -m venv .venv
# PowerShell activation
.\.venv\Scripts\Activate.ps1
# If PowerShell blocks scripts, run (one time):
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

2) Install dependencies

```powershell
pip install -r requirements.txt
```

3) Run the app

```powershell
python main.py
```

## Build a standalone .exe app

1) Install PyInstaller

```powershell
pip install pyinstaller
```

2) Create windowed executable

```powershell
pyinstaller --noconfirm --onefile --windowed --name "Notepad+++" main.py
```

- Output will be in `dist\Notepad+++\Notepad+++ .exe` 
- `--windowed` removes the console window; omit it if you want stdout/stderr

2.1) app icon

```powershell
pyinstaller --onefile --windowed --name "Notepad+++" --icon path\to\app.ico main.py
```

<img width="1442" height="951" alt="image" src="https://github.com/user-attachments/assets/4b27dd3a-de4e-466d-8f27-efeda08316b8" />

preview
