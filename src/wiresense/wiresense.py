import asyncio
import csv
import json
import logging
import os
import pathlib
import time
from typing import Callable, Dict, List, Any

import aiohttp
import aiohttp.web
import websockets
from aiohttp import web


PATH = str(pathlib.Path("").absolute()).replace("\\", "/")

log = logging.getLogger(__name__)

# Store active WebSocket connections
active_connections = set()


class Wiresense:
    sensors: List["Wiresense"] = []
    configured: bool = False
    clients: List[websockets.WebSocketServerProtocol]

    def __init__(self, name: str, exec_function: Callable[[], Dict[str, Any]], base_file_path: str) -> None:
        """
        Initializes the Wiresense instance.

        :param name: The name of the sensor.
        :param exec_function: The function that reads the sensor value and returns an object with key-value pairs.
        :param base_file_path: The base file path (with extension) for logging sensor data in CSV format.
        """

        self.name: str = ""
        self.exec_function: Callable[[], Dict[str, Any]]

        excluded_chars = ["\n", "\r"]
        if any(sensor.name == name for sensor in Wiresense.sensors):
            raise ValueError(f"Sensor with name '{name}' already exists.")
        elif any(ec in name for ec in excluded_chars):
            excluded_chars_bytes = ", ".join([repr(ec.encode("UTF-8")) for ec in excluded_chars])
            raise ValueError(f"Sensor name cannot include the following chars: {excluded_chars_bytes}")

        self.name = name
        self.exec_function = exec_function
        self.base_file_path = base_file_path
        Wiresense.sensors.append(self)

        # Validate exec_function
        data = exec_function()
        if not isinstance(data, dict) or not data:
            raise ValueError("exec_function must return a non-empty dictionary.")

        base_name, ext = os.path.splitext(self.base_file_path)
        dir_name = os.path.dirname(self.base_file_path)
        os.makedirs(dir_name, exist_ok=True)

        # now_iso = datetime.datetime.now().isoformat()
        timestamp = int(time.time())
        self.csv_file_path = f"{base_name}_{timestamp}{ext}"

        with open(self.csv_file_path, mode="w", newline="", encoding="UTF-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp"] + list(data.keys()))

    @staticmethod
    async def config(options: Dict[str, Any]) -> None:
        """
        Configures the Wiresense library with the specified options.
        :param options: Configuration options (key-value pairs).
        :param options.port: The port for the web server and WebSocket server.
        """

        if not Wiresense.configured:
            log.info("Starting Server...")
            # run_server(port=options.get("port"))
            server_task = asyncio.create_task(_run_async_server(port=options.get("port")))
            await asyncio.gather(server_task)
        else:
            log.info("Server already configured")

    async def execute(self) -> str:
        """
        Runs the sensor's read function and sends the data to the WebSocket server.
        Also logs the data to the specified CSV file.

        :return: The JSON payload as string sent to the WebSocket server.
        """

        if not Wiresense.configured:
            raise RuntimeError("Wiresense is not configured. Call configure() before creating instances.")

        data = self.exec_function()
        if not isinstance(data, dict) or not data:
            raise ValueError("exec_function must return a non-empty dictionary.")

        payload = {"key": self.name, "data": data}
        timestamp = int(time.time())

        with open(self.csv_file_path, mode="a", newline="", encoding="UTF-8") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp] + list(data.values()))

        payload_str = json.dumps(payload)

        await _broadcast(payload_str)
        return payload_str


async def _handle_http_request(request):
    """
    Handles an incoming HTTP request and serves the requested file if it exists.

    :param request: The incoming HTTP request object.
    :return: A web.FileResponse object if the file is found, otherwise raises web.HTTPNotFound.
    """

    url_path = request.match_info.get("path", "")
    url_path = url_path.replace("\r", "\\r").replace("\n", "\\n")
    url_parts = url_path.split("/")

    if len(url_parts) == 2 and url_parts[1] == "data.csv":
        s_name = url_parts[0]
        try:
            file_path = [sensor.csv_file_path for sensor in Wiresense.sensors if sensor.name == s_name][0]
        except IndexError:
            log.info("Sensor not found!")
            raise web.HTTPNotFound()

        if file_path:
            if os.path.isfile(file_path):
                log.info(f"File of Sensor: '{s_name}' send! ('{file_path}')")
                return web.FileResponse(file_path, headers={"Content-Type": "text/csv"})
            else:
                log.error(f"File of Sensor: '{s_name}' does not exist! ('{file_path}')")
                raise web.HTTPInternalServerError()
    else:
        log.info(f"Invalid Path: '{url_path}'")
        raise web.HTTPNotFound()


async def _websocket_handler(request):
    """
    Handles an incoming WebSocket connection.

    This function manages the WebSocket lifecycle, including connection, message handling, and disconnection.

    :param request: The incoming WebSocket request object.
    :return: The WebSocket response object.
    """

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    await _on_connect(ws)

    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            await _on_message(ws, msg.data)
        elif msg.type == aiohttp.WSMsgType.CLOSE:
            await ws.close()
        else:
            log.warning(f"Recieved unknown msg.type: '{msg.type}' from WS Client")

    await _on_disconnect(ws)
    return ws


async def _on_connect(ws):
    """
    Handles a new WebSocket client connection.

    :param ws: The WebSocket connection object.
    """

    active_connections.add(ws)
    log.info(f"WebSocket Client connection established")


async def _on_disconnect(ws):
    """
    Handles the disconnection of a WebSocket client.

    :param ws: The WebSocket connection object.
    """

    active_connections.remove(ws)
    log.info(f"WebSocket Client connection closed")


async def _on_message(ws, message: str):
    """
    Handles an incoming message from a WebSocket client and sends back a response.

    This function is primarily used to verify that the WebSocket communication is working
    by echoing the received message back to the client.

    :param ws: The WebSocket connection object.
    :param message: The message received from the WebSocket client.
    """

    log.info(f"Received message: {message}")
    await ws.send_str(f"Message received!\n{message}")


async def _broadcast(message: str):
    """
    Broadcasts a message to all connected WebSocket clients.

    :param message: The message to broadcast.
    """

    for ws in active_connections:
        await ws.send_str(message)
    log.info("Broadcast message send!")


async def _run_async_server(*, host: str = "0.0.0.0", port: int = 8080):
    """
    Starts the web server with specified host and port.

    The server handles HTTP requests and WebSocket connections.

    :param host: The host address to bind the server to (default is "0.0.0.0").
    :param port: The port number to bind the server to (default is 8080).
    """

    app = web.Application()
    app.router.add_get('/', _websocket_handler)
    app.router.add_get('/{path:.*}', _handle_http_request)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()

    Wiresense.configured = True
    log.info(f"Server Running on: http://{host}:{port}")
