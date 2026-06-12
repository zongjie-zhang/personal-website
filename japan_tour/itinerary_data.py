STOPS = [
    {
        "slug": "tokyo",
        "city": "Tokyo",
        "city_zh": "东京",
        "dates": "7.20-7.23",
        "nights": "3 nights",
        "nights_zh": "3晚",
        "note": "Grand Bach Hotel, first Tokyo base before flying north.",
        "note_zh": "东京第一站，住 Grand Bach Hotel，之后飞往北海道。"
    },
    {
        "slug": "sapporo",
        "city": "Sapporo",
        "city_zh": "札幌",
        "dates": "7.23-7.25",
        "nights": "2 nights",
        "nights_zh": "2晚",
        "note": "Onsen Ryokan Yuen and the start of the Hokkaido leg.",
        "note_zh": "住 Onsen Ryokan Yuen，北海道段从这里开始。"
    },
    {
        "slug": "lake-toya",
        "city": "Lake Toya",
        "city_zh": "洞爷湖",
        "dates": "7.25-7.27",
        "nights": "2 nights",
        "nights_zh": "2晚",
        "note": "Toya Center Village stay, with Lake Toya buses paid separately.",
        "note_zh": "洞爷湖改住 Toya Center Village，洞爷站到湖区巴士另付。"
    },
    {
        "slug": "furano",
        "city": "Furano",
        "city_zh": "富良野",
        "dates": "7.27-7.29",
        "nights": "2 nights",
        "nights_zh": "2晚",
        "note": "Lavender fields, Biei day options, and slower Hokkaido mornings.",
        "note_zh": "薰衣草、美瑛备选，节奏放慢一点。"
    },
    {
        "slug": "osaka",
        "city": "Osaka · Kobe · Nara",
        "city_zh": "大阪 · 神户 · 奈良",
        "dates": "7.29-8.1",
        "nights": "3 nights",
        "nights_zh": "3晚",
        "note": "Three Kansai nights based in Osaka: one Osaka day, one Kobe day, one Nara day.",
        "note_zh": "大阪住三晚，以大阪为基地，一天大阪、一天神户、一天奈良。"
    },
    {
        "slug": "kyoto",
        "city": "Kyoto",
        "city_zh": "京都",
        "dates": "8.1-8.3",
        "nights": "2 nights",
        "nights_zh": "2晚",
        "note": "Two-night Kyoto base before returning through Tokyo.",
        "note_zh": "京都住两晚，最后从京都经东京回杭州。"
    },
    {
        "slug": "narita",
        "city": "Narita",
        "city_zh": "成田",
        "dates": "8.3-8.4",
        "nights": "1 night",
        "nights_zh": "1晚",
        "note": "Kyoto to Tokyo, stay near Narita before the Hangzhou flight.",
        "note_zh": "京都回东京，成田机场附近住一晚，第二天飞杭州。"
    }
]

HOTELS = [
    {"city": "Tokyo", "hotel": "Grand Bach Hotel", "nights": "3", "price": "¥4110", "note": "First Tokyo stay"},
    {"city": "Sapporo", "hotel": "Onsen Ryokan Yuen", "nights": "2", "price": "¥4104", "note": "City onsen ryokan"},
    {"city": "Lake Toya", "hotel": "Toya Center Village", "nights": "2", "price": "¥2801", "note": "Lake Toya stay"},
    {"city": "Furano", "hotel": "Nozo Hotel", "nights": "2", "price": "¥3747", "note": "Furano base"},
    {"city": "Osaka", "hotel": "Sugata Hotel Osaka", "nights": "3", "price": "¥1314", "note": "Osaka / Kobe / Nara base"},
    {"city": "Kyoto", "hotel": "TBD", "nights": "2", "price": "¥2000", "note": "Pending"},
    {"city": "Narita", "hotel": "Narita Tobu Hotel", "nights": "1", "price": "¥415", "note": "Airport night"}
]

BUDGET_CARDS = [
    {"label": "Flights", "label_zh": "机票", "value": "¥3709", "detail": "Hangzhou-Tokyo round trip + Japan domestic legs", "detail_zh": "杭州往返东京 + 东京-札幌、札幌-大阪"},
    {"label": "Hokkaido Pass", "label_zh": "北海道 5 日交通票", "value": "¥930", "detail": "5-day Hokkaido rail pass", "detail_zh": "北海道 5 日交通票"},
    {"label": "Hotels per person", "label_zh": "酒店人均", "value": "¥9396", "detail": "¥18791 total, about ¥627 / person / night", "detail_zh": "酒店合计 ¥18791，人均约 ¥9396，约 ¥627 / 人 / 晚"},
    {"label": "Visa", "label_zh": "签证", "value": "¥210", "detail": "Japan visa fee", "detail_zh": "日本签证费用"},
    {"label": "Current total", "label_zh": "目前单人花费", "value": "¥14245", "detail": "Current single-person spend", "detail_zh": "目前单人花费"},
    {"label": "Estimated total", "label_zh": "预计单人总花费", "value": "¥21000", "detail": "Expected single-person total", "detail_zh": "预计单人总预算"}
]

