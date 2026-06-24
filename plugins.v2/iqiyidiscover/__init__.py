import json
import random
import string
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests

from app import schemas
from app.core.config import settings
from app.core.event import Event, eventmanager
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import DiscoverSourceEventData
from app.schemas.types import ChainEventType


CHANNEL_PARAMS = {
    "tv": {"id": "2", "name": "电视剧", "type": "电视剧"},
    "short_drama": {"id": "35", "name": "短剧", "type": "短剧"},
    "movie": {"id": "1", "name": "电影", "type": "电影"},
    "variety": {"id": "6", "name": "综艺", "type": "综艺"},
    "anime": {"id": "4", "name": "动漫", "type": "动漫"},
    "children": {"id": "15", "name": "少儿", "type": "少儿"},
    "comic": {"id": "37", "name": "漫剧", "type": "漫剧"},
    "documentary": {"id": "3", "name": "纪录片", "type": "纪录片"},
    "knowledge": {"id": "12", "name": "知识", "type": "知识"},
}

MOVIEPILOT_MEDIA_TYPES = {
    "movie": "电影",
    "tv": "电视剧",
    "short_drama": "电视剧",
    "variety": "电视剧",
    "anime": "电视剧",
    "children": "电视剧",
    "comic": "电视剧",
    "documentary": "电视剧",
    "knowledge": "电视剧",
}

MODE_PARAMS = {
    "11": "最热",
    "4": "最新",
    "8": "高分",
}

RECENT_FREE_SMART_TAG_VALUE = "近期转免"
RECENT_FREE_SMART_TAG_PARAM = f"smart_tag_v2={RECENT_FREE_SMART_TAG_VALUE}"

SHORT_DRAMA_MODE_PARAMS = {
    "11": "最热",
    "4": "最新",
}

VARIETY_MODE_PARAMS = {
    "11": "最热",
    "4": "最新",
}

ANIME_MODE_PARAMS = {
    "11": "最热",
    "4": "最新",
}

CHILDREN_MODE_PARAMS = {
    "11": "最热",
    "4": "最新",
}

COMIC_MODE_PARAMS = {
    "11": "最热",
    "4": "最新",
}

DOCUMENTARY_MODE_PARAMS = {
    "11": "最热",
    "4": "最新",
}

KNOWLEDGE_MODE_PARAMS = {
    "11": "最热",
    "4": "最新",
}

YEAR_PARAMS = {
    "market_release_date_level=即将上线": "即将上线",
    "market_release_date_level=2026": "2026",
    "market_release_date_level=2025": "2025",
    "market_release_date_level=2024": "2024",
    "market_release_date_level=2023": "2023",
    "market_release_date_level=2022": "2022",
    "market_release_date_level=2021": "2021",
    "market_release_date_level=2020": "2020",
    "market_release_date_level=2010-2019": "10年代",
    "market_release_date_level=2000-2009": "00年代",
    "market_release_date_level=1990-1999": "90年代",
    "market_release_date_level=1980-1989": "80年代",
}

PAY_PARAMS = {
    RECENT_FREE_SMART_TAG_PARAM: "近期转免",
    "is_purchase=0": "免费",
    "is_limit_free=1": "限免",
    "charge_control_paymark=1_1_1,is_purchase=1": "VIP",
}

SHORT_DRAMA_YEAR_PARAMS = {
    "market_release_date_level=即将上线": "即将上线",
    "market_release_date_level=2026": "2026",
    "market_release_date_level=2025": "2025",
    "market_release_date_level=2024": "2024",
    "market_release_date_level=2023": "2023",
    "market_release_date_level=2022": "2022",
    "market_release_date_level=2000-2021": "更早",
}

SHORT_DRAMA_PAY_PARAMS = {
    RECENT_FREE_SMART_TAG_PARAM: "近期转免",
    "is_purchase=0": "免费",
    "charge_control_paymark=1_1_1,is_purchase=1": "VIP",
    "is_exclusive=1": "独播",
}

MOVIE_YEAR_PARAMS = {
    "market_release_date_level=即将上线": "即将上线",
    "market_release_date_level=2026": "2026",
    "market_release_date_level=2025": "2025",
    "market_release_date_level=2024": "2024",
    "market_release_date_level=2023": "2023",
    "market_release_date_level=2022": "2022",
    "market_release_date_level=2021": "2021",
    "market_release_date_level=2020": "2020",
    "market_release_date_level=2010-2019": "10年代",
    "market_release_date_level=2000-2009": "00年代",
    "market_release_date_level=1990-1999": "90年代",
    "market_release_date_level=1980-1989": "80年代",
    "market_release_date_level=1970-1979": "70年代",
    "market_release_date_level=1960-1969": "60年代",
    "market_release_date_level=1950-1959": "50年代",
    "market_release_date_level=1919-1949": "更早",
}

MOVIE_PAY_PARAMS = {
    RECENT_FREE_SMART_TAG_PARAM: "近期转免",
    "is_purchase=0": "免费",
    "is_cloud_cinema=1,is_purchase=1": "云影院",
    "charge_control_paymark=1_1_1,is_purchase=1": "VIP",
}

MOVIE_TIME_FILTER = {
    "label": "时间",
    "model": "year",
    "items": MOVIE_YEAR_PARAMS,
}

MOVIE_PAY_FILTER = {
    "label": "资费",
    "model": "is_purchase",
    "items": MOVIE_PAY_PARAMS,
}

VARIETY_YEAR_PARAMS = {
    "market_release_date_level=即将上线": "即将上线",
    "market_release_date_level=2026": "2026",
    "market_release_date_level=2025": "2025",
    "market_release_date_level=2024": "2024",
    "market_release_date_level=2023": "2023",
    "market_release_date_level=2022": "2022",
    "market_release_date_level=2021": "2021",
    "market_release_date_level=2020": "2020",
    "market_release_date_level=2010-2019": "10年代",
    "market_release_date_level=2000-2009": "00年代",
}

VARIETY_PAY_PARAMS = {
    RECENT_FREE_SMART_TAG_PARAM: "近期转免",
    "is_purchase=0": "免费",
    "charge_control_paymark=1_1_1,is_purchase=1": "VIP",
}

VARIETY_TIME_FILTER = {
    "label": "时间",
    "model": "year",
    "items": VARIETY_YEAR_PARAMS,
}

VARIETY_PAY_FILTER = {
    "label": "资费",
    "model": "is_purchase",
    "items": VARIETY_PAY_PARAMS,
}

ANIME_YEAR_PARAMS = {
    "market_release_date_level=即将上线": "即将上线",
    "market_release_date_level=2026": "2026",
    "market_release_date_level=2025": "2025",
    "market_release_date_level=2024": "2024",
    "market_release_date_level=2023": "2023",
    "market_release_date_level=2022": "2022",
    "market_release_date_level=2021": "2021",
    "market_release_date_level=2020": "2020",
    "market_release_date_level=2010-2019": "10年代",
    "market_release_date_level=2000-2009": "00年代",
    "market_release_date_level=1900-1999": "更早",
}

ANIME_PAY_PARAMS = {
    RECENT_FREE_SMART_TAG_PARAM: "近期转免",
    "is_purchase=0": "免费",
    "is_purchase=1": "VIP",
}

ANIME_TIME_FILTER = {
    "label": "时间",
    "model": "year",
    "items": ANIME_YEAR_PARAMS,
}

ANIME_PAY_FILTER = {
    "label": "资费",
    "model": "is_purchase",
    "items": ANIME_PAY_PARAMS,
}

CHILDREN_YEAR_PARAMS = {
    "market_release_date_level=即将上线": "即将上线",
    "market_release_date_level=2026": "2026",
    "market_release_date_level=2025": "2025",
    "market_release_date_level=2024": "2024",
    "market_release_date_level=2023": "2023",
    "market_release_date_level=2022": "2022",
    "market_release_date_level=2021": "2021",
    "market_release_date_level=2020": "2020",
    "market_release_date_level=2010-2019": "10年代",
    "market_release_date_level=2000-2009": "00年代",
}

CHILDREN_PAY_PARAMS = {
    RECENT_FREE_SMART_TAG_PARAM: "近期转免",
    "is_purchase=0": "免费",
    "charge_control_paymark=1_1_1,is_purchase=1": "VIP",
}

CHILDREN_TIME_FILTER = {
    "label": "时间",
    "model": "year",
    "items": CHILDREN_YEAR_PARAMS,
}

CHILDREN_PAY_FILTER = {
    "label": "资费",
    "model": "is_purchase",
    "items": CHILDREN_PAY_PARAMS,
}

COMIC_YEAR_PARAMS = {
    "market_release_date_level=即将上线": "即将上线",
    "market_release_date_level=2026": "2026",
    "market_release_date_level=2025": "2025",
    "market_release_date_level=2024": "2024",
    "market_release_date_level=1900-2023": "更早",
}

COMIC_PAY_PARAMS = {
    RECENT_FREE_SMART_TAG_PARAM: "近期转免",
    "is_purchase=0": "免费",
    "charge_control_paymark=1_1_1,is_purchase=1": "VIP",
}

COMIC_TIME_FILTER = {
    "label": "时间",
    "model": "year",
    "items": COMIC_YEAR_PARAMS,
}

COMIC_PAY_FILTER = {
    "label": "资费",
    "model": "is_purchase",
    "items": COMIC_PAY_PARAMS,
}

DOCUMENTARY_YEAR_PARAMS = {
    "market_release_date_level=即将上线": "即将上线",
    "market_release_date_level=2026": "2026",
    "market_release_date_level=2025": "2025",
    "market_release_date_level=2024": "2024",
    "market_release_date_level=2023": "2023",
    "market_release_date_level=2022": "2022",
    "market_release_date_level=2021": "2021",
    "market_release_date_level=2020": "2020",
    "market_release_date_level=2010-2019": "10年代",
    "market_release_date_level=2000-2009": "00年代",
}

DOCUMENTARY_PAY_PARAMS = {
    RECENT_FREE_SMART_TAG_PARAM: "近期转免",
    "is_purchase=0": "免费",
    "is_purchase=1": "VIP",
}

DOCUMENTARY_TIME_FILTER = {
    "label": "时间",
    "model": "year",
    "items": DOCUMENTARY_YEAR_PARAMS,
}

DOCUMENTARY_PAY_FILTER = {
    "label": "资费",
    "model": "is_purchase",
    "items": DOCUMENTARY_PAY_PARAMS,
}

KNOWLEDGE_PAY_PARAMS = {
    "is_purchase=0": "免费",
    "charge_control_support_tvod=1_1_1,is_purchase=1": "付费",
    "charge_control_support_monthly=1_1_1,is_purchase=1": "VIP",
}

KNOWLEDGE_PAY_FILTER = {
    "label": "资费",
    "model": "is_purchase",
    "items": KNOWLEDGE_PAY_PARAMS,
}

