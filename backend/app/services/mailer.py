"""邮件发送抽象：默认 ConsoleMailer 只打印验证码。

后续可新增 ``SmtpMailer`` / ``HttpMailer`` 接入真实 SMTP 或云邮件服务，
并在 ``get_mailer()`` 中按 ``settings.mailer_provider`` 分发。
"""
import logging
from typing import Protocol
from app.core.config import get_settings
logger=logging.getLogger(__name__)
class Mailer(Protocol):
    def send_verification_code(self,email:str,code:str)->str|None: ...
class ConsoleMailer:
    def send_verification_code(self,email:str,code:str)->str:
        logger.info("Verification code for %s: %s",email,code)
        return code
def get_mailer()->Mailer:
    if get_settings().mailer_provider=="console": return ConsoleMailer()
    return ConsoleMailer()
