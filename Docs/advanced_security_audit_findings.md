# Advanced Security Audit Findings: Vulnerability & Hardening Guide

This document outlines hidden security vulnerabilities identified within the Faculty Appraisal codebase. It is designed to prepare the system for external audit and implement key security upgrades.

---

## 1. Vulnerability: Insecure File Upload Validation (Stored XSS & Path Traversal)
* **File Location**: [upload.py](file:///C:/Users/ruhan/fahh/Faculty_appraisal/src/api/v1/upload.py) (see `/upload` route)

### The Risk:
1. **Stored Cross-Site Scripting (XSS)**: The endpoint accepts any file content type. If a malicious user uploads an HTML file containing JavaScript (e.g., `<script>steal_session_token()</script>`) or an SVG file with embedded scripts, the file is saved to local storage. Because the application serves these files on the same origin using `FileResponse` at `/api/v1/upload/view/{path}`, accessing the link will execute the malicious code in the context of the user's browser (e.g., an HOD or VC reviewing the file).
2. **Path Traversal**: The filename is cleaned using `.replace(" ", "_")` to create `safe_name`, which is then joined: `os.path.join(target_dir, f"{content_hash}_{safe_name}")`. If a crafted request sends `../../etc/passwd` or `../../main.py` in the filename, `os.path.join` resolves this relative to the base directory and can overwrite core code or system configuration files.

### Hardening Recommendation:
* Enforce strict file extension whitelisting (e.g., only `.pdf`, `.png`, `.jpg`).
* Extract only the base name of the uploaded file using `os.path.basename()` to neutralize relative path indicators.
* Read the "magic bytes" (file signatures) of the uploaded content to verify it matches the claimed file type rather than relying solely on the browser-sent `Content-Type` header.

---

## 2. Vulnerability: Insecure Direct Object Reference (IDOR) on Uploaded Files
* **File Location**: [upload.py](file:///C:/Users/ruhan/fahh/Faculty_appraisal/src/api/v1/upload.py) (see `/upload/view/{path}` route)

### The Risk:
* The `/upload/view/{path:path}` endpoint serves files from local disk or redirects to GCP GCS. However, this route does **not require authentication** (it is missing the `CurrentUser` dependency).
* Anyone who discovers or guesses a URL pattern (such as `/api/v1/upload/view/faculty/dean@dypiu.ac.in/hash_cv.pdf`) can access confidential salary slips, academic declarations, and personal files without logging in.

### Hardening Recommendation:
* Add the `CurrentUser` dependency to the `view_file` endpoint.
* Verify that the requesting user is either the owner of the document (matching their email in the path) or a supervisor with authority over the owner according to `has_authority_over()`.

---

## 3. Vulnerability: Hardcoded Cryptographic Fallbacks & Session Forgery
* **File Locations**: [main.py](file:///C:/Users/ruhan/fahh/Faculty_appraisal/src/main.py) & [local_auth.py](file:///C:/Users/ruhan/fahh/Faculty_appraisal/src/setup/local_auth.py)

### The Risk:
* If the environment variable `JWT_SECRET_KEY` is not explicitly set, both files fall back to `"fallback-secret-change-in-production"` or `"your-fallback-secret-key-change-in-production"`.
* Starlette's `SessionMiddleware` signs cookies using this secret. If the system is deployed using the fallback key, any user can forge a session cookie declaring them as `admin@example.com` and gain access to the raw database management UI at `/admin`.
* Access tokens expire after **7 days** (`ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7`). If a token is stolen, the session remains active for a week with no blacklist or token revocation mechanism.

### Hardening Recommendation:
* Raise a fatal startup error if `JWT_SECRET_KEY` is not configured in the environment variables (except when explicitly running in `development` mode).
* Shorten access token lifetimes to 15–30 minutes and implement refresh tokens or session-check middleware.

---

## 4. Vulnerability: Memory Exhaustion DoS in Rate Limiting
* **File Location**: [rate_limit.py](file:///C:/Users/ruhan/fahh/Faculty_appraisal/src/setup/rate_limit.py)

### The Risk:
* The sliding-window rate limiter stores timestamps in an in-memory dictionary `_buckets: dict[str, list[float]]`.
* When an incoming request checks rate limits (e.g., on `/forgot-password` or `/login`), keys are added dynamically. While the list of timestamps is pruned to keep only recent entries, **empty lists/keys are never removed** from `_buckets`.
* An attacker can send millions of login attempts using randomized emails. This creates millions of dictionary keys, growing memory usage unboundedly until the server runs out of RAM and crashes (OOM Denial of Service).
* Because the rate limiter is stored in the FastAPI memory space, it does not share state across multiple scaled instances (e.g., on GCP Cloud Run).

### Hardening Recommendation:
* Periodically purge keys with empty lists from the dictionary, or set a maximum size for the cache dictionary (e.g., using a Least Recently Used (LRU) cache).
* Transition to a central key-value store like Redis for production clustering.

---

## 5. Vulnerability: Missing Rate Limiting on Database-Write Endpoints
* **File Location**: [feedback.py](file:///C:/Users/ruhan/fahh/Faculty_appraisal/src/api/v1/feedback.py) (see public `create_feedback` route)

### The Risk:
* The `/feedback` endpoint allows public POST requests to save user feedback in the database without any authentication, rate-limiting, or CAPTCHA checks.
* An attacker can easily script a loop to submit millions of entries, filling the Postgres disk and exhausting database connections.

### Hardening Recommendation:
* Apply the `check_rate_limit` utility to `/feedback` restricting submissions per client IP (e.g., 5 requests per hour).
