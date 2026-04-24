"""台股戰情中心 API 套件

從 api_server.py 拆分出來的模組化 API 定義。結構：
- response.py: 自訂 Response class
- state.py:    全域單例（loader 等）
- deps.py:     FastAPI 依賴（API Key 驗證）
- routers/:    各主題 APIRouter

api_server.py 仍為進入點，負責建立 FastAPI app、middleware 與掛載 routers。
"""
