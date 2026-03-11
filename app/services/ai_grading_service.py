"""AI 自动评分服务 - 调用 DeepSeek API 进行作业评分"""
import json
import os
from flask import current_app
from openai import OpenAI


class AIGradingService:
    """AI 评分服务类"""
    
    @staticmethod
    def get_client():
        """获取 DeepSeek API 客户端"""
        api_key = current_app.config.get('DEEPSEEK_API_KEY', '')
        base_url = current_app.config.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
        
        if not api_key:
            raise ValueError('未配置 DeepSeek API Key，请在 docker-compose.yml 中设置 DeepSeek_API_KEY')
        
        return OpenAI(api_key=api_key, base_url=base_url)
    
    @staticmethod
    def extract_file_content(file_path):
        """
        提取文件内容
        支持：txt, md, py, java, c, cpp, js, html, css, pdf, docx
        """
        if not file_path or not os.path.exists(file_path):
            return None, "文件不存在"
        
        file_ext = os.path.splitext(file_path)[1].lower()
        
        try:
            # 纯文本和代码文件
            text_extensions = ['.txt', '.md', '.py', '.java', '.c', '.cpp', '.h', 
                             '.js', '.ts', '.html', '.css', '.json', '.xml', 
                             '.sql', '.sh', '.yaml', '.yml', '.go', '.rs']
            
            if file_ext in text_extensions:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                return content, None
            
            # PDF 文件
            elif file_ext == '.pdf':
                try:
                    import pdfplumber
                    text_parts = []
                    with pdfplumber.open(file_path) as pdf:
                        for page in pdf.pages:
                            page_text = page.extract_text()
                            if page_text:
                                text_parts.append(page_text)
                    content = '\n'.join(text_parts)
                    return content if content.strip() else (None, "PDF 文件无法提取文本内容")
                except Exception as e:
                    return None, f"PDF 解析失败: {str(e)}"
            
            # Word 文件
            elif file_ext == '.docx':
                try:
                    from docx import Document
                    doc = Document(file_path)
                    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                    content = '\n'.join(paragraphs)
                    return content if content.strip() else (None, "Word 文件无法提取文本内容")
                except Exception as e:
                    return None, f"Word 解析失败: {str(e)}"
            
            # 不支持的格式
            else:
                return None, f"不支持的文件格式: {file_ext}"
                
        except Exception as e:
            return None, f"文件读取失败: {str(e)}"
    
    @staticmethod
    def build_grading_prompt(assignment_title, assignment_description, grading_criteria, student_content, max_score=100):
        """
        构建评分 Prompt
        """
        prompt = f"""你是一位专业的教师，请根据以下评分标准对学生作业进行评分。

【作业题目】
{assignment_title}

【作业要求】
{assignment_description or '无具体要求'}

【评分标准】
{grading_criteria or '请根据作业完成质量、内容完整性、逻辑清晰度进行综合评分'}

【满分】
{max_score} 分

【学生作业内容】
{student_content}

【输出要求】
请以 JSON 格式输出评分结果，格式如下：
{{
    "score": <总分，整数，0-{max_score}>,
    "comment": "<详细评语，说明得分原因和改进建议，100-300字>"
}}

注意：
1. 只输出 JSON，不要输出其他内容
2. score 必须是整数
3. comment 必须详细说明评分理由"""
        
        return prompt
    
    @staticmethod
    def grade_submission(assignment_title, assignment_description, grading_criteria, 
                        student_content, max_score=100):
        """
        调用 AI 进行评分
        
        返回: (score, comment, error)
        """
        try:
            client = AIGradingService.get_client()
            model = current_app.config.get('DEEPSEEK_MODEL', 'deepseek-reasoner')
            
            prompt = AIGradingService.build_grading_prompt(
                assignment_title, 
                assignment_description,
                grading_criteria, 
                student_content, 
                max_score
            )
            
            # 调用 DeepSeek API
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一位专业、公正的教师，擅长评估学生作业并给出建设性的反馈。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # 降低随机性，使评分更稳定
                max_tokens=2000
            )
            
            # 解析响应
            result_text = response.choices[0].message.content.strip()
            
            # 尝试提取 JSON
            # 有时模型会在 JSON 前后添加额外文本，需要提取
            json_start = result_text.find('{')
            json_end = result_text.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = result_text[json_start:json_end]
                result = json.loads(json_str)
                
                score = int(result.get('score', 0))
                comment = result.get('comment', '')
                
                # 确保分数在有效范围内
                score = max(0, min(score, max_score))
                
                return score, comment, None
            else:
                return None, None, "AI 返回格式错误，无法解析评分结果"
                
        except json.JSONDecodeError as e:
            current_app.logger.error(f"AI 评分 JSON 解析失败: {e}, 原始响应: {result_text}")
            return None, None, f"AI 返回格式错误: {str(e)}"
        except ValueError as e:
            return None, None, str(e)
        except Exception as e:
            current_app.logger.error(f"AI 评分失败: {e}")
            return None, None, f"AI 评分失败: {str(e)}"
    
    @staticmethod
    def grade_submission_by_file(assignment_title, assignment_description, grading_criteria,
                                 file_path, max_score=100):
        """
        通过文件路径进行评分（自动提取文件内容）
        
        返回: (score, comment, error)
        """
        # 提取文件内容
        content, extract_error = AIGradingService.extract_file_content(file_path)
        
        if extract_error:
            return None, None, extract_error
        
        if not content or not content.strip():
            return None, None, "文件内容为空"
        
        # 限制内容长度（避免超出 token 限制）
        max_content_length = 50000  # 约 50K 字符
        if len(content) > max_content_length:
            content = content[:max_content_length] + "\n\n[内容过长，已截断...]"
        
        return AIGradingService.grade_submission(
            assignment_title,
            assignment_description,
            grading_criteria,
            content,
            max_score
        )
    
    @staticmethod
    def check_api_available():
        """
        检查 API 是否可用
        
        返回: (is_available, message)
        """
        api_key = current_app.config.get('DEEPSEEK_API_KEY', '')
        
        if not api_key:
            return False, "未配置 DeepSeek API Key"
        
        if api_key == 'your-deepseek-api-key-here':
            return False, "请配置真实的 DeepSeek API Key"
        
        try:
            client = AIGradingService.get_client()
            # 简单测试调用
            response = client.chat.completions.create(
                model=current_app.config.get('DEEPSEEK_MODEL', 'deepseek-reasoner'),
                messages=[{"role": "user", "content": "测试"}],
                max_tokens=10
            )
            return True, "API 连接正常"
        except Exception as e:
            return False, f"API 连接失败: {str(e)}"
