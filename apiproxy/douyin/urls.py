#!/usr/bin/env python
# -*- coding: utf-8 -*-


class Urls(object):
    def __init__(self):
        ######################################### WEB #########################################
        # Homepage recommendation
        self.TAB_FEED = 'https://www.douyin.com/aweme/v1/web/tab/feed/?'

        # User short info (returns info for provided user sec_uids)
        self.USER_SHORT_INFO = 'https://www.douyin.com/aweme/v1/web/im/user/info/?'

        # User detailed info
        self.USER_DETAIL = 'https://www.douyin.com/aweme/v1/web/user/profile/other/?'

        # User works
        self.USER_POST = 'https://www.douyin.com/aweme/v1/web/aweme/post/?'

        # Work info
        self.POST_DETAIL = 'https://www.douyin.com/aweme/v1/web/aweme/detail/?'

        # User likes A
        # Requires odin_tt
        self.USER_FAVORITE_A = 'https://www.douyin.com/aweme/v1/web/aweme/favorite/?'

        # User likes B
        self.USER_FAVORITE_B = 'https://www.iesdouyin.com/web/api/v2/aweme/like/?'

        # User history
        self.USER_HISTORY = 'https://www.douyin.com/aweme/v1/web/history/read/?'

        # User collections
        self.USER_COLLECTION = 'https://www.douyin.com/aweme/v1/web/aweme/listcollection/?'

        # User comments
        self.COMMENT = 'https://www.douyin.com/aweme/v1/web/comment/list/?'

        # Homepage friend works
        self.FRIEND_FEED = 'https://www.douyin.com/aweme/v1/web/familiar/feed/?'

        # Followed user works
        self.FOLLOW_FEED = 'https://www.douyin.com/aweme/v1/web/follow/feed/?'

        # All works under a collection
        # Only requires X-Bogus
        self.USER_MIX = 'https://www.douyin.com/aweme/v1/web/mix/aweme/?'

        # List of all user collections
        # Requires ttwid
        self.USER_MIX_LIST = 'https://www.douyin.com/aweme/v1/web/mix/list/?'

        # Live
        self.LIVE = 'https://live.douyin.com/webcast/room/web/enter/?'
        self.LIVE2 = 'https://webcast.amemv.com/webcast/room/reflow/info/?'

        # Music
        self.MUSIC = 'https://www.douyin.com/aweme/v1/web/music/aweme/?'

        #######################################################################################


if __name__ == '__main__':
    pass
