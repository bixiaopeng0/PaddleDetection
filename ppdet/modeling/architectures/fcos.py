# Copyright (c) 2020 PaddlePaddle Authors. All Rights Reserved. 
#   
# Licensed under the Apache License, Version 2.0 (the "License");   
# you may not use this file except in compliance with the License.  
# You may obtain a copy of the License at   
#   
#     http://www.apache.org/licenses/LICENSE-2.0    
#   
# Unless required by applicable law or agreed to in writing, software   
# distributed under the License is distributed on an "AS IS" BASIS, 
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  
# See the License for the specific language governing permissions and   
# limitations under the License.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import paddle
from ppdet.core.workspace import register, create
from .meta_arch import BaseArch

__all__ = ['FCOS']


@register
class FCOS(BaseArch):
    """
    FCOS network, see https://arxiv.org/abs/1904.01355

    Args:
        backbone (object): backbone instance
        neck (object): 'FPN' instance
        fcos_head (object): 'FCOSHead' instance
    """

    __category__ = 'architecture'

    def __init__(self, backbone, neck='FPN', fcos_head='FCOSHead'):
        super(FCOS, self).__init__()
        self.backbone = backbone
        self.neck = neck
        self.fcos_head = fcos_head

    @classmethod
    def from_config(cls, cfg, *args, **kwargs):
        backbone = create(cfg['backbone'])

        kwargs = {'input_shape': backbone.out_shape}
        neck = create(cfg['neck'], **kwargs)

        kwargs = {'input_shape': neck.out_shape}
        fcos_head = create(cfg['fcos_head'], **kwargs)

        return {
            'backbone': backbone,
            'neck': neck,
            "fcos_head": fcos_head,
        }

    def _forward(self):
        body_feats = self.backbone(self.inputs)
        fpn_feats = self.neck(body_feats)
        is_teacher = self.inputs.get('is_teacher', False)
        if self.training or is_teacher:
            losses = self.fcos_head(fpn_feats, self.inputs)
            return losses
        else:
            fcos_head_outs = self.fcos_head(fpn_feats, self.inputs)
            bbox_pred, bbox_num = self.fcos_head.post_process(
                fcos_head_outs, self.inputs['scale_factor'])
            return {'bbox': bbox_pred, 'bbox_num': bbox_num}

    def get_loss(self):
        return self._forward()

    def get_pred(self):
        return self._forward()
