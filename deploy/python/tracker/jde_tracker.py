# Copyright (c) 2021 PaddlePaddle Authors. All Rights Reserved.
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

import numpy as np
from collections import defaultdict
from ppdet.modeling.mot.matching import jde_matching as matching
from ppdet.modeling.mot.motion import KalmanFilter
from ppdet.modeling.mot.tracker.base_jde_tracker import TrackState, BaseTrack, STrack
from ppdet.modeling.mot.tracker.base_jde_tracker import joint_stracks, sub_stracks, remove_duplicate_stracks

__all__ = ['JDETracker']


class JDETracker(object):
    """
    JDE tracker, support single class and multi classes

    Args:
        num_classes (int): the number of classes
        det_thresh (float): threshold of detection score
        track_buffer (int): buffer for tracker
        min_box_area (int): min box area to filter out low quality boxes
        vertical_ratio (float): w/h, the vertical ratio of the bbox to filter
            bad results, set 1.6 default for pedestrian tracking. If set <0
            means no need to filter bboxes.
        tracked_thresh (float): linear assignment threshold of tracked 
            stracks and detections
        r_tracked_thresh (float): linear assignment threshold of 
            tracked stracks and unmatched detections
        unconfirmed_thresh (float): linear assignment threshold of 
            unconfirmed stracks and unmatched detections
        motion (object): KalmanFilter instance
        conf_thres (float): confidence threshold for tracking
        metric_type (str): either "euclidean" or "cosine", the distance metric 
            used for measurement to track association.
    """

    def __init__(self,
                 num_classes=1,
                 det_thresh=0.3,
                 track_buffer=30,
                 min_box_area=200,
                 vertical_ratio=1.6,
                 tracked_thresh=0.7,
                 r_tracked_thresh=0.5,
                 unconfirmed_thresh=0.7,
                 motion='KalmanFilter',
                 conf_thres=0,
                 metric_type='euclidean'):
        self.num_classes = num_classes
        self.det_thresh = det_thresh
        self.track_buffer = track_buffer
        self.min_box_area = min_box_area
        self.vertical_ratio = vertical_ratio

        self.tracked_thresh = tracked_thresh
        self.r_tracked_thresh = r_tracked_thresh
        self.unconfirmed_thresh = unconfirmed_thresh
        self.motion = KalmanFilter()
        self.conf_thres = conf_thres
        self.metric_type = metric_type

        self.frame_id = 0
        self.tracked_tracks_dict = defaultdict(list) # dict(list[STrack])
        self.lost_tracks_dict = defaultdict(list) # dict(list[STrack])
        self.removed_tracks_dict = defaultdict(list) # dict(list[STrack])

        self.max_time_lost = 0
        # max_time_lost will be calculated: int(frame_rate / 30.0 * track_buffer)

    def update(self, pred_dets_dict, pred_embs_dict):
        """
        Processes the image frame and finds bounding box(detections).
        Associates the detection with corresponding tracklets and also handles
            lost, removed, refound and active tracklets.

        Args:
            pred_dets_dict (dict(np.ndarray)): Detection results of the image.
            pred_embs_dict (dict(np.ndarray)): Embedding results of the image.

        Return:
            output_stracks_dict (dict(list)): The list contains information
                regarding the online_tracklets for the recieved image tensor.
        """
        self.frame_id += 1
        if self.frame_id == 1:
            STrack.init_count(self.num_classes)
        activated_tracks_dict = defaultdict(list)
        refined_tracks_dict = defaultdict(list)
        lost_tracks_dict = defaultdict(list)
        removed_tracks_dict = defaultdict(list)
        output_tracks_dict = defaultdict(list)

        for cls_id in range(self.num_classes):
            pred_dets = pred_dets_dict[cls_id]
            pred_embs = pred_embs_dict[cls_id]

            remain_inds = np.nonzero(pred_dets[:, 4] > self.conf_thres)
            if len(remain_inds) == 0:
                pred_dets = np.zeros([1, 5])
                pred_embs = np.zeros([1, 1])
            else:
                pred_dets = pred_dets[remain_inds]
                pred_embs = pred_embs[remain_inds]

            # Filter out the image with box_num = 0. pred_dets = [[0.0, 0.0, 0.0 ,0.0]]
            empty_pred = True if len(pred_dets) == 1 and np.sum(
                pred_dets) == 0.0 else False
            """ Step 1: Network forward, get detections & embeddings"""
            if len(pred_dets) > 0 and not empty_pred:
                detections = [
                    STrack(STrack.tlbr_to_tlwh(tlbrs[:4]), tlbrs[4], f, self.num_classes, cls_id, 30)
                    for (tlbrs, f) in zip(pred_dets, pred_embs)
                ]
            else:
                detections = []
                
            ''' Add newly detected tracklets to tracked_stracks'''
            unconfirmed_dict = defaultdict(list)
            tracked_tracks_dict = defaultdict(list)
            for track in self.tracked_tracks_dict[cls_id]:
                if not track.is_activated:
                    # previous tracks which are not active in the current frame are added in unconfirmed list
                    unconfirmed_dict[cls_id].append(track)
                else:
                    # Active tracks are added to the local list 'tracked_stracks'
                    tracked_tracks_dict[cls_id].append(track)
            """ Step 2: First association, with embedding"""
            # building tracking pool for the current frame
            track_pool_dict = defaultdict(list)
            track_pool_dict[cls_id] = joint_stracks(
                tracked_tracks_dict[cls_id], self.lost_tracks_dict[cls_id])

            # Predict the current location with KF
            STrack.multi_predict(track_pool_dict[cls_id], self.motion)

            dists = matching.embedding_distance(
                track_pool_dict[cls_id], detections, metric=self.metric_type)
            dists = matching.fuse_motion(self.motion, dists,
                                         track_pool_dict[cls_id], detections)
            matches, u_track, u_detection = matching.linear_assignment(
                dists, thresh=self.tracked_thresh)  # thresh=0.7

            for i_tracked, idet in matches:
                # i_tracked is the id of the track and idet is the detection
                track = track_pool_dict[cls_id][i_tracked]
                det = detections[idet]
                if track.state == TrackState.Tracked:
                    # If the track is active, add the detection to the track
                    track.update(detections[idet], self.frame_id)
                    activated_tracks_dict[cls_id].append(track)
                else:
                    # We have obtained a detection from a track which is not active,
                    # hence put the track in refind_stracks list
                    track.re_activate(det, self.frame_id, new_id=False)
                    refined_tracks_dict[cls_id].append(track)

            # None of the steps below happen if there are no undetected tracks.
            """ Step 3: Second association, with IOU"""
            detections = [detections[i] for i in u_detection]
            r_tracked_stracks = []
            for i in u_track:
                if track_pool_dict[cls_id][i].state == TrackState.Tracked:
                    r_tracked_stracks.append(track_pool_dict[cls_id][i])

            dists = matching.iou_distance(r_tracked_stracks, detections)
            matches, u_track, u_detection = matching.linear_assignment(
                dists, thresh=self.r_tracked_thresh)

            for i_tracked, idet in matches:
                track = r_tracked_stracks[i_tracked]
                det = detections[idet]
                if track.state == TrackState.Tracked:
                    track.update(det, self.frame_id)
                    activated_tracks_dict[cls_id].append(track)
                else:
                    track.re_activate(det, self.frame_id, new_id=False)
                    refined_tracks_dict[cls_id].append(track)

            for it in u_track:
                track = r_tracked_stracks[it]
                if not track.state == TrackState.Lost:
                    track.mark_lost()
                    lost_tracks_dict[cls_id].append(track)
            '''Deal with unconfirmed tracks, usually tracks with only one beginning frame'''
            detections = [detections[i] for i in u_detection]
            dists = matching.iou_distance(unconfirmed_dict[cls_id], detections)
            matches, u_unconfirmed, u_detection = matching.linear_assignment(
                dists, thresh=self.unconfirmed_thresh)
            for i_tracked, idet in matches:
                unconfirmed_dict[cls_id][i_tracked].update(detections[idet],
                                                           self.frame_id)
                activated_tracks_dict[cls_id].append(unconfirmed_dict[cls_id][
                    i_tracked])
            for it in u_unconfirmed:
                track = unconfirmed_dict[cls_id][it]
                track.mark_removed()
                removed_tracks_dict[cls_id].append(track)
            """ Step 4: Init new stracks"""
            for inew in u_detection:
                track = detections[inew]
                if track.score < self.det_thresh:
                    continue
                track.activate(self.motion, self.frame_id)
                activated_tracks_dict[cls_id].append(track)
            """ Step 5: Update state"""
            for track in self.lost_tracks_dict[cls_id]:
                if self.frame_id - track.end_frame > self.max_time_lost:
                    track.mark_removed()
                    removed_tracks_dict[cls_id].append(track)

            self.tracked_tracks_dict[cls_id] = [
                t for t in self.tracked_tracks_dict[cls_id]
                if t.state == TrackState.Tracked
            ]
            self.tracked_tracks_dict[cls_id] = joint_stracks(
                self.tracked_tracks_dict[cls_id], activated_tracks_dict[cls_id])
            self.tracked_tracks_dict[cls_id] = joint_stracks(
                self.tracked_tracks_dict[cls_id], refined_tracks_dict[cls_id])
            self.lost_tracks_dict[cls_id] = sub_stracks(
                self.lost_tracks_dict[cls_id], self.tracked_tracks_dict[cls_id])
            self.lost_tracks_dict[cls_id].extend(lost_tracks_dict[cls_id])
            self.lost_tracks_dict[cls_id] = sub_stracks(
                self.lost_tracks_dict[cls_id], self.removed_tracks_dict[cls_id])
            self.removed_tracks_dict[cls_id].extend(removed_tracks_dict[cls_id])
            self.tracked_tracks_dict[cls_id], self.lost_tracks_dict[
                cls_id] = remove_duplicate_stracks(
                    self.tracked_tracks_dict[cls_id],
                    self.lost_tracks_dict[cls_id])

            # get scores of lost tracks
            output_tracks_dict[cls_id] = [
                track for track in self.tracked_tracks_dict[cls_id]
                if track.is_activated
            ]

        return output_tracks_dict
