# ReversingLabs Bulk Upload Tool

Bulk-uploads files to ReversingLabs Spectra Analyze (A1000) via the official Python SDK. Recursive directory traversal, retry with backoff, rate limiting, per-file status output.

## Prerequisites

- Python 3.x
- Access to a Spectra Analyze (A1000) instance
- Valid API token
- Bash (Linux/macOS)

## Setup

```bash
# 1. Clone / copy the repo
# 2. Create your config
mv rl_upload.conf.example rl_upload.conf

# 3. Edit rl_upload.conf with your values:
#    RL_HOST="https://your-a1000-instance"
#    RL_TOKEN="your-api-token"
#    RL_PATH="/path/to/samples"
#    RL_RECURSIVE="no"

# 4. Make executable (optional)
chmod +x upload.sh
```

The virtual environment and SDK are installed automatically on first run.

## Usage

```bash
# Upload everything configured in rl_upload.conf
./upload.sh

# Override path for a single run
./upload.sh /other/samples

# Single file
./upload.sh /path/to/one_sample.bin

# With options
./upload.sh --exclude '*.txt' --sleep 5 --retries 5 --no-verify-ssl

# Show all options
./upload.sh --help
```

## CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `PATH` (positional) | `RL_PATH` | File or directory to upload |
| `--host` | `RL_HOST` | A1000 host URL |
| `--token` | `RL_TOKEN` | API token |
| `--no-verify-ssl` | verify on | Disable SSL verification |
| `--recursive` / `--no-recursive` | `RL_RECURSIVE` (default: no) | Recurse into subdirectories |
| `--exclude PATTERN` | none | Exclude filenames (fnmatch, repeatable) |
| `--sleep N` | `RL_SLEEP` (default: 2) | Seconds between uploads |
| `--retries N` | 3 | Max retries per file |
| `--retry-delay N` | 5 | Base retry delay (seconds x attempt) |
| `--timeout N` | 300 | HTTP request timeout in seconds |

## Output

```
Spectra Analyze Bulk Uploader
─────────────────────────────
Path:       /data/samples
Recursive:  yes

Scanning ...
Found 47 files

[ 1/47] [OK]   trojan_a.bin (HTTP 201)
[ 2/47] [OK]   trojan_b.bin (HTTP 201)
[ 3/47] [FAIL] corrupt.dat (HTTP 400 Bad Request)
[ 4/47] [OK]   packed_sample.exe (HTTP 201)
...

════════════════════════════════
  Done.  44 uploaded │ 2 failed │ 47 total
════════════════════════════════
```

## File Structure

```
.
├── upload.sh                  # Entry point -- run this
├── rl_upload.py               # Python uploader (CLI)
├── rl_upload.conf.example    # Config template (tracked)
├── rl_upload.conf            # Your config (gitignored)
├── .gitattributes             # Enforces LF line endings
└── .venv/                     # Auto-created virtual environment (gitignored)
```

## Retry Behavior

- Retries on: timeouts, connection errors, HTTP 429 (rate limit), HTTP 5xx
- Does NOT retry on: HTTP 4xx (bad request, auth failure, etc.)
- Backoff: `retry_delay x attempt_number`

## Troubleshooting

- **Authentication failed**: Check `RL_TOKEN` in `rl_upload.conf`
- **Connection errors**: Check `RL_HOST` is correct and reachable
- **Broken venv**: Delete `.venv/` and re-run -- it rebuilds automatically

## Links

- [Spectra Analyze API Docs](https://docs.reversinglabs.com/SpectraAnalyze/API%20Documentation/submissions/)
- [Python SDK](https://github.com/reversinglabs/reversinglabs-sdk-py3)

## Disclaimer

This tool was vibe-coded with AI assistance. While it has been tested against the SDK's public API surface, you should verify uploads against your Spectra Analyze instance before relying on it in production. Use at your own risk.
