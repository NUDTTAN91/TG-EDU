"""AI 自动评分服务 - 调用 DeepSeek API 进行作业评分"""
import json
import os
import io
from flask import current_app
from openai import OpenAI


class AIGradingService:
    """АI 评分服务类"""
    
    @staticmethod
    def get_client():
        """获取 DeepSeek API 客户端"""
        api_key = current_app.config.get('DEEPSEEK_API_KEY', '')
        base_url = current_app.config.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
        
        if not api_key:
            raise ValueError('未配置 DeepSeek API Key，请在 docker-compose.yml 中设置 DeepSeek_API_KEY')
        
        return OpenAI(api_key=api_key, base_url=base_url)
    
    @staticmethod
    def ocr_image(image):
        """
        对图片进行 OCR 识别
        
        参数: image - PIL Image 对象
        返回: 识别的文本
        """
        try:
            import pytesseract
            # 使用中文+英文识别
            text = pytesseract.image_to_string(image, lang='chi_sim+eng')
            return text.strip()
        except Exception as e:
            current_app.logger.warning(f"OCR 识别失败: {e}")
            return ""
    
    @staticmethod
    def extract_file_content(file_path):
        """
        提取文件内容（支持 OCR 图片识别）
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
            
            # PDF 文件（文本 + OCR 图片）
            elif file_ext == '.pdf':
                return AIGradingService._extract_pdf_content(file_path)
            
            # Word 文件（文本 + OCR 图片）
            elif file_ext == '.docx':
                return AIGradingService._extract_docx_content(file_path)
            
            # 不支持的格式
            else:
                return None, f"不支持的文件格式: {file_ext}"
                
        except Exception as e:
            return None, f"文件读取失败: {str(e)}"
    
    @staticmethod
    def _extract_pdf_content(file_path):
        """提取 PDF 内容（文本 + OCR 图片）"""
        try:
            import pdfplumber
            from PIL import Image
            
            all_content = []
            
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    page_content = []
                    
                    # 1. 提取页面文本
                    page_text = page.extract_text()
                    if page_text:
                        page_content.append(page_text)
                    
                    # 2. 提取页面图片并 OCR
                    try:
                        images = page.images
                        for img_idx, img in enumerate(images):
                            # 获取图片数据
                            if 'stream' in img:
                                img_data = img['stream'].get_data()
                                pil_image = Image.open(io.BytesIO(img_data))
                                ocr_text = AIGradingService.ocr_image(pil_image)
                                if ocr_text:
                                    page_content.append(f"[图片{img_idx+1}内容]: {ocr_text}")
                    except Exception as e:
                        current_app.logger.warning(f"PDF 页面{page_num} 图片提取失败: {e}")
                    
                    if page_content:
                        all_content.append(f"--- 第{page_num}页 ---\n" + "\n".join(page_content))
            
            content = "\n\n".join(all_content)
            
            # 如果 pdfplumber 提取失败，尝试用 pdf2image 进行整页 OCR
            if not content.strip():
                content = AIGradingService._pdf_full_ocr(file_path)
            
            return (content, None) if content.strip() else (None, "PDF 文件无法提取文本内容")
            
        except Exception as e:
            return None, f"PDF 解析失败: {str(e)}"
    
    @staticmethod
    def _pdf_full_ocr(file_path):
        """将 PDF 每页转为图片进行 OCR（用于扫描件 PDF）"""
        try:
            from pdf2image import convert_from_path
            
            # 将 PDF 转换为图片
            images = convert_from_path(file_path, dpi=200)
            
            all_text = []
            for page_num, image in enumerate(images, 1):
                ocr_text = AIGradingService.ocr_image(image)
                if ocr_text:
                    all_text.append(f"--- 第{page_num}页 ---\n{ocr_text}")
            
            return "\n\n".join(all_text)
        except Exception as e:
            current_app.logger.warning(f"PDF 整页 OCR 失败: {e}")
            return ""
    
    @staticmethod
    def _extract_docx_content(file_path):
        """提取 Word 内容（文本 + OCR 图片）"""
        try:
            from docx import Document
            from PIL import Image
            
            doc = Document(file_path)
            all_content = []
            
            # 1. 提取段落文本
            for para in doc.paragraphs:
                if para.text.strip():
                    all_content.append(para.text)
            
            # 2. 提取图片并 OCR
            img_idx = 0
            for rel in doc.part.rels.values():
                if "image" in rel.target_ref:
                    try:
                        img_idx += 1
                        image_data = rel.target_part.blob
                        pil_image = Image.open(io.BytesIO(image_data))
                        ocr_text = AIGradingService.ocr_image(pil_image)
                        if ocr_text:
                            all_content.append(f"[图片{img_idx}内容]: {ocr_text}")
                    except Exception as e:
                        current_app.logger.warning(f"Word 图片{img_idx} OCR 失败: {e}")
            
            content = "\n".join(all_content)
            return (content, None) if content.strip() else (None, "Word 文件无法提取文本内容")
            
        except Exception as e:
            return None, f"Word 解析失败: {str(e)}"
    
    @staticmethod
    def build_grading_prompt(assignment_title, assignment_description, grading_criteria, student_content, reference_answer=None, max_score=100):
        """
        构建评分 Prompt
        """
        # 基础 Prompt
        prompt = f"""你是一位专业的教师，请根据以下评分标准对学生作业进行评分。

