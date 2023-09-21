# PyTorch StudioGAN: https://github.com/POSTECH-CVLab/PyTorch-StudioGAN
# The MIT License (MIT)
# See license file or visit https://github.com/POSTECH-CVLab/PyTorch-StudioGAN for details

# src/metrics/preparation.py

from os.path import exists, join
import os

from torch.nn import DataParallel
from torch.nn.parallel import DistributedDataParallel as DDP
from PIL import Image
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.transforms as transforms
import numpy as np

import metrics.model_mae_net as MAE

from metrics.inception_net import InceptionV3
import metrics.fid as fid
import metrics.ins as ins
import utils.misc as misc
import utils.ops as ops
import utils.resize as resize
import clip


class LoadEvalModel(object):
    def __init__(self, eval_backbone, resize_fn, world_size, distributed_data_parallel, device, logger=None):
        super(LoadEvalModel, self).__init__()
        self.eval_backbone = eval_backbone
        self.resize_fn = resize_fn
        
        self.save_output = misc.SaveOutput()

        if device == 0 and logger is not None:
            logger.info(f"Load Evaluation Model using {eval_backbone} backbone.")

        if self.eval_backbone == "MAE":
            self.res, mean, std = 224, [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
            chkpt_dir = '/raid/varsha/MAE/mae_pretrain_vit_base.pth'
            # chkpt_dir = '/raid/varsha/MAE/fine_tuned_ckpt/mae_finetuned_vit_base.pth'
            self.model = MAE.prepare_model(chkpt_dir, 'vit_base_patch16').to(device)
            # self.model = MAE.prepare_model(resize_input=False, normalize_input=False).to(device)
            print("loaded MAE")
        elif self.eval_backbone == "DINO_V2":
            self.res, mean, std = 224, [123.675, 116.28, 103.53], [58.395, 57.12, 57.375]
            self.model = torch.hub.load('facebookresearch/dinov2', 'dinov2_vitb14_lc').to(device)

        elif self.eval_backbone == "Inception_V3":
            self.res, mean, std = 299, [0.5, 0.5, 0.5], [0.5, 0.5, 0.5]
            self.model = InceptionV3(resize_input=False, normalize_input=False).to(device)
        elif self.eval_backbone == "SwAV":
            self.res, mean, std = 224, [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
            self.model = torch.hub.load("facebookresearch/swav", "resnet50").to(device)
            hook_handles = []
            for name, layer in self.model.named_children():
                if name == "fc":
                    handle = layer.register_forward_pre_hook(self.save_output)
                    hook_handles.append(handle)
        elif self.eval_backbone == "CLIP":
            self.res, mean, std = 224, [0.48145466, 0.4578275, 0.40821073], [0.26862954, 0.26130258, 0.27577711]
            self.model = clip.load("ViT-B/32", jit=False)[0].to(device)
        else:
            raise NotImplementedError

        if self.eval_backbone=="CLIP":
            if resize_fn=="legacy":
                self.resizer = resize.make_resizer("PyTorch", 'bicubic', (self.res, self.res))
            else: raise ValueError("CLIP backbone only supports legacy resize_fn")
        else:
            self.resizer = resize.build_resizer(mode=resize_fn, size=self.res)
        self.trsf = transforms.Compose([transforms.ToTensor()])
        self.mean = torch.Tensor(mean).view(1, 3, 1, 1).to("cuda")
        self.std = torch.Tensor(std).view(1, 3, 1, 1).to("cuda")

        if world_size > 1 and distributed_data_parallel:
            misc.make_model_require_grad(self.model)
            self.model = DDP(self.model, device_ids=[device], broadcast_buffers=True)
        elif world_size > 1 and distributed_data_parallel is False:
            self.model = DataParallel(self.model, output_device=device)
        else:
            pass

    def eval(self):
        self.model.eval()

    def get_outputs(self, x, quantize=False):
        if quantize:
            x = ops.quantize_images(x)
        else:
            x = x.detach().cpu().numpy().astype(np.uint8)
        x = ops.resize_images(x, self.resizer, self.trsf, self.mean, self.std)

        if self.eval_backbone == "Inception_V3":
            repres, logits = self.model(x)
        elif self.eval_backbone == "SwAV":
            logits = self.model(x)
            repres = self.save_output.outputs[0][0]
            self.save_output.clear()
        elif self.eval_backbone == "CLIP":
            ## logits are used for calculation of Inception Score(IS), prdc etc, this fucntion provides
            ## only the representations, so only calculation FID for now from CLIP Backbone.
            ## This also throws error when used with MultiGPU, so using only Single GPU to
            ## calculate the FID_Clip or iFID_Clip.
            repres = self.model.encode_image(x)
            ## For now, keeping the logits = repres, which is wrong, but simply passing it here
            ## for the sake of return value. Also, logits are not used in FID Calculation.
            logits = repres 
        elif self.eval_backbone == "MAE":
            repres = self.model(x)
            logits = repres 
        elif self.eval_backbone == "DINO_V2":
            repres = self.model(x)
            logits = repres 

        return repres, logits


def prepare_moments(data_loader, eval_model, quantize, cfgs, logger, device):
    disable_tqdm = device != 0
    eval_model.eval()
    moment_dir = join(cfgs.RUN.save_dir, "moments")
    if not exists(moment_dir):
        os.makedirs(moment_dir)
    moment_path = join(moment_dir, cfgs.DATA.name + "_" + cfgs.RUN.ref_dataset + "_" + \
                       cfgs.RUN.resize_fn + "_" + str(cfgs.DATA.img_size) + "_" + cfgs.RUN.eval_backbone + "_moments.npz")
    is_file = os.path.isfile(moment_path)
    if is_file:
        mu = np.load(moment_path)["mu"]
        sigma = np.load(moment_path)["sigma"]
    else:
        if device == 0:
            logger.info("Calculate moments of {ref} dataset using {eval_backbone} model.".\
                        format(ref=cfgs.RUN.ref_dataset, eval_backbone=cfgs.RUN.eval_backbone))
        mu, sigma = fid.calculate_moments(data_loader=data_loader,
                                          eval_model=eval_model,
                                          num_generate="N/A",
                                          batch_size=cfgs.OPTIMIZATION.batch_size,
                                          quantize=quantize,
                                          world_size=cfgs.OPTIMIZATION.world_size,
                                          DDP=cfgs.RUN.distributed_data_parallel,
                                          disable_tqdm=disable_tqdm,
                                          fake_feats=None)

        if device == 0:
            logger.info("Save calculated means and covariances to disk.")
        np.savez(moment_path, **{"mu": mu, "sigma": sigma})
    return mu, sigma


def calculate_ins(data_loader, eval_model, quantize, splits, cfgs, logger, device):
    disable_tqdm = device != 0
    if device == 0:
        logger.info("Calculate inception score of the {ref} dataset uisng pre-trained {eval_backbone} model.".\
                    format(ref=cfgs.RUN.ref_dataset, eval_backbone=cfgs.RUN.eval_backbone))
    is_score, is_std = ins.eval_dataset(data_loader=data_loader,
                                        eval_model=eval_model,
                                        quantize=quantize,
                                        splits=splits,
                                        batch_size=cfgs.OPTIMIZATION.batch_size,
                                        world_size=cfgs.OPTIMIZATION.world_size,
                                        DDP=cfgs.RUN.distributed_data_parallel,
                                        disable_tqdm=disable_tqdm)
    if device == 0:
        logger.info("Inception score={is_score}-Inception_std={is_std}".format(is_score=is_score, is_std=is_std))
