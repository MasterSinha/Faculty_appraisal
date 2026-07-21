import sys
import os
import asyncio
import socket
from dotenv import load_dotenv

# Ensure Faculty_appraisal directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from src.setup.email_utils import dispatch_email


def test_socket_ports(host: str):
    print(f"\n--- 1. Testing TCP Socket Connectivity to {host} ---")
    for port in [587, 465, 25]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        try:
            s.connect((host, port))
            print(f"  Port {port:3d}: [OPEN & REACHABLE]")
        except Exception as e:
            print(f"  Port {port:3d}: [BLOCKED / TIMED OUT] -> {e}")
        finally:
            s.close()


async def main():
    target_email = sys.argv[1] if len(sys.argv) > 1 else os.getenv("MAIL_USERNAME") or os.getenv("SMTP_USER")
    
    print("==========================================================")
    print("  FACULTY APPRAISAL SYSTEM — EMAIL DIAGNOSTIC TOOL")
    print("==========================================================")
    
    server = os.getenv("MAIL_SERVER") or os.getenv("SMTP_HOST", "smtp.gmail.com")
    user   = os.getenv("MAIL_USERNAME") or os.getenv("SMTP_USER", "")
    pw     = os.getenv("MAIL_PASSWORD") or os.getenv("SMTP_PASSWORD", "")
    port   = os.getenv("MAIL_PORT") or os.getenv("SMTP_PORT", "587")
    
    print(f"MAIL_SERVER:   {server}")
    print(f"MAIL_PORT:     {port}")
    print(f"MAIL_USERNAME: {user or '(empty)'}")
    print(f"MAIL_PASSWORD: {'*' * len(pw) if pw else '(empty)'}")
    print(f"TARGET EMAIL:  {target_email or '(none provided)'}")

    test_socket_ports(server)

    if not target_email:
        print("\n[!] Please provide a target email address: python scripts/test_email.py your_email@example.com")
        sys.exit(1)

    print(f"\n--- 2. Attempting Email Dispatch to {target_email} ---")
    success = await dispatch_email(
        recipients=[target_email],
        subject="Email Diagnostic Test — Faculty Appraisal System",
        body_html="<h3>Diagnostic Test</h3><p>Your server email dispatch system is configured and working!</p>"
    )

    print("\n==========================================================")
    if success:
        print(f"SUCCESS: Email was successfully sent to {target_email}!")
    else:
        print("FAILURE: Email could not be sent. Review diagnostic messages above.")
    print("==========================================================")


if __name__ == "__main__":
    asyncio.run(main())
