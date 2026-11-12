# Creative Approval Portal

A Flask portal for static ad production. A client reviewer submits a brief, a
designer uploads a draft, the reviewer requests changes or approves, and the
manager delivers the approved files to the client.

Web Engineering CSE601330 — Flask project.

## What it does

| Role | What they can do |
| --- | --- |
| Manager | Manage accounts and client records, set up campaigns, assign work and reviewers, and send approved delivery batches. |
| Designer | Read submitted briefs for their team, update assigned tasks, upload drafts, and submit a version for review. |
| Client reviewer | Create briefs for their organisation, review assigned versions, request changes or approve, and acknowledge deliveries. |

The database holds **40 related SQLAlchemy tables**, and every one of them has a
create, read, update and delete screen. `docs/SCHEMA.md` lists each table, its
fields and the page that owns it.

## Requirements

Python 3.12 or newer, Flask, Flask-SQLAlchemy and SQLite. Pages are rendered
with Jinja2 and styled with plain CSS. No JavaScript is needed.

## Setup

```bash
git clone <this repository> creative-approval
cd creative-approval
python -m venv .venv
```

Activate the environment.

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
source .venv/bin/activate
```

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

## Configuration

The app reads one environment variable, `PORTAL_SECRET_KEY`, and refuses to
start without it. It signs the session cookie, so reuse the same value across
restarts if you want open sessions to stay valid, and keep it out of source
control.

Windows PowerShell:

```powershell
$env:PORTAL_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
```

macOS or Linux:

```bash
export PORTAL_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
```

Other settings live in `portal/__init__.py`: the SQLite database in the Flask
instance folder, an 8 MB request cap for uploads, and HTTP-only, SameSite=Lax
session cookies. Set `SESSION_COOKIE_SECURE=True` when serving over HTTPS.

## Create the database and start the site

```bash
python -m flask --app portal init-db
```

```bash
python -m flask --app portal seed-demo
```

```bash
python -m flask --app portal run --debug
```

`init-db` reports `40 tables created or already present`. `seed-demo` asks for
a password and uses it for every demo account. Open
<http://127.0.0.1:5000/login>.

### Demo logins

All three accounts use the password you typed at the seed prompt.

| Email | Role |
| --- | --- |
| `manager@example.test` | Manager (Dana Price) |
| `designer@example.test` | Designer (Sam Ortiz), member of Studio One |
| `client@example.test` | Client reviewer (Riya Khan), Northwind Coffee, may approve |
| `client2@example.test` | Client reviewer (Tom Lund), Lumen Fitness — used to show scope checks |

The seed also creates the Northwind Roast brand, the Autumn Roast Launch
campaign, an Instagram feed channel, a Square 1080 format, a submitted brief
with a requirement and a deliverable, and a task assigned to the designer.

`seed-starter` is the smaller command from the build guide: it creates only
`manager@example.test` and one `Demo Client` record.

## Run the tests

```bash
python -m unittest discover -s tests
```

The suite builds a fresh in-memory database and a temporary upload folder for
each test. It checks the 40-table schema, foreign-key enforcement, sign-in,
session and role rules, brand CRUD with its validation and uniqueness errors,
Post/Redirect/Get, cross-parent validation, uploads (valid, wrong extension,
contents that do not match the extension, scoped downloads, deletion), the full
approval and delivery path, and that every screen renders for the role that
owns it.

## How the code is organised

```
portal/
  __init__.py      application factory, blueprint registration, CLI commands
  extensions.py    the SQLAlchemy object
  security.py      session helpers, CSRF protection, role decorators
  access.py        scope rules: which campaign records an account may touch
  workflow.py      derived version status and the allowed values
  forms.py         field descriptions and server-side validation
  resources.py     the record registry that drives the shared CRUD screens
  commands.py      seed-starter and seed-demo
  models/          the 40 tables, grouped by area
  views/           auth, dashboard, settings, clients, campaigns, briefs,
                   creatives, reviews, deliveries, manage
  templates/       base.html, macros.html and one folder per screen group
  static/app.css   layout and form styles
