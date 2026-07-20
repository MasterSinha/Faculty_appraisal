# Security Hardening & Implementation Plan

This planning document outlines the technical steps to remediate vulnerabilities and protect the Faculty Appraisal System during the upcoming security audit.

---

## 1. File Upload Restrictions & Audit (Point 1)

### VM Audit Script
To inspect all existing file extensions in your current local upload directory without breaking compatibility for old uploads, run this Python one-liner on the local VM terminal inside the project root:

```bash
python -c "import os; exts={os.path.splitext(f)[1].lower() for r, d, fs in os.walk('./uploads') for f in fs}; print('Existing Extensions:', exts)"
```

### Proposed Enforcement
1. **Frontend Info**: Update the file uploader component to clearly show:
   * Supported formats: `.pdf`, `.jpg`, `.jpeg`, `.png`
   * Max size limit: **5 MB**
2. **Backend Whitelist**: Validate both the file extension and the magic bytes header at the `/upload` API level. Reject files larger than `5 * 1024 * 1024` bytes.

---

## 2. Secure File Access via Fetch & Blob URLs (Point 2)

We will use **Option 2 (Javascript Fetch + Blob URLs)** to secure file viewing.

### How it Works:
1. **Frontend Request**: Instead of opening `<a href="http://backend/view/path" target="_blank">`, the frontend makes a request using `fetch()` and attaches the standard `Authorization: Bearer <token>` header.
2. **File Conversion**: The response is parsed as a binary `Blob`:
   ```javascript
   const response = await fetch('/api/v1/upload/view/path', {
     headers: { 'Authorization': `Bearer ${token}` }
   });
   const fileBlob = await response.blob();
   const fileUrl = URL.createObjectURL(fileBlob);
   ```
3. **Display**: The generated `fileUrl` (which looks like `blob:http://localhost/d2b512...`) is rendered inside a modal iframe or a temporary tab.
4. **Security Benefit**: DevTools will show the API endpoint `/api/v1/upload/view/path`. However, because the backend endpoint now requires the Bearer token, unauthorized users or hackers who copy the URL from DevTools will receive a `401 Unauthorized` response.

---

## 3. Environment & Configuration Security (Point 3)

Since the local VM has a active `.env` file containing a JWT string, the direct risk is mitigated. However, to prevent configuration mistakes during future VM server migrations, we plan to implement a startup check:
* **Fail-Safe Startup**: Check `JWT_SECRET_KEY` during FastAPI initialization in `main.py`. If it matches the fallback default string and the environment is not set to `development`, the backend will print a critical security warning to console logs or refuse to boot.

---

## 4. Reverse Proxying with Cloudflare (Point 4)

Deploying Cloudflare (Free Tier) in front of the local VM is highly recommended:
* **IP Obfuscation**: Cloudflare acts as a reverse proxy. Attacking scripts or scanners scanning university subnets will only see Cloudflare IPs, preventing direct DDoS attacks on your college gateway.
* **SSL Offloading**: Cloudflare can automatically handle HTTPS encryption (serving the site over secure HTTPS using free SSL certificates) even if the internal university network uses HTTP.

---

## 5. Deactivating the Feedback Feature (Point 5)

To prevent spam database writes on the unused feedback system, we will temporarily isolate the route.
* **Implementation**: Comment out or remove the router registration in `main.py`:
  ```python
  # app.include_router(feedback_router, prefix="/api/v1")
  ```
* This completely blocks `/api/v1/feedback` requests at the API gateway layer without deleting any code, allowing future reactivation.

---

## 6. Additional Security Threats & Hardening Opportunities

To ensure the system passes the security specialist's review with flying colors, consider these other architectural protections:

### A. Strict Database Isolation
* **Threat**: PostgreSQL default port `5432` left open to the campus network.
* **Fix**: Configure PostgreSQL (`postgresql.conf` and `pg_hba.conf`) to only bind to `localhost` (`127.0.0.1`) or the internal Docker bridge network. No external VM interfaces should expose database ports.

### B. Input Sanitization (Stored XSS in Appraisals)
* **Threat**: Faculty members entering HTML tags (e.g. `<img src=x onerror=alert(1)>`) inside text input fields. When an HOD or Dean reviews the form, if the React frontend renders these strings as HTML, it executes the payload.
* **Fix**: Ensure that the React frontend renders all text fields using standard text nodes (i.e. `{text_content}`) rather than rich-text HTML interpreters (like `dangerouslySetInnerHTML`), or pass all HTML text inputs through a sanitizer library (such as `bleach` on the backend).

### C. SSL Plaintext Sniffing
* **Threat**: If the site is accessed over HTTP (`http://`), passwords and JWT tokens are sent in plaintext across the college Wi-Fi/LAN. Anyone with a packet sniffer (like Wireshark) on the same network can hijack admin accounts.
* **Fix**: Enforce HTTPS redirection at the web server (Nginx or Cloudflare) and set `secure=True` on cookies.
