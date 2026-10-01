# Iron Fitness Gym — Django + MySQL

Complete responsive gym website with a Django backend, MySQL support, member accounts, memberships, classes, bookings, contact enquiries and Django Admin.

## Quick start (Windows)

1. Open PowerShell in this folder.
2. Create and activate a virtual environment:
```powershell
python -m venv venv
venv\Scripts\activate
```
3. Install packages:
```powershell
pip install -r requirements.txt
```
4. For the fastest local run, the included `.env` uses SQLite. Then:
```powershell
python manage.py migrate
python manage.py seed_demo_data
python manage.py createsuperuser
python manage.py runserver
```
Open `http://127.0.0.1:8000/`.

## MySQL

Create a database, for example:
```sql
CREATE DATABASE iron_fitness CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'gym_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON iron_fitness.* TO 'gym_user'@'localhost';
FLUSH PRIVILEGES;
```
Copy `.env.example` to `.env` and set:
`DB_ENGINE=mysql`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.
Then run migrations and the seed command.

## Main URLs

- `/` Home
- `/about.html` About
- `/services.html` Services
- `/classes.html` Classes
- `/trainers.html` Trainers
- `/membership.html` Membership
- `/contact.html` Contact
- `/register/` Register
- `/login/` Login
- `/dashboard/` Member dashboard
- `/book/` Class booking
- `/admin/` Admin panel

## Notes

- The visual frontend has been rebuilt with a new responsive CSS design.
- The backend models/forms/admin from the supplied project are connected to the pages.
- Run `python manage.py seed_demo_data` to add starter memberships, trainers and classes.
- Trainer images can be uploaded through Admin.
