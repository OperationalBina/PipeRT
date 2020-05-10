from pipert.contrib.detection_demo.models import *  # set ONNX_EXPORT in models.py
# from detection_demo.utils.datasets import *
from pipert.contrib.detection_demo.utils import *
from pipert.core.message import PredictionPayload
from pipert.utils.structures import Instances, Boxes
from pipert.core import Routine, QueueHandler, RoutineTypes


class YoloV3Logic(Routine):
	routine_type = RoutineTypes.PROCESSING

	def __init__(self, in_queue, out_queue, cfg, names, weights, img_size, conf_thresh, nms_thresh, half, batch,
	             *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.in_queue = QueueHandler(in_queue)
		self.out_queue = QueueHandler(out_queue)
		self.batch = batch
		self.img_size = (320, 192) if ONNX_EXPORT else img_size  # (320, 192) or (416, 256) or (608, 352)
		self.half = half
		self.cfg = cfg
		self.weights = weights
		self.classes = load_classes(names)
		self.colors = [[random.randint(0, 255) for _ in range(3)] for _ in range(len(self.classes))]
		self.conf_thresh = conf_thresh
		self.nms_thresh = nms_thresh
		self.model = None
		self.device = None

	def main_logic(self, *args, **kwargs):
		msgs = self.in_queue.non_blocking_get()
		if msgs:
			if not self.batch:
				msgs = [msgs]

			out_keys = []
			images = []
			for msg in msgs:
				images.append(msg.get_payload())
				if self.batch:
					out_keys.append(msg.out_key)

			im0shape = images[0].shape
			images, *_ = self.letterbox(np.array(images), new_shape=self.img_size)
			imshape = images[0].shape

			# Normalize RGB
			images = images[:, :, :, ::-1].transpose(0, 3, 1, 2)  # BGR to RGB and switch to NxCxWxH
			images = np.ascontiguousarray(images, dtype=np.float16 if self.half else np.float32)  # uint8 to fp16/fp32
			images /= 255.0
			images = torch.from_numpy(images).to(self.device)

			with torch.no_grad():
				preds, _ = self.model(images)

			dets = non_max_suppression(preds, self.conf_thresh, self.nms_thresh)

			results = []
			for det in dets:
				if det is not None and len(det):
					# Rescale boxes from img_size to im0 size
					det[:, :4] = scale_coords(imshape, det[:, :4], im0shape).round()

					res = Instances(im0shape)
					res.set("pred_boxes", Boxes(det[:, :4]))
					res.set("scores", det[:, 4])
					res.set("class_scores", det[:, 5:-1].unsqueeze(1))
					res.set("pred_classes", det[:, -1].round().int())
				else:
					res = Instances(im0shape)
					res.set("pred_boxes", [])
				results.append(res)

			if len(msgs) != len(results):
				self.logger.debug(f"Detections missing!! Got a batch of size {len(msgs)} "
				                  f"but only have {len(results)} results!")

			snd_batch = {}
			for msg, res in zip(msgs, results):
				msg.payload = PredictionPayload(res.to("cpu"))
				if self.batch:
					snd_batch[msg.out_key] = msg

			success = self.out_queue.deque_non_blocking_put(snd_batch if self.batch else msgs[0])
			return success

		else:
			return None

	def setup(self, *args, **kwargs):
		self.state.dropped = 0
		self.device = torch_utils.select_device(force_cpu=ONNX_EXPORT)
		self.model = Darknet(self.cfg, self.img_size)
		if self.weights.endswith('.pt'):  # pytorch format
			self.model.load_state_dict(torch.load(self.weights, map_location=self.device)['model'])
		else:  # darknet format
			_ = load_darknet_weights(self.model, self.weights)
		self.model.fuse()
		self.model.to(self.device).eval()
		# Half precision
		self.half = self.half and self.device.type != 'cpu'  # half precision only supported on CUDA

		if self.half:
			self.model.half()

	def cleanup(self, *args, **kwargs):
		del self.model, self.device, self.classes, self.colors

	@staticmethod
	def get_constructor_parameters():
		dicts = Routine.get_constructor_parameters()
		dicts.update({
			"in_queue": "Queue",
			"out_queue": "Queue",
			"cfg": "str",
			"names": "str",
			"weights": "str",
			"img_size": "int",
			"conf_thresh": "float",
			"nms_thresh": "float",
			"half": "bool",
			"batch": "bool"
		})
		return dicts

	def does_routine_use_queue(self, queue_name):
		return (self.in_queue == queue_name) or (self.out_queue == queue_name)

	@staticmethod
	def letterbox(imgs, new_shape=416, color=(128, 128, 128), mode='auto'):
		# imgs.shape = (NxWxHxC)
		# Resize a rectangular images to a 32 pixel multiple rectangles
		# https://github.com/ultralytics/yolov3/issues/232
		shape = imgs.shape[1:3]  # current shape [height, width]

		if isinstance(new_shape, int):
			ratio = float(new_shape) / max(shape)
		else:
			ratio = max(new_shape) / max(shape)  # ratio  = new / old
		ratiow, ratioh = ratio, ratio
		new_unpad = (int(round(shape[1] * ratio)), int(round(shape[0] * ratio)))

		# Compute padding https://github.com/ultralytics/yolov3/issues/232
		if mode == 'auto':  # minimum rectangle
			dw = np.mod(new_shape - new_unpad[0], 32) / 2  # width padding
			dh = np.mod(new_shape - new_unpad[1], 32) / 2  # height padding
		elif mode == 'square':  # square
			dw = (new_shape - new_unpad[0]) / 2  # width padding
			dh = (new_shape - new_unpad[1]) / 2  # height padding
		elif mode == 'rect':  # square
			dw = (new_shape[1] - new_unpad[0]) / 2  # width padding
			dh = (new_shape[0] - new_unpad[1]) / 2  # height padding
		elif mode == 'scaleFill':
			dw, dh = 0.0, 0.0
			new_unpad = (new_shape, new_shape)
			ratiow, ratioh = new_shape / shape[1], new_shape / shape[0]
		else:
			raise ValueError(f"Unrecognized padding mode {mode}")

		top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
		left, right = int(round(dw - 0.1)), int(round(dw + 0.1))

		reshaped = []
		for img in imgs:
			if shape[::-1] != new_unpad:  # resize
				# INTER_AREA is better, INTER_LINEAR is faster
				img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_AREA)
			img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)  # add border
			reshaped.append(img)

		return np.array(reshaped), ratiow, ratioh, dw, dh
