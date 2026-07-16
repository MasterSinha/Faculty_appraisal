# Additional Security Auditing Vulnerabilities & Mitigations

This document outlines structural, container, and configuration vulnerabilities discovered in the Faculty Appraisal System that were not covered in previous discussions.

---

## 1. Vulnerability: Development Backdoor via Mock Authentication
* **File Location**: [dependencies.py](file:///C:/Users/ruhan/fahh/Faculty_appraisal/src/setup/dependencies.py) (see `get_current_user` function)

### The Risk:
* The auth guard checks the environment variable `ALLOW_MOCK_USER`:
  ```python
  if not authorization:
      if os.getenv("ALLOW_MOCK_USER", "false").lower() == "true":
          return User(
              id="00000000-0000-0000-0000-000000000001",
              email="admin@example.com",
              roles=["admin", "faculty"],
              ...
          )
  ```
* If a developer or server administrator sets `ALLOW_MOCK_USER=true` in the VM's `.env` configuration file for testing and forgets to disable it, **any user** can bypass authentication completely by omitting the `Authorization` HTTP header. The server will treat the unauthenticated request as a privileged `admin` session.

### Hardening Recommendation:
* Completely remove the mock user logic from production code.
* Alternatively, add a check that automatically rejects `ALLOW_MOCK_USER=true` if `ENVIRONMENT=production`.

---

## 2. Vulnerability: Publicly Exposed Database Port in Docker
* **File Location**: [docker-compose.local.yml](file:///C:/Users/ruhan/fahh/Faculty_appraisal/docker-compose.local.yml) (see `db` service definition)

### The Risk:
* The Docker Compose file maps the PostgreSQL port to the host:
  ```yaml
  ports:
    - "5432:5432"
  ```
* Because the backend server and database run inside the same Docker bridge network, they communicate directly via the container hostname (`db:5432`). Exposing `5432` on the host machine means anyone on the university campus network can scan the host VM's IP, find PostgreSQL listening, and launch brute-force password guessing attacks directly.

### Hardening Recommendation:
* Remove the `ports` mapping from the `db` service definition in `docker-compose.local.yml` entirely. Communication inside the Docker network does not require port mapping.
* If local external access is required for debugging, bind it only to localhost: `127.0.0.1:5432:5432`.

---

## 3. Vulnerability: Privileged Container Execution (Running as Root)
* **File Location**: [Dockerfile](file:///C:/Users/ruhan/fahh/Faculty_appraisal/Dockerfile)

### The Risk:
* The Dockerfile does not define a non-privileged system user (`USER` instruction). Gunicorn and Uvicorn execute inside the container as the root user.
* If an attacker manages to exploit a vulnerability (like the file upload or path traversal) to achieve remote code execution (RCE), they immediately run commands as `root`. This significantly increases the risk of container escape exploits, potentially compromising the host Linux VM.

### Hardening Recommendation:
* Create a dedicated non-root group and user inside the Dockerfile:
  ```dockerfile
  RUN groupadd -g 999 appuser && useradd -r -u 999 -g appuser appuser
  USER appuser
  ```
* Ensure appropriate ownership permissions (`chown`) are configured on `/app/uploads` and target directories before switching users.

---

## 4. Vulnerability: Missing OWASP Security Response Headers
* **File Location**: [main.py](file:///C:/Users/ruhan/fahh/Faculty_appraisal/src/main.py)

### The Risk:
* The application does not return basic security headers in its HTTP responses. An automated vulnerability scanner will instantly flag these missing items:
  1. **X-Frame-Options: DENY**: Prevents Clickjacking (embedding your site inside an iframe on another domain to hijack clicks).
  2. **X-Content-Type-Options: nosniff**: Prevents MIME-sniffing (instructing the browser not to execute uploaded files as scripts if they have mismatched extensions).
  3. **Content-Security-Policy (CSP)**: Restricts the locations from which scripts and assets can load.

### Hardening Recommendation:
* Add a middleware in FastAPI to append security headers to every response:
  ```python
  @app.middleware("http")
  async def add_security_headers(request: Request, call_next):
      response = await call_next(request)
      response.headers["X-Frame-Options"] = "DENY"
      response.headers["X-Content-Type-Options"] = "nosniff"
      response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
      return response
  ```

---

## 5. Vulnerability: Lack of Password Complexity Policy
* **File Location**: [auth.py](file:///C:/Users/ruhan/fahh/Faculty_appraisal/src/api/v1/auth.py) (see `/register` route)

### The Risk:
* The registration route accepts any string password without checking its complexity, length, or entropy. Users could use standard, weak passwords (e.g., `password123`), making them susceptible to credential stuffing.

### Hardening Recommendation:
* Enforce a password validator schema using Pydantic (e.g., minimum 8 characters, requiring at least one number, one uppercase letter, and one special character).
