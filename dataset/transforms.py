import copy
from PIL import Image
from typing import Optional, List, Tuple, Callable, Union, Dict, Sequence
import numpy as np
import random
import torchvision.transforms as T
from functools import wraps
import torch.nn as nn
import glob
import os
from torchvision.transforms.functional import InterpolationMode
from abc import ABCMeta, abstractmethod

# all methods based on PIL
__all__ = ['color_jitter', # 颜色抖动
           'random_color_jitter',# [随机]颜色抖动
           'random_horizonflip', # [随机]水平翻转
           'random_verticalflip', # [随机]上下翻转
           'random_crop', # [随机]抠图
           'random_augment', # RandAug
           'center_crop', # 中心抠图
           'resize', # 缩放
           'centercrop_resize', # 中心抠图+缩放
           'random_cutout', # 随机CutOut
           'random_cutaddnoise', # 随机CutOut+增加噪音
           'random_affine', # 随机仿射变换
           'to_tensor', # 转Tensor
           'to_tensor_without_div', # 转Tensor不除255
           'normalize', # Normalize
           'random_gaussianblur', # 随机高斯模糊
           'random_autocontrast', # 随机对比度增强
           'random_adjustsharpness', # 随机锐化
           'random_rotate', # 随机(角度)旋转
           'random_invert', # 随机翻转 黑变白 白变黑 这种翻转
           'random_equalize',
           'random_augmix', # 随机样本自混合
           'random_grayscale', # 随机灰度 input几通道 forward也是几通道
           'random_crop_and_resize', # 随机crop再resize
           'pad2square', # 按最大边填充正方向
           'create_AugTransforms',
           'list_augments']

"""
References: https://pytorch.org/vision/stable/auto_examples/transforms/plot_transforms_illustrations.html#sphx-glr-auto-examples-transforms-plot-transforms-illustrations-py
"""

AUG_METHODS = {}
def register_method(fn: Callable):
    key = fn.__name__
    if key in AUG_METHODS:
        raise ValueError(f"An entry is already registered under the name '{key}'.")
    AUG_METHODS[key] = fn
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper

