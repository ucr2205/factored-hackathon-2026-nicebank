"""Print the current TOTP code of a demo customer, for manual tests of the step-up (card block) and password reset.

Demo customers carry a test-only TOTP seed in the local realm (`nicebank-demo-otp-<username>`, see
infra/keycloak/README.md), so nobody needs to enroll a phone. Local test realm only.

Usage: poetry run python scripts/totp.py cliente03
"""

from __future__ import annotations

import sys
import time

from smoke_chat import totp


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].startswith("cliente"):
        sys.exit("usage: poetry run python scripts/totp.py clienteNN")
    left = 30 - int(time.time()) % 30
    print(f"{totp(f'nicebank-demo-otp-{sys.argv[1]}')}  (valid for {left} s more)", flush=True)


if __name__ == "__main__":
    main()
