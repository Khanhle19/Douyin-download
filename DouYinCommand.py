#!/usr/bin/env python
# -*- coding: utf-8 -*-


import argparse
import os
import sys
import json
import yaml
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path
import logging

# Logger basic config (console handler provided by utils.logger for deep logs)
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
# Rename logger to avoid conflicts
douyin_logger = logging.getLogger("DouYin")

# Safe to use douyin_logger now
try:
    import asyncio
    import aiohttp
    ASYNC_SUPPORT = True
except ImportError:
    ASYNC_SUPPORT = False
    douyin_logger.warning("aiohttp is not installed; async downloads are unavailable")

from apiproxy.douyin.douyin import Douyin
from apiproxy.douyin.download import Download
from apiproxy.douyin import douyin_headers
from apiproxy.common import utils

@dataclass
class DownloadConfig:
    """Download configuration container"""
    link: List[str]
    path: Path
    music: bool = True
    cover: bool = True
    avatar: bool = True
    json: bool = True
    start_time: str = ""
    end_time: str = ""
    folderstyle: bool = True
    mode: List[str] = field(default_factory=lambda: ["post"])
    thread: int = 5
    cookie: Optional[str] = None
    database: bool = True
    number: Dict[str, int] = field(default_factory=lambda: {
        "post": 0, "like": 0, "allmix": 0, "mix": 0, "music": 0
    })
    increase: Dict[str, bool] = field(default_factory=lambda: {
        "post": False, "like": False, "allmix": False, "mix": False, "music": False
    })
    
    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "DownloadConfig":
        """Load configuration from YAML file"""
        # TODO: implement YAML loading logic
        
    @classmethod 
    def from_args(cls, args) -> "DownloadConfig":
        """Load configuration from CLI arguments"""
        # TODO: implement argument loading logic
        
    def validate(self) -> bool:
        """Validate configuration"""
        # TODO: implement validation logic

configModel = {
    "link": [],
    "path": os.getcwd(),
    "music": True,
    "cover": True,
    "avatar": True,
    "json": True,
    "start_time": "",
    "end_time": "",
    "folderstyle": True,
    "mode": ["post"],
    "number": {
        "post": 0,
        "like": 0,
        "allmix": 0,
        "mix": 0,
        "music": 0,
    },
    'database': True,
    "increase": {
        "post": False,
        "like": False,
        "allmix": False,
        "mix": False,
        "music": False,
    },
    "thread": 5,
    "cookie": os.environ.get("DOUYIN_COOKIE", "")
}

def argument():
    parser = argparse.ArgumentParser(description='Douyin bulk downloader helper')
    parser.add_argument("--cmd", "-C", help="Use command line (True) or config file (False), default False",
                        type=utils.str2bool, required=False, default=False)
    parser.add_argument("--link", "-l",
                        help="Share links for videos/albums, live, collections, music collections, or profile URLs; you can set multiple links (strip extra text, keep only URL starting with https://v.douyin.com/ or https://www.douyin.com/)",
                        type=str, required=False, default=[], action="append")
    parser.add_argument("--path", "-p", help="Download save directory, defaults to current working directory",
                        type=str, required=False, default=os.getcwd())
    parser.add_argument("--music", "-m", help="Download music from video (True/False), default True",
                        type=utils.str2bool, required=False, default=True)
    parser.add_argument("--cover", "-c", help="Download video cover (True/False), default True; applies to video downloads",
                        type=utils.str2bool, required=False, default=True)
    parser.add_argument("--avatar", "-a", help="Download author avatar (True/False), default True",
                        type=utils.str2bool, required=False, default=True)
    parser.add_argument("--json", "-j", help="Save retrieved data (True/False), default True",
                        type=utils.str2bool, required=False, default=True)
    parser.add_argument("--folderstyle", "-fs", help="Folder style, default True",
                        type=utils.str2bool, required=False, default=True)
    parser.add_argument("--mode", "-M", help="For profile links: choose posted works (post), liked works (like), or all collections (mix); default post; multiple modes allowed",
                        type=str, required=False, default=[], action="append")
    parser.add_argument("--postnumber", help="Number of posts to download from profile; 0 means all",
                        type=int, required=False, default=0)
    parser.add_argument("--likenumber", help="Number of liked posts to download; 0 means all",
                        type=int, required=False, default=0)
    parser.add_argument("--allmixnumber", help="Number of collections to download from profile; 0 means all",
                        type=int, required=False, default=0)
    parser.add_argument("--mixnumber", help="Number of items to download within a single collection; 0 means all",
                        type=int, required=False, default=0)
    parser.add_argument("--musicnumber", help="Number of items to download under music (original sound); 0 means all",
                        type=int, required=False, default=0)
    parser.add_argument("--database", "-d", help="Use database (default True); incremental updates unavailable if disabled",
                        type=utils.str2bool, required=False, default=True)
    parser.add_argument("--postincrease", help="Enable incremental download for profile posts (True/False), default False",
                        type=utils.str2bool, required=False, default=False)
    parser.add_argument("--likeincrease", help="Enable incremental download for profile likes (True/False), default False",
                        type=utils.str2bool, required=False, default=False)
    parser.add_argument("--allmixincrease", help="Enable incremental download for profile collections (True/False), default False",
                        type=utils.str2bool, required=False, default=False)
    parser.add_argument("--mixincrease", help="Enable incremental download within a single collection (True/False), default False",
                        type=utils.str2bool, required=False, default=False)
    parser.add_argument("--musicincrease", help="Enable incremental download under music (original sound) (True/False), default False",
                        type=utils.str2bool, required=False, default=False)
    parser.add_argument("--thread", "-t",
                        help="Set thread count, default 5",
                        type=int, required=False, default=5)
    parser.add_argument("--cookie", help="Set cookie string: \"name1=value1; name2=value2;\" (include quotes)",
                        type=str, required=False, default='')
    parser.add_argument("--config", "-F", 
                       type=argparse.FileType('r', encoding='utf-8'),
                       help="Path to configuration file")
    args = parser.parse_args()
    if args.thread <= 0:
        args.thread = 5

    return args


