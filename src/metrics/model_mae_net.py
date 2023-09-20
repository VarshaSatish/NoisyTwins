import sys
import os

import torch
import numpy as np
import torch.nn as nn
import matplotlib.pyplot as plt
from PIL import Image
import metrics.models_vit as models_vit
from metrics.models_vit import interpolate_pos_embed
from timm.models.layers import trunc_normal_
from timm.utils import accuracy

class Identity(nn.Module):
    def __init__(self):
        super().__init__()
        
    def forward(self, x):
        return x

def prepare_model(chkpt_dir, arch='vit_base_patch16'):
    model = models_vit.__dict__[arch](
        num_classes=1010,
        drop_path_rate=0.1,
        global_pool=True,
    )
    
    model.head = Identity()
    model.fc_norm = Identity()
    
    ## # model = torch.nn.Sequential(*(list(model.children())[:-2]))
    # print("new model")
    # print(model)
    # exit(0)
    if chkpt_dir:
        checkpoint = torch.load(chkpt_dir, map_location='cpu')

        print("Load pre-trained checkpoint from: %s" % chkpt_dir)
        checkpoint_model = checkpoint['model']
        state_dict = model.state_dict()
        for k in ['head.weight', 'head.bias']:
            if k in checkpoint_model and checkpoint_model[k].shape != state_dict[k].shape:
                print(f"Removing key {k} from pretrained checkpoint")
                del checkpoint_model[k]

        # interpolate position embedding
        interpolate_pos_embed(model, checkpoint_model)

        # load pre-trained model
        msg = model.load_state_dict(checkpoint_model, strict=False)
        print(msg)
        global_pool = True
        # if global_pool:
        #     assert set(msg.missing_keys) == {'head.weight', 'head.bias', 'fc_norm.weight', 'fc_norm.bias'}
        # else:
        #     assert set(msg.missing_keys) == {'head.weight', 'head.bias'}

        # manually initialize fc layer
        # trunc_normal_(model.head.weight, std=2e-5)
    return model