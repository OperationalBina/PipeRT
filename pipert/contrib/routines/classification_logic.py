import time
from pipert import Routine
from pipert.core import Message
from pipert.core.routine import RoutineTypes
from queue import Empty
import torch
import torchvision


class ClassificationLogic(Routine):
    routine_type = RoutineTypes.PROCESSING

    def __init__(self, in_queue, out_queue, weights, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.weights = weights
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.net = torchvision.models.resnet50(pretrained=False)
        self.transform = torchvision.transforms.Compose(
            [torchvision.transforms.ToTensor(),
             torchvision.transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
        self.net = self.net.to(self.device)
        self.net.fc = torch.nn.Linear(self.net.fc.in_features, 2)
        chkpt = torch.load(self.weights, map_location=self.device)
        chkpt['state_dict'] = \
            {k[4:]: v for k, v in chkpt['state_dict'].items() if self.net.state_dict()[k[4:]].numel() == v.numel()}
        self.net.load_state_dict(chkpt['state_dict'], strict=False)

    def main_logic(self, *args, **kwargs):
        try:
            frame_msg = self.in_queue.get(block=False)
            frame = frame_msg.get_payload()
            frame = self.transform(frame)
            frame = frame.to(self.device)
            frame = frame.unsqueeze(0)
            pred = self.net(frame)
            pred = torch.nn.functional.softmax(pred, dim=1).detach()[0, 1].item()
            pred = str(round(pred, 2))

            try:
                self.out_queue.get(block=False)
                self.state.dropped += 1
            except Empty:
                pass
            pred_msg = Message(pred, frame_msg.source_address)
            self.out_queue.put(pred_msg, block=False)

            return True

        except Empty:
            time.sleep(0)
            return False

    def setup(self, *args, **kwargs):
        self.state.dropped = 0

    def cleanup(self, *args, **kwargs):
        # del self.model, self.device, self.classes, self.colors
        pass

    @staticmethod
    def get_constructor_parameters():
        dicts = Routine.get_constructor_parameters()
        dicts.update({
            "in_queue": "QueueIn",
            "out_queue": "QueueOut",
        })
        return dicts

    def does_routine_use_queue(self, queue):
        return (self.in_queue == queue) or (self.out_queue == queue)