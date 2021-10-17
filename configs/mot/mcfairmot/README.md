English | [简体中文](README_cn.md)

# MCFairMOT (Multi-class FairMOT)

## Table of Contents
- [Introduction](#Introduction)
- [Model Zoo](#Model_Zoo)
- [Getting Start](#Getting_Start)
- [Citations](#Citations)

## Introduction

MCFairMOT is the Multi-class extended version of [FairMOT](https://arxiv.org/abs/2004.01888).

## Model Zoo
### MCFairMOT Results on VisDrone2019 Val Set

| backbone       | input shape | MOTA | IDF1 |  IDS  |    FP   |   FN   |    FPS    | download | config |
| :--------------| :------- | :----: | :----: | :----: | :----: | :----: | :------: | :----: |:-----: |
| DLA-34(paper)  | 1088x608 |  83.3  |  81.9  |   544  |  3822  |  14095  |     -   |    -   |   -    |
| DLA-34         | 1088x608 |  83.2  |  83.1  |   499  |  3861  |  14223  |     -   | [model](https://paddledet.bj.bcebos.com/models/mot/mcfairmot_dla34_30e_1088x608.pdparams) | [config](./mcfairmot_dla34_30e_1088x608.yml) |

### MCFairMOT Results on BDD100K Val Set
| backbone       | input shape | MOTA | IDF1 |  IDS  |    FP   |   FN   |    FPS    | download | config |
| :--------------| :------- | :----: | :----: | :---: | :----: | :---: | :------: | :----: |:----: |
| DLA-34         | 1088x608 |  83.2  |  83.1  |  499  |  3861  | 14223 |    -     |[model](https://paddledet.bj.bcebos.com/models/mot/mcfairmot_dla34_30e_1088x608.pdparams) | [config](./mcfairmot_dla34_30e_1088x608.yml) |


## Getting Start

### 1. Training

Training MCFairMOT on 2 GPUs with following command

```bash
python -m paddle.distributed.launch --log_dir=./mcfairmot_dla34_30e_1088x608/ --gpus 0,1 tools/train.py -c configs/mot/mcfairmot/mcfairmot_dla34_30e_1088x608.yml
```


### 2. Evaluation

Evaluating the track performance of MCFairMOT on val dataset in single GPU with following commands:

```bash
# use weights released in PaddleDetection model zoo
CUDA_VISIBLE_DEVICES=0 python tools/eval_mot.py -c configs/mot/mcfairmot/mcfairmot_dla34_30e_1088x608.yml -o weights=https://paddledet.bj.bcebos.com/models/mot/mcfairmot_dla34_30e_1088x608.pdparams

# use saved checkpoint in training
CUDA_VISIBLE_DEVICES=0 python tools/eval_mot.py -c configs/mot/mcfairmot/mcfairmot_dla34_30e_1088x608.yml -o weights=output/mcfairmot_dla34_30e_1088x608/model_final.pdparams
```
**Notes:**
 The default evaluation dataset is MOT-16 Train Set. If you want to change the evaluation dataset, please refer to the following code and modify `configs/datasets/mot.yml`：

### 3. Inference

Inference a vidoe on single GPU with following command:

```bash
# inference on video and save a video
CUDA_VISIBLE_DEVICES=0 python tools/infer_mot.py -c configs/mot/mcfairmot/mcfairmot_dla34_30e_1088x608.yml -o weights=https://paddledet.bj.bcebos.com/models/mot/mcfairmot_dla34_30e_1088x608.pdparams --video_file={your video name}.mp4  --save_videos
```
**Notes:**
 Please make sure that [ffmpeg](https://ffmpeg.org/ffmpeg.html) is installed first, on Linux(Ubuntu) platform you can directly install it by the following command:`apt-get update && apt-get install -y ffmpeg`.


### 4. Export model

```bash
CUDA_VISIBLE_DEVICES=0 python tools/export_model.py -c configs/mot/mcfairmot/mcfairmot_dla34_30e_1088x608.yml -o weights=https://paddledet.bj.bcebos.com/models/mot/mcfairmot_dla34_30e_1088x608.pdparams
```

### 5. Using exported model for python inference

```bash
python deploy/python/mot_jde_infer.py --model_dir=output_inference/mcfairmot_dla34_30e_1088x608 --video_file={your video name}.mp4 --device=GPU --save_mot_txts
```
**Notes:**
The tracking model is used to predict the video, and does not support the prediction of a single image. The visualization video of the tracking results is saved by default. You can add `--save_mot_txts` to save the txt result file, or `--save_images` to save the visualization images.


## Citations
```
@article{zhang2020fair,
  title={FairMOT: On the Fairness of Detection and Re-Identification in Multiple Object Tracking},
  author={Zhang, Yifu and Wang, Chunyu and Wang, Xinggang and Zeng, Wenjun and Liu, Wenyu},
  journal={arXiv preprint arXiv:2004.01888},
  year={2020}
}
```