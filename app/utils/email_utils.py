import logging
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from dotenv import load_dotenv

load_dotenv()

class EmailSender:
    def __init__(self):
        self.sender_email = os.getenv("EMAIL_SENDER_EMAIL")
        self.sender_password = os.getenv("EMAIL_SENDER_PASSWORD")
        self.smtp_server = os.getenv("EMAIL_SMTP_SERVER")
        self.smtp_port = os.getenv("EMAIL_SMTP_PORT")
        self.receiver_emails = os.getenv("EMAIL_RECEIVER_EMAIL")
        self.subject = os.getenv("EMAIL_SUBJECT")
        self.cc_emails = os.getenv("EMAIL_CC")

    def generate_authorization_email(self, claim_ids):
        if not claim_ids:
            raise ValueError("Claims ID 列表不能为空")

        def safe_get_claim_id(item):
            if isinstance(item, dict):
                return item.get("claim_id", "未知ID")
            elif hasattr(item, "claim_id"):
                return getattr(item, "claim_id", "未知ID")
            else:
                return "未知ID"

        claims_list = ["    - " + safe_get_claim_id(cid) for cid in claim_ids]
        claims_str = "\n".join(claims_list)

        template = f"""\
     尊敬的老师

     您好！

     附件为AI辅助完成的预授权审核结果，供您参考。
     以下为本次涉及的 Claims ID:\n{claims_str}
     本次审核结果已综合参考用户就诊信息、保险条款、特约条款及账户余额等关键要素，供您审阅。
     如有任何疑问或反馈，烦请不吝指正，我们将持续改进模型能力。

     感谢您的支持！"""

        return template.strip()

    def send_email(self, claim_ids, attachment_path=None):
        if isinstance(self.receiver_emails, str):
            self.receiver_emails = [email.strip() for email in self.receiver_emails.split(',')]

        cc_emails = []
        if self.cc_emails:
            if isinstance(self.cc_emails, str):
                cc_emails = [email.strip() for email in self.cc_emails.split(',')]
            else:
                cc_emails = self.cc_emails

        msg = MIMEMultipart()
        msg['From'] = self.sender_email
        msg['To'] = ', '.join(self.receiver_emails)

        if cc_emails:
            msg['CC'] = ', '.join(cc_emails)

        msg['Subject'] = self.subject

        body = self.generate_authorization_email(claim_ids)
        msg.attach(MIMEText(body, 'plain'))

        if attachment_path:
            if not os.path.isfile(attachment_path):
                logging.error(f" 文件不存在：{attachment_path}")
                return False

            try:
                with open(attachment_path, "rb") as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
                msg.attach(part)
            except Exception as e:
                logging.error(f" 添加附件失败: {e}")
                return False

        all_recipients = self.receiver_emails + cc_emails

        try:
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, all_recipients, msg.as_string())
            logging.info(" 邮件发送成功！")
            return True
        except Exception as e:
            logging.error(f" 邮件发送失败: {e}")
            return False