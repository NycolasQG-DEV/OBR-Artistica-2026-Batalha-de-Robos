from PySide6.QtWidgets import QTextBrowser, QSizePolicy
from PySide6.QtCore import Qt
from players.base_player import BaseSlidePlayer
from engine.config import SlideConfig

class HTMLSlidePlayer(BaseSlidePlayer):
    def __init__(self, config: SlideConfig, parent=None):
        super().__init__(config, parent)

        self.browser = QTextBrowser(self)
        self.browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.browser.setStyleSheet("""
            QTextBrowser {
                background-color: #111827;
                border: 2px solid rgba(0, 240, 255, 0.2);
                border-radius: 12px;
                padding: 30px;
            }
        """)
        self.layout.addWidget(self.browser)

    async def prepare(self):
        content = self.config.get("content", "<h1>Sem conteúdo HTML</h1>")
        styled_html = f"""
        <html>
        <head>
            <style>
                body {{
                    background-color: #111827;
                    color: #f3f4f6;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                }}
                h1 {{ color: #00f0ff; }}
                h2 {{ color: #ff007f; }}
                p {{ font-size: 18px; line-height: 1.6; }}
            </style>
        </head>
        <body>
            {content}
        </body>
        </html>
        """
        self.browser.setHtml(styled_html)
