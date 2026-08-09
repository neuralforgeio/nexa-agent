from pathlib import Path

p = Path(r"C:\Users\Dearly Febriano\openforge\tools\file_tools.py")
lines = p.read_text(encoding="utf-8", errors="surrogateescape").splitlines()

new_block = '''async def write_file(path: str, content: str, **_: Any) -> str:
    """
    Write text content to a file in the workspace.

    Creates parent directories if they do not exist. Overwrites the file
    if it already exists.

    Args:
        path:    Relative path to the file inside the workspace.
        content: The text content to write (max 1MB).

    Returns:
        A confirmation message with the byte count.

    Raises:
        ValueError: If the path escapes the workspace, the target is an
            existing directory, the content exceeds 1MB, or a permission
            / OS error occurs during the write.

    Example:
        >>> await write_file("notes.txt", "hello")  # doctest: +SKIP
        'wrote 5 bytes to notes.txt'
    """
    # Size cap.
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_FILE_SIZE:
        raise ValueError(f"content too large ({len(encoded)} bytes, max {MAX_FILE_SIZE} = 1MB)")

    full = resolve_in_workspace(path)
    # v5.0.2: block any write that targets the protected core.
    ensure_safe_write(full, "write")

    if full.exists() and full.is_dir():
        raise ValueError(f"cannot write file: '{path}' is an existing directory")

    tmp = full.with_name(full.name + ".tmp")
    try:
        full.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(content, "utf-8")
        os.replace(str(tmp), str(full))
    except PermissionError as exc:
        raise ValueError(f"permission denied writing '{path}': {exc}") from exc
    except IsADirectoryError as exc:
        raise ValueError(f"'{path}' is a directory, not a file: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"could not write '{path}': {exc}") from exc
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass

    return f"wrote {len(encoded)} bytes to {path}"
'''

start = next(i for i, l in enumerate(lines) if l.startswith("async def write_file("))
end = next(i for i, l in enumerate(lines) if start and 'return f"wrote' in l)
lines[start : end + 1] = new_block.splitlines()
p.write_text("\n".join(lines), encoding="utf-8")
print("ok-rewritten")