【作业题目】
{assignment_title}

【作业要求】
{assignment_description or '无具体要求'}

【评分标准】
{grading_criteria or '请根据作业完成质量、内容完整性、逻辑清晰度进行综合评分'}"""
        
        # 如果有参考答案，添加到 Prompt
        if reference_answer:
            prompt += f"""

【参考答案】
{reference_answer}

注意：请将学生作业与参考答案进行对比，评估学生答案的正确性和完整性。"""
        
        prompt += f"""

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
                        student_content, reference_answer=None, max_score=100):
        """
        调用 AI 进行评分
        
        返回: dict {success, score, comment, error}
        """
        try:
            client = AIGradingService.get_client()
            model = current_app.config.get('DEEPSEEK_MODEL', 'deepseek-reasoner')
            
            prompt = AIGradingService.build_grading_prompt(
                assignment_title, 
                assignment_description,
                grading_criteria, 
                student_content,
                reference_answer,
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
                
                return {'success': True, 'score': score, 'comment': comment, 'error': None}
            else:
                return {'success': False, 'score': None, 'comment': None, 'error': "AI 返回格式错误，无法解析评分结果"}
                
        except json.JSONDecodeError as e:
            current_app.logger.error(f"AI 评分 JSON 解析失败: {e}, 原始响应: {result_text}")
            return {'success': False, 'score': None, 'comment': None, 'error': f"AI 返回格式错误: {str(e)}"}
        except ValueError as e:
            return {'success': False, 'score': None, 'comment': None, 'error': str(e)}
        except Exception as e:
            current_app.logger.error(f"AI 评分失败: {e}")
            return {'success': False, 'score': None, 'comment': None, 'error': f"AI 评分失败: {str(e)}"}
    
    @staticmethod
    def grade_submission_by_file(assignment_title, assignment_description, grading_criteria,
                                 file_path, reference_answer=None, max_score=100):
        """
        通过文件路径进行评分（自动提取文件内容）
        
        返回: dict {success, score, comment, error}
        """
        # 提取文件内容
        content, extract_error = AIGradingService.extract_file_content(file_path)
        
        if extract_error:
            return {'success': False, 'score': None, 'comment': None, 'error': extract_error}
        
        if not content or not content.strip():
            return {'success': False, 'score': None, 'comment': None, 'error': "文件内容为空"}
        
        # 限制内容长度（避免超出 token 限制）
        max_content_length = 50000  # 约 50K 字符
        if len(content) > max_content_length:
            content = content[:max_content_length] + "\n\n[内容过长，已截断...]"
        
        return AIGradingService.grade_submission(
            assignment_title,
            assignment_description,
            grading_criteria,
            content,
            reference_answer,
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
