"""Thin entrypoint for the legacy Kassandra app.

This file stays intentionally small.
The full application lives in app/legacy/kassandra_app_legacy.py.
"""

from app.legacy.kassandra_app_legacy import *  # noqa: F401,F403


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