tests/             the unittest suite
docs/SCHEMA.md     the 40 tables and the page that owns each one
```

Routes follow one pattern: `GET` reads, `GET` and `POST` on the same URL for a
form, and `POST` for deletes, workflow actions and sign-out. Record routes use
integer path converters. A successful `POST` redirects to a `GET` with a flash
message, so refreshing never repeats a write. An invalid `POST` re-renders the
form with status 400, the message and the submitted values.

`portal/resources.py` describes each ordinary table once — its fields, list
columns, access rule and parent page — and `portal/views/manage.py` turns that
description into the create, edit and delete screens. Screens with their own
business rules (uploads, review decisions, deliveries, and Brand, which is
written out in long form in `portal/views/campaigns.py`) have dedicated views.

## The approval flow

| Visible state | Database condition | Available action |
| --- | --- | --- |
| Draft | Version has no review round. | Designer adds a preview and submits the version. |
| In review | Round exists and has no decision. | Assigned reviewers comment. An eligible reviewer decides. |
| Changes requested | Decision outcome is `changes_requested`. | Designer creates the next version. |
| Approved | Decision outcome is `approved`. | Manager adds the version to a delivery batch. |
| Delivered | Approved version appears in a sent batch. | Client opens the batch and records receipt. |

Rules the server enforces: a brief needs a requirement and a deliverable before
it can be submitted; a creative can only start under a submitted brief; a
version needs a preview image before review; a new version is allowed only
after changes were requested; one decision per round, with a note required for
`changes_requested`; only a reviewer who is a client member with `can_approve`
and an assignment with `can_decide` may decide; only approved versions of the
same campaign can be delivered; and one receipt per batch and recipient.
Reviewed versions and sent batches cannot be deleted, so history stays intact.

## Uploads

Images are stored in `instance/uploads` and are never served from the package.
The view accepts PNG and JPEG only, checks the file signature against the
extension, stores the file under a random UUID name, keeps the cleaned original
as the display name, and records the type and size. `GET /files/<id>` checks
access through the version, creative, deliverable, brief and campaign before
sending the file, and adds `X-Content-Type-Options: nosniff`. Deleting a draft
file commits the record deletion first, then removes the stored bytes.

## Security notes

Every `POST` carries a per-session token that the server compares before the
request is handled. Guests are redirected to `/login`, a disallowed role gets
403, and a record outside the account's scope gets 404. Passwords are stored as
Werkzeug hashes. Foreign keys are enforced on every SQLite connection, so a
parent with dependent rows cannot be deleted; the view rolls back and explains
what to remove first.

## Five minute demo

1. Sign in as the manager. Show the seeded campaign, then create, rename and
   delete a temporary brand.
2. Sign in as the client. Submit a brief and show the server-side error on a
   blank required field.
3. As the designer, upload version 1 and submit it. As the client, request
   changes. Upload version 2 and approve it. Show both versions with their
   decisions.
4. As the manager, build and send a delivery batch. As the client, acknowledge
   it. Finish with the table count from `init-db` and this README.

## Demo deployment

The portal also runs on Vercel as a serverless function. Vercel's Flask
preset serves the WSGI app exported by `app.py` in the project root. That
host has a read-only filesystem apart from a scratch directory, so the
deployment is a **demo only**:

- `PORTAL_DATA_DIR=/tmp/portal` puts the SQLite file and uploads in the one
  writable place.
- `PORTAL_DEMO_SEED=1` builds the schema and the demo records on an empty
  scratch directory, which happens on every cold start.
- Anything created through the deployed site — briefs, versions, uploads,
  decisions — is therefore lost when the instance recycles, and the site
  returns to the same seeded state.

Sign in there with `manager@example.test`, `designer@example.test` or
`client@example.test` and the password in `PORTAL_DEMO_PASSWORD`
(`demo-pass-123` unless the deployment overrides it).

For a deployment that keeps its data, point `SQLALCHEMY_DATABASE_URI` at a
managed Postgres database and store uploaded images in the database or an
object store instead of `instance/uploads`. The local SQLite setup described
above is what the assignment asks for and is unaffected by any of this.

## Credits

The application factory, the security helpers and the Brand CRUD module follow
the structure given in the course build guide (*Creative Approval Portal —
Flask Project Build Guide*, Web Engineering CSE601330). Everything else is
written for this project.
