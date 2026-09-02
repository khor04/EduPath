from flask import Flask, render_template
from config import Config
from extensions import db, login_manager, mail

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    mail.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        from models.users import User
        return User.query.get(int(user_id))

    # Register blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.transcript import transcript_bp
    from routes.record import record_bp
    from routes.analysis import analysis_bp
    from routes.career import career_bp
    from routes.benchmark import benchmark_bp
    from routes.profile import profile_bp
    from routes.info import info_bp
    from routes.chat import chat_bp


    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(transcript_bp)
    app.register_blueprint(record_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(career_bp)
    app.register_blueprint(benchmark_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(info_bp)
    app.register_blueprint(chat_bp)


    # Landing page only
    @app.route("/")
    def landing():
        return render_template("landing.html")

    # Create database tables
    with app.app_context():
        from models.users import User
        from models.transcript import Transcript
        from models.semester import Semester
        from models.course import Course
        from models.skill_profile import SkillProfile
        from models.career_recommendation import CareerRecommendation
        from models.target_cgpa import TargetCGPA
        from models.feedback import Feedback
        from models.contact import ContactMessage
        from models.course_skill_mapping import CourseSkillMapping
        from models.programme_course_relevance import ProgrammeCourseRelevance
        from models.onet_occupation import OnetOccupation
        from models.onet_occupation_concept import OnetOccupationConcept

        db.create_all()
        print("✅ Database tables created successfully")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)