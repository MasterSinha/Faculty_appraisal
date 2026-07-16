# OSINT & IP Exposure Security Review

This analysis reviews whether sensitive host VM IP addresses are leaked within the codebase files, git history, or documentation, and evaluates the security risks of public IP exposure.

---

## 1. Findings: IP Leakage in Code, Docs, and Git History

Our automated repository scan identified that the **VM's public IP (`150.129.156.37`)** and **private intranet IP (`10.100.0.23`)** are exposed in several locations:

### A. Exposure in Active Source Code
* **File Location**: [auth.py](file:///C:/Users/ruhan/fahh/Faculty_appraisal/src/api/v1/auth.py) (lines 189–200)
* **The Code**:
  ```python
  allowed_hosts = [
      ...
      "10.100.0.23",
      "10.100.0.23:3000",
      "150.129.156.37",
      "150.129.156.37:3000",
      ...
  ]
  ```
* **Risk**: The VM IPs are hardcoded directly inside the password reset validation logic. If this codebase is hosted on a public version control repository (such as public GitHub/GitLab), it leaks the exact hosting details to the internet.

### B. Exposure in Project Documentation
* **File Location**: [LOCAL_VM_DEPLOYMENT_CONTEXT.md](file:///C:/Users/ruhan/fahh/Faculty_appraisal/Docs/LOCAL_VM_DEPLOYMENT_CONTEXT.md)
* **The Lines**:
  * Line 147: `server_name pbas.dypiu.ac.in 10.100.0.23 150.129.156.37;`
  * Line 232: `ALLOWED_ORIGINS: "http://pbas.dypiu.ac.in,http://10.100.0.23,http://150.129.156.37"`
  * Line 334: `Access URL: http://10.100.0.23/`
* **Risk**: The deployment context documentation explicitly logs both the public and private IP addresses for setup guidance.

### C. Exposure in Git Commit History
* Since the IPs were committed directly to `auth.py` and `LOCAL_VM_DEPLOYMENT_CONTEXT.md`, they are permanently recorded in the git history database. Even if you delete these lines from the current code, they will remain searchable in past commit logs (e.g. via `git log -p`) unless the git history is explicitly rewritten/purged.

---

## 2. Threat Analysis: Domain vs. Raw IP Exposure

### A. Is Exposing `http://pbas.dypiu.ac.in` a Threat?
* **No**. The public domain name must be public so that faculty members and administrators can access the system. It is a standard and expected exposure.

### B. Is Exposing the Raw VM IP (`150.129.156.37`) a Threat?
* **Yes, a significant one**. 
* **WAF Bypass**: If you deploy a security proxy (like Cloudflare) to protect `pbas.dypiu.ac.in` from DDoS and web attacks, it only works if attackers go through the domain. If they discover the raw public IP `150.129.156.37`, they can send requests directly to the VM IP, completely bypassing Cloudflare's firewall and rate limits.
* **Direct Server Scanning**: Attackers who scan the raw public IP can identify open management ports, such as SSH (22), database ports (5432), or testing Docker containers (8002). This exposes the host operating system directly to brute-force and remote exploitation attempts.

---

## 3. Hardening Recommendations

1. **Remove Hardcoded IPs from Code**:
   * Replace the hardcoded IPs in `auth.py` and `main.py` with environment variable reads. For example, add the VM IPs to `CORS_ALLOWED_ORIGINS` inside the private `.env` file instead of committing them to the repository.
2. **Sanitize Documentation**:
   * Replace the actual public IP `150.129.156.37` in [LOCAL_VM_DEPLOYMENT_CONTEXT.md](file:///C:/Users/ruhan/fahh/Faculty_appraisal/Docs/LOCAL_VM_DEPLOYMENT_CONTEXT.md) with placeholder variables (e.g., `<VM_PUBLIC_IP>`) before the code is audited or shared.
3. **Configure firewall (UFW) on VM**:
   * Ensure that the host VM firewall blocks all external inbound traffic *except* for ports `80` (HTTP) and `443` (HTTPS) from trusted sources. Block port `8002` and `5432` from public access.
