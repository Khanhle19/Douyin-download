#!/usr/bin/env python
# -*- coding: utf-8 -*-


import time
import copy


class Result(object):
    def __init__(self):
        # Author info
        self.authorDict = {
            "avatar_thumb": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            },
            "avatar": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            },
            "cover_url": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            },
            # Number of liked works
            "favoriting_count": "",
            # Number of followers
            "follower_count": "",
            # Number of following
            "following_count": "",
            # Nickname
            "nickname": "",
            # Whether download is allowed
            "prevent_download": "",
            # User url id
            "sec_uid": "",
            # Whether private account
            "secret": "",
            # Short id
            "short_id": "",
            # Signature
            "signature": "",
            # Total likes received
            "total_favorited": "",
            # User id
            "uid": "",
            # User custom unique id (Douyin ID)
            "unique_id": "",
            # Age
            "user_age": "",

        }
        # Image info
        self.picDict = {
            "height": "",
            "mask_url_list": "",
            "uri": "",
            "url_list": [],
            "width": ""
        }
        # Music info
        self.musicDict = {
            "cover_hd": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            },
            "cover_large": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            },
            "cover_medium": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            },
            "cover_thumb": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            },
            # Music author Douyin ID
            "owner_handle": "",
            # Music author id
            "owner_id": "",
            # Music author nickname
            "owner_nickname": "",
            "play_url": {
                "height": "",
                "uri": "",
                "url_key": "",
                "url_list": [],
                "width": ""
            },
            # Music title
            "title": "",
        }
        # Video info
        self.videoDict = {
            "play_addr": {
                "uri": "",
                "url_list": [],
            },
            "cover_original_scale": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            },
            "dynamic_cover": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            },
            "origin_cover": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            },
            "cover": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            }
        }
        # Mix info
        self.mixInfo = {
            "cover_url": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": 720
            },
            "ids": "",
            "is_serial_mix": "",
            "mix_id": "",
            "mix_name": "",
            "mix_pic_type": "",
            "mix_type": "",
            "statis": {
                "current_episode": "",
                "updated_to_episode": ""
            }
        }
        # Work info
        self.awemeDict = {
            # Work creation time
            "create_time": "",
            # awemeType=0 Video, awemeType=1 Image set, awemeType=2 Live
            "awemeType": "",
            # Work id
            "aweme_id": "",
            # Author info
            "author": self.authorDict,
            # Work description
            "desc": "",
            # Images
            "images": [],
            # Music
            "music": self.musicDict,
            # Collection
            "mix_info": self.mixInfo,
            # Video
            "video": self.videoDict,
            # Work statistics
            "statistics": {
                "admire_count": "",
                "collect_count": "",
                "comment_count": "",
                "digg_count": "",
                "play_count": "",
                "share_count": ""
            }
        }
        # User work list
        self.awemeList = []
        # Live info
        self.liveDict = {
            # awemeType=0 Video, awemeType=1 Image set, awemeType=2 Live
            "awemeType": "",
            # Whether live
            "status": "",
            # Live title
            "title": "",
            # Live cover
            "cover": "",
            # Avatar
            "avatar": "",
            # Viewer count
            "user_count": "",
            # Nickname
            "nickname": "",
            # sec_uid
            "sec_uid": "",
            # Live room viewing status
            "display_long": "",
            # Pull stream
            "flv_pull_url": "",
            # Partition
            "partition": "",
            "sub_partition": "",
            # Clearest address
            "flv_pull_url0": "",
        }



    # Simplify raw JSON data (dataRaw) into defined data structure (dataNew)
    # Converted data
    def dataConvert(self, awemeType, dataNew, dataRaw):
        for item in dataNew:
            try:
                # Work creation time
                if item == "create_time":
                    dataNew['create_time'] = time.strftime(
                        "%Y-%m-%d %H.%M.%S", time.localtime(dataRaw['create_time']))
                    continue
                # Set awemeType
                if item == "awemeType":
                    dataNew["awemeType"] = awemeType
                    continue
                # When parsed link is image
                if item == "images":
                    if awemeType == 1:
                        for image in dataRaw[item]:
                            for i in image:
                                self.picDict[i] = image[i]
                            # Deep copy dictionary
                            self.awemeDict["images"].append(copy.deepcopy(self.picDict))
                    continue
                # When parsed link is video
                if item == "video":
                    if awemeType == 0:
                        self.dataConvert(awemeType, dataNew[item], dataRaw[item])
                    continue
                # Enlarge small avatar
                if item == "avatar":
                    for i in dataNew[item]:
                        if i == "url_list":
                            for j in self.awemeDict["author"]["avatar_thumb"]["url_list"]:
                                dataNew[item][i].append(j.replace("100x100", "1080x1080"))
                        elif i == "uri":
                            dataNew[item][i] = self.awemeDict["author"]["avatar_thumb"][i].replace("100x100",
                                                                                                   "1080x1080")
                        else:
                            dataNew[item][i] = self.awemeDict["author"]["avatar_thumb"][i]
                    continue

                # Original JSON is [{}] while ours is {}
                if item == "cover_url":
                    self.dataConvert(awemeType, dataNew[item], dataRaw[item][0])
                    continue

                # Get 1080p video based on uri
                if item == "play_addr":
                    dataNew[item]["uri"] = dataRaw["bit_rate"][0]["play_addr"]["uri"]
                    # Use this API to get 1080p
                    # dataNew[item]["url_list"] = "https://aweme.snssdk.com/aweme/v1/play/?video_id=%s&ratio=1080p&line=0" \
                    #                             % dataNew[item]["uri"]
                    dataNew[item]["url_list"] = copy.deepcopy(dataRaw["bit_rate"][0]["play_addr"]["url_list"])
                    continue

                # Regular recursive traversal of dictionary
                if isinstance(dataNew[item], dict):
                    self.dataConvert(awemeType, dataNew[item], dataRaw[item])
                else:
                    # Assignment
                    dataNew[item] = dataRaw[item]
            except Exception as e:
                # Remove this warning, it's often misleading
                # print("[  Warning  ]: %s not found in interface during data conversion\r" % (item))
                pass

    def clearDict(self, data):
        for item in data:
            # Regular recursive traversal of dictionary
            if isinstance(data[item], dict):
                self.clearDict(data[item])
            elif isinstance(data[item], list):
                data[item] = []
            else:
                data[item] = ""


if __name__ == '__main__':
    pass
