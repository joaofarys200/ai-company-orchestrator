import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
from backend.websocket.context import WebSocketSessionState
from backend.websocket.handlers.chat import ChatWebSocketHandler
from backend.websocket.handlers.common import WebSocketRuntimeCallbacks


class ChatAttachmentsHandlerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_agents = MagicMock()
        self.mock_database = MagicMock()
        self.mock_database.create_session.return_value = MagicMock(id=99)
        self.mock_connections = MagicMock()
        self.mock_connections.send = AsyncMock()
        self.mock_connections.broadcast = AsyncMock()
        
        self.callbacks = MagicMock(spec=WebSocketRuntimeCallbacks)
        self.callbacks.conversation_history = []
        self.callbacks.parse_file_context = MagicMock(side_effect=lambda p: p)
        self.callbacks.broadcast_state = AsyncMock()
        self.callbacks.run_orchestration_task = AsyncMock()
        
        self.mock_logger = MagicMock()
        self.handler = ChatWebSocketHandler(
            agents=self.mock_agents,
            database=self.mock_database,
            connections=self.mock_connections,
            callbacks=self.callbacks,
            logger=self.mock_logger,
        )
        self.session = WebSocketSessionState()
        self.mock_ws = MagicMock()

    async def test_directive_with_document_attachment_injects_delimited_context(self):
        message = {
            "type": "directive",
            "text": "Analisa o relatório de vendas",
            "attachments": [
                {
                    "id": "att-1",
                    "name": "vendas.csv",
                    "type": "document",
                    "size": 150,
                    "textContent": "produto,valor\nitemA,100\nitemB,250",
                }
            ],
        }

        await self.handler.directive(self.mock_ws, message, self.session)

        # Allow spawned task to run
        await asyncio.sleep(0.01)

        # Check conversation history has injected context
        history = self.callbacks.conversation_history
        self.assertEqual(len(history), 1)
        user_msg = history[0]["content"]
        self.assertIn("Analisa o relatório de vendas", user_msg)
        self.assertIn("--- Conteúdo do Anexo [DOCUMENT: vendas.csv (150 bytes)] ---", user_msg)
        self.assertIn("produto,valor\nitemA,100\nitemB,250", user_msg)

        # Check confirmation sent over websocket
        self.mock_connections.send.assert_awaited()
        sent_calls = [call.args[1] for call in self.mock_connections.send.await_args_list]
        self.assertTrue(
            any("1 anexo(s) integrados com sucesso" in str(c.get("content")) for c in sent_calls)
        )

    async def test_directive_with_image_attachment_injects_multimodal_notice(self):
        message = {
            "type": "directive",
            "text": "Explica o diagrama da arquitetura",
            "attachments": [
                {
                    "id": "att-img-1",
                    "name": "arquitetura.png",
                    "type": "image",
                    "size": 52400,
                    "dataUrl": "data:image/png;base64,iVBORw0KGgo...",
                }
            ],
        }

        await self.handler.directive(self.mock_ws, message, self.session)
        await asyncio.sleep(0.01)

        history = self.callbacks.conversation_history
        self.assertEqual(len(history), 1)
        user_msg = history[0]["content"]
        self.assertIn("--- Anexo [IMAGEM MULTIMODAL: arquitetura.png (52400 bytes)] ---", user_msg)

    async def test_large_attachment_truncated_safely(self):
        massive_text = "A" * 20000
        message = {
            "type": "directive",
            "text": "Resume o log gigante",
            "attachments": [
                {
                    "id": "att-big",
                    "name": "log_gigante.txt",
                    "type": "document",
                    "size": len(massive_text),
                    "textContent": massive_text,
                }
            ],
        }

        await self.handler.directive(self.mock_ws, message, self.session)
        await asyncio.sleep(0.01)

        history = self.callbacks.conversation_history
        user_msg = history[0]["content"]
        self.assertIn("[truncado para 15000 caracteres para preservar orçamento de contexto]", user_msg)


if __name__ == "__main__":
    unittest.main()