def yamlConfig():
    curPath = os.path.dirname(os.path.realpath(sys.argv[0]))
    yamlPath = os.path.join(curPath, "config.yml")
    
    try:
        with open(yamlPath, 'r', encoding='utf-8') as f:
            configDict = yaml.safe_load(f)
            
        # Simplify configuration updates using dictionary comprehension
        for key in configModel:
            if key in configDict:
                if isinstance(configModel[key], dict):
                    configModel[key].update(configDict[key] or {})
                else:
                    configModel[key] = configDict[key]
                    
        # Special handling for cookies
        if configDict.get("cookies"):
            cookieStr = "; ".join(f"{k}={v}" for k,v in configDict["cookies"].items())
            configModel["cookie"] = cookieStr
            
        # Special handling for end_time
        if configDict.get("end_time") == "now":
                configModel["end_time"] = time.strftime("%Y-%m-%d", time.localtime())
            
    except FileNotFoundError:
        douyin_logger.warning("Configuration file config.yml not found")
    except Exception as e:
        douyin_logger.warning(f"Error parsing configuration file: {str(e)}")


def validate_config(config: dict) -> bool:
    """Validate configuration validity"""
    required_keys = {
        'link': list,
        'path': str,
        'thread': int
    }
    
    for key, typ in required_keys.items():
        if key not in config or not isinstance(config[key], typ):
            douyin_logger.error(f"Invalid configuration item: {key}")
            return False
            
    if not all(isinstance(url, str) for url in config['link']):
        douyin_logger.error("Link configuration format error")
        return False
        
    return True


def main():
    start = time.time()

    # Configuration initialization
    args = argument()
    if args.cmd:
        update_config_from_args(args)
    else:
        yamlConfig()

    if not validate_config(configModel):
        return

    if not configModel["link"]:
        douyin_logger.error("Download link not set")
        return

    # Cookie handling
    if configModel["cookie"]:
        douyin_headers["Cookie"] = configModel["cookie"]

    # Path handling
    configModel["path"] = os.path.abspath(configModel["path"])
    os.makedirs(configModel["path"], exist_ok=True)
    douyin_logger.info(f"Data save path {configModel['path']}")

    # Initialize downloader
    dy = Douyin(database=configModel["database"])
    dl = Download(
        thread=configModel["thread"],
        music=configModel["music"],
        cover=configModel["cover"],
        avatar=configModel["avatar"],
        resjson=configModel["json"],
        folderstyle=configModel["folderstyle"]
    )

    # Process each link
    for link in configModel["link"]:
        process_link(dy, dl, link)

    # Calculate time elapsed
    duration = time.time() - start
    douyin_logger.info(f'\n[Download Complete]: Total time: {int(duration/60)} minutes {int(duration%60)} seconds\n')


