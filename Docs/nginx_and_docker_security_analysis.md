# Nginx & Docker Infrastructure Security Analysis

This analysis reviews the VM deployment command and the Nginx configuration file shown in the system screenshots, highlighting infrastructure vulnerabilities and providing hardening recommendations.

---

## 1. Vulnerability: Bypassing Backend Authentication via Nginx Static Aliasing
* **File Reference**: `/etc/nginx/sites-available/appraisal` (see `location /uploads/` and `location /AAA/uploads/`)

### The Issue:
In the Nginx configuration, uploaded files are served statically using the `alias` directive:
```nginx
location /uploads/ {
    alias /home/dypiu/uploads/;
}
```
* **The Security Flaw**: Because Nginx handles requests to `/uploads/` directly at the filesystem layer, **it bypasses the FastAPI backend entirely**. 
* Even if we implement secure authorization check logic inside the FastAPI `/api/v1/upload/view` endpoint, any user can access `https://pbas.dypiu.ac.in/uploads/some_faculty/cv.pdf` directly. Nginx will serve the file statically without performing token or role checks.
* This represents a complete bypass of File Object-Level Authorization (IDOR).

### Hardening Recommendation:
* Remove the `alias` location block for `/uploads/` from the public Nginx server configuration.
* Route all file-viewing requests to the backend proxy:
  ```nginx
  location /uploads/ {
      proxy_pass http://127.0.0.1:8002/api/v1/upload/view/;
      proxy_set_header Host $host;
      ...
  }
  ```
  *(This ensures that every file request hits the FastAPI container, running the secure authentication checks we planned in [security_hardening_plan.md](file:///C:/Users/ruhan/fahh/Faculty_appraisal/Docs/security_hardening_plan.md)).*

---

## 2. Vulnerability: Infinite Upload Size Allowed at Proxy Level
* **File Reference**: `/etc/nginx/sites-available/appraisal` (see `client_max_body_size 0;`)

### The Issue:
* The Nginx configuration sets:
  ```nginx
  client_max_body_size 0;
  ```
* In Nginx, a value of `0` **disables checking of client request body sizes**.
* **The Security Flaw**: This allows clients to upload files of infinite size. An attacker can easily exploit this by uploading massive (e.g., 50GB+) files to exhaust the VM's disk space, causing a system-wide Denial of Service (DoS) crash.

### Hardening Recommendation:
* Limit request payload sizes at the Nginx level to match your application limit (e.g. 10MB):
  ```nginx
  client_max_body_size 10M;
  ```

---

## 3. Vulnerability: Direct Port Exposure on Public Interfaces
* **File Reference**: VM Deploy Command
  `sudo docker run ... -p 8002:8080 ...`

### The Issue:
* The Docker deploy command binds port `8002` globally:
  `-p 8002:8080` (which is equivalent to `-p 0.0.0.0:8002:8080`).
* **The Security Flaw**: This exposes the FastAPI container port directly to any computer on the local network/internet. An attacker on the campus network can bypass Nginx blocks, security filters, or rate-limiting entirely by connecting directly to the container port at `http://<VM_IP>:8002/api/v1/...`.

### Hardening Recommendation:
* Restrict the container port binding to the local loopback interface (`127.0.0.1`). This forces all traffic to route through Nginx:
  ```bash
  sudo docker run -d --name faculty_appraisal_backend_test \
    --add-host=host.docker.internal:host-gateway \
    -v /home/dypiu/Faculty_appraisal/uploads_test:/app/uploads_test \
    --env-file /home/dypiu/Faculty_appraisal/.env.test \
    -p 127.0.0.1:8002:8080 \
    faculty_appraisal_backend:test
  ```
