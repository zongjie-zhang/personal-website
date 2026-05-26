# Deploy Notes

This project is a Flask app served from `sbb.py`.

## Production start command

```bash
gunicorn -w 2 -b 0.0.0.0:$PORT sbb:app
```

## Required environment variables

- `FLASK_SECRET_KEY`
- `DB_HOST`
- `DB_PORT`
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`
- `APP_URL_PREFIX` when deploying under a path such as `/project/chopin`

Optional:

- `FLASK_ENV=production`
- `FLASK_DEBUG=0`
- `PRODUCTION=1`

## Health check

Use:

```text
/healthz
```

## Before public launch

1. Move database credentials out of code and into environment variables.
2. Use a managed MySQL database.
3. Keep `FLASK_DEBUG=0` in production.
4. Do not expose user password hashes in the admin UI.
5. Make sure audio, score PDFs, and cover images are included in deployment.

## Database inventory

The app code currently depends on these MySQL tables:

- `users`
- `playlists`
- `playlist_tracks`
- `works`
- `recordings`
- `descriptions`
- `places`
- `friends`

If you deploy to a new database, these tables and their data must be migrated together.

## Static assets that must ship

These folders are part of the product, not optional extras:

- `static/audio/`
- `static/score/`
- `static/image/`

If any of them are missing in production, parts of the site will look broken or stop working.

## Recommended first public stack

For this codebase, the simplest path is:

1. Put the code in a GitHub repo.
2. Deploy the app as a Python web service.
3. Provision a managed MySQL instance.
4. Set environment variables from `.env.example`.
5. Import your existing local database into the managed MySQL instance.

If the app is mounted below your main site, for example at
`zongjiezhang.com/project/chopin`, set:

```text
APP_URL_PREFIX=/project/chopin
```

## Public launch cautions

- Uploaded avatars are currently stored directly in the database as base64 data URLs.
- Audio files and cover images may have copyright constraints if the site becomes broadly public.
- The app currently uses a single Flask process design, so keep the first launch modest and monitor traffic.
