#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Spectra Analyze (A1000) bulk file uploader."""

import argparse
import fnmatch
import inspect
import os
import sys
import time

import requests


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="Upload files to ReversingLabs Spectra Analyze (A1000).",
    )
    p.add_argument(
        "path", metavar="PATH", nargs="?", default=None,
        help="File or directory to upload",
    )
    p.add_argument(
        "--path", dest="path_flag", default=None,
        help="File or directory to upload (alternative to positional)",
    )
    p.add_argument(
        "--host", default=os.environ.get("RL_HOST"),
        help="A1000 host URL (or set RL_HOST)",
    )
    p.add_argument(
        "--token", default=os.environ.get("RL_TOKEN"),
        help="API token (or set RL_TOKEN)",
    )
    p.add_argument(
        "--verify-ssl", dest="verify_ssl", action="store_true", default=True,
        help="Enable SSL verification (default)",
    )
    p.add_argument(
        "--no-verify-ssl", dest="verify_ssl", action="store_false",
        help="Disable SSL verification",
    )
    _recursive_default = os.environ.get("RL_RECURSIVE", "no").lower() in ("1", "yes", "true", "on")
    p.add_argument(
        "--recursive", dest="recursive", action="store_true", default=_recursive_default,
        help="Recurse into subdirectories (default: no, or set RL_RECURSIVE)",
    )
    p.add_argument(
        "--no-recursive", dest="recursive", action="store_false",
        help="Do not recurse into subdirectories",
    )
    p.add_argument(
        "--exclude", action="append", default=[], metavar="PATTERN",
        help="Exclude filenames matching this fnmatch pattern (repeatable)",
    )
    p.add_argument(
        "--sleep", type=float, default=float(os.environ.get("RL_SLEEP", "2")),
        help="Seconds to wait between uploads (default: 2, or set RL_SLEEP)",
    )
    p.add_argument(
        "--retries", type=int, default=3,
        help="Max upload retries per file (default: 3)",
    )
    p.add_argument(
        "--retry-delay", type=float, default=5,
        help="Base retry delay in seconds, multiplied by attempt (default: 5)",
    )
    p.add_argument(
        "--timeout", type=int, default=300,
        help="HTTP request timeout in seconds (default: 300)",
    )

    args = p.parse_args()

    # Resolve path: positional > --path flag > RL_PATH env
    target = args.path or args.path_flag or os.environ.get("RL_PATH")
    if not target:
        p.error("PATH is required (positional, --path, or set RL_PATH)")
    args.target_path = target

    if not args.host:
        p.error("--host is required (or set RL_HOST)")
    if not args.token:
        p.error("--token is required (or set RL_TOKEN)")

    return args


# ---------------------------------------------------------------------------
# Timeout patching
# ---------------------------------------------------------------------------

def patch_timeout(timeout):
    """Monkey-patch requests so the SDK respects a default timeout."""
    original_send = requests.Session.send

    def patched_send(self, request, **kwargs):
        kwargs.setdefault("timeout", timeout)
        return original_send(self, request, **kwargs)

    requests.Session.send = patched_send


# ---------------------------------------------------------------------------
# SDK method resolution
# ---------------------------------------------------------------------------

def _make_path_caller(method):
    """Build a callable(file_path) that calls a path-based SDK upload method.

    Inspects the method signature to find the correct parameter name
    (file_path, file_source, sample_path, ...).  Falls back to positional.
    """
    sig = inspect.signature(method)
    params = list(sig.parameters.keys())
    # First non-self parameter is the path arg
    path_param = params[1] if len(params) > 1 and params[0] == "self" else (params[0] if params else None)
    if path_param:
        return lambda fp, m=method, p=path_param: m(**{p: fp})
    return lambda fp, m=method: m(fp)


def _make_handle_caller(method):
    """Build a callable(file_path) that opens a file and calls a handle-based SDK upload method."""
    sig = inspect.signature(method)
    params = list(sig.parameters.keys())
    handle_param = params[1] if len(params) > 1 and params[0] == "self" else (params[0] if params else None)

    def _upload(fp, m=method, p=handle_param):
        with open(fp, "rb") as fh:
            if p:
                return m(**{p: fh})
            return m(fh)
    return _upload


