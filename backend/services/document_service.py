import os
import markdown
from datetime import datetime
from typing import Dict, Any, List
from ..config import settings
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header


class DocumentService:
    def __init__(self):
        self.output_dir = settings.OUTPUT_DIR
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_merit_markdown(
        self,
        meeting_info: Dict[str, Any],
        hall_info: Dict[str, Any],
        summary: str,
        fundraising_copy: str,
        merit_list: str,
        dialogue_turns: List[Dict[str, Any]] = None,
    ) -> str:
        date_str = meeting_info.get("date", datetime.now()).strftime("%Y年%m月%d日")
        meeting_title = meeting_info.get("title", "寺庙修缮募捐会议")

        dialogue_section = ""
        if dialogue_turns:
            dialogue_section = "\n\n## 会议对话实录\n\n"
            for turn in dialogue_turns:
                speaker = turn.get("speaker", "未知")
                role = turn.get("speaker_role", "")
                content = turn.get("content", "")
                timestamp = turn.get("timestamp", "")
                role_display = f"（{role}）" if role else ""
                dialogue_section += f"> **{speaker}{role_display}** [{timestamp}]：{content}\n\n"

        damage_details = hall_info.get("damage_details", {})
        repair_plan = hall_info.get("repair_plan", {})

        damage_section = ""
        if damage_details:
            damage_section = "### 殿堂病害情况\n\n"
            for key, value in damage_details.items():
                damage_section += f"- **{key}**：{value}\n"

        repair_section = ""
        if repair_plan:
            repair_section = "\n### 修缮方案\n\n"
            for key, value in repair_plan.items():
                repair_section += f"- **{key}**：{value}\n"

        markdown_content = f"""# 【{hall_info.get('name', '古刹殿堂')}】修缮募捐功德纪要

**日期**：{date_str}
**会议**：{meeting_title}

---

## 一、殿堂概况

**名称**：{hall_info.get('name', '')}
**描述**：{hall_info.get('description', '')}
**预估修缮费用**：{hall_info.get('estimated_cost', '待评估')}

{damage_section}
{repair_section}

---

## 二、会议纪要

{summary}

---

## 三、募捐倡议

{fundraising_copy}

---

## 四、功德回向

{merit_list}

{dialogue_section}

---

*本纪要由寺庙修缮募捐系统自动生成*
*愿以此功德，普及于一切，我等与众生，皆共成佛道。*
"""

        return markdown_content

    def save_markdown(self, content: str, filename: str = None) -> str:
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"功德纪要_{timestamp}.md"

        file_path = os.path.join(self.output_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return file_path

    def markdown_to_html(self, markdown_content: str) -> str:
        html_content = markdown.markdown(
            markdown_content,
            extensions=["tables", "fenced_code", "nl2br"],
        )

        styled_html = f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>寺庙修缮募捐功德纪要</title>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&display=swap');
                body {{
                    font-family: 'Noto Serif SC', serif;
                    line-height: 1.8;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    background: linear-gradient(135deg, #fdfbfb 0%, #f5f0e8 100%);
                    color: #4a3728;
                }}
                h1, h2, h3 {{
                    color: #8b4513;
                    border-bottom: 2px solid #d4a574;
                    padding-bottom: 10px;
                    margin-top: 30px;
                }}
                h1 {{
                    text-align: center;
                    font-size: 2em;
                    color: #654321;
                }}
                blockquote {{
                    border-left: 4px solid #b8860b;
                    padding-left: 20px;
                    margin: 20px 0;
                    background: #faf8f5;
                    padding: 15px 20px;
                    border-radius: 0 8px 8px 0;
                }}
                hr {{
                    border: none;
                    border-top: 1px dashed #d4a574;
                    margin: 30px 0;
                }}
                .footer {{
                    text-align: center;
                    color: #8b7355;
                    font-style: italic;
                    margin-top: 50px;
                    padding-top: 20px;
                    border-top: 1px solid #d4a574;
                }}
            </style>
        </head>
        <body>
            {html_content}
            <div class="footer">
                <p>愿以此功德，普及于一切</p>
                <p>我等与众生，皆共成佛道</p>
            </div>
        </body>
        </html>
        """

        return styled_html


class EmailService:
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD

    def send_email(
        self,
        to_emails: List[str],
        subject: str,
        markdown_content: str,
        html_content: str = None,
    ) -> Dict[str, Any]:
        if not self.smtp_host or not self.smtp_user:
            return {
                "success": False,
                "message": "邮件服务未配置",
            }

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = Header(subject, "utf-8")
            msg["From"] = self.smtp_user
            msg["To"] = ", ".join(to_emails)

            plain_part = MIMEText(markdown_content, "plain", "utf-8")
            msg.attach(plain_part)

            if html_content:
                html_part = MIMEText(html_content, "html", "utf-8")
                msg.attach(html_part)

            context = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            context.login(self.smtp_user, self.smtp_password)
            context.sendmail(self.smtp_user, to_emails, msg.as_string())
            context.quit()

            return {
                "success": True,
                "message": f"已成功发送给 {len(to_emails)} 位信众",
                "recipients": to_emails,
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"发送邮件失败: {str(e)}",
            }


document_service = DocumentService()
email_service = EmailService()