TV_GENRE_PARAMS = {
    "three_category_id_v2=2289882683101933": "古装",
    "three_category_id_v2=4705204050526533": "战争",
    "three_category_id_v2=3986463450987233": "谍战",
    "three_category_id_v2=8732878771828133": "爱情",
    "three_category_id_v2=2902737390744633": "罪案",
    "three_category_id_v2=5836257895783433": "悬疑",
    "three_category_id_v2=2375714428805633": "家庭",
    "three_category_id_v2=3596610849005133": "军旅",
    "three_category_id_v2=3842875764248933": "喜剧",
    "three_category_id_v2=8014138172289033": "都市",
    "three_category_id_v2=7045121828267433": "武侠",
    "three_category_id_v2=2378923092196533": "言情",
    "three_category_id_v2=4069086533300333": "偶像",
    "three_category_id_v2=8902937931540733": "青春",
    "three_category_id_v2=7146194725077733": "农村",
    "three_category_id_v2=1466860523361833": "穿越",
    "three_category_id_v2=8035796650176933": "奇幻",
    "three_category_id_v2=7174270529747133": "历史",
    "three_category_id_v2=4087536347797533": "年代",
    "three_category_id_v2=2771984357569433": "科幻",
    "three_category_id_v2=3196330091002833": "生活",
    "three_category_id_v2=3797954476777933": "剧情",
    "three_category_id_v2=2971723653646733": "励志",
    "three_category_id_v2=7399679132950733": "婚姻",
    "three_category_id_v2=7245663290192433": "警匪",
    "three_category_id_v2=7655570038367133": "犯罪",
    "three_category_id_v2=7174270529747233": "推理",
    "three_category_id_v2=3228416724910933": "商战",
    "three_category_id_v2=6147498244691133": "宫廷",
    "three_category_id_v2=2702998094667233": "仙侠",
    "three_category_id_v2=2835355459537833": "神话",
    "three_category_id_v2=7086834452347833": "动作",
    "three_category_id_v2=2681339616779433": "复仇",
    "three_category_id_v2=8391958286555633": "惊悚",
    "three_category_id_v2=2535330033": "其他",
}

TV_SUBGENRE_PARAMS = {
    "three_category_id_v2=1009625990172533": "古偶甜宠",
    "three_category_id_v2=1016043316954133": "古装探案",
    "three_category_id_v2=1138774691652233": "奇幻冒险",
    "three_category_id_v2=1383435275200733": "婚姻生活",
    "three_category_id_v2=1384237441048433": "熟龄浪漫",
    "three_category_id_v2=1515792640071333": "江湖恩怨",
    "three_category_id_v2=1674621477915933": "家族斗争",
    "three_category_id_v2=1693873458260733": "青春校园",
    "three_category_id_v2=1699488619194533": "医疗题材",
    "three_category_id_v2=1894414920185633": "古装神话",
    "three_category_id_v2=1993081319452733": "知青往事",
    "three_category_id_v2=2009926802254433": "怀旧情感",
    "three_category_id_v2=2072495738375033": "时代报告",
    "three_category_id_v2=2121427855085033": "苦情催泪",
    "three_category_id_v2=2138273337886433": "护宝传奇",
    "three_category_id_v2=2147899328059033": "警匪罪案",
    "three_category_id_v2=2186403288748633": "东方玄幻",
    "three_category_id_v2=2394966409150533": "家庭喜剧",
    "three_category_id_v2=2504863130285333": "乡村题材",
    "three_category_id_v2=2540960593431933": "民国传奇",
    "three_category_id_v2=2688559109409033": "古装喜剧",
    "three_category_id_v2=2710217587296533": "都市奇幻",
    "three_category_id_v2=2760754035701733": "英雄正义",
    "three_category_id_v2=2792840669609833": "爱情喜剧",
    "three_category_id_v2=2800862328086833": "成长烦恼",
    "three_category_id_v2=2859420434968733": "反腐倡廉",
    "three_category_id_v2=3000601624163933": "个人传奇",
    "three_category_id_v2=3002205955859333": "情感悬疑",
    "three_category_id_v2=3192319261764233": "个人成长",
    "three_category_id_v2=3567732878488133": "传统武侠",
    "three_category_id_v2=3684849092252233": "民国探案",
    "three_category_id_v2=3690464253185933": "战争传奇",
    "three_category_id_v2=3729770379723233": "都市喜剧",
    "three_category_id_v2=3755439686850133": "探寻真相",
    "three_category_id_v2=3839667100858533": "刑侦破案",
    "three_category_id_v2=3990474280225833": "女性传奇",
    "three_category_id_v2=4208663390800233": "科幻冒险",
    "three_category_id_v2=4560012032092733": "古装爱情",
    "three_category_id_v2=4604131153716233": "虐心绝症",
    "three_category_id_v2=4615361475584233": "百姓趣闻",
    "three_category_id_v2=4735686352739133": "军旅题材",
    "three_category_id_v2=4934623482968933": "警察故事",
    "three_category_id_v2=5016444399434033": "人性反思",
    "three_category_id_v2=5380627694289933": "扫黑缉毒",
    "three_category_id_v2=5671011731157433": "偶像爱情",
    "three_category_id_v2=5768875964576733": "甜虐爱情",
    "three_category_id_v2=5800160432637133": "男性传奇",
    "three_category_id_v2=5800962598484933": "奇幻爱情",
    "three_category_id_v2=5933319963355133": "破镜重圆",
    "three_category_id_v2=5962197933872333": "青春励志",
    "three_category_id_v2=7621076906916433": "仙侠玄幻",
    "three_category_id_v2=5984658577608033": "历史演义",
    "three_category_id_v2=6747518298770733": "女扮男装",
    "three_category_id_v2=6360072194331733": "前世今生",
    "three_category_id_v2=8229920785320233": "童年神剧",
    "three_category_id_v2=8122430561728733": "革命抗战",
    "three_category_id_v2=8689561816052333": "抗日战争",
    "three_category_id_v2=7864133158769133": "反特谍战",
    "three_category_id_v2=7308232226313133": "传奇变革",
    "three_category_id_v2=7374009825824433": "乱世情缘",
    "three_category_id_v2=7187907349157933": "剿匪",
    "three_category_id_v2=6767572444963133": "女性励志",
    "three_category_id_v2=7860122329530533": "年代爱情",
    "three_category_id_v2=7661987365148633": "青春爱恋",
    "three_category_id_v2=8987967511396833": "先婚后爱",
    "three_category_id_v2=6401784818411933": "推理解谜",
    "three_category_id_v2=8867642634241733": "搭档破案",
    "three_category_id_v2=6798054747175933": "都市生活",
    "three_category_id_v2=8898927102302033": "罪案纪实",
    "three_category_id_v2=7855309334444333": "都市家庭",
    "three_category_id_v2=8566830441354433": "家长里短",
    "three_category_id_v2=7913065275478833": "家庭教育",
    "three_category_id_v2=7845683344271933": "原生家庭",
    "three_category_id_v2=8506668002776933": "都市爱情",
    "three_category_id_v2=4004913265484633": "亲情",
    "three_category_id_v2=7284167250881933": "温暖人间",
    "three_category_id_v2=2789632006219233": "特种兵",
    "three_category_id_v2=8103980747231333": "青春喜剧",
    "three_category_id_v2=8045422640349333": "情景喜剧",
    "three_category_id_v2=1089040409095033": "轻喜剧",
    "three_category_id_v2=8720044118264933": "情感悬疑",
    "three_category_id_v2=8567632607202033": "追求梦想",
    "three_category_id_v2=7487917376197733": "怀旧情感",
    "three_category_id_v2=8704000801310933": "功夫武打",
    "three_category_id_v2=8696781308681733": "女性成长",
    "three_category_id_v2=3641532136476233": "浪漫",
    "three_category_id_v2=4738092850282133": "历史剧",
    "three_category_id_v2=7408502957275533": "家族兴衰",
    "three_category_id_v2=6242955980567433": "宅门风云",
    "three_category_id_v2=3540459239666133": "上海滩",
    "three_category_id_v2=8019753333222833": "超能力",
    "three_category_id_v2=7073197632936933": "个人奋斗",
    "three_category_id_v2=7872956983093833": "乡村振兴",
    "three_category_id_v2=6077709815941633": "时代变迁",
    "three_category_id_v2=5488117917881733": "职场剧",
    "three_category_id_v2=1726762258016433": "姐妹情",
    "three_category_id_v2=6238945151329033": "青年奋斗",
    "three_category_id_v2=6608743607118633": "仙情侠缘",
    "three_category_id_v2=7629098565392933": "文学改编",
}

TV_REGION_PARAMS = {
    "three_category_id_v2=8052642132978633": "内地",
    "three_category_id_v2=6679334201716133": "中国香港",
    "three_category_id_v2=5724756842953133": "中国台湾",
    "three_category_id_v2=8097563420449933": "美国",
    "three_category_id_v2=4017747919047533": "韩国",
    "three_category_id_v2=7671613355321033": "泰国",
    "three_category_id_v2=6234934322090433": "日本",
    "three_category_id_v2=6993783214014833": "英国",
    "three_category_id_v2=2283850033": "其他",
}

TV_HALL_PARAMS = {
    "smart_tag_v2=荣誉殿堂": "荣誉殿堂",
    "smart_tag_v2=国民殿堂": "国民殿堂",
    "smart_tag_v2=人气殿堂": "人气殿堂",
    "smart_tag_v2=佳片殿堂": "佳片殿堂",
}

TV_SPEC_PARAMS = {
    "is_qiyi_produced=1": "自制",
    "is_exclusive=1": "独播",
}

TV_AWARD_PARAMS = {
    "structure_id=95be70850d6d967f_2_9": "白玉兰奖",
    "structure_id=25e3cb1182fe4d8e_2_9": "飞天奖",
    "structure_id=73c6eb6653d2771c_2_9": "金鹰奖",
}

TV_THEATER_PARAMS = {
    "smart_tag_v2=迷雾剧场": "迷雾剧场",
    "smart_tag_v2=恋恋剧场": "恋恋剧场",
    "smart_tag_v2=小逗剧场": "小逗剧场",
    "smart_tag_v2=大家剧场": "大家剧场",
    "smart_tag_v2=微尘剧场": "微尘剧场",
}

TV_ACTOR_PARAMS = {
    "smart_tag_v2=张凌赫": "张凌赫",
    "smart_tag_v2=黄景瑜": "黄景瑜",
    "smart_tag_v2=田曦薇": "田曦薇",
    "smart_tag_v2=白鹿": "白鹿",
    "smart_tag_v2=杨志刚": "杨志刚",
    "smart_tag_v2=欧豪": "欧豪",
    "smart_tag_v2=于和伟": "于和伟",
    "smart_tag_v2=张嘉益": "张嘉益",
    "smart_tag_v2=张译": "张译",
    "smart_tag_v2=杨旭文": "杨旭文",
    "smart_tag_v2=郭京飞": "郭京飞",
    "smart_tag_v2=任嘉伦": "任嘉伦",
    "smart_tag_v2=赵丽颖": "赵丽颖",
    "smart_tag_v2=孙俪": "孙俪",
    "smart_tag_v2=靳东": "靳东",
    "smart_tag_v2=李沁": "李沁",
    "smart_tag_v2=虞书欣": "虞书欣",
    "smart_tag_v2=曾舜晞": "曾舜晞",
    "smart_tag_v2=宋轶": "宋轶",
    "smart_tag_v2=白宇": "白宇",
}

TV_RECOMMEND_PARAMS = {
    "structure_id=812b38302498d408_2_7": "豆瓣高分",
    "smart_tag_v2=热度破10000": "热度破10000",
    "smart_tag_v2=评论破1000万": "评论破1000万",
    "smart_tag_v2=弹幕破1000万": "弹幕破1000万",
}

