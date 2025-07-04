import sys
import time
from collections import deque, namedtuple
from multiprocessing import Manager, Process, Value
import signal

import onnxruntime as ort
from loguru import logger

ort.set_default_logger_severity(4)  # NOQA
logger.add(sys.stdout, format="{level} | {message}")  # NOQA
logger.remove(0)  # NOQA
import cv2
import numpy as np
from omegaconf import OmegaConf


from models.constants_en import classes as classes_en
from models.constants_ru import classes as classes_ru

Gesture = namedtuple("Gesture", ['gloss', 'label', 'score'])

class RecognitionMP(Process):
    def __init__(self, model_path: str, stride:int,  tensors_list, prediction_list, verbose, window_size, language):
        super().__init__()
        self.verbose = verbose
        self.output_names = None
        self.input_shape = None
        self.input_name = None
        self.session = None
        self.model_path = model_path
        self.window_size = window_size
        self.tensors_list = tensors_list
        self.prediction_list = prediction_list
        self.language = language
        self.started = Value("i", 0)
        self.stride = Value("i", stride)
        self.running = Value("i", 1)

    def clear_tensors(self):
        try:
            if self.tensors_list.__len__() > 1:
                for _ in range(self.window_size if self.stride.value is None else self.stride.value):
                    self.tensors_list.pop(0)
        except:
            pass

    def clear_all(self):
        self.tensors_list[:] = []
        self.prediction_list[:] = []

    def terminate(self):
        self.running.value = 0

    def run(self):
        if self.session is None:
            logger.info(f" --- Recognizer started...")
            providers = ["CUDAExecutionProvider" if ort.get_device() == "GPU" else "CPUExecutionProvider"]
            logger.info(f" --- Running on {providers}")
            opts = ort.SessionOptions()
            opts.inter_op_num_threads = 2
            self.session = ort.InferenceSession(self.model_path, providers=providers, sess_options=opts)
            self.input_name = self.session.get_inputs()[0].name
            self.input_shape = self.session.get_inputs()[0].shape
            self.output_names = [output.name for output in self.session.get_outputs()]
            self.started.value = 1
            logger.info(f" --- Recognizer started successfully")

        while self.running.value:
            if len(self.tensors_list) >= self.window_size:
                len_tensor_list = len(self.tensors_list)
                input_tensor = np.stack(self.tensors_list[: self.window_size], axis=0)[None]
                self.clear_tensors()
                st = time.time()
                outputs = self.session.run(self.output_names, {self.input_name: input_tensor.astype(np.float32)})[0][0]
                et = round(time.time() - st, 3)

                best_indx = outputs.argmax()

                if self.language == "ru":
                    gloss = classes_ru[best_indx]
                elif self.language == "en":
                    gloss = classes_en[best_indx]
                else:
                    gloss = classes_ru[best_indx]

                self.prediction_list.append(Gesture(gloss=gloss, label=best_indx, score=outputs[best_indx]))

                if self.verbose:
                    logger.info(
                        f"- Prediction time {et}, new gloss: {gloss} , score: {outputs[best_indx]}")
                    logger.info(f" --- {len_tensor_list} frames in queue")
            else:
                time.sleep(0.01)

        logger.info("Recognition process stopped")

class Runner:
    def __init__(
            self,
            config: OmegaConf = None,
            verbose: bool = True,
            language: str = "ru"
    ) -> None:
        self.manager = Manager()
        self.tensors_list = self.manager.list()
        self.prediction_list = self.manager.list()
        self.frame_counter = 0
        self.frame_interval = config.frame_interval
        self.stride = config.stride
        self.model_path = config.model_path
        self.mean = config.mean
        self.std = config.std
        self.threshold = config.threshold
        self.window_size = config.window_size
        self.x = 300 / 2 - 224 / 2
        self.y = 300 / 2 - 224 / 2
        self.language = language

        self.recognizer = RecognitionMP(
            model_path=self.model_path,
            stride=self.stride,
            tensors_list=self.tensors_list,
            prediction_list=self.prediction_list,
            verbose=verbose,
            window_size=self.window_size,
            language=self.language
        )
        logger.info(f" --- Recognizer process...")
        self.recognizer.start()

    def terminate(self):
        if self.recognizer:
            self.recognizer.terminate()
            self.recognizer.join(timeout=2.0)
            if self.recognizer.is_alive():
                self.recognizer.terminate()
            self.recognizer = None

    def clear_all(self):
        if self.recognizer:
            self.recognizer.clear_all()

    def add_frame(self, image):
        self.frame_counter += 1
        if self.frame_counter == self.frame_interval:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            image = self.resize(image, (224, 224))

            mean = np.array(self.mean).reshape(1, 1, 3)
            std = np.array(self.std).reshape(1, 1, 3)
            image = (image.astype(np.float32) - mean) / std

            image = np.transpose(image, [2, 0, 1])
            self.tensors_list.append(image)
            self.frame_counter = 0

    @staticmethod
    def resize(im, new_shape=(224, 224)):
        shape = im.shape[:2]
        if isinstance(new_shape, int):
            new_shape = (new_shape, new_shape)

        r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
        new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
        dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]

        dw /= 2
        dh /= 2

        if shape[::-1] != new_unpad:
            im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        im = cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114))
        return im
