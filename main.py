import json
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Adiciona o middleware CORS
app.add_middleware(
    CORSMiddleware,
    # Permite todas as origens. Ajuste conforme necessário.
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos os métodos.
    allow_headers=["*"],  # Permite todos os headers.
)

templates = Jinja2Templates(directory="templates")

# Monta a pasta "static" no caminho "/static"
app.mount("/static", StaticFiles(directory="static"), name="static")


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str, nickname: str = "", client_id=0, sender: WebSocket = None):
        for connection in self.active_connections:
            if connection != sender:
                await connection.send_text(json.dumps({"nickname": nickname, "message": message, "client_id": client_id}))


manager = ConnectionManager()


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("start.html", context={"request": request})


@app.get("/chat")
async def get(request: Request, nickname: str = ""):
    return templates.TemplateResponse("index.html", context={"request": request, "name": nickname})


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket)

    # Espera pela primeira mensagem após a conexão, que deve conter o nickname
    data = await websocket.receive_text()
    data_dict = {}
    if data:
        try:
            data_dict = json.loads(data)
        except json.JSONDecodeError:
            print(f"Failed to decode JSON: {data}")
            await manager.send_personal_message("Erro: Mensagem não está no formato correto.", websocket)
            return  # Encerre a conexão se a primeira mensagem não for válida

    nickname = data_dict.get("nickname", "Anonymous")

    # Envie a notificação de que o usuário entrou no chat
    await manager.broadcast("entrou no chat!", nickname, client_id)

    message = data_dict.get("message", "")
    if message:
        await manager.broadcast(message, nickname, client_id)

    try:
        while True:
            data = await websocket.receive_text()
            data_dict = {}
            if data:
                try:
                    data_dict = json.loads(data)
                except json.JSONDecodeError:
                    print(f"Failed to decode JSON: {data}")
                    await manager.send_personal_message("Erro: Mensagem não está no formato correto.", websocket)
                    continue  # Skip to the next iteration

            message = data_dict.get("message", "")
            if message:
                await manager.broadcast(message, nickname, client_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast("saiu do chat!", nickname, client_id)
    except Exception as e:
        print(e)
