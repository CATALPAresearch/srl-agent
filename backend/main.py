"""Local development server. Production runs gunicorn (see docker-compose.yml).

Defaults are safe: only reachable from this machine, debugger off. The Werkzeug debugger
allows running code in the browser, so never combine FLASK_DEBUG=1 with a public HOST.

    poetry run python main.py                      # http://127.0.0.1:5000
    FLASK_DEBUG=1 poetry run python main.py        # with debugger + auto reload
    HOST=<lan-ip> poetry run python main.py        # reachable from other devices (no debug!)
"""
import os

from app import app

if __name__ == '__main__':
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true"),
    )
