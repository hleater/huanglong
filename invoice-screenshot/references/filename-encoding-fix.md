# Chinese Filename Encoding Recovery

## Symptom

A file transferred from Windows to Linux shows garbled Chinese characters in the filename, with `?` replacing some characters:

```
�?00出行-12.67�?1个行程】高德打车电子发�?pdf
```

## Root Cause

The filename was originally encoded in **GBK/GB18030** (Windows Simplified Chinese default) or was correctly UTF-8 but got corrupted during transfer. The corruption pattern: the **3rd byte of 3-byte UTF-8 CJK characters was replaced by `0x3f` (`?`)**, while valid sequences pass through unchanged.

This typically happens when:
- File is transferred via a tool that does byte-level conversion without proper charset handling
- SSH/SFTP client on Windows sends filename bytes interpreted under wrong encoding
- A charset conversion was attempted but truncated multi-byte sequences

## Diagnosis

### 1. Check system locale
```bash
locale
# Should show: LANG=zh_CN.UTF-8
locale -a
# Should include: zh_CN.utf8
```

### 2. Inspect the garbled filename hex
```bash
ls /path/to/ | grep -aP '[^\x00-\x7F]' | head -1 | xxd
```

### 3. Identify corruption pattern
Valid UTF-8 3-byte CJK character: `E5 85 B1` (共)
Corrupted version: `E5 85 3F` → the continuation byte `B1` was replaced by `3F` (`?`)

Look for the pattern: first two bytes of a 3-byte UTF-8 sequence followed by `0x3f`:
- `eX XX 3f` where `eX` is 0xe0-0xef (start of 3-byte UTF-8)

## Recovery

Use Python to rename the file by reconstructing the correct bytes:

```python
import os, pathlib

p = pathlib.Path('/path/to/dir')
for f in p.iterdir():
    if '?' in f.name and any(c in f.name for c in '出行发票'):
        # Build correct filename by replacing 0x3f with the expected continuation byte
        raw = f.name.encode('utf-8', errors='surrogateescape')
        # Strategy 1: If you know the expected characters, replace directly
        fixed_bytes = raw.replace(b'\x3f', b'\x90').replace(b'\x3f', b'\xb1').replace(b'\x3f', b'\xa8')
        # Strategy 2: Better — reconstruct from known correct filename
        correct = '【00出行-12.67共1个行程】高德打车电子发票.pdf'
        f.rename(p / correct)
        print(f'Renamed: {f.name} → {correct}')
```

### Common replacement byte values for corrupted filenames
- `【` → `e3 80 90` (3rd byte `90`)
- `】` → `e3 80 91` (3rd byte `91`)
- `共` → `e5 85 b1` (3rd byte `b1`)
- `票` → `e7 a5 a8` (3rd byte `a8`)

## Prevention

- Use `scp -O` (legacy protocol, no encoding transformation) or `rsync --iconv=GBK,UTF-8` when transferring from Windows
- For Open WebUI uploads: filenames pass through correctly if the browser sends UTF-8; ensure the upload page charset is UTF-8
- Configure Windows SFTP clients (WinSCP, FileZilla) to use UTF-8 for filenames
