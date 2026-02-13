
<div align="center">

# Notepad+++

<img style="width: 25%; aspect-ratio: 1" src="goose.png">
</div>

<br/>
<br/>
<br/>

.pdf annotation app built with Python + PyQt6.

1. **Create & activate venv**

	```powershell
	python -m venv .venv
	.\.venv\Scripts\Activate.ps1
	# If PowerShell blocks scripts, run (one time):
	# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
	```

2. **Install dependencies**

	```powershell
	pip install -r requirements.txt
	```

3. **Run the app**

	```powershell
	python main.py
	```

---

## Build a Standalone .exe App

1. **Install PyInstaller and Pillow**

	```powershell
	pip install pyinstaller pillow
	```

2. **Convert your PNG icon to .ico**     OPTIONAL: preview image exists; goose.png

	Place your png (eg; `goose.png`) in the project root. Then run:

	```powershell
	python convert_to_ico.py
	# This creates goose.ico with all required sizes
	```

3. **Build the executable app**

	```powershell
	pyinstaller --noconfirm --onefile --windowed --name "Notepad+++" --icon goose.ico main.py
	```

	- Output: `dist\Notepad+++.exe`
	- If the icon does not show, ensure goose.ico is valid and in the project root
	- `--windowed` removes the console window; omit it for debug output

4. **Run the app**

	```powershell
	.\dist\Notepad+++.exe
	```

---

<img width="1442" height="951" alt="image" src="https://github.com/user-attachments/assets/4b27dd3a-de4e-466d-8f27-efeda08316b8" />

preview