def resolve_upload_fn(a1000):
    """Return a callable(file_path) that uploads a single file.

    Probes the A1000 instance for known method names across SDK versions,
    inspects the real parameter names, and builds a matching caller.
    """
    # Path-based methods (preferred)
    for name in ("upload_sample_from_path", "submit_file_from_path"):
        method = getattr(a1000, name, None)
        if method is not None:
            return _make_path_caller(method)

    # File-handle methods (fallback)
    for name in ("upload_sample_from_file", "submit_file_from_handle"):
        method = getattr(a1000, name, None)
        if method is not None:
            return _make_handle_caller(method)

    print("ERROR: Could not find a supported upload method on the A1000 SDK object.", file=sys.stderr)
    print("       Installed SDK may be too old or too new. Methods checked:", file=sys.stderr)
    print("       upload_sample_from_path, submit_file_from_path,", file=sys.stderr)
    print("       upload_sample_from_file, submit_file_from_handle", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# File collection
# ---------------------------------------------------------------------------

def collect_files(target_path, recursive, excludes):
    """Return (file_list, skipped_count).

    file_list contains absolute paths. skipped_count is the number of
    files that matched an exclude pattern.
    """
    if os.path.isfile(target_path):
        basename = os.path.basename(target_path)
        for pattern in excludes:
            if fnmatch.fnmatch(basename, pattern):
                return [], 1
        return [os.path.abspath(target_path)], 0

    if not os.path.isdir(target_path):
        print(f"ERROR: Path does not exist: {target_path}", file=sys.stderr)
        sys.exit(1)

    files = []
    skipped = 0

    if recursive:
        for root, _dirs, filenames in os.walk(target_path):
            for fname in filenames:
                full = os.path.join(root, fname)
                if not os.path.isfile(full):
                    continue
                if any(fnmatch.fnmatch(fname, p) for p in excludes):
                    skipped += 1
                    continue
                files.append(os.path.abspath(full))
    else:
        for fname in os.listdir(target_path):
            full = os.path.join(target_path, fname)
            if not os.path.isfile(full):
                continue
            if any(fnmatch.fnmatch(fname, p) for p in excludes):
                skipped += 1
                continue
            files.append(os.path.abspath(full))

    files.sort()
    return files, skipped


# ---------------------------------------------------------------------------
# Upload with retry
# ---------------------------------------------------------------------------

def upload_with_retry(upload_fn, file_path, retries, retry_delay):
    """Try uploading a file, retrying on transient errors.

    Returns (response, error_string).  On success error_string is None.
    """
    last_err = "unknown error"

    for attempt in range(1, retries + 1):
        try:
            response = upload_fn(file_path)
            code = response.status_code

            if 200 <= code < 300:
                return response, None

            # Decide whether to retry
            if code == 429 or code >= 500:
                last_err = f"HTTP {code}"
            else:
                # 4xx (not 429) -- don't retry
                return response, f"HTTP {code}"

        except requests.exceptions.Timeout:
            last_err = "timeout"
        except requests.exceptions.ConnectionError as exc:
            last_err = f"connection error: {exc}"
        except Exception as exc:
            # SDK may wrap HTTP errors in its own exceptions.
            # If the exception carries a response, check if it is retryable.
            inner_resp = getattr(exc, "response", None)
            if inner_resp is not None and hasattr(inner_resp, "status_code"):
                code = inner_resp.status_code
                if code == 429 or code >= 500:
                    last_err = f"HTTP {code} (via {type(exc).__name__})"
                else:
                    return None, f"HTTP {code}"
            else:
                # Truly unknown error -- don't retry
                return None, str(exc)

        if attempt < retries:
            wait = retry_delay * attempt
            pad = " " * 10
            print(f"{pad}Attempt {attempt}/{retries}: {last_err}, retrying in {wait:.0f}s...")
            time.sleep(wait)

    return None, f"{last_err} after {retries} attempts"


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def print_header(target_path, recursive, file_count):
    print()
    print("Spectra Analyze Bulk Uploader")
    print("\u2500" * 29)
    mode = "(single file)" if os.path.isfile(target_path) else ""
    print(f"Path:       {target_path} {mode}".rstrip())
    if not os.path.isfile(target_path):
        print(f"Recursive:  {'yes' if recursive else 'no'}")
    print()


def print_summary(uploaded, failed, skipped, total):
    parts = [f"{uploaded} uploaded", f"{failed} failed"]
    if skipped > 0:
        parts.append(f"{skipped} skipped")
    parts.append(f"{total} total")
    summary = " \u2502 ".join(parts)
    bar = "\u2550" * (len(summary) + 8)
    print()
    print(bar)
    print(f"  Done.  {summary}")
    print(bar)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    # Lazy-import SDK so --help works even without the SDK installed
    try:
        from ReversingLabs.SDK.a1000 import A1000
    except ImportError:
        print("ERROR: reversinglabs-sdk-py3 is not installed.", file=sys.stderr)
        print("       Run: pip install reversinglabs-sdk-py3", file=sys.stderr)
        sys.exit(1)

    # Patch timeout before any SDK HTTP calls
    patch_timeout(args.timeout)

    # Initialise SDK client -- only pass user_agent if the constructor accepts it
    init_kwargs = dict(host=args.host, token=args.token, verify=args.verify_ssl)
    init_sig = inspect.signature(A1000.__init__)
    if "user_agent" in init_sig.parameters:
        init_kwargs["user_agent"] = "rl-bulk-uploader/1.0"
    a1000 = A1000(**init_kwargs)

    upload_fn = resolve_upload_fn(a1000)

    # Collect files
    files, skipped = collect_files(args.target_path, args.recursive, args.exclude)
    total_seen = len(files) + skipped

    # Header
    print_header(args.target_path, args.recursive, len(files))

    print(f"Scanning ...")
    if skipped > 0:
        print(f"Found {total_seen} files ({skipped} excluded)")
    else:
        print(f"Found {len(files)} files")
    print()

    if not files:
        print_summary(0, 0, skipped, total_seen)
        return

    uploaded = 0
    failed = 0
    width = len(str(len(files)))
    base_path = args.target_path if os.path.isdir(args.target_path) else os.path.dirname(args.target_path)

    for idx, fpath in enumerate(files, 1):
        rel = os.path.relpath(fpath, base_path)
        response, err = upload_with_retry(upload_fn, fpath, args.retries, args.retry_delay)

        counter = f"[{idx:>{width}}/{len(files)}]"

        if err is None:
            print(f"{counter} [OK]   {rel} (HTTP {response.status_code})")
            uploaded += 1
        else:
            print(f"{counter} [FAIL] {rel} ({err})")
            failed += 1

        # Sleep between uploads (but not after the last one)
        if idx < len(files):
            time.sleep(args.sleep)

    print_summary(uploaded, failed, skipped, total_seen)

    # Exit with non-zero if anything failed
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
