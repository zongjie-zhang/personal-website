# Railway Deploy

This app can serve your personal homepage at `/` and your Chopin site at
`/project/chopin` from the same Flask service.

## 1. Push the project to GitHub

Upload this whole `milestone_4` folder as a GitHub repository.

## 2. Create a Railway project

1. In Railway, create a new project from your GitHub repo.
2. Add a MySQL database service to the same Railway project.

## 3. Web service start command

If Railway does not detect it automatically, use:

```bash
gunicorn -w 2 -b 0.0.0.0:$PORT sbb:app
```

`Procfile` already contains the same command.

## 4. Environment variables

Set these on the web service:

```text
FLASK_SECRET_KEY=replace-with-a-long-random-secret
FLASK_ENV=production
FLASK_DEBUG=0
PRODUCTION=1
```

For Railway MySQL, this app already supports Railway's default variables:

- `MYSQLHOST`
- `MYSQLPORT`
- `MYSQLUSER`
- `MYSQLPASSWORD`
- `MYSQLDATABASE`

So you usually do not need to remap them manually.

## 5. Import your existing local MySQL data

Your current tables that matter are:

- `users`
- `playlists`
- `playlist_tracks`
- `works`
- `recordings`
- `descriptions`
- `places`
- `friends`

Export them from local MySQL and import them into the Railway MySQL database.

Example local export:

```bash
mysqldump -u root -p --databases chopin_db > chopin_db.sql
```

Example import into Railway MySQL:

```bash
mysql -h <MYSQLHOST> -P <MYSQLPORT> -u <MYSQLUSER> -p <MYSQLDATABASE> < chopin_db.sql
```

## 6. Connect your domain

Point `zongjiezhang.com` to this Flask service.

Then the site structure will be:

- `/` -> personal homepage
- `/project` -> project area
- `/game` -> game area
- `/project/chopin` -> Chopin project

## 7. What to test after deploy

1. Homepage opens.
2. `/project/chopin` opens.
3. Search works.
4. Login / register.
5. Favorites.
6. Playlist save / delete.
7. Audio files and score PDFs load correctly.
