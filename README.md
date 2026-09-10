# FYP Project
# Student GPA Analysis and Prediction System

The system allows students to upload academic transcripts in PDF format, where relevant information such as course details, grades, GPA, and CGPA are automatically extracted and processed. Students can review and verify the extracted data before it is stored in the database to ensure accuracy.


The system provides several analytical features, including GPA progression visualisation, CGPA prediction, benchmarking against students from the same department and batch, and academic strength and weakness analysis. In addition, it includes a career recommendation component that identifies potential career pathways based on students' academic performance and skill profiles derived from completed courses.

Tech Stack
- Frontend: HTML, CSS, JavaScript, Bootstrap
- Backend: Python Flask
- Database: Supabase, Cloudinary
- AI Integration: Google Gemini API
- Data Visualization: Chart.js

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in real values (a free-tier account works for each service):
   ```
   copy .env.example .env
   ```
   - `DATABASE_URL` — a PostgreSQL connection string (e.g. from [Supabase](https://supabase.com))
   - `GEMINI_API_KEY` — from [Google AI Studio](https://aistudio.google.com/apikey)
   - `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` — from your [Cloudinary](https://cloudinary.com) dashboard
   - `MAIL_PASSWORD` — a Gmail app password for the sender account configured in `config.py`
   - `SECRET_KEY` — any long random string

3. Run the app:
   ```
   python app.py
   ```
## Deployment

The application is served in production using Gunicorn through the
`Procfile`, rather than Flask's development server.

Before deployment, configure all required environment variables on the
hosting platform, including:

- `FLASK_ENV=production`
- Database configuration
- Gemini API credentials
- Cloudinary credentials
- Secret key
- Other required `.env` variables

`FLASK_ENV=production` enables secure session cookies for HTTPS deployments.
For local development, leave it unset when running over plain HTTP.

The application uses a single Gunicorn worker with four threads
(`--workers 1 --threads 4`) to maintain consistent in-process rate
limiting.

`.python-version` / `runtime.txt` pin the Python interpreter to 3.13.5,
the version this app is actually developed and tested against. Without
this, Render's auto-detected default can drift to a newer Python release
than any dependency here has been tested with -- this happened once:
Python 3.14 exposed a `Path.__deepcopy__` recursion bug in
`matplotlib==3.10.0` that never surfaces on 3.13, which broke every
report preview/download in production while working fine locally.