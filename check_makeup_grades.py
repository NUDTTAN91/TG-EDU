#!/usr/bin/env python3
from app import create_app, db
from app.models import AssignmentGrade

app = create_app()
with app.app_context():
    grades = AssignmentGrade.query.filter_by(is_makeup=True).all()
    if not grades:
        print("没有找到补交评分记录")
    else:
        print(f"找到 {len(grades)} 条补交评分记录：")
        for g in grades:
            print(f"  Student ID: {g.student_id}")
            print(f"  Grade (存储在数据库): {g.grade}")
            print(f"  Original Grade: {g.original_grade}")
            print(f"  Discount Rate: {g.discount_rate}")
            print(f"  ---")