TIME_FILTER = {
    "label": "时间",
    "model": "year",
    "items": YEAR_PARAMS,
}

PAY_FILTER = {
    "label": "资费",
    "model": "is_purchase",
    "items": PAY_PARAMS,
}

SHORT_DRAMA_TIME_FILTER = {
    "label": "时间",
    "model": "year",
    "items": SHORT_DRAMA_YEAR_PARAMS,
}

SHORT_DRAMA_PAY_FILTER = {
    "label": "资费",
    "model": "is_purchase",
    "items": SHORT_DRAMA_PAY_PARAMS,
}

FILTER_GROUPS = {
    "tv": [
        {
            "label": "类型",
            "model": "genre",
            "items": TV_GENRE_PARAMS,
        },
        {
            "label": "细选",
            "model": "subgenre",
            "items": TV_SUBGENRE_PARAMS,
        },
        {
            "label": "地区",
            "model": "region",
            "items": TV_REGION_PARAMS,
        },
        TIME_FILTER,
        PAY_FILTER,
        {
            "label": "殿堂",
            "model": "hall",
            "items": TV_HALL_PARAMS,
        },
        {
            "label": "规格",
            "model": "spec",
            "items": TV_SPEC_PARAMS,
        },
        {
            "label": "奖项",
            "model": "award",
            "items": TV_AWARD_PARAMS,
        },
        {
            "label": "剧场",
            "model": "theater",
            "items": TV_THEATER_PARAMS,
        },
        {
            "label": "演员",
            "model": "actor",
            "items": TV_ACTOR_PARAMS,
        },
        {
            "label": "推荐",
            "model": "recommend",
            "items": TV_RECOMMEND_PARAMS,
        },
    ],
    "short_drama": [
        {
            "label": "类型",
            "model": "genre",
            "items": {
                "smart_tag_v2=穿越": "穿越",
                "smart_tag_v2=逆袭": "逆袭",
                "smart_tag_v2=重生": "重生",
                "smart_tag_v2=爱情": "爱情",
                "smart_tag_v2=玄幻": "玄幻",
                "smart_tag_v2=现代言情": "现代言情",
                "smart_tag_v2=总裁": "总裁",
                "smart_tag_v2=虐恋": "虐恋",
                "smart_tag_v2=甜宠": "甜宠",
                "smart_tag_v2=神豪": "神豪",
                "smart_tag_v2=女性成长": "女性成长",
                "smart_tag_v2=古风权谋": "古风权谋",
                "smart_tag_v2=家庭伦理": "家庭伦理",
                "smart_tag_v2=复仇": "复仇",
                "smart_tag_v2=悬疑推理": "悬疑推理",
                "smart_tag_v2=古风言情": "古风言情",
                "smart_tag_v2=生活": "生活",
                "smart_tag_v2=刑侦": "刑侦",
                "smart_tag_v2=恐怖": "恐怖",
            },
        },
        {
            "label": "受众",
            "model": "audience",
            "items": {
                "smart_tag_v2=男频": "男频",
                "smart_tag_v2=女频": "女频",
            },
        },
        SHORT_DRAMA_TIME_FILTER,
        SHORT_DRAMA_PAY_FILTER,
        {
            "label": "设定",
            "model": "setting",
            "items": {
                "smart_tag_v2=大女主": "大女主",
                "smart_tag_v2=马甲": "马甲",
                "smart_tag_v2=小人物": "小人物",
                "smart_tag_v2=无敌神医": "无敌神医",
                "smart_tag_v2=草根": "草根",
                "smart_tag_v2=扮猪吃虎": "扮猪吃虎",
                "smart_tag_v2=青梅竹马": "青梅竹马",
                "smart_tag_v2=打脸虐渣": "打脸虐渣",
                "smart_tag_v2=先婚后爱": "先婚后爱",
                "smart_tag_v2=都市修仙": "都市修仙",
                "smart_tag_v2=闪婚": "闪婚",
                "smart_tag_v2=萌宝": "萌宝",
                "smart_tag_v2=豪门恩怨": "豪门恩怨",
                "smart_tag_v2=强者回归": "强者回归",
                "smart_tag_v2=破镜重圆": "破镜重圆",
                "smart_tag_v2=欢喜冤家": "欢喜冤家",
                "smart_tag_v2=赘婿逆袭": "赘婿逆袭",
                "smart_tag_v2=暗恋成真": "暗恋成真",
                "smart_tag_v2=亲情": "亲情",
                "smart_tag_v2=传承觉醒": "传承觉醒",
            },
        },
        {
            "label": "背景",
            "model": "background",
            "items": {
                "smart_tag_v2=古风": "古风",
                "smart_tag_v2=架空": "架空",
                "smart_tag_v2=民国": "民国",
                "smart_tag_v2=乡村": "乡村",
                "smart_tag_v2=现代": "现代",
                "smart_tag_v2=星际": "星际",
                "smart_tag_v2=都市": "都市",
            },
        },
    ],
    "movie": [
        {
            "label": "类型",
            "model": "genre",
            "items": {
                "three_category_id_v2=3842875764248933": "喜剧",
                "three_category_id_v2=7821618368840933": "动画",
                "three_category_id_v2=7086834452347833": "动作",
                "three_category_id_v2=8732878771828133": "爱情",
                "three_category_id_v2=7128547076428333": "恐怖",
                "three_category_id_v2=4705204050526533": "战争",
                "three_category_id_v2=8391958286555633": "惊悚",
                "three_category_id_v2=8201844980650933": "枪战",
                "three_category_id_v2=2771984357569433": "科幻",
                "three_category_id_v2=7655570038367133": "犯罪",
                "three_category_id_v2=5836257895783433": "悬疑",
                "three_category_id_v2=8035796650176933": "奇幻",
                "three_category_id_v2=3797954476777933": "剧情",
                "three_category_id_v2=8902937931540733": "青春",
                "three_category_id_v2=2094956382110833": "冒险",
                "three_category_id_v2=2375714428805633": "家庭",
                "three_category_id_v2=2679735285084233": "少儿",
                "three_category_id_v2=7245663290192433": "警匪",
                "three_category_id_v2=7174270529747133": "历史",
                "three_category_id_v2=7045121828267433": "武侠",
                "three_category_id_v2=6015140879820833": "伦理",
                "three_category_id_v2=3281359670859033": "灾难",
                "three_category_id_v2=5002807580023233": "传记",
                "three_category_id_v2=3341522109436533": "运动",
                "three_category_id_v2=1247067081091833": "音乐",
                "three_category_id_v2=4150907449765833": "魔幻",
                "three_category_id_v2=3567732878487833": "歌舞",
                "three_category_id_v2=8795447707948733": "戏曲",
                "three_category_id_v2=2951669507454533": "玄幻",
                "three_category_id_v2=5156021256933833": "悲剧",
                "three_category_id_v2=7455830742289933": "史诗",
                "three_category_id_v2=3727363882180333": "西部",
                "three_category_id_v2=1535330033": "其他",
            },
        },
        {
            "label": "地区",
            "model": "region",
            "items": {
                "three_category_id_v2=8052642132978633": "内地",
                "three_category_id_v2=6679334201716133": "中国香港",
                "three_category_id_v2=5724756842953133": "中国台湾",
                "three_category_id_v2=8097563420449933": "美国",
                "three_category_id_v2=4017747919047533": "韩国",
                "three_category_id_v2=6234934322090433": "日本",
                "three_category_id_v2=3299007319508333": "欧洲",
                "three_category_id_v2=8084728766886733": "印度",
                "three_category_id_v2=7671613355321033": "泰国",
                "three_category_id_v2=4957084126704233": "丹麦",
                "three_category_id_v2=6993783214014833": "英国",
                "three_category_id_v2=1283850033": "其他",
            },
        },
        MOVIE_TIME_FILTER,
        MOVIE_PAY_FILTER,
        {
            "label": "奖项",
            "model": "award",
            "items": {
                "smart_tag_v2=奥斯卡": "奥斯卡",
                "smart_tag_v2=金像奖": "金像奖",
                "smart_tag_v2=金鸡奖": "金鸡奖",
                "smart_tag_v2=戛纳电影节": "戛纳电影节",
                "smart_tag_v2=威尼斯电影节": "威尼斯电影节",
                "smart_tag_v2=柏林电影节": "柏林电影节",
                "smart_tag_v2=金球奖": "金球奖",
                "smart_tag_v2=华表奖": "华表奖",
            },
        },
        {
            "label": "推荐",
            "model": "recommend",
            "items": {
                "smart_tag_v2=高分悬疑片": "高分悬疑片",
                "smart_tag_v2=高票房": "高票房",
                "smart_tag_v2=高分战争片": "高分战争片",
                "smart_tag_v2=高分喜剧片": "高分喜剧片",
                "smart_tag_v2=冷门佳作": "冷门佳作",
                "structure_id=812b38302498d408_1_7": "豆瓣高分",
            },
        },
    ],
    "variety": [
        {
            "label": "类型",
            "model": "genre",
            "items": {
                "three_category_id_v2=3842875764248933": "喜剧",
                "three_category_id_v2=7220796148913633": "真人秀",
                "three_category_id_v2=1733179584798033": "音乐",
                "three_category_id_v2=2279454527081633": "脱口秀",
                "three_category_id_v2=3840469266705833": "观察",
                "three_category_id_v2=7119723252103433": "访谈",
                "three_category_id_v2=2709415421448933": "游戏",
                "three_category_id_v2=6413015140279833": "晚会",
                "three_category_id_v2=6011130050582133": "曲艺",
                "three_category_id_v2=6149904742234233": "竞技",
                "three_category_id_v2=1977840168346533": "竞演",
                "three_category_id_v2=1026471472974333": "文化",
                "three_category_id_v2=6535330033": "其他",
            },
        },
        {
            "label": "地区",
            "model": "region",
            "items": {
                "three_category_id_v2=8052642132978633": "内地",
                "three_category_id_v2=1681038804697433": "港台",
                "three_category_id_v2=4017747919047533;should,three_category_id_v2=8936628897143933;should": "海外",
            },
        },
        VARIETY_TIME_FILTER,
        VARIETY_PAY_FILTER,
        {
            "label": "风格",
            "model": "style",
            "items": {
                "three_category_id_v2=4749323172149933": "搞笑",
                "three_category_id_v2=1828637320674233": "烧脑",
                "three_category_id_v2=2840168454623933": "合家欢",
                "three_category_id_v2=7164644539574633": "治愈",
                "three_category_id_v2=5898826831904033": "慢生活",
            },
        },
    ],
    "anime": [
        {
            "label": "类型",
            "model": "genre",
            "items": {
                "three_category_id_v2=2951669507454533": "玄幻",
                "three_category_id_v2=8035796650176933": "奇幻",
                "three_category_id_v2=7045121828267433": "武侠",
                "three_category_id_v2=1843878471780633": "恋爱",
                "three_category_id_v2=1708312443519433": "搞笑",
                "three_category_id_v2=5354958387163433": "冒险",
                "three_category_id_v2=1521407801005233": "热血",
                "three_category_id_v2=6219693170984133": "治愈",
                "three_category_id_v2=2771984357569433": "科幻",
                "three_category_id_v2=7174270529747233": "推理",
                "three_category_id_v2=6149904742234233": "竞技",
                "three_category_id_v2=2971723653646733": "励志",
                "three_category_id_v2=4684347738486233": "机战",
                "three_category_id_v2=4069086533300333": "偶像",
                "three_category_id_v2=4535330033": "其他",
            },
        },
        {
            "label": "地区",
            "model": "region",
            "items": {
                "three_category_id_v2=8052642132978633": "内地",
                "three_category_id_v2=6234934322090433": "日本",
                "three_category_id_v2=8936628897143933": "欧美",
                "three_category_id_v2=4283850033": "其他",
            },
        },
        ANIME_TIME_FILTER,
        ANIME_PAY_FILTER,
        {
            "label": "连载",
            "model": "serial",
            "items": {
                "is_album_finished=0": "连载中",
                "is_album_finished=1": "已完结",
            },
        },
        {
            "label": "版本",
            "model": "version",
            "items": {
                "three_category_id_v2=3419332196663433": "动画",
                "three_category_id_v2=2276245863690833": "动画电影",
                "three_category_id_v2=6566228817190733": "动态漫画",
            },
        },
    ],
    "children": [
        {
            "label": "年龄",
            "model": "age",
            "items": {
                "three_category_id_v2=8422440588768333": "0-1岁",
                "three_category_id_v2=5988669406846533": "2-3岁",
                "three_category_id_v2=2853805274034833": "4-6岁",
                "three_category_id_v2=2913165546764733": "7-10岁",
                "three_category_id_v2=6134663591127833": "11-14岁",
            },
        },
        CHILDREN_TIME_FILTER,
        CHILDREN_PAY_FILTER,
        {
            "label": "类型",
            "model": "genre",
            "items": {
                "smart_tag_v2=动画": "看动画",
                "smart_tag_v2=玩玩具": "玩玩具",
                "three_category_id_v2=1247067081091833": "听儿歌",
                "smart_tag_v2=绘本": "看绘本",
                "three_category_id_v2=3087235535715533": "涨知识",
                "three_category_id_v2=4826331093529133": "学英语",
                "smart_tag_v2=拼音": "识字拼音",
                "three_category_id_v2=2988569136448533": "好习惯",
                "three_category_id_v2=8865236136698633": "国学",
                "three_category_id_v2=4610548480497933": "做手工",
                "three_category_id_v2=7362779503956633": "冒险救援",
                "three_category_id_v2=7308232226313233": "生活日常",
                "three_category_id_v2=1708312443519433": "搞笑",
                "three_category_id_v2=1683445302240633": "动物",
                "three_category_id_v2=3067181389523233": "公主",
            },
        },
        {
            "label": "系列",
            "model": "series",
            "items": {
                "smart_tag_v2=小猪佩奇": "小猪佩奇",
                "smart_tag_v2=汪汪队立大功": "汪汪队",
                "smart_tag_v2=猪猪侠": "猪猪侠",
                "smart_tag_v2=喜羊羊与灰太狼": "喜羊羊与灰太狼",
                "smart_tag_v2=超级飞侠": "超级飞侠",
                "smart_tag_v2=猫和老鼠": "猫和老鼠",
                "smart_tag_v2=海绵宝宝": "海绵宝宝",
                "smart_tag_v2=小马宝莉": "小马宝莉",
                "smart_tag_v2=迷你特工队": "迷你特工队",
                "smart_tag_v2=托马斯和他的朋友们": "托马斯",
                "smart_tag_v2=芭比": "芭比",
            },
        },
        {
            "label": "语种",
            "model": "language",
            "items": {
                "smart_tag_v2=普通话": "普通话",
                "smart_tag_v2=英语": "英语",
            },
        },
    ],
    "comic": [
        {
            "label": "类型",
            "model": "genre",
            "items": {
                "smart_tag_v2=逆袭": "逆袭",
                "smart_tag_v2=穿越": "穿越",
                "smart_tag_v2=大女主": "大女主",
                "smart_tag_v2=系统": "系统",
                "smart_tag_v2=玄幻": "玄幻",
                "smart_tag_v2=搞笑": "搞笑",
                "smart_tag_v2=废柴": "废柴",
                "smart_tag_v2=悬疑": "悬疑",
                "smart_tag_v2=恋爱": "恋爱",
                "smart_tag_v2=末日": "末日",
                "smart_tag_v2=战神": "战神",
                "smart_tag_v2=扮猪吃老虎": "扮猪吃老虎",
                "smart_tag_v2=修仙": "修仙",
                "smart_tag_v2=觉醒": "觉醒",
                "smart_tag_v2=无敌": "无敌",
                "smart_tag_v2=科幻": "科幻",
                "smart_tag_v2=开局": "开局",
                "smart_tag_v2=异能": "异能",
            },
        },
        {
            "label": "受众",
            "model": "audience",
            "items": {
                "smart_tag_v2=男频": "男频",
                "smart_tag_v2=女频": "女频",
                "smart_tag_v2=平衡": "平衡",
            },
        },
        COMIC_TIME_FILTER,
        COMIC_PAY_FILTER,
    ],
    "documentary": [
        {
            "label": "类型",
            "model": "genre",
            "items": {
                "three_category_id_v2=7300210567835933": "自然",
                "three_category_id_v2=6475584076400333": "历史",
                "three_category_id_v2=2792840669609633": "人文",
                "three_category_id_v2=7186303017462533": "美食",
                "three_category_id_v2=8175373507676633": "医疗",
                "three_category_id_v2=1001604331695633": "萌宠",
                "three_category_id_v2=7533640829516933": "财经",
                "three_category_id_v2=4041812894478533": "罪案",
                "three_category_id_v2=7705304320924433": "竞技",
                "three_category_id_v2=7213576656284533": "灾难",
                "three_category_id_v2=8326180687044233": "军事",
                "three_category_id_v2=3891005715111133": "探险",
                "three_category_id_v2=5675022560395733": "社会",
                "three_category_id_v2=3208362578718433": "科技",
                "three_category_id_v2=5893211670970233": "旅游",
                "three_category_id_v2=3412120033": "其他",
            },
        },
        {
            "label": "出品",
            "model": "producer",
            "items": {
                "three_category_id_v2=4748521006302433": "爱奇艺",
                "three_category_id_v2=6612754436357133": "央视",
                "three_category_id_v2=1827835154826533": "BBC",
                "three_category_id_v2=1169256993864833": "国家地理",
                "three_category_id_v2=2180788127814633": "探索频道",
                "three_category_id_v2=5823423242220333": "美国历史频道",
                "three_category_id_v2=8363882481886233": "朗思文化",
                "three_category_id_v2=3773970033": "其他",
            },
        },
        {
            "label": "地区",
            "model": "region",
            "items": {
                "three_category_id=": "国内",
                "three_category_id=20324": "国外",
            },
        },
        DOCUMENTARY_TIME_FILTER,
        DOCUMENTARY_PAY_FILTER,
    ],
    "knowledge": [
        {
            "label": "类型",
            "model": "genre",
            "items": {
                "three_category_id_v2=3082422540629633": "亲子",
                "three_category_id_v2=4431665496460733": "文史",
                "three_category_id_v2=2183194625357733": "中小学",
                "three_category_id_v2=2442294194164733": "外语",
                "three_category_id_v2=2433470369840033": "运动健身",
                "three_category_id_v2=3706507570139933": "艺术",
                "three_category_id_v2=6382532838067233": "职场",
                "three_category_id_v2=5755239145165733": "财经",
                "three_category_id_v2=5942143787679933": "生活",
                "three_category_id_v2=3930311841648333": "心理",
                "three_category_id_v2=3284568334250033": "互联网",
                "three_category_id_v2=4968314448572033": "职业考证",
                "three_category_id_v2=2229720244524333": "健康",
                "three_category_id_v2=7060362979373733": "大学",
                "three_category_id_v2=6984959389689933": "党政",
            },
        },
        {
            "label": "年级",
            "model": "grade",
            "items": {
                "three_category_id_v2=5853103378585233": "一年级",
                "three_category_id_v2=3886192720024833": "二年级",
                "three_category_id_v2=1940138373505033": "三年级",
                "three_category_id_v2=6521307529719633": "四年级",
                "three_category_id_v2=5301213275367933": "五年级",
                "three_category_id_v2=4675523914161533": "六年级",
                "three_category_id_v2=6567030983038233": "初一",
                "three_category_id_v2=2838564122928733": "初二",
                "three_category_id_v2=7171864032204133": "初三",
                "three_category_id_v2=8479394363954933": "高一",
                "three_category_id_v2=4648250275339933": "高二",
                "three_category_id_v2=7410107288970933": "高三",
            },
        },
        {
            "label": "科目",
            "model": "subject",
            "items": {
                "three_category_id_v2=7111701593626433": "语文",
                "three_category_id_v2=8033390152633733": "数学",
                "three_category_id_v2=2402185901779733": "英语",
            },
        },
        KNOWLEDGE_PAY_FILTER,
    ],
}


