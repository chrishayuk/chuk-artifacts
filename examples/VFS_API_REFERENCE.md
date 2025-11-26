# chuk-virtual-fs API Reference

Quick reference for the correct VFS method names used in examples.

## Directory Operations

| Operation | Method | Example |
|-----------|--------|---------|
| List directory | `ls(path)` | `files = await vfs.ls("/")` |
| Create directory | `mkdir(path)` | `await vfs.mkdir("/src")` |
| Remove directory | `rmdir(path)` | `await vfs.rmdir("/old")` |
| Change directory | `cd(path)` | `await vfs.cd("/src")` |
| Check if directory | `is_dir(path)` | `is_dir = await vfs.is_dir("/src")` |

## File Operations

| Operation | Method | Example |
|-----------|--------|---------|
| Write file | `write_file(path, data)` | `await vfs.write_file("/file.txt", b"content")` |
| Read file | `read_file(path)` | `data = await vfs.read_file("/file.txt")` |
| Delete file | `rm(path)` | `await vfs.rm("/file.txt")` |
| Copy file | `cp(source, dest)` | `await vfs.cp("/a.txt", "/b.txt")` |
| Move/rename file | `mv(source, dest)` | `await vfs.mv("/old.txt", "/new.txt")` |
| Check exists | `exists(path)` | `exists = await vfs.exists("/file.txt")` |
| Check if file | `is_file(path)` | `is_file = await vfs.is_file("/file.txt")` |
| Get file info | `get_node_info(path)` | `info = await vfs.get_node_info("/file.txt")` |
| Touch file | `touch(path)` | `await vfs.touch("/new.txt")` |

## Metadata Operations

| Operation | Method | Example |
|-----------|--------|---------|
| Get metadata | `get_metadata(path)` | `meta = await vfs.get_metadata("/file.txt")` |
| Set metadata | `set_metadata(path, meta)` | `await vfs.set_metadata("/file.txt", {"key": "value"})` |

## Batch Operations

| Operation | Method | Example |
|-----------|--------|---------|
| Batch create | `batch_create_files(specs)` | `await vfs.batch_create_files([...])` |
| Batch read | `batch_read_files(paths)` | `data = await vfs.batch_read_files(["/a", "/b"])` |
| Batch write | `batch_write_files(data)` | `await vfs.batch_write_files({"/a": b"data"})` |
| Batch delete | `batch_delete_paths(paths)` | `await vfs.batch_delete_paths(["/a", "/b"])` |

## Streaming Operations

| Operation | Method | Example |
|-----------|--------|---------|
| Stream write | `stream_write(path, stream)` | `await vfs.stream_write("/big.dat", stream)` |
| Stream read | `stream_read(path, chunk_size)` | `async for chunk in vfs.stream_read("/big.dat"): ...` |

## System Operations

| Operation | Method | Example |
|-----------|--------|---------|
| Initialize | `initialize()` | `await vfs.initialize()` |
| Close/cleanup | `close()` | `await vfs.close()` |
| Get stats | `get_storage_stats()` | `stats = await vfs.get_storage_stats()` |
| Get provider | `get_provider_name()` | `name = await vfs.get_provider_name()` |

## Common Patterns

### List directory and get info
```python
files = await vfs.ls("/")
for file in files:
    info = await vfs.get_node_info(f"/{file}")
    print(f"{file}: {info.size} bytes")
```

### Create nested directory structure
```python
await vfs.mkdir("/src")
await vfs.mkdir("/src/utils")
await vfs.write_file("/src/utils/helpers.py", b"# helpers")
```

### Copy and rename pattern
```python
# Copy
await vfs.cp("/template.txt", "/new.txt")

# Rename (move)
await vfs.mv("/old_name.txt", "/new_name.txt")
```

### Check and create
```python
if not await vfs.exists("/config"):
    await vfs.mkdir("/config")
    await vfs.write_file("/config/settings.json", b'{}')
```

## Notes

- All methods are async and must be awaited
- Paths should start with `/`
- Methods return `bool` for success/failure or actual data
- Use `read_file()` for binary data, returns `bytes`
- Use `write_file()` for both text and binary data (pass `bytes`)
