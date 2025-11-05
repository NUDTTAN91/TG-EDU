import sqlite3

conn = sqlite3.connect('storage/data/homework.db')
cursor = conn.cursor()

# 查询学生188的所有评分记录
cursor.execute("""
    SELECT student_id, assignment_id, grade, original_grade, discount_rate, is_makeup 
    FROM assignment_grade 
    WHERE student_id = 188
    ORDER BY updated_at DESC
    LIMIT 5
""")

results = cursor.fetchall()
if results:
    print(f"找到 {len(results)} 条记录：")
    for result in results:
        print(f"\n学生ID: {result[0]}")
        print(f"作业ID: {result[1]}")
        print(f"数据库中的grade字段: {result[2]}")
        print(f"原始分数: {result[3]}")
        print(f"折扣率: {result[4]}%" if result[4] else "折扣率: 无")
        print(f"是否补交: {result[5]}")
        if result[3] and result[4]:
            print(f"计算验证: {result[3]} × {result[4]}% = {result[3] * result[4] / 100}")
else:
    print("未找到学生188的评分记录")

conn.close()