def __load_official_filter_groups() -> Dict[str, List[dict]]:
    """
    Load verified filter params captured from iQIYI's official videolib tag API.
    """
    path = Path(__file__).with_name("official_filters.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        filters = payload.get("filters") or {}
        return {
            str(channel): [
                {
                    "label": str(group["label"]),
                    "model": str(group["model"]),
                    "items": dict(group.get("items") or {}),
                }
                for group in groups
                if isinstance(group, dict) and group.get("label") and group.get("model")
            ]
            for channel, groups in filters.items()
            if isinstance(groups, list)
        }
    except Exception as err:
        logger.warning(f"加载爱奇艺官方筛选参数失败，使用内置兜底参数：{err}")
        return {}


def __load_official_linked_subgenres() -> Dict[str, Dict[str, Dict[str, str]]]:
    """
    读取官方类型到细选的联动参数。
    """
    path = Path(__file__).with_name("official_filters.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        linked_subgenres = payload.get("linked_subgenres") or {}
        normalized: Dict[str, Dict[str, Dict[str, str]]] = {}
        for channel, channel_mapping in linked_subgenres.items():
            if not isinstance(channel_mapping, dict):
                continue
            normalized_channel: Dict[str, Dict[str, str]] = {}
            for genre_param, subgenre_items in channel_mapping.items():
                if not isinstance(subgenre_items, dict) or not subgenre_items:
                    continue
                normalized_channel[str(genre_param)] = {
                    str(param): str(text)
                    for param, text in subgenre_items.items()
                }
            if normalized_channel:
                normalized[str(channel)] = normalized_channel
        return normalized
    except Exception as err:
        logger.warning(f"加载爱奇艺官方联动细选失败，使用内置兜底参数：{err}")
        return {}


TV_SUBGENRE_PARAMS_BY_GENRE = {
    "three_category_id_v2=2289882683101933": {
        "": "全部",
        "three_category_id_v2=4560012032092733": "古装爱情",
        "three_category_id_v2=2688559109409033": "古装喜剧",
        "three_category_id_v2=1009625990172533": "古偶甜宠",
        "three_category_id_v2=1016043316954133": "古装探案",
        "three_category_id_v2=1894414920185633": "古装神话",
        "three_category_id_v2=1515792640071333": "江湖恩怨",
        "three_category_id_v2=2186403288748633": "东方玄幻",
        "three_category_id_v2=7621076906916433": "仙侠玄幻",
        "three_category_id_v2=3567732878488133": "传统武侠",
        "three_category_id_v2=5768875964576733": "甜虐爱情",
        "three_category_id_v2=5984658577608033": "历史演义",
        "three_category_id_v2=6747518298770733": "女扮男装",
        "three_category_id_v2=6360072194331733": "前世今生",
        "three_category_id_v2=8229920785320233": "童年神剧",
    },
    "three_category_id_v2=4705204050526533": {
        "": "全部",
        "three_category_id_v2=8122430561728733": "革命抗战",
        "three_category_id_v2=3690464253185933": "战争传奇",
        "three_category_id_v2=8689561816052333": "抗日战争",
        "three_category_id_v2=7864133158769133": "反特谍战",
        "three_category_id_v2=3192319261764233": "个人成长",
        "three_category_id_v2=7308232226313133": "传奇变革",
        "three_category_id_v2=2540960593431933": "民国传奇",
        "three_category_id_v2=7374009825824433": "乱世情缘",
        "three_category_id_v2=7187907349157933": "剿匪",
    },
    "three_category_id_v2=3986463450987233": {
        "": "全部",
        "three_category_id_v2=7864133158769133": "反特谍战",
        "three_category_id_v2=3690464253185933": "战争传奇",
        "three_category_id_v2=8689561816052333": "抗日战争",
        "three_category_id_v2=8122430561728733": "革命抗战",
        "three_category_id_v2=3192319261764233": "个人成长",
        "three_category_id_v2=6767572444963133": "女性励志",
    },
    "three_category_id_v2=8732878771828133": {
        "": "全部",
        "three_category_id_v2=4560012032092733": "古装爱情",
        "three_category_id_v2=5671011731157433": "偶像爱情",
        "three_category_id_v2=1384237441048433": "熟龄浪漫",
        "three_category_id_v2=5768875964576733": "甜虐爱情",
        "three_category_id_v2=7860122329530533": "年代爱情",
        "three_category_id_v2=1383435275200733": "婚姻生活",
        "three_category_id_v2=7661987365148633": "青春爱恋",
        "three_category_id_v2=7374009825824433": "乱世情缘",
        "three_category_id_v2=5933319963355133": "破镜重圆",
        "three_category_id_v2=8987967511396833": "先婚后爱",
    },
    "three_category_id_v2=2902737390744633": {
        "": "全部",
        "three_category_id_v2=2147899328059033": "警匪罪案",
        "three_category_id_v2=5380627694289933": "扫黑缉毒",
        "three_category_id_v2=2760754035701733": "英雄正义",
        "three_category_id_v2=4934623482968933": "警察故事",
        "three_category_id_v2=3839667100858533": "刑侦破案",
        "three_category_id_v2=6401784818411933": "推理解谜",
        "three_category_id_v2=8867642634241733": "搭档破案",
        "three_category_id_v2=3755439686850133": "探寻真相",
        "three_category_id_v2=2859420434968733": "反腐倡廉",
        "three_category_id_v2=6798054747175933": "都市生活",
        "three_category_id_v2=8898927102302033": "罪案纪实",
        "three_category_id_v2=5016444399434033": "人性反思",
    },
    "three_category_id_v2=5836257895783433": {
        "": "全部",
        "three_category_id_v2=2147899328059033": "警匪罪案",
        "three_category_id_v2=1016043316954133": "古装探案",
        "three_category_id_v2=6401784818411933": "推理解谜",
        "three_category_id_v2=2710217587296533": "都市奇幻",
        "three_category_id_v2=7864133158769133": "反特谍战",
        "three_category_id_v2=2760754035701733": "英雄正义",
        "three_category_id_v2=3839667100858533": "刑侦破案",
        "three_category_id_v2=5380627694289933": "扫黑缉毒",
        "three_category_id_v2=3684849092252233": "民国探案",
        "three_category_id_v2=2138273337886433": "护宝传奇",
    },
    "three_category_id_v2=2375714428805633": {
        "": "全部",
        "three_category_id_v2=7855309334444333": "都市家庭",
        "three_category_id_v2=6798054747175933": "都市生活",
        "three_category_id_v2=1383435275200733": "婚姻生活",
        "three_category_id_v2=8566830441354433": "家长里短",
        "three_category_id_v2=7913065275478833": "家庭教育",
        "three_category_id_v2=7845683344271933": "原生家庭",
        "three_category_id_v2=2009926802254433": "怀旧情感",
        "three_category_id_v2=1384237441048433": "熟龄浪漫",
        "three_category_id_v2=8506668002776933": "都市爱情",
        "three_category_id_v2=4004913265484633": "亲情",
        "three_category_id_v2=7284167250881933": "温暖人间",
        "three_category_id_v2=2504863130285333": "乡村题材",
    },
    "three_category_id_v2=3596610849005133": {
        "": "全部",
        "three_category_id_v2=4735686352739133": "军旅题材",
        "three_category_id_v2=2760754035701733": "英雄正义",
        "three_category_id_v2=3192319261764233": "个人成长",
        "three_category_id_v2=2789632006219233": "特种兵",
    },
    "three_category_id_v2=3842875764248933": {
        "": "全部",
        "three_category_id_v2=2688559109409033": "古装喜剧",
        "three_category_id_v2=8103980747231333": "青春喜剧",
        "three_category_id_v2=8045422640349333": "情景喜剧",
        "three_category_id_v2=2792840669609833": "爱情喜剧",
        "three_category_id_v2=2394966409150533": "家庭喜剧",
        "three_category_id_v2=1089040409095033": "轻喜剧",
        "three_category_id_v2=4615361475584233": "百姓趣闻",
        "three_category_id_v2=6798054747175933": "都市生活",
        "three_category_id_v2=4560012032092733": "古装爱情",
        "three_category_id_v2=8506668002776933": "都市爱情",
        "three_category_id_v2=5671011731157433": "偶像爱情",
    },
    "three_category_id_v2=8014138172289033": {
        "": "全部",
        "three_category_id_v2=6798054747175933": "都市生活",
        "three_category_id_v2=7855309334444333": "都市家庭",
        "three_category_id_v2=8506668002776933": "都市爱情",
        "three_category_id_v2=2710217587296533": "都市奇幻",
        "three_category_id_v2=3729770379723233": "都市喜剧",
        "three_category_id_v2=1384237441048433": "熟龄浪漫",
        "three_category_id_v2=1383435275200733": "婚姻生活",
        "three_category_id_v2=8566830441354433": "家长里短",
        "three_category_id_v2=5671011731157433": "偶像爱情",
        "three_category_id_v2=2147899328059033": "警匪罪案",
        "three_category_id_v2=8720044118264933": "情感悬疑",
        "three_category_id_v2=8567632607202033": "追求梦想",
        "three_category_id_v2=7487917376197733": "怀旧情感",
    },
    "three_category_id_v2=7045121828267433": {
        "": "全部",
        "three_category_id_v2=1515792640071333": "江湖恩怨",
        "three_category_id_v2=3567732878488133": "传统武侠",
        "three_category_id_v2=8229920785320233": "童年神剧",
        "three_category_id_v2=8704000801310933": "功夫武打",
        "three_category_id_v2=4560012032092733": "古装爱情",
        "three_category_id_v2=5768875964576733": "甜虐爱情",
        "three_category_id_v2=3192319261764233": "个人成长",
    },
    "three_category_id_v2=2378923092196533": {
        "": "全部",
        "three_category_id_v2=4560012032092733": "古装爱情",
        "three_category_id_v2=5671011731157433": "偶像爱情",
        "three_category_id_v2=8506668002776933": "都市爱情",
        "three_category_id_v2=1383435275200733": "婚姻生活",
        "three_category_id_v2=1384237441048433": "熟龄浪漫",
        "three_category_id_v2=8566830441354433": "家长里短",
        "three_category_id_v2=6798054747175933": "都市生活",
        "three_category_id_v2=7855309334444333": "都市家庭",
        "three_category_id_v2=7487917376197733": "怀旧情感",
        "three_category_id_v2=7374009825824433": "乱世情缘",
        "three_category_id_v2=5933319963355133": "破镜重圆",
        "three_category_id_v2=5768875964576733": "甜虐爱情",
        "three_category_id_v2=8696781308681733": "女性成长",
        "three_category_id_v2=4004913265484633": "亲情",
    },
    "three_category_id_v2=4069086533300333": {
        "": "全部",
        "three_category_id_v2=5671011731157433": "偶像爱情",
        "three_category_id_v2=3641532136476233": "浪漫",
        "three_category_id_v2=7661987365148633": "青春爱恋",
        "three_category_id_v2=1693873458260733": "青春校园",
        "three_category_id_v2=8567632607202033": "追求梦想",
        "three_category_id_v2=8506668002776933": "都市爱情",
        "three_category_id_v2=1384237441048433": "熟龄浪漫",
        "three_category_id_v2=6767572444963133": "女性励志",
        "three_category_id_v2=3192319261764233": "个人成长",
    },
    "three_category_id_v2=8902937931540733": {
        "": "全部",
        "three_category_id_v2=1693873458260733": "青春校园",
        "three_category_id_v2=5962197933872333": "青春励志",
        "three_category_id_v2=8567632607202033": "追求梦想",
        "three_category_id_v2=5671011731157433": "偶像爱情",
        "three_category_id_v2=7661987365148633": "青春爱恋",
        "three_category_id_v2=8506668002776933": "都市爱情",
        "three_category_id_v2=6798054747175933": "都市生活",
        "three_category_id_v2=6767572444963133": "女性励志",
        "three_category_id_v2=3192319261764233": "个人成长",
        "three_category_id_v2=2800862328086833": "成长烦恼",
    },
    "three_category_id_v2=7146194725077733": {
        "": "全部",
        "three_category_id_v2=2504863130285333": "乡村题材",
        "three_category_id_v2=2072495738375033": "时代报告",
    },
    "three_category_id_v2=1466860523361833": {
        "": "全部",
        "three_category_id_v2=4560012032092733": "古装爱情",
        "three_category_id_v2=1009625990172533": "古偶甜宠",
        "three_category_id_v2=5671011731157433": "偶像爱情",
        "three_category_id_v2=2710217587296533": "都市奇幻",
        "three_category_id_v2=7661987365148633": "青春爱恋",
        "three_category_id_v2=5800962598484933": "奇幻爱情",
        "three_category_id_v2=5768875964576733": "甜虐爱情",
    },
    "three_category_id_v2=8035796650176933": {
        "": "全部",
        "three_category_id_v2=5800962598484933": "奇幻爱情",
        "three_category_id_v2=1138774691652233": "奇幻冒险",
        "three_category_id_v2=2710217587296533": "都市奇幻",
        "three_category_id_v2=6360072194331733": "前世今生",
        "three_category_id_v2=4560012032092733": "古装爱情",
        "three_category_id_v2=5671011731157433": "偶像爱情",
        "three_category_id_v2=7661987365148633": "青春爱恋",
        "three_category_id_v2=5768875964576733": "甜虐爱情",
    },
    "three_category_id_v2=7174270529747133": {
        "": "全部",
        "three_category_id_v2=5984658577608033": "历史演义",
        "three_category_id_v2=8122430561728733": "革命抗战",
        "three_category_id_v2=3000601624163933": "个人传奇",
        "three_category_id_v2=4738092850282133": "历史剧",
    },
    "three_category_id_v2=4087536347797533": {
        "": "全部",
        "three_category_id_v2=7374009825824433": "乱世情缘",
        "three_category_id_v2=7860122329530533": "年代爱情",
        "three_category_id_v2=7408502957275533": "家族兴衰",
        "three_category_id_v2=7487917376197733": "怀旧情感",
        "three_category_id_v2=1674621477915933": "家族斗争",
        "three_category_id_v2=3690464253185933": "战争传奇",
        "three_category_id_v2=6242955980567433": "宅门风云",
        "three_category_id_v2=8122430561728733": "革命抗战",
        "three_category_id_v2=3540459239666133": "上海滩",
    },
    "three_category_id_v2=2771984357569433": {
        "": "全部",
        "three_category_id_v2=4208663390800233": "科幻冒险",
        "three_category_id_v2=2710217587296533": "都市奇幻",
        "three_category_id_v2=1138774691652233": "奇幻冒险",
        "three_category_id_v2=8019753333222833": "超能力",
    },
    "three_category_id_v2=3196330091002833": {
        "": "全部",
        "three_category_id_v2=6798054747175933": "都市生活",
        "three_category_id_v2=8566830441354433": "家长里短",
        "three_category_id_v2=7284167250881933": "温暖人间",
        "three_category_id_v2=7855309334444333": "都市家庭",
        "three_category_id_v2=2121427855085033": "苦情催泪",
        "three_category_id_v2=4615361475584233": "百姓趣闻",
        "three_category_id_v2=8720044118264933": "情感悬疑",
        "three_category_id_v2=3729770379723233": "都市喜剧",
        "three_category_id_v2=7913065275478833": "家庭教育",
        "three_category_id_v2=8567632607202033": "追求梦想",
        "three_category_id_v2=1993081319452733": "知青往事",
        "three_category_id_v2=2504863130285333": "乡村题材",
        "three_category_id_v2=4004913265484633": "亲情",
    },
    "three_category_id_v2=3797954476777933": {
        "": "全部",
        "three_category_id_v2=6798054747175933": "都市生活",
        "three_category_id_v2=2710217587296533": "都市奇幻",
        "three_category_id_v2=8506668002776933": "都市爱情",
        "three_category_id_v2=1384237441048433": "熟龄浪漫",
        "three_category_id_v2=2760754035701733": "英雄正义",
        "three_category_id_v2=2009926802254433": "怀旧情感",
        "three_category_id_v2=2147899328059033": "警匪罪案",
        "three_category_id_v2=4560012032092733": "古装爱情",
        "three_category_id_v2=5671011731157433": "偶像爱情",
        "three_category_id_v2=8566830441354433": "家长里短",
        "three_category_id_v2=1383435275200733": "婚姻生活",
    },
    "three_category_id_v2=2971723653646733": {
        "": "全部",
        "three_category_id_v2=5962197933872333": "青春励志",
        "three_category_id_v2=6767572444963133": "女性励志",
        "three_category_id_v2=7073197632936933": "个人奋斗",
        "three_category_id_v2=8567632607202033": "追求梦想",
        "three_category_id_v2=7284167250881933": "温暖人间",
        "three_category_id_v2=7872956983093833": "乡村振兴",
        "three_category_id_v2=6077709815941633": "时代变迁",
        "three_category_id_v2=1699488619194533": "医疗题材",
        "three_category_id_v2=2760754035701733": "英雄正义",
        "three_category_id_v2=6798054747175933": "都市生活",
        "three_category_id_v2=5488117917881733": "职场剧",
        "three_category_id_v2=1726762258016433": "姐妹情",
    },
    "three_category_id_v2=7399679132950733": {
        "": "全部",
        "three_category_id_v2=1383435275200733": "婚姻生活",
        "three_category_id_v2=6798054747175933": "都市生活",
        "three_category_id_v2=8566830441354433": "家长里短",
        "three_category_id_v2=1384237441048433": "熟龄浪漫",
        "three_category_id_v2=7845683344271933": "原生家庭",
        "three_category_id_v2=8506668002776933": "都市爱情",
        "three_category_id_v2=7913065275478833": "家庭教育",
        "three_category_id_v2=2009926802254433": "怀旧情感",
        "three_category_id_v2=5933319963355133": "破镜重圆",
        "three_category_id_v2=4004913265484633": "亲情",
        "three_category_id_v2=7284167250881933": "温暖人间",
        "three_category_id_v2=2121427855085033": "苦情催泪",
        "three_category_id_v2=4604131153716233": "虐心绝症",
        "three_category_id_v2=1674621477915933": "家族斗争",
    },
    "three_category_id_v2=7245663290192433": {
        "": "全部",
        "three_category_id_v2=2147899328059033": "警匪罪案",
        "three_category_id_v2=3839667100858533": "刑侦破案",
        "three_category_id_v2=4934623482968933": "警察故事",
        "three_category_id_v2=2760754035701733": "英雄正义",
        "three_category_id_v2=8898927102302033": "罪案纪实",
        "three_category_id_v2=5380627694289933": "扫黑缉毒",
        "three_category_id_v2=6401784818411933": "推理解谜",
        "three_category_id_v2=2859420434968733": "反腐倡廉",
        "three_category_id_v2=3002205955859333": "情感悬疑",
        "three_category_id_v2=3755439686850133": "探寻真相",
        "three_category_id_v2=3192319261764233": "个人成长",
        "three_category_id_v2=5016444399434033": "人性反思",
    },
    "three_category_id_v2=7655570038367133": {
        "": "全部",
        "three_category_id_v2=2147899328059033": "警匪罪案",
        "three_category_id_v2=3839667100858533": "刑侦破案",
        "three_category_id_v2=2760754035701733": "英雄正义",
        "three_category_id_v2=6401784818411933": "推理解谜",
        "three_category_id_v2=5380627694289933": "扫黑缉毒",
        "three_category_id_v2=3755439686850133": "探寻真相",
        "three_category_id_v2=3002205955859333": "情感悬疑",
        "three_category_id_v2=7845683344271933": "原生家庭",
    },
    "three_category_id_v2=7174270529747233": {
        "": "全部",
        "three_category_id_v2=2147899328059033": "警匪罪案",
        "three_category_id_v2=6401784818411933": "推理解谜",
        "three_category_id_v2=2760754035701733": "英雄正义",
        "three_category_id_v2=3755439686850133": "探寻真相",
        "three_category_id_v2=3839667100858533": "刑侦破案",
        "three_category_id_v2=8867642634241733": "搭档破案",
        "three_category_id_v2=5380627694289933": "扫黑缉毒",
        "three_category_id_v2=3192319261764233": "个人成长",
    },
    "three_category_id_v2=3228416724910933": {
        "": "全部",
        "three_category_id_v2=7408502957275533": "家族兴衰",
        "three_category_id_v2=6238945151329033": "青年奋斗",
        "three_category_id_v2=6798054747175933": "都市生活",
    },
    "three_category_id_v2=6147498244691133": {
        "": "全部",
        "three_category_id_v2=1009625990172533": "古偶甜宠",
        "three_category_id_v2=4560012032092733": "古装爱情",
        "three_category_id_v2=5984658577608033": "历史演义",
        "three_category_id_v2=3990474280225833": "女性传奇",
        "three_category_id_v2=5800160432637133": "男性传奇",
    },
    "three_category_id_v2=2702998094667233": {
        "": "全部",
        "three_category_id_v2=6608743607118633": "仙情侠缘",
        "three_category_id_v2=7621076906916433": "仙侠玄幻",
        "three_category_id_v2=4560012032092733": "古装爱情",
        "three_category_id_v2=5768875964576733": "甜虐爱情",
        "three_category_id_v2=6360072194331733": "前世今生",
        "three_category_id_v2=3192319261764233": "个人成长",
    },
    "three_category_id_v2=2835355459537833": {
        "": "全部",
        "three_category_id_v2=1894414920185633": "古装神话",
        "three_category_id_v2=6608743607118633": "仙情侠缘",
    },
    "three_category_id_v2=7086834452347833": {
        "": "全部",
        "three_category_id_v2=3192319261764233": "个人成长",
        "three_category_id_v2=2760754035701733": "英雄正义",
    },
    "three_category_id_v2=2681339616779433": {
        "": "全部",
        "three_category_id_v2=3192319261764233": "个人成长",
        "three_category_id_v2=7629098565392933": "文学改编",
        "three_category_id_v2=1384237441048433": "熟龄浪漫",
        "three_category_id_v2=5768875964576733": "甜虐爱情",
    },
    "three_category_id_v2=8391958286555633": {
        "": "全部",
        "three_category_id_v2=8019753333222833": "超能力",
        "three_category_id_v2=2710217587296533": "都市奇幻",
        "three_category_id_v2=4208663390800233": "科幻冒险",
        "three_category_id_v2=5800160432637133": "男性传奇",
        "three_category_id_v2=3755439686850133": "探寻真相",
        "three_category_id_v2=2147899328059033": "警匪罪案",
        "three_category_id_v2=3839667100858533": "刑侦破案",
    },
}


def __subgenre_show(mtype: str, genre_param: str = "") -> str:
    """
    返回指定频道细选行的显示条件。
    """
    if genre_param:
        return "{{mtype == '" + mtype + "' && genre == '" + genre_param + "'}}"
    return "{{mtype == '" + mtype + "' && !genre}}"


def __expand_linked_subgenre_groups(
    filter_groups: Dict[str, List[dict]],
    linked_subgenres: Dict[str, Dict[str, Dict[str, str]]],
) -> Dict[str, List[dict]]:
    """
    将官方细选从全量平铺扩展为跟随类型切换。
    """
    if not linked_subgenres:
        return filter_groups

    expanded_groups = dict(filter_groups)
    for channel, channel_subgenres in linked_subgenres.items():
        channel_groups = filter_groups.get(channel) or []
        genre_group = next((group for group in channel_groups if group.get("model") == "genre"), None)
        subgenre_group = next((group for group in channel_groups if group.get("model") == "subgenre"), None)
        if not genre_group or not subgenre_group:
            continue

        expanded_channel_groups = []
        for group in channel_groups:
            if group.get("model") == "subgenre":
                continue
            expanded_channel_groups.append(group)
            if group.get("model") != "genre":
                continue

            default_items = channel_subgenres.get("")
            if default_items:
                expanded_channel_groups.append(
                    {
                        "label": "细选",
                        "model": "subgenre",
                        "items": dict(default_items),
                        "show": __subgenre_show(channel),
                    }
                )
            for genre_param in (genre_group.get("items") or {}):
                subgenre_items = channel_subgenres.get(genre_param)
                if not subgenre_items:
                    continue
                expanded_channel_groups.append(
                    {
                        "label": "细选",
                        "model": "subgenre",
                        "items": dict(subgenre_items),
                        "show": __subgenre_show(channel, genre_param),
                    }
                )
        expanded_groups[channel] = expanded_channel_groups
    return expanded_groups


OFFICIAL_LINKED_SUBGENRES = __load_official_linked_subgenres()
if not OFFICIAL_LINKED_SUBGENRES:
    OFFICIAL_LINKED_SUBGENRES = {"tv": TV_SUBGENRE_PARAMS_BY_GENRE}

FILTER_GROUPS = __expand_linked_subgenre_groups(
    __load_official_filter_groups() or FILTER_GROUPS,
    OFFICIAL_LINKED_SUBGENRES,
)


def __filter_items(channel: str, model: str) -> Dict[str, str]:
    """
    按筛选模型读取官方筛选项，避免 UI 行插入后固定下标失效。
    """
    for group in FILTER_GROUPS.get(channel, []):
        if group.get("model") == model:
            return group["items"]
    return {}


TV_GENRE_PARAMS = __filter_items("tv", "genre")
TV_SUBGENRE_PARAMS = __filter_items("tv", "subgenre")
TV_REGION_PARAMS = __filter_items("tv", "region")
TV_HALL_PARAMS = __filter_items("tv", "hall")
TV_SPEC_PARAMS = __filter_items("tv", "spec")
TV_AWARD_PARAMS = __filter_items("tv", "award")
TV_THEATER_PARAMS = __filter_items("tv", "theater")
TV_ACTOR_PARAMS = __filter_items("tv", "actor")
TV_RECOMMEND_PARAMS = __filter_items("tv", "recommend")

SORT_GROUPS = {
    "short_drama": SHORT_DRAMA_MODE_PARAMS,
    "variety": VARIETY_MODE_PARAMS,
    "anime": ANIME_MODE_PARAMS,
    "children": CHILDREN_MODE_PARAMS,
    "comic": COMIC_MODE_PARAMS,
    "documentary": DOCUMENTARY_MODE_PARAMS,
    "knowledge": KNOWLEDGE_MODE_PARAMS,
}

MODERN_LIBRARY_CHANNELS = {"tv", "movie", "short_drama", "variety", "anime", "children", "comic", "documentary", "knowledge"}
FILTER_EXPAND_MODEL = "filter_expand"
FILTER_EXPAND_COLLAPSED_VALUE = "0"
FILTER_EXPAND_EXPANDED_VALUE = "1"
ADVANCED_FILTER_MODELS = {
    "subgenre",
    "age_detail",
    "setting",
    "background",
    "spec",
    "award",
    "theater",
    "actor",
    "producer",
    "person",
    "style",
    "star",
    "serial",
    "version",
    "screen",
    "series",
    "language",
    "duration",
    "grade",
    "subject",
}

FILTER_MODELS = [
    "region",
    "genre",
    "subgenre",
    "age",
    "age_detail",
    "audience",
    "rank",
    "spec",
    "award",
    "hall",
    "theater",
    "recommend",
    "setting",
    "background",
    "actor",
    "style",
    "star",
    "serial",
    "version",
    "screen",
    "series",
    "language",
    "producer",
    "person",
    "grade",
    "subject",
    "duration",
    "year",
    "is_purchase",
]


def _show_condition(show: str) -> str:
    """
    提取 MoviePilot 表达式外层 {{ }}，便于组合额外条件。
    """
    show = str(show or "").strip()
    if show.startswith("{{") and show.endswith("}}"):
        return show[2:-2].strip()
    return show


def _with_filter_expand(show: str, expanded: bool) -> str:
    """
    将频道或联动筛选行条件合并为展开/收起状态条件。
    """
    expand_condition = (
        f"{FILTER_EXPAND_MODEL} == '{FILTER_EXPAND_EXPANDED_VALUE}'"
        if expanded
        else f"{FILTER_EXPAND_MODEL} != '{FILTER_EXPAND_EXPANDED_VALUE}'"
    )
    return "{{" + _show_condition(show) + " && " + expand_condition + "}}"

MODEL_DEFAULT_QUERY_PARAM = {
    "year": "market_release_date_level",
    "is_purchase": "is_purchase",
}
OFFICIAL_FILTER_JSON_KEYS = ("smart_tag_v2", "is_qiyi_produced", "is_exclusive", "structure_id")
OFFICIAL_FILTER_JSON_TRIGGER_KEYS = ("is_qiyi_produced", "is_exclusive")
OFFICIAL_FILTER_JSON_MODELS = {
    "tv": ("hall", "spec", "award"),
    "movie": ("award",),
}
OFFICIAL_FILTER_JSON_MODEL_KEYS = {
    "tv": {
        "recommend": ("structure_id",),
    },
    "movie": {
        "recommend": ("structure_id",),
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/132.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.iqiyi.com/",
    "Origin": "https://www.iqiyi.com",
    "Accept": "application/json, text/plain, */*",
}


class IqiyiDiscover(_PluginBase):
    """
    爱奇艺探索插件，让探索支持爱奇艺片库数据浏览。
    """

    plugin_name = "爱奇艺探索"
    plugin_desc = "让探索支持爱奇艺视频的数据浏览。"
    plugin_icon = "https://www.iqiyi.com/logo.png"
    plugin_version = "1.0.36"
    plugin_label = "探索"
    plugin_author = "qsxazcv"
    author_url = "https://github.com/qsxazcv/MoviePilot-Plugins"
    plugin_config_prefix = "iqiyidiscover_"
    plugin_order = 98
    auth_level = 1

    _enabled = False

    def init_plugin(self, config: dict = None) -> None:
        """
        根据配置初始化插件状态，并补充爱奇艺图片安全域名。
        """
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self.__ensure_image_domains()

    def get_state(self) -> bool:
        """
        获取插件启用状态。
        """
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """
        返回插件远程命令列表。
        """
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        """
        注册爱奇艺探索数据 API。
        """
        return [
            {
                "path": "/iqiyi_discover",
                "endpoint": self.iqiyi_discover,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "爱奇艺探索数据源",
                "description": "获取爱奇艺片库探索数据",
            }
        ]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        返回插件配置表单与默认配置。
        """
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件",
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ], {"enabled": False}

    def get_page(self) -> List[dict]:
        """
        返回插件详情页。
        """
        return [
            {
                "component": "VAlert",
                "props": {
                    "type": "info",
                    "variant": "tonal",
                    "text": "启用后会在 MoviePilot 探索页新增“爱奇艺”数据源。",
                },
            }
        ]

    @staticmethod
    def __ensure_image_domains() -> None:
        """
        将爱奇艺图片域名加入 MoviePilot 安全图片域名。
        """
        domains = (
            ["iqiyipic.com", "www.iqiyipic.com", "m.iqiyipic.com", "u0.iqiyipic.com"]
            + [f"pic{i}.iqiyipic.com" for i in range(10)]
        )
        for domain in domains:
            if domain not in settings.SECURITY_IMAGE_DOMAINS:
                settings.SECURITY_IMAGE_DOMAINS.append(domain)

    @staticmethod
    def __device_id() -> str:
        """
        生成爱奇艺列表接口使用的临时设备 ID。
        """
        return "".join(random.choice(string.hexdigits.lower()) for _ in range(32))

    @staticmethod
    def __normalize_mode(mtype: str, mode: str = "11", allow_recent: bool = False) -> str:
        """
        按频道限制排序值，避免请求 UI 不暴露的历史排序。
        """
        mode = str(mode or "").strip()
        if allow_recent and mode == "24":
            return mode
        allowed_modes = SORT_GROUPS.get(mtype, MODE_PARAMS)
        return mode if mode in allowed_modes else "11"

    @staticmethod
    def __normalize_image(url: str = "") -> str:
        """
        规范化爱奇艺海报地址。
        """
        url = str(url or "").strip()
        if url.startswith("//"):
            return f"https:{url}"
        if url.startswith("http://"):
            return "https://" + url[7:]
        return url

    @staticmethod
    def __pick_title(item: dict) -> str:
        """
        从爱奇艺接口条目中提取标题。
        """
        return str(
            item.get("name")
            or item.get("title")
            or item.get("album_name")
            or item.get("display_name")
            or item.get("short_display_name")
            or ""
        ).strip()

    @staticmethod
    def __pick_year(item: dict) -> str:
        """
        从上线日期字段中提取年份。
        """
        date = item.get("date")
        if isinstance(date, dict) and date.get("year"):
            return str(date.get("year"))
        period = str(item.get("period") or item.get("publishTime") or item.get("showDate") or "")
        if len(period) >= 4 and period[:4].isdigit():
            return period[:4]
        return ""

    @staticmethod
    def __pick_media_id(item: dict) -> str:
        """
        从爱奇艺条目中提取稳定媒体 ID。
        """
        for key in ("albumId", "album_id", "qipuId", "qipu_id", "tvId", "tv_id", "firstId"):
            value = item.get(key)
            if value:
                return str(value)
        return ""

    @staticmethod
    def __to_media(item: dict, mtype: str) -> schemas.MediaInfo:
        """
        将爱奇艺条目转换为 MoviePilot 媒体信息。
        """
        title = IqiyiDiscover.__pick_title(item)
        year = IqiyiDiscover.__pick_year(item)
        image_url = IqiyiDiscover.__normalize_image(
            item.get("imageUrl")
            or item.get("poster")
            or item.get("album_image_url_hover")
            or item.get("album_img")
            or item.get("image_url_normal")
            or item.get("image_cover")
            or item.get("image_url")
            or item.get("thumbnail_url")
            or item.get("banner_image_url")
            or item.get("back_image")
            or ""
        )
        return schemas.MediaInfo(
            type=MOVIEPILOT_MEDIA_TYPES.get(mtype, "电视剧"),
            title=title,
            year=year,
            title_year=f"{title} ({year})" if year else title,
            mediaid_prefix="iqiyi",
            media_id=IqiyiDiscover.__pick_media_id(item),
            poster_path=image_url,
            overview=item.get("description") or item.get("desc") or "",
            vote_average=float(item.get("score") or 0),
        )

    @staticmethod
    def __selected_category_ids(*values: str) -> str:
        """
        将地区、类型、题材等三级分类筛选合并为爱奇艺接口支持的逗号格式。
        """
        selected = []
        for value in values:
            value = str(value or "").strip()
            if value and value not in selected:
                selected.append(value)
        return ",".join(selected)

    @staticmethod
    def __append_query_param(params: Dict[str, List[str]], key: str, value: str) -> None:
        """
        将筛选参数追加到待请求参数中，并保持同一参数去重。
        """
        key = str(key or "").strip()
        value = str(value or "").strip()
        if not key or not value:
            return
        values = params.setdefault(key, [])
        if value not in values:
            values.append(value)

    @classmethod
    def __filter_query_params(cls, mtype: str = "tv", **filters: str) -> Dict[str, str]:
        """
        将探索页筛选模型转换为爱奇艺接口查询参数。
        """
        params: Dict[str, List[str]] = {}
        official_filter_params: Dict[str, List[str]] = {}
        mtype_key = str(mtype or "").strip()
        official_filter_models = OFFICIAL_FILTER_JSON_MODELS.get(mtype_key, ())
        official_filter_model_keys = OFFICIAL_FILTER_JSON_MODEL_KEYS.get(mtype_key, {})
        for model, raw_value in filters.items():
            raw_value = str(raw_value or "").strip()
            if not raw_value:
                continue
            default_key = MODEL_DEFAULT_QUERY_PARAM.get(model, "three_category_id")
            for token in raw_value.split(","):
                token = token.strip()
                if not token:
                    continue
                if "=" in token:
                    key, value = token.split("=", 1)
                else:
                    key, value = default_key, token
                if key == "mode" and model == "is_purchase" and value == "24":
                    cls.__append_query_param(params, "smart_tag_v2", RECENT_FREE_SMART_TAG_VALUE)
                    continue
                if key == "smart_tag_v2" and model == "is_purchase":
                    cls.__append_query_param(params, "smart_tag_v2", RECENT_FREE_SMART_TAG_VALUE)
                    continue
                if key == "mode":
                    continue
                official_filter_keys = official_filter_model_keys.get(model)
                if official_filter_keys is None and model in official_filter_models:
                    official_filter_keys = OFFICIAL_FILTER_JSON_KEYS
                if official_filter_keys and key in official_filter_keys:
                    cls.__append_query_param(official_filter_params, key, value)
                    continue
                cls.__append_query_param(params, key, value)
        query_params = {key: ",".join(values) for key, values in params.items()}
        if official_filter_params:
            official_filter = {key: ",".join(values) for key, values in official_filter_params.items()}
            query_params["filter"] = json.dumps(official_filter, ensure_ascii=False, separators=(",", ":"))
        return query_params

    @staticmethod
    def __apply_official_filter_json(query_params: Dict[str, str]) -> None:
        """
        将爱奇艺官方规格筛选合并到 filter JSON，避免顶层参数被接口忽略。
        """
        if not any(str(query_params.get(key) or "").strip() for key in OFFICIAL_FILTER_JSON_TRIGGER_KEYS):
            return

        official_filter: Dict[str, str] = {}
        existing_filter = str(query_params.pop("filter", "") or "").strip()
        if existing_filter:
            try:
                parsed_filter = json.loads(existing_filter)
            except (TypeError, ValueError):
                parsed_filter = {}
            if isinstance(parsed_filter, dict):
                for key, value in parsed_filter.items():
                    key = str(key or "").strip()
                    value = str(value or "").strip()
                    if key and value:
                        official_filter[key] = value

        for key in OFFICIAL_FILTER_JSON_KEYS:
            value = str(query_params.pop(key, "") or "").strip()
            if value:
                official_filter[key] = value

        if official_filter:
            query_params["filter"] = json.dumps(official_filter, ensure_ascii=False, separators=(",", ":"))

    def __request(
            self,
            page: int,
            mtype: str,
            mode: str = "11",
            three_category_id: str = None,
            year: str = None,
            is_purchase: str = None,
            recent_free: str = None,
            count: int = 24,
            extra_params: Tuple[Tuple[str, str], ...] = (),
    ) -> List[dict]:
        """
        请求爱奇艺推荐列表接口。
        """
        channel = CHANNEL_PARAMS.get(mtype, CHANNEL_PARAMS["tv"])
        mode = self.__normalize_mode(
            mtype,
            mode,
            allow_recent=str(mode or "") == "24" or str(is_purchase or "") in ("0", "0_recent_free"),
        )
        device_id = self.__device_id()
        params = {
            "channel_id": channel["id"],
            "mode": mode,
            "page_id": str(max(int(page or 1), 1)),
            "ret_num": str(max(int(count or 24), 1)),
            "version": "11.0",
            "pcv": "",
            "device": device_id,
            "device_id": device_id,
            "uid": "",
            "passport_id": "",
        }
        url = "https://mesh.if.iqiyi.com/portal/videolib/data"
        if three_category_id:
            params["three_category_id"] = three_category_id
        if year:
            params["market_release_date_level"] = str(year)
        if is_purchase:
            params["is_purchase"] = "0" if str(is_purchase) == "0_recent_free" else str(is_purchase)
        if recent_free:
            params["recent_free"] = str(recent_free)
        for key, value in extra_params or ():
            if key and value:
                params[str(key)] = str(value)
        try:
            response = requests.get(url, params=params, headers=HEADERS, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception as err:
            logger.warning(f"请求爱奇艺探索数据失败: {err}")
            return []
        if data.get("code") not in ("A00000", 0, "0"):
            logger.warning(f"爱奇艺探索接口返回异常: {data.get('code')} {data.get('msg')}")
            return []
        rows = data.get("data") or []
        if isinstance(rows, dict):
            rows = rows.get("list") or rows.get("items") or rows.get("data") or []
        return rows if isinstance(rows, list) else []

    def iqiyi_discover(
        self,
        mtype: str = "tv",
        mode: str = "11",
        filter_expand: str = None,
        region: str = None,
        genre: str = None,
        subgenre: str = None,
        age: str = None,
        age_detail: str = None,
        audience: str = None,
        rank: str = None,
        spec: str = None,
        award: str = None,
        hall: str = None,
        theater: str = None,
        actor: str = None,
        recommend: str = None,
        setting: str = None,
        background: str = None,
        style: str = None,
        star: str = None,
        serial: str = None,
        version: str = None,
        screen: str = None,
        series: str = None,
        language: str = None,
        producer: str = None,
        person: str = None,
        grade: str = None,
        subject: str = None,
        duration: str = None,
        year: str = None,
        is_purchase: str = None,
        page: int = 1,
        count: int = 10,
    ) -> List[schemas.MediaInfo]:
        """
        获取爱奇艺探索数据。
        """
        mode = self.__normalize_mode(mtype, mode)
        query_params = self.__filter_query_params(
            mtype=mtype,
            region=region,
            genre=genre,
            subgenre=subgenre,
            age=age,
            age_detail=age_detail,
            audience=audience,
            rank=rank,
            spec=spec,
            award=award,
            hall=hall,
            theater=theater,
            recommend=recommend,
            setting=setting,
            background=background,
            actor=actor,
            style=style,
            star=star,
            serial=serial,
            version=version,
            screen=screen,
            series=series,
            language=language,
            producer=producer,
            person=person,
            grade=grade,
            subject=subject,
            duration=duration,
            year=year,
            is_purchase=is_purchase,
        )
        filter_mode = query_params.pop("mode", "")
        if filter_mode == "24":
            mode = "24"
            query_params.pop("is_purchase", None)
            query_params.pop("recent_free", None)
        three_category_id = query_params.pop("three_category_id", "")
        year_param = query_params.pop("market_release_date_level", "")
        is_purchase_param = query_params.pop("is_purchase", "")
        recent_free_param = query_params.pop("recent_free", "")
        if recent_free_param and is_purchase_param == "0":
            is_purchase_param = "0_recent_free"
        self.__apply_official_filter_json(query_params)
        rows = self.__request(
            page=page,
            mtype=mtype,
            mode=mode,
            three_category_id=three_category_id,
            year=year_param,
            is_purchase=is_purchase_param,
            recent_free=recent_free_param,
            count=count,
            extra_params=tuple(query_params.items()),
        )
        medias: List[schemas.MediaInfo] = []
        seen = set()
        for item in rows:
            if not isinstance(item, dict):
                continue
            title = self.__pick_title(item)
            media_id = self.__pick_media_id(item)
            if not title or not media_id:
                continue
            key = (title, media_id)
            if key in seen:
                continue
            seen.add(key)
            medias.append(self.__to_media(item, mtype))
            if len(medias) >= max(int(count or 10), 1):
                break
        return medias

    @staticmethod
    def iqiyi_filter_ui() -> List[dict]:
        """
        返回探索页筛选 UI。
        """
        def chip_row(label: str, model: str, items: Dict[str, str], show: str = None) -> dict:
            """
            构造探索页 VChipGroup 行。
            """
            props = {"class": "flex justify-start items-center"}
            if show:
                props["show"] = show
            return {
                "component": "div",
                "props": props,
                "content": [
                    {
                        "component": "div",
                        "props": {"class": "mr-5"},
                        "content": [{"component": "VLabel", "text": label}],
                    },
                    {
                        "component": "VChipGroup",
                        "props": {"model": model},
                        "content": [
                            {
                                "component": "VChip",
                                "props": {
                                    "filter": True,
                                    "tile": True,
                                    "value": key,
                                },
                                "text": value,
                            }
                            for key, value in items.items()
                        ],
                    },
                ],
            }

        def toggle_row(mtype: str) -> dict:
            """
            构造高级筛选展开/收起控制行。
            """
            return {
                "component": "div",
                "props": {
                    "class": "flex justify-start items-center",
                    "show": "{{mtype == '" + mtype + "'}}",
                },
                "content": [
                    {
                        "component": "VChipGroup",
                        "props": {"model": FILTER_EXPAND_MODEL},
                        "content": [
                            {
                                "component": "VChip",
                                "props": {
                                    "filter": True,
                                    "tile": True,
                                    "value": FILTER_EXPAND_EXPANDED_VALUE,
                                },
                                "text": "展开",
                            },
                            {
                                "component": "VChip",
                                "props": {
                                    "filter": True,
                                    "tile": True,
                                    "value": FILTER_EXPAND_COLLAPSED_VALUE,
                                },
                                "text": "收起",
                            },
                        ],
                    }
                ],
            }

        ui = [
            {
                "component": "div",
                "props": {"class": "flex justify-start items-center"},
                "content": [
                    {
                        "component": "div",
                        "props": {"class": "mr-5"},
                        "content": [{"component": "VLabel", "text": "种类"}],
                    },
                    {
                        "component": "VChipGroup",
                        "props": {"model": "mtype"},
                        "content": [
                            {
                                "component": "VChip",
                                "props": {
                                    "filter": True,
                                    "tile": True,
                                    "value": key,
                                },
                                "text": value["name"],
                            }
                            for key, value in CHANNEL_PARAMS.items()
                        ],
                    },
                ],
            },
        ]
        for mtype, groups in FILTER_GROUPS.items():
            show = "{{mtype == '" + mtype + "'}}"
            has_advanced_rows = any(group["model"] in ADVANCED_FILTER_MODELS for group in groups)
            for group in groups:
                group_show = group.get("show") or show
                if group["model"] in ADVANCED_FILTER_MODELS:
                    group_show = _with_filter_expand(group_show, expanded=True)
                ui.append(
                    chip_row(
                        label=group["label"],
                        model=group["model"],
                        items=group["items"],
                        show=group_show,
                    )
                )
            ui.append(
                chip_row(
                    label="排序",
                    model="mode",
                    items=SORT_GROUPS.get(mtype, MODE_PARAMS),
                    show=show,
                )
            )
            if has_advanced_rows:
                ui.append(toggle_row(mtype))
        return ui

    @eventmanager.register(ChainEventType.DiscoverSource)
    def discover_source(self, event: Event) -> None:
        """
        向 MoviePilot 探索页注册爱奇艺数据源。
        """
        if not self._enabled:
            return
        event_data: DiscoverSourceEventData = event.event_data
        depends = {model: ["mtype"] for model in FILTER_MODELS}
        for model in ADVANCED_FILTER_MODELS:
            if model in depends:
                depends[model] = ["mtype", FILTER_EXPAND_MODEL]
        depends[FILTER_EXPAND_MODEL] = ["mtype"]
        depends["subgenre"] = ["mtype", "genre", FILTER_EXPAND_MODEL]
        iqiyi_source = schemas.DiscoverMediaSource(
            name="爱奇艺",
            mediaid_prefix="iqiyidiscover",
            api_path=f"plugin/IqiyiDiscover/iqiyi_discover?apikey={settings.API_TOKEN}",
            filter_params={
                "mtype": "tv",
                "mode": "11",
                FILTER_EXPAND_MODEL: FILTER_EXPAND_COLLAPSED_VALUE,
                **{model: None for model in FILTER_MODELS},
            },
            filter_ui=self.iqiyi_filter_ui(),
            depends=depends,
        )
        if not event_data.extra_sources:
            event_data.extra_sources = [iqiyi_source]
        else:
            event_data.extra_sources.append(iqiyi_source)

    def stop_service(self) -> None:
        """
        停止插件服务。
        """
        return None