def process_link(dy, dl, link):
    """Download logic for processing a single link"""
    douyin_logger.info("-" * 80)
    douyin_logger.info(f"[  INFO  ]: Requesting link: {link}")
    
    try:
        url = dy.getShareLink(link)
        key_type, key = dy.getKey(url)
        
        handlers = {
            "user": handle_user_download,
            "mix": handle_mix_download,
            "music": handle_music_download,
            "aweme": handle_aweme_download,
            "live": handle_live_download
        }
        
        handler = handlers.get(key_type)
        if handler:
            handler(dy, dl, key)
        else:
            douyin_logger.warning(f"[  WARNING  ]: Unknown link type: {key_type}")
    except Exception as e:
        douyin_logger.error(f"Error processing link: {str(e)}")


def handle_user_download(dy, dl, key):
    """Handle user profile download"""
    douyin_logger.info("[  INFO  ]: Requesting works from user profile")
    data = dy.getUserDetailInfo(sec_uid=key)
    nickname = ""
    if data and data.get('user'):
        nickname = utils.replaceStr(data['user']['nickname'])

    userPath = os.path.join(configModel["path"], f"user_{nickname}_{key}")
    os.makedirs(userPath, exist_ok=True)

    for mode in configModel["mode"]:
        douyin_logger.info("-" * 80)
        douyin_logger.info(f"[  INFO  ]: Requesting user profile mode: {mode}")
        
        if mode in ('post', 'like'):
            _handle_post_like_mode(dy, dl, key, mode, userPath)
        elif mode == 'mix':
            _handle_mix_mode(dy, dl, key, userPath)

def _handle_post_like_mode(dy, dl, key, mode, userPath):
    """Handle post/like mode download"""
    datalist = dy.getUserInfo(
        key, 
        mode, 
        35, 
        configModel["number"][mode], 
        configModel["increase"][mode],
        start_time=configModel.get("start_time", ""),
        end_time=configModel.get("end_time", "")
    )
    
    if not datalist:
        return
        
    modePath = os.path.join(userPath, mode)
    os.makedirs(modePath, exist_ok=True)
    
    dl.userDownload(awemeList=datalist, savePath=modePath)

def _handle_mix_mode(dy, dl, key, userPath):
    """Handle collection mode download"""
    mixIdNameDict = dy.getUserAllMixInfo(key, 35, configModel["number"]["allmix"])
    if not mixIdNameDict:
        return

    modePath = os.path.join(userPath, "mix")
    os.makedirs(modePath, exist_ok=True)

    for mix_id, mix_name in mixIdNameDict.items():
        douyin_logger.info(f'[  INFO  ]: Downloading works in collection [{mix_name}]')
        mix_file_name = utils.replaceStr(mix_name)
        datalist = dy.getMixInfo(
            mix_id, 
            35, 
            0, 
            configModel["increase"]["allmix"], 
            key,
            start_time=configModel.get("start_time", ""),
            end_time=configModel.get("end_time", "")
        )
        
        if datalist:
            dl.userDownload(awemeList=datalist, savePath=os.path.join(modePath, mix_file_name))
            douyin_logger.info(f'[  INFO  ]: Download complete for works in collection [{mix_name}]')

def handle_mix_download(dy, dl, key):
    """Handle single collection download"""
    douyin_logger.info("[  INFO  ]: Requesting works from single collection")
    try:
        datalist = dy.getMixInfo(
            key, 
            35, 
            configModel["number"]["mix"], 
            configModel["increase"]["mix"], 
            "",
            start_time=configModel.get("start_time", ""),
            end_time=configModel.get("end_time", "")
        )
        
        if not datalist:
            douyin_logger.error("Failed to get collection information")
            return
            
        mixname = utils.replaceStr(datalist[0]["mix_info"]["mix_name"])
        mixPath = os.path.join(configModel["path"], f"mix_{mixname}_{key}")
        os.makedirs(mixPath, exist_ok=True)
        dl.userDownload(awemeList=datalist, savePath=mixPath)
    except Exception as e:
        douyin_logger.error(f"Error processing collection: {str(e)}")

def handle_music_download(dy, dl, key):
    """Handle music works download"""
    douyin_logger.info("[  INFO  ]: Requesting works under music (original sound)")
    datalist = dy.getMusicInfo(key, 35, configModel["number"]["music"], configModel["increase"]["music"])

    if datalist:
        musicname = utils.replaceStr(datalist[0]["music"]["title"])
        musicPath = os.path.join(configModel["path"], f"music_{musicname}_{key}")
        os.makedirs(musicPath, exist_ok=True)
        dl.userDownload(awemeList=datalist, savePath=musicPath)

