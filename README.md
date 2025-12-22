# Patcher

This patcher allows you to more easily prepare an environment for exploring the Hytale Server without publishing the decompiled code.




## Setup

* Clone this repository and `cd` into it.

* Create a Python virtual environment in the `.venv` folder. The command for this varies by platform but it is probably 
one of these: 
  - `python -m venv .venv`
  - `python3 -m venv .venv` (Linux)
  - `py -3.13 -m venv .venv` (Windows)  

  In the last one, specifying the version is recommended if you have multiple Pythons installed.

* Activate the virtual environment:
  - Windows: `".venv\Scripts\activate"`  (including the quotes)
  - Linux/Mac: `source .venv/bin/activate`

* Install these dependencies and ensure they are on PATH:
  - `git`
  - `java` you need JDK 25 or newer
  - `jar` (comes with JDK inside the bin folder)
  - `mvn`
## Usage

All commands should be ran from inside the venv, hence `python` is the right command to invoke python.

First run this:
```shell
python run.py setup
```
It will
- download the ~~Hytale server jar~~ (currently it's a placeholder jar for playing around) into `work/download`
- decompile it using Fernflower and save the output to `work/decompile`
- set up a Maven project in `hytale-server` with the decompiled code

You can then open the `hytale-server` folder in your favorite IDE and begin exploring the code. For *IntelliJ IDEA*,
you must first setup the SDK. After opening the project (you can open the `pom.xml` file, IDEA will prompt you to open
the entire project) press Ctrl+Alt+Shift+S and under _Project_ configure SDK and Language level to *25*.


This decompiled code is likely broken. To apply existing patches:
```shell
python run.py applySourcePatches
```
It reads the patches from `src-patches` folder and applies them to corresponding decompiled source files.

_If you are reading this too soon, we may not have created those patches yet. Please wait until then, do not
contribute that yourself, as crowdsourcing this part will be strenuous. More importantly, do not blindly have a LLM
fix the code for you, the result may be even worse._

When you made some changes, you can rebuild patches by running:
```shell
python run.py makeSourcePatches
```
This will modify the patch files inside the `src-patches` folder to reflect your local changes. Keep in mind that we 
have not intended this to be a collaborative project, so please be careful when combining multiple patches. There is 
also some leftover code about feature patches, but those should not be used at the moment.

Should there be any issues with these scripts when Hytale drops, we will make sure to address them as soon as possible.