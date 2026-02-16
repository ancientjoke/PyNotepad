
<div align="center">

# Notepad+++

<img style="width: 25%; aspect-ratio: 1" src="./notepadplusplusplus.png">
</div>

<br/>
<br/>
<br/>

.pdf annotation app built with Python + PyQt6.

## Windowns Installation 1/2

---

1. **Create & activate venv**

	```powershell
	python -m venv .venv
	.\.venv\Scripts\Activate.ps1

  	# If PowerShell blocks scripts, run:
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

2. **Build the executable app**

	```powershell
	pyinstaller --noconfirm --onefile --windowed --name "Notepad+++" --icon notepadplusplusplus.ico main.py
	```

	- Output: `dist\Notepad+++.exe`
	- If the icon does not show, ensure notepadplusplusplus.ico is valid and in the project root, alternatively whatever .ico image u choose
	- `--windowed` removes the console window; omit it for debug output, if choosing to modify the app

3. **Run the app**
	located in dist folder as .exe file, pin to taskbar
	```powershell
	.\dist\Notepad+++.exe
	```
---

## Mac Installation 2/2

---

1. **Create & activate venv**

	```bash
	python3 -m venv .venv
	source .venv/bin/activate
	```

2. **Install dependencies**

	```bash
	pip install -r requirements.txt
	```

3. **Run the app**

	```bash
	python3 main.py
	```

---

## Build a Standalone .app

1. **Install PyInstaller and Pillow**

	```bash
	pip install pyinstaller pillow
	```

2. **Build the app bundle**

	```bash
	pyinstaller --noconfirm --onefile --windowed --name "Notepad+++" --icon notepadplusplusplus.icns main.py
	```
	- For a proper Mac icon, use a `.icns` file. Convert your icon if needed with `iconutil` or online tools
	- `--windowed` removes the terminal window , omit for debug output

3. **Run the app**

	located in dist folder as Notepad+++ file, pin to taskbar
	```bash
	./dist/Notepad+++
	```
 
---

## Preview

windows preview
<div align="center">
	<img width="1442" height="951" alt="image" src="https://github.com/user-attachments/assets/4b27dd3a-de4e-466d-8f27-efeda08316b8" />
	<img width="1405" height="934" alt="image" src="https://github.com/user-attachments/assets/f2dbcb58-1163-47f7-85a3-5be9cccbd54d" />
	<img width="1404" height="932" alt="image" src="https://github.com/user-attachments/assets/984e08cb-4c75-4141-879c-bc51bf674d3a" />
</div>

mac preview
<div align="center">
	...
</div>

---

## todo:
	- allow for inapp modifications to app layout
	- add written notes + coding indentations options
	- etc etc.
