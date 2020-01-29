# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
import numpy as np
import pycocotools.mask as mask_util
from enum import Enum, unique
from pipert.utils.visualizer.visualizer import Visualizer
from pipert.utils.structures import Instances


@unique
class ColorMode(Enum):
    """
    Enum of different color modes to use for instance visualizations.

    Attributes:
        IMAGE: Picks a random color for every instance and overlay segmentations with low opacity.
        SEGMENTATION: Let instances of the same category have similar colors, and overlay them with
            high opacity. This provides more attention on the quality of segmentation.
        IMAGE_BW: same as IMAGE, but convert all areas without masks to gray-scale.
            Only available for drawing per-instance mask predictions.
    """

    IMAGE = 0
    SEGMENTATION = 1
    IMAGE_BW = 2


from pipert.utils.visualizer.colormap import random_color


class _DetectedInstance:
    """
    Used to store data about detected objects in video frame,
    in order to transfer color to objects in the future frames.

    Attributes:
        label (int):
        bbox (tuple[float]):
        mask_rle (dict):
        color (tuple[float]): RGB colors in range (0, 1)
        ttl (int): time-to-live for the instance. For example, if ttl=2,
            the instance color can be transferred to objects in the next two frames.
    """

    __slots__ = ["label", "bbox", "mask_rle", "color", "ttl"]

    def __init__(self, label, bbox, mask_rle, color, ttl):
        self.label = label
        self.bbox = bbox
        self.mask_rle = mask_rle
        self.color = color
        self.ttl = ttl


def _create_text_labels(classes, scores, class_names, ids):
    """
    Args:
        classes (list[int] or None):
        scores (list[float] or None):
        class_names (list[str] or None):
        ids (list[int] or None):

    Returns:
        list[str] or None
    """
    labels = None
    if classes is not None and class_names is not None and len(class_names) > 1:
        labels = [class_names[i] for i in classes]

    if scores is not None:
        if labels is None:
            labels = ["conf: {:.0f}%".format(s * 100) for s in scores]
        else:
            labels = ["{} - conf: {:.0f}%".format(label, s * 100) for label, s in zip(labels, scores)]

    if ids is not None:
        if labels is None:
            labels = ["id: {:.0f}%".format(i) for i in ids]
        else:
            labels = ["{} - id: {}".format(label, i) for label, i in zip(labels, ids)]

    return labels


class VideoVisualizer:
    def __init__(self, metadata, instance_mode=ColorMode.IMAGE):
        """
        Args:
            metadata (MetadataCatalog): image metadata.
        """
        self.metadata = metadata
        self._old_instances = []
        assert instance_mode in [
            ColorMode.IMAGE,
            ColorMode.IMAGE_BW,
        ], "Other mode not supported yet."
        self._instance_mode = instance_mode

    def draw_instance_predictions(self, frame, predictions):
        """
        Draw instance-level prediction results on an image.

        Args:
            frame (ndarray): an RGB image of shape (H, W, C), in the range [0, 255].
            predictions (Instances): the output of an instance detection/segmentation
                model. Following fields will be used to draw:
                "pred_boxes", "pred_classes", "scores", "pred_masks" (or "pred_masks_rle").

        Returns:
            output (VisImage): image object with visualizations.
        """

        frame_visualizer = Visualizer(frame, self.metadata)
        if not predictions.has("pred_boxes") or not predictions.pred_boxes:
            return frame_visualizer.output
        num_instances = len(predictions)
        # if num_instances == 0:
        #     return frame_visualizer.output

        boxes = predictions.pred_boxes.tensor.numpy() if predictions.has("pred_boxes") else None
        scores = predictions.scores if predictions.has("scores") else None
        classes = predictions.pred_classes.numpy() if predictions.has("pred_classes") else None
        keypoints = predictions.pred_keypoints if predictions.has("pred_keypoints") else None
        ids = predictions.track_ids if predictions.has("track_ids") else None

        if predictions.has("pred_masks"):
            masks = predictions.pred_masks
            # mask IOU is not yet enabled
            # masks_rles = mask_util.encode(np.asarray(masks.permute(1, 2, 0), order="F"))
            # assert len(masks_rles) == num_instances
        else:
            masks = None

        detected = [
            _DetectedInstance(classes[i], boxes[i], mask_rle=None, color=None, ttl=8)
            for i in range(num_instances)
        ]
        colors = self._assign_colors(detected)

        labels = _create_text_labels(classes, scores, self.metadata.get("thing_classes", None), ids)

        if self._instance_mode == ColorMode.IMAGE_BW:
            # any() returns uint8 tensor
            frame_visualizer.output.img = frame_visualizer._create_grayscale_image(
                (masks.any(dim=0) > 0).numpy() if masks is not None else None
            )
            alpha = 0.3
        else:
            alpha = 0.5

        frame_visualizer.overlay_instances(
            boxes=None if masks is not None else boxes,  # boxes are a bit distracting
            masks=masks,
            labels=labels,
            keypoints=keypoints,
            assigned_colors=colors,
            alpha=alpha,
        )

        return frame_visualizer.output

    def draw_sem_seg(self, frame, sem_seg, area_threshold=None):
        """
        Args:
            sem_seg (ndarray or Tensor): semantic segmentation of shape (H, W),
                each value is the integer label.
            area_threshold (Optional[int]): only draw segmentations larger than the threshold
        """
        # don't need to do anything special
        frame_visualizer = Visualizer(frame, self.metadata)
        frame_visualizer.draw_sem_seg(sem_seg, area_threshold=None)
        return frame_visualizer.output

    def _assign_colors(self, instances):
        """
        Naive tracking heuristics to assign same color to the same instance,
        will update the internal state of tracked instances.

        Returns:
            list[tuple[float]]: list of colors.
        """

        # Compute iou with either boxes or masks:
        is_crowd = np.zeros((len(instances),), dtype=np.bool)
        if instances[0].bbox is None:
            assert instances[0].mask_rle is not None
            # use mask iou only when box iou is None
            # because box seems good enough
            rles_old = [x.mask_rle for x in self._old_instances]
            rles_new = [x.mask_rle for x in instances]
            ious = mask_util.iou(rles_old, rles_new, is_crowd)
            threshold = 0.5
        else:
            boxes_old = [x.bbox for x in self._old_instances]
            boxes_new = [x.bbox for x in instances]
            ious = mask_util.iou(boxes_old, boxes_new, is_crowd)
            threshold = 0.6
        if len(ious) == 0:
            ious = np.zeros((len(self._old_instances), len(instances)), dtype="float32")

        # Only allow matching instances of the same label:
        for old_idx, old in enumerate(self._old_instances):
            for new_idx, new in enumerate(instances):
                if old.label != new.label:
                    ious[old_idx, new_idx] = 0

        matched_new_per_old = np.asarray(ious).argmax(axis=1)
        max_iou_per_old = np.asarray(ious).max(axis=1)

        # Try to find match for each old instance:
        extra_instances = []
        for idx, inst in enumerate(self._old_instances):
            if max_iou_per_old[idx] > threshold:
                newidx = matched_new_per_old[idx]
                if instances[newidx].color is None:
                    instances[newidx].color = inst.color
                    continue
            # If an old instance does not match any new instances,
            # keep it for the next frame in case it is just missed by the detector
            inst.ttl -= 1
            if inst.ttl > 0:
                extra_instances.append(inst)

        # Assign random color to newly-detected instances:
        for inst in instances:
            if inst.color is None:
                inst.color = random_color(rgb=True, maximum=1)
        self._old_instances = instances[:] + extra_instances
        return [d.color for d in instances]
