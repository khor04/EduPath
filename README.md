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

