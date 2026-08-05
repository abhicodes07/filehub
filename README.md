<div align="center">
  <img src="assets/filehub.png"/>
</div>

## Introduction

The **filehub** is a asynchronous CLI designed for browsing a Github repo, pick files with an interactive `fzf` menu, and download them with concurrent streaming. This is very useful if you have a low bandwidth network or only need a particular file or subdirectory from a large repository. You can also download a whole repository however, it is recommended to use the `git clone` method.

## Features

- Interactive file selection using fzf
- Asynchronous / concurrent downloads for speed
- Supports specifiying repositories by owner/repo or Github URL

## Requirements

- Python 3.8+
- pip
- fzf (command-line fuzzy finder)
  - macOS: `brew install fzf`
  - Debian/Ubuntu: `sudo apt install fzf`

## Basic Usage

```bash
Usage: filehub [OPTIONS] COMMAND [ARGS]...

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  fetch
  zip
  gist

```

for example:

```bash
filehub fetch https://github.com/abhicodes07/filehub/tree/main/assets/ -d
```

---

<div align="center">
  <img src="https://img.shields.io/badge/license-mit-c4a7e7?style=for-the-badge&labelColor=%23191724&link=https%3A%2F%2Fgithub.com%2Fabhicodes07%2Ffilehub-cli%2Fblob%2Fmain%2FLICENSE" alt="LICENSE">

</div>

<p align="center">
	Copyright &copy; 2026-present <a href="https://github.com/abhicodes07" target="_blank">Abhi9av</a>
</p>