class Cutout:
    """Randomly mask out one or more patches from an image.
    Args:
        n_holes (int): Number of patches to cut out of each image.
        length (int): The length (in pixels) of each square patch.
    """
    def __init__(self, n_holes: int, length: int, ratio: float,
                 h_range: Optional[List[int]] = None, w_range: Optional[List[int]] = None,
                 prob: float = 0.5):
        self.n_holes = n_holes
        self.length = length
        self.ratio = ratio
        self.h_range = h_range
        self.w_range = w_range
        self.prob = prob

    def __call__(self, image):
        """
        Args:
            img (Tensor): Tensor image of size (C, H, W) from PIL
        Returns:
            PIL: Image with n_holes of dimension length x length cut out of it.
        """
        if random.random() > self.prob:
            return image
        img = copy.deepcopy(image) # protect source image

        h = self.h_range if self.h_range is not None else [0, img.height] # PIL Image size->(w,h)
        w = self.w_range if self.w_range is not None else [0, img.width]

        mask_w = int(random.uniform(1-self.ratio, 1+self.ratio) * self.length)
        mask_h = self.length
        mask = Image.new('RGB', size=(mask_w, mask_h), color=0)

        for n in range(self.n_holes):
            # center
            y = np.random.randint(*h)
            x = np.random.randint(*w)

            # left-up
            x1 = max(0, x - self.length // 2)
            y1 = max(0, y - self.length // 2)

            img.paste(mask, (x1, y1))

        return  img

class CutAddNoise:
    """Randomly mask out one or more patches from an image.
    Args:
        n_holes (int): Number of patches to cut out of each image.
        length (int): The length (in pixels) of each square patch.
    """

    def __init__(self, n_holes: int, length: int, noisy_src: str,
                 h_range: Optional[List[int]] = None, w_range: Optional[List[int]] = None,
                 prob: float = 0.5, ):
        self.n_holes = n_holes
        self.length = length
        self.h_range = h_range
        self.w_range = w_range
        self.prob = prob
        self.noisy = glob.glob(f'{noisy_src}/*.jpg')
        assert os.path.splitext(self.noisy[0])[-1] == '.jpg', 'only support .jpg'

    def __call__(self, image):
        """
        Args:
            img (Tensor): Tensor image of size (C, H, W) from PIL
        Returns:
            PIL: Image with n_holes of dimension length x length cut out of it.
        """
        if random.random() > self.prob:
            return image
        img = copy.deepcopy(image)  # protect source image

        h = self.h_range if self.h_range is not None else [0, img.height]  # PIL Image size->(w,h)
        w = self.w_range if self.w_range is not None else [0, img.width]

        noisy_image = Image.open(random.choice(self.noisy)).convert('RGB')
        noisy_image = noisy_image.resize(size=(image.width, image.height))

        for n in range(self.n_holes):
            # center
            y = np.random.randint(*h)
            x = np.random.randint(*w)

            # left-up
            x1 = max(0, x - self.length // 2)
            y1 = max(0, y - self.length // 2)

            # right-bottom
            x2 = min(noisy_image.width, x + self.length // 2)
            y2 = min(noisy_image.height, y + self.length // 2)

            noisy_box = noisy_image.crop((x1, y1, x2, y2))
            img.paste(noisy_box, (x1, y1))

        return img

class CenterCropAndResize(nn.Sequential):
    def __init__(self, center_size, re_size):
        super().__init__(T.CenterCrop(center_size),
                         T.Resize(re_size, interpolation=InterpolationMode.BILINEAR))

class RandomColorJitter(T.ColorJitter):
    def __init__(self, prob: float = 0.5, *args, **kargs):
        super().__init__(*args, **kargs)
        self.prob = prob

    def forward(self, img):
        r = random.random()
        if r < self.prob:
            return super().forward(img)
        else: return img

class PILToTensorNoDiv:
    def __init__(self):
        self.pil2tensor = T.PILToTensor()

    def __call__(self, pic):
        return self.pil2tensor(pic).float()

class BaseClassWiseAugmenter(metaclass=ABCMeta):
    def __init__(self, base_transforms: Dict, class_transforms_mapping: Optional[Dict[str, List[int]]]):
        self.base_transforms = create_AugTransforms(base_transforms)
        if class_transforms_mapping is not None:
            class_transforms = dict()
            for c, t in class_transforms_mapping.items():
                if isinstance(t, str): t = t.split()
                transform = []
                for i in t:
                    transform.append(self.base_transforms.transforms[int(i)])
                class_transforms[c] = T.Compose(transform)
            self.class_transforms = class_transforms
        else:
            self.class_transforms = None

    @abstractmethod
    def __call__(self, image, label: Union[List, int], class_indices: List[int]):
        return self.base_transforms(img=image)

class PadIfNeed:
    def __init__(self, pad_value: Union[int, Sequence], mode: str):
        if isinstance(pad_value, int):
            pad_value = (pad_value, pad_value, pad_value)
        else:
            assert len(pad_value) == 3, 'pad_value 只能是三维向量或int'

        assert mode in ('edge', 'average'), 'mode 只能edge[填一端]和average[填两端]'

        self.pad_value = pad_value
        self.mode = mode

    def __call__(self, image):
        w, h = image.size
        max_size = max(w, h)
        new_im = Image.new('RGB', (max_size, max_size), self.pad_value)
        if self.mode == 'average':
            new_im.paste(image, ((max_size - w) // 2, (max_size - h) // 2))
        else:
            new_im.paste(image, (max_size-w, max_size-h))
        return new_im

@register_method
def random_cutout(n_holes:int = 1, length: int = 200, ratio: float = 0.2,
                  h_range: Optional[List[int]] = None, w_range: Optional[List[int]] = None, prob: float = 0.5):
    return Cutout(n_holes, length, ratio, h_range, w_range, prob)

@register_method
def random_cutaddnoise(n_holes:int = 1, length: int = 200, noisy_src: str = None,
                  h_range: Optional[List[int]] = None, w_range: Optional[List[int]] = None, prob: float = 0.5):
    return CutAddNoise(n_holes, length, noisy_src, h_range, w_range, prob)

@register_method
def color_jitter(brightness: float = 0.1,
                 contrast: float = 0.1,
                 saturation: float = 0.1,
                 hue: float = 0.1):
    return T.ColorJitter(brightness=brightness, contrast=contrast, saturation=saturation, hue=hue)

@register_method
def random_autocontrast(p: float=0.5):
    return T.RandomAutocontrast(p=p)

@register_method
def random_adjustsharpness(sharpness_factor: float=2, p=0.5):
    return T.RandomAdjustSharpness(sharpness_factor, p=p)

@register_method
def random_invert(p: float=0.5):
    return T.RandomInvert(p=p)

@register_method
def random_equalize(p: float=0.5):
    return T.RandomEqualize(p=p)

@register_method
def random_augmix(*args, **kwargs):
    return T.AugMix(*args, **kwargs)

@register_method
def random_crop(*args, **kwargs):
    return T.RandomCrop(*args, **kwargs)
@register_method
def random_color_jitter(prob: float = 0.5, *args, **kwargs):
    # brightness: float = 0.1, contrast: float = 0.1, saturation: float = 0.1, hue: float = 0.1
    return RandomColorJitter(prob = prob, *args, **kwargs)

@register_method
def random_horizonflip(p: float = 0.5):
    return T.RandomHorizontalFlip(p=p)

@register_method
def random_verticalflip(p: float = 0.5):
    return T.RandomVerticalFlip(p=p)

@register_method
def random_rotate(degrees: Union[Sequence, int]):
    return T.RandomRotation(degrees = degrees, interpolation=InterpolationMode.BILINEAR)
@register_method
def to_tensor():
    return T.ToTensor()

@register_method
def to_tensor_without_div():
    return PILToTensorNoDiv()

@register_method
def normalize(mean: Tuple = (0.485, 0.456, 0.406), std: Tuple = (0.229, 0.224, 0.225)):
    return T.Normalize(mean=mean if isinstance(mean, tuple) else eval(mean),
                       std=std if isinstance(std, tuple) else eval(std))

@register_method
def random_augment(num_ops: int = 2, magnitude: int = 9, num_magnitude_bins: int = 31,):
    return T.RandAugment(num_ops=num_ops, magnitude=magnitude, num_magnitude_bins=num_magnitude_bins)

@register_method
def center_crop(size):
    # size (sequence or int): Desired output size of the crop. If size is an
    # int instead of sequence like (h, w), a square crop (size, size) is
    # made. If provided a sequence of length 1, it will be interpreted as (size[0], size[0]).
    return T.CenterCrop(size=size)

@register_method
def resize(size = 224):
    # size (sequence or int) -> square or rectangle: Desired output size. If size is a sequence like
    # (h, w), output size will be matched to this. If size is an int,smaller
    # edge of the image will be matched to this number. i.e,
    # if height > width, then image will be rescaled to (size * height / width, size).
    return T.Resize(size = size, interpolation=InterpolationMode.BILINEAR)

@register_method
def centercrop_resize(center_size: tuple, re_size: tuple):
    return CenterCropAndResize(center_size, re_size)

@register_method
def random_affine(degrees = 0., translate = 0., scale = 0., shear = 0., fill=0, center=None):
    return T.RandomAffine(degrees=degrees, translate=translate, scale=scale, shear=shear, fill=fill, center=center)

@register_method
def random_gaussianblur(prob: float = 0.5, kernel_size=3, sigma=(0.1, 2.0)): # 每次transform sigma会均匀采样一次 除非传sigma是固定值
    return T.RandomApply([T.GaussianBlur(kernel_size=kernel_size, sigma=sigma)], p = prob)

@register_method
def random_grayscale(p: float = 0.5): # 图是几通道 灰度输出也是几通道
    return T.RandomGrayscale(p=p)

@register_method
def random_crop_and_resize(size, *args, **kwargs):
    return T.RandomResizedCrop(size = size, *args, **kwargs)

@register_method
def pad2square(pad_value: Union[int, Sequence] = 0, mode: str = 'average'):
    return PadIfNeed(pad_value, mode)

@register_method
def random_choice(transforms: list):
    return T.RandomChoice(transforms=transforms)

def create_AugTransforms(augments: dict):

    def addAugToSequence(aug_name: str, params: Union[dict, str], aug_list: list) -> None:
        if params == 'no_params':
            aug_list.append(AUG_METHODS[aug_name]())
        else:
            assert isinstance(params, dict), '参数必须以键值对[dict]的形式传进来'
            aug_list.append(AUG_METHODS[aug_name](**params))

    augs = []
    for key, params in augments.items():
        if key == 'random_choice':
            assert isinstance(params, list), 'random_choice必须要把增强方法写成列表形式传进来'
            choice_aug_list = []
            for choice in augments[key]:
                assert isinstance(choice, dict) and len(choice)==1, f'random_choice中每个增强方法都要求是字典 这里{len(params)}个增强需要包装成{len(params)}个字典'
                choice_key, choice_param = tuple(*choice.items())
                addAugToSequence(choice_key, choice_param, choice_aug_list)
            # 把random_choice作为单独的aug加进去
            augs.append(AUG_METHODS[key](choice_aug_list))
        else:
            addAugToSequence(key, params, augs)

    return T.Compose(augs)
    # augments = augments.strip().split()
    # return T.Compose(tuple(map(lambda x: AUG_METHODS[x](**kwargs) if x not in _imgsz_related_methods else AUG_METHODS[x](imgsz, **kwargs), augments)))

def list_augments():
    augments = [k for k, v in AUG_METHODS.items()]
    return sorted(augments)

SPATIAL_TRANSFORMS = set([T.CenterCrop, T.Resize, CenterCropAndResize, T.RandomCrop, T.RandomResizedCrop, PadIfNeed])