def handle_aweme_download(dy, dl, key):
    """Handle single work download"""
    douyin_logger.info("[  INFO  ]: Requesting single work")
    
    # Maximum retries
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            douyin_logger.info(f"[  INFO  ]: Attempt {retry_count+1} to get work information")
            result = dy.getAwemeInfo(key)
            
            if not result:
                douyin_logger.error("[  ERROR  ]: Failed to get work information")
                retry_count += 1
                if retry_count < max_retries:
                    douyin_logger.info("[  INFO  ]: Waiting 5 seconds to retry...")
                    time.sleep(5)
                continue
            
            # Directly use the returned dictionary, no need to unpack
            datanew = result
            
            if datanew:
                awemePath = os.path.join(configModel["path"], "aweme")
                os.makedirs(awemePath, exist_ok=True)
                
                # Check video URL before downloading
                video_url = datanew.get("video", {}).get("play_addr", {}).get("url_list", [])
                if not video_url or len(video_url) == 0:
                    douyin_logger.error("[  ERROR  ]: Unable to get video URL")
                    retry_count += 1
                    if retry_count < max_retries:
                        douyin_logger.info("[  INFO  ]: Waiting 5 seconds to retry...")
                        time.sleep(5)
                    continue
                    
                douyin_logger.info(f"[  INFO  ]: Video URL obtained, preparing to download")
                dl.userDownload(awemeList=[datanew], savePath=awemePath)
                douyin_logger.info(f"[  SUCCESS  ]: Video download complete")
                return True
            else:
                douyin_logger.error("[  ERROR  ]: Work data is empty")
                
            retry_count += 1
            if retry_count < max_retries:
                douyin_logger.info("[  INFO  ]: Waiting 5 seconds to retry...")
                time.sleep(5)
                
        except Exception as e:
            douyin_logger.error(f"[  ERROR  ]: Error processing work: {str(e)}")
            retry_count += 1
            if retry_count < max_retries:
                douyin_logger.info("[  INFO  ]: Waiting 5 seconds to retry...")
                time.sleep(5)
    
    douyin_logger.error("[  FAILED  ]: Maximum retries reached, unable to download video")

def handle_live_download(dy, dl, key):
    """Handle live stream download"""
    douyin_logger.info("[  INFO  ]: Performing live stream parsing")
    live_json = dy.getLiveInfo(key)
    
    if configModel["json"] and live_json:
        livePath = os.path.join(configModel["path"], "live")
        os.makedirs(livePath, exist_ok=True)
        
        live_file_name = utils.replaceStr(f"{key}{live_json['nickname']}")
        json_path = os.path.join(livePath, f"{live_file_name}.json")
        
        douyin_logger.info("[  INFO  ]: Saving retrieved information to result.json")
        with open(json_path, "w", encoding='utf-8') as f:
            json.dump(live_json, f, ensure_ascii=False, indent=2)

# Conditionally define asynchronous function
if ASYNC_SUPPORT:
    async def download_file(url, path):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    with open(path, 'wb') as f:
                        f.write(await response.read())
                    return True
        return False

def update_config_from_args(args):
    """Update configuration from command line arguments"""
    configModel["link"] = args.link
    configModel["path"] = args.path
    configModel["music"] = args.music
    configModel["cover"] = args.cover
    configModel["avatar"] = args.avatar
    configModel["json"] = args.json
    configModel["folderstyle"] = args.folderstyle
    configModel["mode"] = args.mode if args.mode else ["post"]
    configModel["thread"] = args.thread
    configModel["cookie"] = args.cookie
    configModel["database"] = args.database
    
    # Update number dictionary
    configModel["number"]["post"] = args.postnumber
    configModel["number"]["like"] = args.likenumber
    configModel["number"]["allmix"] = args.allmixnumber
    configModel["number"]["mix"] = args.mixnumber
    configModel["number"]["music"] = args.musicnumber
    
    # Update increase dictionary
    configModel["increase"]["post"] = args.postincrease
    configModel["increase"]["like"] = args.likeincrease
    configModel["increase"]["allmix"] = args.allmixincrease
    configModel["increase"]["mix"] = args.mixincrease
    configModel["increase"]["music"] = args.musicincrease

if __name__ == "__main__":
    main()
