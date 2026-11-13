#!/home/hatch/workspace/cf-venv/bin/python
"""Chunked variant of cf_pages.py deploy for large sites.

Same endpoints, same credential mechanism, same content hashes as
cf_pages.py cmd_deploy — only the asset-upload step is split into batches
(max 300 files / ~6 MiB raw per batch) instead of one giant POST, because
the helper's single-batch upload is untested for very large sites.

Usage: deploy_chunked.py <directory> <project> [--branch main]
"""
import base64
import importlib.util
import json
import mimetypes
import sys
from pathlib import Path

HELPER = Path.home() / "workspace/custom-connectors/custom.cloudflare/bin/cf_pages.py"
spec = importlib.util.spec_from_file_location("cf_pages", HELPER)
cf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cf)

MAX_BATCH_FILES = 300
MAX_BATCH_BYTES = 6 * 1024 * 1024


def main(argv):
    if len(argv) < 2:
        print("usage: deploy_chunked.py <directory> <project> [--branch main]", file=sys.stderr)
        return 2
    directory, project = argv[0], argv[1]
    branch = "main"
    if "--branch" in argv:
        branch = argv[argv.index("--branch") + 1]

    root = Path(directory)
    if not root.is_dir():
        raise cf.PagesError(f"not a directory: {root}")

    payload, _ = cf._request("GET", f"{cf.API}/accounts")
    accounts = cf._ok(payload, "accounts")
    if len(accounts) != 1:
        raise cf.PagesError(f"expected exactly 1 account, got {len(accounts)}")
    account_id = accounts[0]["id"]
    print(f"account: {accounts[0].get('name')}")
    base = f"{cf.API}/accounts/{account_id}/pages"

    files = cf.collect(root)
    special = {}
    for name in cf.SPECIAL_FILES:
        p = files.pop("/" + name, None)
        if p is not None:
            special[name] = p.read_bytes()

    manifest = {}
    by_hash = {}
    for url_path, p in files.items():
        h = cf.file_hash(p.read_bytes(), p.suffix.lstrip("."))
        manifest[url_path] = h
        by_hash[h] = p
    print(f"{len(files)} files ({len(by_hash)} unique)"
          + (f" + {', '.join(sorted(special))}" if special else ""))

    try:
        payload, _ = cf._request("GET", f"{base}/projects/{project}")
        cf._ok(payload, "get project")
        print(f"project exists: {project}")
    except cf.PagesError as exc:
        if "HTTP 404" not in str(exc):
            raise
        payload, _ = cf._request(
            "POST", f"{base}/projects",
            json_body={"name": project, "production_branch": "main"})
        cf._ok(payload, "create project")
        print(f"created project: {project}")

    payload, _ = cf._request("GET", f"{base}/projects/{project}/upload-token")
    jwt = cf._ok(payload, "upload-token")["jwt"]
    print("upload token obtained")

    payload, _ = cf._request(
        "POST", f"{cf.API}/pages/assets/check-missing",
        json_body={"hashes": list(by_hash)}, auth="jwt", jwt=jwt)
    missing = cf._ok(payload, "check-missing")
    print(f"uploading {len(missing)} / {len(by_hash)} files "
          "(the rest are already cached)")

    if missing:
        batch, batch_bytes, sent = [], 0, 0
        n_batches = 0
        for h in missing:
            p = by_hash[h]
            data = p.read_bytes()
            if batch and (len(batch) >= MAX_BATCH_FILES
                          or batch_bytes + len(data) > MAX_BATCH_BYTES):
                payload, _ = cf._request(
                    "POST", f"{cf.API}/pages/assets/upload",
                    json_body=batch, auth="jwt", jwt=jwt, timeout=300.0)
                cf._ok(payload, "upload")
                sent += len(batch)
                n_batches += 1
                print(f"sent batch {n_batches}: {len(batch)} files ({sent}/{len(missing)})")
                batch, batch_bytes = [], 0
            ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            batch.append({
                "key": h,
                "value": base64.b64encode(data).decode(),
                "metadata": {"contentType": ctype},
                "base64": True,
            })
            batch_bytes += len(data)
        if batch:
            payload, _ = cf._request(
                "POST", f"{cf.API}/pages/assets/upload",
                json_body=batch, auth="jwt", jwt=jwt, timeout=300.0)
            cf._ok(payload, "upload")
            sent += len(batch)
            n_batches += 1
            print(f"sent batch {n_batches}: {len(batch)} files ({sent}/{len(missing)})")

    payload, _ = cf._request(
        "POST", f"{cf.API}/pages/assets/upsert-hashes",
        json_body={"hashes": list(by_hash)}, auth="jwt", jwt=jwt)
    cf._ok(payload, "upsert-hashes")

    fields = [
        ("branch", None, branch.encode(), None),
        ("manifest", None, json.dumps(manifest).encode(), None),
    ]
    for name, content in special.items():
        fields.append((name, name, content, None))
    body, ctype = cf._multipart(fields)
    payload, _ = cf._request(
        "POST", f"{base}/projects/{project}/deployments",
        data=body, content_type=ctype)
    result = cf._ok(payload, "create deployment")
    print(f"deployed: {result.get('url', '')}")
    print(f"environment: {result.get('environment', '')}")
    print(f"deployment id: {result.get('id', '')}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except cf.PagesError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