STOP_DETAILS = {
    "tokyo": {
        "hero_image": "image/stops/tokyo.png",
        "map": "https://www.openstreetmap.org/export/embed.html?bbox=139.681%2C35.628%2C139.832%2C35.734&layer=mapnik&marker=35.6762%2C139.6503",
        "map_link": "https://www.openstreetmap.org/?mlat=35.6762&mlon=139.6503#map=12/35.6762/139.6503",
        "hotel": {
            "name": "Grand Bach Hotel",
            "price": "¥4110 / 3晚",
            "per_person": "约 ¥2055 / person",
            "note": "银座/东京市区住宿基底，适合抵达后先把节奏放稳。",
            "images": ["image/hotels/tokyo-grand-bach.png"]
        },
        "days": [
            {"date": "7.20", "title": "Arrive in Tokyo / 抵达东京", "plan": "杭州飞东京，抵达后进城入住。晚餐就近，少排景点，留时间调整。"},
            {"date": "7.21", "title": "Central Tokyo / 东京市区", "plan": "银座、丸之内、东京站一带轻松走；下午可安排咖啡、书店或商场避暑。"},
            {"date": "7.22", "title": "Tokyo Tower or Skytree / 东京塔或晴空树", "plan": "浅草、上野、东京塔或晴空树任选一条线，不硬塞跨城移动。"},
            {"date": "7.23", "title": "Fly to Sapporo / 飞札幌", "plan": "上午退房去机场，东京飞札幌，抵达后入住 Onsen Ryokan Yuen。"}
        ],
        "transport": [
            {"step": "杭州 -> 东京", "time": "约 3-4 小时飞行 + 入境", "cost": "¥2723 往返机票的一部分", "detail": "抵达后用机场铁路或巴士进东京市区。"},
            {"step": "东京市内移动", "time": "单程 10-35 分钟", "cost": "按 IC 卡实付", "detail": "以地铁/JR 为主，尽量按区域走，减少换乘。"},
            {"step": "东京 -> 札幌", "time": "约 1.5 小时飞行 + 机场交通", "cost": "¥986 国内段的一部分", "detail": "7.23 飞新千岁，再进札幌市区。"}
        ]
    },
    "sapporo": {
        "hero_image": "image/stops/sapporo.png",
        "map": "https://www.openstreetmap.org/export/embed.html?bbox=141.275%2C43.025%2C141.445%2C43.105&layer=mapnik&marker=43.0618%2C141.3545",
        "map_link": "https://www.openstreetmap.org/?mlat=43.0618&mlon=141.3545#map=12/43.0618/141.3545",
        "hotel": {
            "name": "Onsen Ryokan Yuen",
            "price": "¥4104 / 2晚",
            "per_person": "约 ¥2052 / person",
            "note": "札幌市区温泉旅馆感，适合北海道第一站放松。",
            "images": ["image/hotels/sapporo-yuen.png"]
        },
        "days": [
            {"date": "7.23", "title": "Arrive in Sapporo / 抵达札幌", "plan": "新千岁机场进札幌，入住后在大通公园、狸小路附近简单晚餐。"},
            {"date": "7.24", "title": "Sapporo City / 札幌市区", "plan": "北海道大学、旧道厅、大通公园、薄野夜景；午后热或雨就回酒店休息。"},
            {"date": "7.25", "title": "Rail Pass Starts / 周游券启用", "plan": "启用 5 日北海道铁路周游券，从札幌坐 JR 去洞爷站，再转巴士到洞爷湖。"}
        ],
        "transport": [
            {"step": "新千岁机场 -> 札幌", "time": "JR 快速约 40 分钟", "cost": "单独购票或 IC 卡支付", "detail": "7.23 抵达日不急着启用 5 日券。"},
            {"step": "札幌市内", "time": "单程 5-25 分钟", "cost": "地铁/步行实付", "detail": "市区景点集中，按天气调整。"},
            {"step": "札幌 -> 洞爷站", "time": "JR 约 1小时50分-2小时10分", "cost": "北海道铁路周游券覆盖", "detail": "7.25 开始用 5 日券。"}
        ]
    },
    "lake-toya": {
        "hero_image": "image/stops/lake-toya.png",
        "map": "https://www.openstreetmap.org/export/embed.html?bbox=140.70%2C42.50%2C141.05%2C42.72&layer=mapnik&marker=42.5646%2C140.8204",
        "map_link": "https://www.openstreetmap.org/?mlat=42.5646&mlon=140.8204#map=12/42.5646/140.8204",
        "hotel": {
            "name": "Toya Center Village",
            "price": "¥2801 / 2晚",
            "per_person": "约 ¥1400.5 / person",
            "note": "洞爷湖住宿改为 Toya Center Village，预算更轻，仍以湖区慢节奏为主。",
            "images": ["image/hotels/lake-toya-kohantei.png"]
        },
        "days": [
            {"date": "7.25", "title": "Sapporo to Lake Toya / 札幌到洞爷湖", "plan": "JR 到洞爷站，转巴士到洞爷湖区域。入住 Toya Center Village 后湖边散步。"},
            {"date": "7.26", "title": "Lake Day / 洞爷湖慢游", "plan": "上午湖边、游船或有珠山方向；下午回住宿休息，晚上看天气安排湖畔散步。"},
            {"date": "7.27", "title": "To Furano / 前往富良野", "plan": "退房后巴士回洞爷站，JR 经札幌/旭川方向去富良野。"}
        ],
        "transport": [
            {"step": "洞爷站 -> 洞爷湖区域", "time": "巴士约 20 分钟", "cost": "巴士另付，周游券不含", "detail": "注意巴士班次，别按 JR 到站时间排太紧。"},
            {"step": "湖区移动", "time": "步行/巴士 10-30 分钟", "cost": "按实际付费", "detail": "湖区以步行为主，远一点再用巴士。"},
            {"step": "洞爷 -> 富良野", "time": "约 4-5 小时，需换乘", "cost": "JR 段周游券覆盖", "detail": "建议把这天当作移动日，不塞重景点。"}
        ]
    },
    "furano": {
        "hero_image": "image/stops/furano.png",
        "map": "https://www.openstreetmap.org/export/embed.html?bbox=142.22%2C43.27%2C142.55%2C43.43&layer=mapnik&marker=43.3420%2C142.3832",
        "map_link": "https://www.openstreetmap.org/?mlat=43.3420&mlon=142.3832#map=12/43.3420/142.3832",
        "hotel": {
            "name": "Nozo Hotel",
            "price": "¥3747 / 2晚",
            "per_person": "约 ¥1873.5 / person",
            "note": "富良野住宿基地，适合薰衣草、美瑛和北海道田园风景。",
            "images": ["image/hotels/furano-nozo.png"]
        },
        "days": [
            {"date": "7.27", "title": "Arrive in Furano / 抵达富良野", "plan": "下午/傍晚抵达，入住后就近晚餐，轻松恢复。"},
            {"date": "7.28", "title": "Lavender and Biei / 薰衣草与美瑛", "plan": "富田农场、美瑛拼一条线；如果天气热，上午主攻户外，下午回酒店休息。"},
            {"date": "7.29", "title": "To Osaka / 飞往大阪", "plan": "富良野去新千岁机场，飞大阪，进入关西段。"}
        ],
        "transport": [
            {"step": "富良野/美瑛区域", "time": "JR/巴士单段 20-60 分钟", "cost": "JR 段周游券覆盖，巴士另付", "detail": "花田季班次要提前看，留缓冲。"},
            {"step": "富良野 -> 新千岁机场", "time": "约 2.5-3.5 小时", "cost": "JR 段周游券覆盖", "detail": "这是 5 日券的最后重要用法之一。"},
            {"step": "新千岁 -> 大阪", "time": "飞行约 2 小时", "cost": "¥986 国内段的一部分", "detail": "抵达后进大阪市区入住。"}
        ]
    },
    "osaka": {
        "hero_image": "image/stops/osaka.png",
        "map": "https://www.openstreetmap.org/export/embed.html?bbox=135.05%2C34.35%2C135.95%2C34.95&layer=mapnik&marker=34.6937%2C135.5023",
        "map_link": "https://www.openstreetmap.org/?mlat=34.6937&mlon=135.5023#map=9/34.6937/135.5023",
        "hotel": {
            "name": "Sugata Hotel Osaka",
            "price": "¥1314 / 3晚",
            "per_person": "约 ¥657 / person",
            "note": "大阪住三晚，用作大阪、奈良、神户三地的关西基地。",
            "images": ["image/hotels/osaka-sugata.png"]
        },
        "days": [
            {"date": "7.29", "title": "Arrive in Osaka / 抵达大阪", "plan": "新千岁飞大阪，机场进城入住。晚上道顿堀或梅田简单吃饭。"},
            {"date": "7.30", "title": "Kobe Day Trip / 神户一日", "plan": "大阪往返神户，北野异人馆、港区或三宫一带，晚上回大阪。"},
            {"date": "7.31", "title": "Nara Day Trip / 奈良一日", "plan": "大阪往返奈良，奈良公园、东大寺、春日大社，控制步行和暴晒。"},
            {"date": "8.1", "title": "Osaka to Kyoto / 大阪到京都", "plan": "上午大阪城或中之岛轻松收尾，下午去京都入住。"}
        ],
        "transport": [
            {"step": "大阪机场 -> 市区", "time": "约 40-70 分钟", "cost": "按机场和线路实付", "detail": "关西机场/伊丹机场路线不同，按实际航班确认。"},
            {"step": "大阪 -> 神户 -> 大阪", "time": "单程约 25-45 分钟", "cost": "JR/阪急/阪神实付", "detail": "住大阪，神户做轻松一日往返。"},
            {"step": "大阪 -> 奈良 -> 大阪", "time": "单程约 40-55 分钟", "cost": "近铁/JR 实付", "detail": "奈良公园和东大寺区域步行为主。"},
            {"step": "大阪 -> 京都", "time": "JR/私铁约 30-50 分钟", "cost": "约 ¥400-¥600 级别，按线路实付", "detail": "京都住宿位置决定选 JR、阪急或京阪。"}
        ]
    },
    "kyoto": {
        "hero_image": "image/stops/kyoto.png",
        "map": "https://www.openstreetmap.org/export/embed.html?bbox=135.68%2C34.93%2C135.86%2C35.08&layer=mapnik&marker=35.0116%2C135.7681",
        "map_link": "https://www.openstreetmap.org/?mlat=35.0116&mlon=135.7681#map=12/35.0116/135.7681",
        "hotel": {
            "name": "TBD Kyoto Stay",
            "price": "¥2000 / 2晚",
            "per_person": "约 ¥1000 / person",
            "note": "京都酒店待定，建议优先选四条河原町、京都站或东山交通方便区域。",
            "images": ["image/hotels/kyoto-tbd.png"]
        },
        "days": [
            {"date": "8.1", "title": "Arrive in Kyoto / 抵达京都", "plan": "大阪到京都，入住后走鸭川、祇园或四条河原町。"},
            {"date": "8.2", "title": "Kiyomizu and Higashiyama / 清水寺东山线", "plan": "清水寺、二年坂三年坂、八坂神社、祇园，早出避开人流和高温。"},
            {"date": "8.3", "title": "Kyoto to Narita / 京都到成田", "plan": "京都到东京，再转成田机场附近酒店，作为回国前一晚。"}
        ],
        "transport": [
            {"step": "京都市内公交/地铁", "time": "单程 15-45 分钟", "cost": "按 IC 卡/一日券实际选择", "detail": "旺季公交慢，地铁 + 步行更稳。"},
            {"step": "京都 -> 东京", "time": "新干线约 2小时15分", "cost": "单独购票，按实际票价", "detail": "这段不在北海道周游券范围内。"},
            {"step": "东京 -> 成田机场附近", "time": "约 50-90 分钟", "cost": "按 Skyliner/N'EX/普通线路实付", "detail": "看酒店接驳和第二天航班时间。"}
        ]
    },
    "narita": {
        "hero_image": "image/stops/narita.png",
        "map": "https://www.openstreetmap.org/export/embed.html?bbox=140.28%2C35.70%2C140.48%2C35.84&layer=mapnik&marker=35.7767%2C140.3189",
        "map_link": "https://www.openstreetmap.org/?mlat=35.7767&mlon=140.3189#map=12/35.7767/140.3189",
        "hotel": {
            "name": "Narita Tobu Hotel",
            "price": "¥415 / 1晚",
            "per_person": "约 ¥207.5 / person",
            "note": "回国前机场夜，重点是接驳方便和睡眠稳定。",
            "images": ["image/hotels/narita-tobu.png"]
        },
        "days": [
            {"date": "8.3", "title": "Kyoto to Narita / 京都到成田", "plan": "从京都经东京到成田，入住机场附近，整理行李。"},
            {"date": "8.4", "title": "Narita to Hangzhou / 成田飞杭州", "plan": "按航班时间搭酒店接驳或公共交通去航站楼，东京 -> 杭州。"}
        ],
        "transport": [
            {"step": "成田机场周边", "time": "酒店接驳通常 10-20 分钟", "cost": "以酒店接驳政策为准", "detail": "入住时确认第二天班车时刻。"},
            {"step": "东京 -> 杭州", "time": "约 3-4 小时飞行", "cost": "¥2723 往返机票的一部分", "detail": "建议提前到机场，预留退税/托运行李时间。"}
        ]
    }
}
