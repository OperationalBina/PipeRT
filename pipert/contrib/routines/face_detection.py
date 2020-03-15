import torch
from pipert import Routine
from pipert.core.message import Message
from pipert.utils.structures import Instances, Boxes
from queue import Empty
import time
import cv2


class FaceDetection(Routine):

    def __init__(self, in_queue, out_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.face_cas = None

    def main_logic(self, *args, **kwargs):
        try:
            frame_msg = self.in_queue.get(block=False)
            frame = frame_msg.get_payload()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            faces = self.face_cas.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(20, 20)
            )
            if len(faces):
                faces = torch.from_numpy(faces)
                faces[:, 2:] += faces[:, :2]
                # print(faces.size(), faces)
                new_instances = Instances(frame.shape[:2])
                new_instances.set("pred_boxes", Boxes(faces))
                new_instances.set("pred_classes", torch.zeros(faces.size(0)).int())
            else:
                new_instances = Instances(frame.shape[:2])
                new_instances.set("pred_classes", [])

            try:
                self.out_queue.get(block=False)
                self.state.dropped += 1
            except Empty:
                pass
            pred_msg = Message(new_instances, frame_msg.source_address)
            self.out_queue.put(pred_msg, block=False)

            return True

        except Empty:
            time.sleep(0)
            return False

    def setup(self, *args, **kwargs):
        #TODO need to check why local path not working
        casc_path = "/home/internet/Desktop/pipeFork/PipeRT/pipert/contrib/face_detect/haarcascade_frontalface_default.xml"
        self.face_cas = cv2.CascadeClassifier(casc_path)
        self.state.dropped = 0

    def cleanup(self, *args, **kwargs):
        pass
