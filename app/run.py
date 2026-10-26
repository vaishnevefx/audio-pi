"""Entry point: initialise DB, seed defaults, start the scheduler, serve the portal."""
import config
import db
import display
import scheduler
from webapp import app


def main():
    db.init_db()
    db.ensure_seed()
    display.start()
    scheduler.start()
    from waitress import serve
    print(f"Pi Audio Portal listening on http://{config.HOST}:{config.PORT}")
    # channel_timeout reaps stuck/slow client connections so a flaky network
    # path can never exhaust the server and wedge it.
    serve(app, host=config.HOST, port=config.PORT, threads=12,
          channel_timeout=30, cleanup_interval=10, ident="PiAudioPortal")


if __name__ == "__main__":
    main()
