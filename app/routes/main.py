"""主路由"""
from flask import Blueprint, render_template
from app.models import Assignment

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    """首页"""
    assignments = Assignment.query.filter_by(
        is_active=True
    ).order_by(Assignment.created_at.desc()).limit(50).all()
    return render_template('index.html', assignments=assignments)
