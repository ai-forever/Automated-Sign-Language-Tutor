from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import base64
import cv2
import numpy as np
from omegaconf import OmegaConf
import uvicorn
from loguru import logger
import os

from models import Runner

class Controller:
    def __init__(self, lang='ru'):
        self.current_mode = "LIVE"
        self.current_gloss = None
        self.current_predict = None
        self.language = lang
        self.model_runner = None

    def init_runner(self, config_path):
        try:
            if self.model_runner:
                self.model_runner.terminate()

            conf = OmegaConf.load(config_path)
            self.model_runner = Runner(config=conf, verbose=True, language=self.language)
            while True:
                if self.model_runner.recognizer.started.value:
                    break
            logger.info(f"Model initialized for language: {self.language}")
            return True
        except Exception as e:
            logger.error(f"Error initializing model: {e}")
            return False

    def choose_answer(self):
        if not self.model_runner or not self.model_runner.prediction_list:
            return None

        if len(self.model_runner.prediction_list) < 2:
            return None

        a = self.model_runner.prediction_list[-2]
        b = self.model_runner.prediction_list[-1]

        if b.label == 0:
            return None

        if a.label == b.label:
            if max(a.score, b.score) > self.model_runner.threshold:
                if self.current_predict is not None:
                    if self.current_predict != b.label:
                        self.current_predict = b.label
                        return b.gloss
                else:
                    self.current_predict = b.label
                    return b.gloss

        return None

    def set_new_mode(self, mode):
        if self.model_runner:
            self.model_runner.clear_all()
        self.current_mode = mode
        self.current_predict = None

    def set_new_gloss(self, gloss):
        if self.model_runner:
            self.model_runner.clear_all()
        self.current_gloss = gloss

    def set_language(self, lang):
        self.language = lang
        self.set_new_mode("LIVE")
        self.current_gloss = None
        self.current_predict = None

        config_path = f"models/config_{lang}.yaml"
        if not os.path.exists(config_path):
            logger.error(f"Config file not found for language: {lang}")
            return False

        return self.init_runner(config_path)

    def processing(self, data):
        """
        Process json.

        Parameters
        ----------
        data : json
            json data from frontend.
        """

        msg_type = data.get("type")
        if msg_type == "MODE":
            new_mode = data.get("mode")
            if self.current_mode != new_mode:
                self.set_new_mode(new_mode)
                logger.info(f"New MODE {new_mode} setted correctly")
                return {"status": 200,"message":f"New MODE {new_mode} setted correctly" }
            logger.warning(f"New MODE equal current MODE")
            return {"status": 200,"message":"New MODE equal current MODE"}

        elif msg_type == "LANGUAGE":
            new_lang = data.get("lang")
            if new_lang in ["ru", "en"]:
                success = self.set_language(new_lang)
                if success:
                    return {"status": 200, "message": f"Language changed to {new_lang}"}
                else:
                    return {"status": 500, "message": f"Failed to load model for {new_lang}"}
            else:
                return {"status": 400, "message": "Invalid language"}

        elif msg_type == "GLOSS":
            new_gloss = data.get("gloss").lower()
            if self.current_mode != "TRAINING":
                return {"status": 200,"message":"GLOSS must be set only in TRAINING MODE"}
            else:
                logger.info(f"New GLOSS {new_gloss} setted correctly")
                self.set_new_gloss(new_gloss)
                return {"status": 200,"message":f"New GLOSS {new_gloss} setted correctly"}

        elif msg_type == "IMAGE":
            if not self.model_runner:
                return {"status": 503, "message": "Model not initialized"}

            image_raw = data.get("image")

            if image_raw is not None:
                if image_raw.startswith("data:image"):
                    try:
                        image = base64_to_image(image_raw)
                        self.model_runner.add_frame(image)
                    except Exception as e:
                        logger.error(f"Error processing image: {e}")
                        return {"status": 500, "message": "Error processing image"}
                else:
                    return {"status": 400,"message":"Image raw must be start with data:image"}

        elif msg_type == "repr":
            mess = {
                "current_gloss": self.current_gloss,
                "current_mode": self.current_mode,
                "prediction_list": print(self.model_runner.prediction_list),
                "len_frames": self.model_runner.tensors_list.__len__()
            }
            return mess

        if self.model_runner and (self.current_mode == "TRAINING" and self.current_gloss is not None) or self.current_mode == "LIVE":
            if self.model_runner.prediction_list.__len__() > 1:
                answer = self.choose_answer()
                if answer is not None:
                    return {"text": answer, "type": 'WORD'}

        return {"status":200}

app = FastAPI(
    title="SignFlow",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def base64_to_image(base64_string):
    _, base64_data = base64_string.split(",", 1)
    image_bytes = base64.b64decode(base64_data)
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    return image

@app.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    backend_controller = Controller(lang='ru')

    config_path = "models/config_ru.yaml"
    if not os.path.exists(config_path):
        await websocket.send_json({
            "status": 500,
            "message": "Russian model config not found"
        })
        return

    if not backend_controller.init_runner(config_path):
        await websocket.send_json({
            "status": 500,
            "message": "Failed to initialize Russian model"
        })
        return

    try:
        while True:
            data = await websocket.receive_json()
            answer = backend_controller.processing(data)

            if answer is not None:
                await websocket.send_json(answer)

    except WebSocketDisconnect:
        logger.info("Client disconnected")
        if backend_controller.model_runner:
            backend_controller.model_runner.terminate()
        cv2.destroyAllWindows()
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if backend_controller.model_runner:
            backend_controller.model_runner.terminate()

if __name__ == "__main__":
    uvicorn.run("server_fapi:app", host="localhost", port=3003, reload=True, workers=1)
