# Render

The service is a native Python web service. Official runtime notes: https://render.com/docs/python-version and https://render.com/docs/blueprint-spec.

`PYTHON_VERSION` is `3.14.3`, which is Render's current default and the interpreter that passed the local suite. The process listens on `PORT`.

`preDeployCommand` runs `python -m aftermath_api.migrate` with `DIRECT_URL`. The web process uses `DATABASE_URL` (transaction pooler, prepared statements disabled).

The private signing file is a Render secret file mounted at `/etc/secrets/production_ed25519.key`. `T2_SIGNING_KEY` is that path. The file is not in Git.

No cron service is declared. Render cron is not assumed to be free. The hourly paper cycle is `POST /internal/jobs/paper-cycle` with the job token and idempotency key `paper-cycle:{utc-hour}`.

This file does not contain a service URL. The repository has not been pushed, and Render has not been connected.
