import re
from collections import deque
import math
from lxml import etree
import copy


def append_node(parent, attrib_dict, node_id=None):
    new_node = etree.Element('node')
    for k, v in attrib_dict.items():
        new_node.set(k, v)
    if node_id is not None:
        new_node.set('id', node_id)
    parent.append(new_node)

def bbox_to_coords(bbox_string):
    pattern = r"\[(-?\d+\.?\d*),(-?\d+\.?\d*),(-?\d+\.?\d*),(-?\d+\.?\d*)\]"
    matches = re.findall(pattern, bbox_string)
    values = matches[0]
    
    # Convert to int if all values are integers, otherwise use float
    if all('.' not in x for x in values):
        return list(map(int, values))
    return list(map(float, values))

def coords_to_bbox(coords):
    return f"[{coords[0]},{coords[1]},{coords[2]},{coords[3]}]"


def bounds_to_coords(bounds_string):
    pattern = r"\[(-?\d+\.?\d*),(-?\d+\.?\d*)\]\[(-?\d+\.?\d*),(-?\d+\.?\d*)\]"
    matches = re.findall(pattern, bounds_string)
    values = matches[0]
    
    # Convert to int if all values are integers, otherwise use float
    if all('.' not in x for x in values):
        return list(map(int, values))
    return list(map(float, values))


def coords_to_bounds(bounds):
    return f"[{bounds[0]},{bounds[1]}][{bounds[2]},{bounds[3]}]"


def check_valid_bounds(bounds):
    bounds = bounds_to_coords(bounds)

    return bounds[0] >= 0 and bounds[1] >= 0 and \
           bounds[0] < bounds[2] and bounds[1] < bounds[3]


def check_point_containing(bounds, x, y, window, threshold=0):
    bounds = bounds_to_coords(bounds)

    screen_threshold_x = threshold * window[0]
    screen_threshold_y = threshold * window[1]

    return bounds[0] - screen_threshold_x <= x <= bounds[2] + screen_threshold_x and \
           bounds[1] - screen_threshold_y <= y <= bounds[3] + screen_threshold_y


def check_bounds_containing(bounds_contained, bounds_containing):
    bounds_contained = bounds_to_coords(bounds_contained)
    bounds_containing = bounds_to_coords(bounds_containing)

    return bounds_contained[0] >= bounds_containing[0] and \
           bounds_contained[1] >= bounds_containing[1] and \
           bounds_contained[2] <= bounds_containing[2] and \
           bounds_contained[3] <= bounds_containing[3]


def check_bounds_intersection(bounds1, bounds2):
    bounds1 = bounds_to_coords(bounds1)
    bounds2 = bounds_to_coords(bounds2)

    return bounds1[0] < bounds2[2] and bounds1[2] > bounds2[0] and \
           bounds1[1] < bounds2[3] and bounds1[3] > bounds2[1]


def get_bounds_area(bounds):
    bounds = bounds_to_coords(bounds)
    return (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])


def get_bounds_center(bounds):
    bounds = bounds_to_coords(bounds)
    return (bounds[0]+bounds[2]) // 2 , (bounds[1] + bounds[3]) // 2


def calculate_point_distance(x1, y1, x2, y2):
    distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    return distance


def compare_bounds_area(bounds1, bounds2):
    """
    :return:
        if bounds1 is smaller than bounds2, return true
        else return false
    """
    return get_bounds_area(bounds1) < get_bounds_area(bounds2)


def compare_y_in_bounds(bounds1, bounds2):
    """
    :return:
        if y in bounds1 is smaller than that in bounds2, return true
        else return false
    """
    bounds1 = bounds_to_coords(bounds1)
    bounds2 = bounds_to_coords(bounds2)

    return bounds1[1] < bounds2[1] and bounds1[3] < bounds2[3]


def calculate_iou(box1, box2):
    x1_min, y1_min, x1_max, y1_max = box1
    x2_min, y2_min, x2_max, y2_max = box2
    
    x_intersection_min = max(x1_min, x2_min)
    y_intersection_min = max(y1_min, y2_min)
    x_intersection_max = min(x1_max, x2_max)
    y_intersection_max = min(y1_max, y2_max)
    
    intersection_width = max(0, x_intersection_max - x_intersection_min)
    intersection_height = max(0, y_intersection_max - y_intersection_min)
    intersection_area = intersection_width * intersection_height
    
    box1_area = (x1_max - x1_min) * (y1_max - y1_min)
    box2_area = (x2_max - x2_min) * (y2_max - y2_min)
    
    union_area = box1_area + box2_area - intersection_area
    
    iou = intersection_area / union_area
    return iou


class MiniMapSpecialCheck:
    def __init__(self, xml_string, root):
        self.xml_string = xml_string
        self.root = root

    def check(self):
        page, page_type = self.check_page()
        
        self.base_node = None
        self.retrieve_times = 0
        check_type = ''
        if page == "filter":
            self.recycler_node = None
            self.recycler_bounds = "[0,0][0,0]"
            self.check_filter(page_type)
            check_type = "remove"
        elif page == "route":
            self.check_route(page_type)
            check_type = "remove"
        elif page == "search-result":
            self.check_search_result(page_type)
            check_type = "remove"
        elif page == "taxi" or page == "search_near":
            self.check_taxi(page_type)
            check_type = "remove"
        elif page == "distance_filter":
            self.check_distance_filter(page_type)
            check_type = "remove"
        return page_type, check_type

    def check_page(self):
        page_map = {
            "filter": [
                (["距离优先", "推荐排序"], "推荐排序"),
                (["好评优先", "推荐排序"], "推荐排序"),
                (["距离", "km内"], "位置距离"),
                (["烤肉", "烧烤", "螺蛳粉"], "全部分类"),
                (["烤肉", "烧烤", "蛋糕店"], "全部分类"),
                (["水产海鲜", "火锅", "熟食"], "全部分类"),
                (["水产海鲜", "火锅", "早餐"], "全部分类"),
                (["麻辣烫", "小吃快餐", "螺蛳粉", "面馆"], "全部分类"),
                (["星级(可多选)", "价格"], "星级酒店"),
                (["品牌", "宾客类型", "特色主题"], "更多筛选"),
                (["92#", "95#", "98#", "0#"], "油类型"),
                (["全部品牌", "中国石化", "中国石油", "壳牌"], "全部品牌")
            ],
            "route": [
                (["驾车", "火车", "步行", "收起"], "出行方式"),
                (["选择日期", "日", "一", "二", "三", "四", "五", "六"], "选择日期"),
                (["选择出发时间弹窗", "现在出发"], "选择出发时间"),
                (["选择出发时间", "确定"], "选择出发时间_taxi")
            ],
            "search-result": [
                (["周边", "收藏", "分享", "路线", "导航"], "周边收藏")
            ],
            "taxi": [
                (["推荐", "出租", "立即打车"], "打车界面")
            ],
            "distance_filter": [
                (["位置距离", "区域", "地铁"], "位置距离筛选")
            ],
            "search_near": [
                 (["首页", "附近", "消息", "打车", "我的", "搜索"], "搜索附近")
            ]
        }

        for key, values in page_map.items():
            for keywords, page_type in values:
                if all(k in self.xml_string for k in keywords):
                    return key, page_type
        return None, None

    def get_distance_filter_base_node(self, node, page_type):
        page_criteria = {
            "位置距离筛选": [("位置距离", 5)],
        }

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if pattern == content_desc or pattern == text:
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'], node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_distance_filter_base_node(child, page_type)

    def check_distance_filter(self, page_type):
        for back_steps in [5, 9]: # 2 phases
            self.base_node = None
            self.get_distance_filter_base_node(self.root, page_type)
            node = self.base_node
            if node is None:
                return
            self.retrieve_times = back_steps

            while self.retrieve_times > 0:
                if node.getparent() is not None:
                    node = node.getparent()
                    self.retrieve_times -= 1
                else:
                    return

            parent = node.getparent()

            for ind, child in reversed(list(enumerate(parent))):
                if child != node:
                    parent.remove(child)
        

    def get_filter_base_node(self, node, page_type):
        page_criteria = {
            "推荐排序": [("距离优先", 14), ("好评优先", 14)],
            "位置距离": [("km内", 8)],
            "全部分类": [("烤肉", 14), ("火锅", 14), ("螺蛳粉", 14)],
            "星级酒店": [("星级(可多选)", 10)],
            "更多筛选": [("品牌", 9)],
            "全部品牌": [("全部品牌", 14)],
            "油类型": [("95#", 14)]
        }

        pattern_need_fuzzy = ["km内"]

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if (pattern in pattern_need_fuzzy and (pattern in content_desc or pattern in text)) or \
                   (pattern not in pattern_need_fuzzy and (pattern == content_desc or pattern == text)):
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'], node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        # Find a node that can scroll in a loop.
        if 'RecyclerView' in node.attrib.get('class', '') and 'true' in node.attrib.get('scrollable', ''):
            # If the node is not unique, find the one that is larger.
            if compare_bounds_area(self.recycler_bounds, node.attrib['bounds']):
                self.recycler_node = node
                self.recycler_bounds = node.attrib['bounds']

        for child in list(node):
            self.get_filter_base_node(child, page_type)

    def check_filter(self, page_type):
        self.get_filter_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                break
                # return

        parent = node.getparent()
        if parent is not None:
            delete_ind = parent.index(node) + 1
            try:
                parent.remove(list(parent)[delete_ind])
                parent.remove(list(parent)[delete_ind])
            except Exception:
                pass

        if self.recycler_node.getparent() is not None:
            self.recycler_node.getparent().remove(self.recycler_node)

    def get_route_base_node(self, node, page_type):
        page_criteria = {
            "出行方式": [("收起", 2)],
            "选择日期": [("选择日期", 5)],
            "选择出发时间": [("选择出发时间", 5)],
            "选择出发时间_taxi": [("选择出发时间", 3)]
        }

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if pattern == content_desc or pattern == text:
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'], node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break
        
        for child in list(node):
            self.get_route_base_node(child, page_type)

    def check_route(self, page_type):
        self.get_route_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        for ind, child in reversed(list(enumerate(parent))):
            if child != node:
                parent.remove(child)
    
    def get_search_result_base_node(self, node, page_type):
        page_criteria = {
            "周边收藏": [("收藏按钮", 3)],
        }

        pattern_need_fuzzy = ["收藏按钮"]

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if (pattern in pattern_need_fuzzy and (pattern in content_desc or pattern in text)) or \
                   (pattern not in pattern_need_fuzzy and (pattern == content_desc or pattern == text)):
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'], node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_search_result_base_node(child, page_type)

    def get_search_result_base_node_phase2(self, node, page_type):
        page_criteria = {
            "周边收藏": [("搜索", 4)],
        }

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if pattern == content_desc or pattern == text:
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'], node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_search_result_base_node_phase2(child, page_type)

    def check_search_result(self, page_type):
        self.get_search_result_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return
            
        parent = node.getparent()
        for ind, child in reversed(list(enumerate(parent))):
            if child != node and check_bounds_intersection(child.attrib['bounds'], node.attrib['bounds']):
                for ch in child.iter():
                    if check_bounds_containing(ch.attrib['bounds'], node.attrib['bounds']):
                        ch_parent = ch.getparent()
                        ch_parent.remove(ch)

        # phase 2
        self.base_node = None
        self.get_search_result_base_node_phase2(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()

        nodes_to_check = list(enumerate(parent))
        for ind, child in nodes_to_check:
            if child != node and check_bounds_intersection(child.attrib['bounds'], node.attrib['bounds']):
               parent.remove(child)



    def get_taxi_base_node(self, node, page_type):
        page_criteria = {
            "打车界面": [("立即打车", 7)],
            "搜索附近": [("搜索", 3)]
        }

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if pattern == content_desc or pattern == text:
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'], node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_taxi_base_node(child, page_type)

    def check_taxi(self, page_type):
        self.get_taxi_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return
            
        parent = node.getparent()

        nodes_to_check = list(enumerate(parent))
        for ind, child in nodes_to_check:
            if child != node and check_bounds_intersection(child.attrib['bounds'], node.attrib['bounds']):
                for ch in child.iter():
                    if check_bounds_containing(ch.attrib['bounds'], node.attrib['bounds']):
                        ch_parent = ch.getparent()
                        ch_parent.remove(ch)
                    else:
                        if not (-1, ch) in nodes_to_check:
                            nodes_to_check.append((-1, ch))


class WeiXinSpecialCheck:
    def __init__(self, xml_string, root):
        self.xml_string = xml_string
        self.root = root

    def check(self):
        page, page_type = self.check_page()
        self.base_node = None
        self.retrieve_times = 0
        check_type = ''
        if page == "search":
            self.check_search(page_type)
            check_type = "remove"
        elif page == "moments":
            self.check_moments_icons(page_type)
            check_type = "add"
        elif page == "menu":
            self.base_node = {}
            self.check_menu(page_type)
            check_type = "remove"
        elif page == "official_account":
            self.check_account_subscription(page_type)
            check_type = "add"
        elif page == "chat_details":
            self.check_chat_settings(page_type)
            check_type = "remove"
        elif page == "settings":
            self.check_settings(page_type)
            check_type = "remove"
        elif page == "article_search":
            check_type = "unchanged"
        elif page == "money":
            self.check_money(page_type)
            check_type = "money"
        elif page == "pay_set":
            self.check_payset(page_type)
            check_type = "remove"
        return page_type, check_type

    def check_page(self):
        page_map = {
            "search": [
                (["排序", "类型", "时间", "范围"], "搜索-全部")
            ],
            "moments": [
                (["朋友圈", "拍照分享"], "朋友圈-全部"),
                (["轻触更换封面", "拍照分享"], "朋友圈-全部")
            ],
            "official_account": [
                (["头像", "消息", "服务", "阅读", "赞", "搜索"], "公众号-首页")
            ],
            "chat_details": [
                (["聊天信息", "查找聊天记录", "添加成员"], "聊天信息")
            ],
            "settings": [
                (["朋友圈权限", "不让", "不看", "朋友圈的范围"], "设置-朋友权限-朋友圈"),
                (["添加我的方式", "搜索到我", "群聊"], "设置-朋友权限-添加我的方式"), # 未测试
                (["朋友权限", "添加我的方式", "仅聊天", "朋友圈"], "设置-朋友权限"),
                (["深色模式", "跟随系统", "开启后"], "设置-通用-深色模式"),
                (["通用", "界面和显示", "多语言"], "设置-通用"),
                (["聊天背景", "选择背景图", "拍一张"], "设置-聊天-聊天背景"),
                (["聊天", "使用听筒播放", "聊天记录"], "设置-聊天"),
                (["新消息通知", "通知开关", "消息提示音"], "设置-新消息通知"), # 未测试
                (["账号与安全", "微信号", "手机号", "密码"], "设置-账号与安全"), # 未测试
                (["设置", "账号与安全", "通用", "隐私", "朋友权限"], "设置"),
            ], # 注意，settings 类型优先级高于 menu，因为 settings 页面的 xml 也包含了 menu 中的文本
            "menu": [
                (["微信", "通讯录", "发现", "我"], "首页"),
            ],
            "article_search": [
                (["搜索范围", "发布时间", "综合排序"], "文章搜索-筛选")
            ],
            "money": [
                (["发红包", "塞钱进红包"], "微信-红包")
            ],
            "pay_set": [
                (["支付设置", "自动续费"], "微信-支付设置"),
                (["扣费记录", "关闭扣费服务"], "微信-关闭自动扣费")
            ]
        }

        for key, values in page_map.items():
            for keywords, page_type in values:
                if all(k in self.xml_string for k in keywords):
                    return key, page_type
        return None, None

    def check_moments_icons(self, page_type):
        page_criteria = {
            "朋友圈-全部": {"ImageView": "选项", "RelativeLayout": "选项：广告屏蔽"}
        }

        nodes_with_attribute = self.root.xpath('//*[@NAF="true"]')
        for node in nodes_with_attribute:
            if node.attrib['class'].split('.')[-1] in page_criteria[page_type]:
                node.attrib['text'] = page_criteria[page_type][node.attrib['class'].split('.')[-1]]
                del node.attrib['NAF']

    def check_account_subscription(self, page_type):
        page_criteria = {
            "公众号-首页": {"id/amr": "关注公众号"}
        }

        nodes_with_attribute = self.root.xpath('//*[@NAF="true"]')
        for node in nodes_with_attribute:
            if node.attrib['resource-id'].split(':')[-1] in page_criteria[page_type]:
                node.attrib['text'] = page_criteria[page_type][node.attrib['resource-id'].split(':')[-1]]
                del node.attrib['NAF']

    def check_chat_settings(self, page_type):
        page_criteria = {
            "聊天信息": ["id/ocy"]
        }

        nodes_with_attribute = self.root.xpath('//*[@NAF="true"]')
        for node in nodes_with_attribute:
            if node.attrib['resource-id'].split(':')[-1] in page_criteria[page_type]:
                # 干扰模型判断，直接删除
                node.getparent().remove(node)
    
    def get_money_base_node(self, node, page_type):
        page_criteria = {
            "微信-红包": [("未领取的红包", 0), ("可直接使用", 0)]
        }

        pattern_need_fuzzy = []

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if pattern in content_desc or pattern in text:
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'], node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break


        for child in list(node):
            self.get_money_base_node(child, page_type)

    def check_money(self, page_type):
        self.get_money_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        if parent is not None:
            parent.remove(node)

    def get_payset_base_node(self, node, page_type):
        page_criteria = {
            "微信-支付设置": [("自动续费", 2)],
            "微信-关闭自动扣费": [("扣费记录", 3)]
        }

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if pattern in content_desc or pattern in text:
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'], node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break


        for child in list(node):
            self.get_payset_base_node(child, page_type)

    def check_payset(self, page_type):
        self.get_payset_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        if parent is not None:
            for ind, child in reversed(list(enumerate(parent))):
                if child != node:
                    parent.remove(child)
    
    def get_search_base_node(self, node, page_type):
        page_criteria = {
            "搜索-全部": [("清空", 1)]
        }

        pattern_need_fuzzy = []

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if (pattern in pattern_need_fuzzy and (pattern in content_desc or pattern in text)) or \
                   (pattern not in pattern_need_fuzzy and (pattern == content_desc or pattern == text)):
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'], node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break


        for child in list(node):
            self.get_search_base_node(child, page_type)

    def check_search(self, page_type):
        self.get_search_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        if parent is not None:
            delete_ind = parent.index(node) + 1
            del parent[delete_ind:]
    
    def get_menu_base_node(self, node, page_type):
        page_criteria = {
            "首页": ["微信", "通讯录", "发现", "我"]
        }
        retrieve_times = 1

        if 'content-desc' in node.attrib:
            content_desc = node.attrib['content-desc']
            text = node.attrib['text']
            if text in page_criteria.get(page_type, []) or content_desc in page_criteria.get(page_type, []):
                if text not in self.base_node or compare_y_in_bounds(self.base_node[text].attrib['bounds'], node.attrib['bounds']):
                    self.base_node[text] = node
                    self.retrieve_times = retrieve_times

        for child in list(node):
            self.get_menu_base_node(child, page_type)

    def check_menu(self, page_type):
        self.get_menu_base_node(self.root, page_type)
        # self.base_node = {}
        # self.base_node = list(self.base_node.values())
        base_node_list = list(self.base_node.values())
        if len(base_node_list) == 0:
            return
        
        cur = None
        for node in base_node_list:
            if node.get("selected", "false") == "false":
                cur = node
                break
        
        self.base_node = cur

        while self.retrieve_times > 0:
            if cur.getparent() is not None:
                cur = cur.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = cur.getparent()
        view_node = None
        for node in list(parent)[0].iter():
            if "ListView" in node.attrib["class"] or "RecyclerView" in node.attrib["class"]:
                view_node = node
                break

        if view_node is not None:
            for node in list(view_node):
                intersect = False
                for check_node in base_node_list:
                    if check_bounds_intersection(node.attrib['bounds'], check_node.attrib['bounds']):
                        intersect = True
                        break
                if intersect:
                    view_node.remove(node)
                

    def get_settings_base_node(self, node, page_type):
        page_criteria = {
            "设置": [("账号与安全", 4)],
            "设置-朋友权限": [("添加我的方式", 3)],
            "设置-朋友权限-朋友圈": [("朋友圈权限", 1)],
            "设置-朋友权限-添加我的方式": [("添加我的方式", 1)], # 未测试
            "设置-通用": [("界面和显示", 3)],
            "设置-通用-深色模式": [("开启后", 3)],
            "设置-聊天": [("聊天背景", 3)],
            "设置-聊天-聊天背景": [("选择背景图", 3)],
            "设置-新消息通知": [("新消息通知", 1)], # 未测试
            "设置-账号与安全": [("账号与安全", 1)], # 未测试
        }

        pattern_need_fuzzy = ["开启后"]

        if 'text' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if (pattern in pattern_need_fuzzy and (pattern in content_desc or pattern in text)) or \
                   (pattern not in pattern_need_fuzzy and (pattern == content_desc or pattern == text)):
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'], node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break


        for child in list(node):
            self.get_settings_base_node(child, page_type)

    def check_settings(self, page_type):
        self.get_settings_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        # 循环，向外每一层都删去兄弟节点
        parent = node.getparent()
        while parent is not None:
            for ind, child in reversed(list(enumerate(parent))):
                if child != node:
                    parent.remove(child)
            node = parent
            parent = node.getparent()


class ElemeSpecialCheck:
    def __init__(self, xml_string, root):
        self.xml_string = xml_string
        self.root = root

    def check(self):
        page, page_type = self.check_page()

        self.base_node = None
        self.retrieve_times = 0
        check_type = ''
        if page == "search":
            # self.check_search(page_type)
            check_type = "add"
        elif page == "add_to_cart":
            self.check_add_to_cart(page_type)
            check_type = "add"
        return page_type, check_type

    def check_page(self):
        page_map = {
            "search": [
                (["销量优先", "速度优先", "筛选"], "饿了么-搜索筛选")
            ],
            "add_to_cart": [
                (["选好了"], "饿了么-选好了")
            ]
        }

        for key, values in page_map.items():
            for keywords, page_type in values:
                xml_string = self.xml_string
                check = []
                for k in keywords:
                    check.append(k in xml_string)
                    xml_string = xml_string.replace(k, "", 1)
                if all(check):
                    return key, page_type
        return None, None
    
    def get_add_to_cart_base_node(self, node, page_type):
        page_criteria = {
            "饿了么-选好了": [("选好了", 0)]
        }

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if pattern == content_desc or pattern == text:
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or check_bounds_containing(node.attrib['bounds'], self.base_node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_add_to_cart_base_node(child, page_type)

    def check_add_to_cart(self, page_type):
        self.get_add_to_cart_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        pattern = "选好了"

        if parent is not None:
            if pattern == parent.attrib['content-desc'] or pattern == parent.attrib['text']:
                grandparent = parent.getparent()
                if grandparent is not None:
                    grandparent.remove(parent)
                    attrib_dict = copy.deepcopy(node.attrib)
                    append_node(grandparent, attrib_dict)


class MeituanSpecialCheck:
    def __init__(self, xml_string, root):
        self.xml_string = xml_string
        self.root = root

    def check(self):
        page, page_type = self.check_page()

        self.base_node = None
        self.retrieve_times = 0
        check_type = ''
        if page == "home":
            self.check_home(page_type)
            check_type = "remove"
        elif page == "favourite":
            self.check_favourite(page_type)
            check_type = "remove"
        elif page == "search":
            self.check_search(page_type)
            check_type = "remove"
        elif page == "rating":
            self.check_rating(page_type)
            check_type = "add"
        elif page == "choose":
            self.check_choose(page_type)
            check_type = "remove"
        elif page == "dingdan":
            self.check_dingdan(page_type)
            check_type = "remove"
        elif page == "waimai":
            self.check_waimai(page_type)
            check_type = "remove"
        return page_type, check_type

    def check_page(self):
        page_map = {
            "home": [
                (["我的", "消息", "购物车", "扫一扫"], "首页"),
            ],
            "favourite": [
                (["全部服务", "全部服务"], "全部服务"),
                (["全部地区", "全部地区"], "全部地区"),
            ],
            "search": [
                (["综合排序", "综合排序"], "综合排序"),
                (["商家品质", "价格", "营业状态"], "筛选"),
                (["美团专送","美团快送","到店自取"],"优惠筛选"),
            ],
            "rating": [
                (["满意", "评价", "总体"], "评价"),
            ],
            "choose": [
                (["蔬菜豆品","水果鲜花","休闲零食"],"美团优选"),
            ],
            "dingdan":[
                (["按时间选择","近1个月"],"订单筛选"),
            ],
            "waimai": [
                (["已选规格", "总计"], "选择规格"),
            ],
        }

        for key, values in page_map.items():
            for keywords, page_type in values:
                xml_string = self.xml_string
                check = []
                for k in keywords:
                    check.append(k in xml_string)
                    xml_string = xml_string.replace(k, "", 1)
                if all(check):
                    return key, page_type
        return None, None

    def check_rating(self, page_type):
        page_criteria = {
            "评价": {"ViewGroup": "{num}星"}
        }

        nodes_with_attribute = self.root.xpath('//*[@NAF="true"]')
        nodes_group = {}
        for node in nodes_with_attribute:
            bounds = bounds_to_coords(node.attrib['bounds'])
            if bounds[1] not in nodes_group:
                nodes_group[bounds[1]] = []
            nodes_group[bounds[1]].append(node)
        for y, nodes in nodes_group.items():
            nodes.sort(key=lambda x: bounds_to_coords(x.attrib['bounds'])[0])
            for i, node in enumerate(nodes):
                if node.attrib['class'].split('.')[-1] in page_criteria[page_type]:
                    node.attrib['text'] = page_criteria[page_type][node.attrib['class'].split('.')[-1]].format(num=(i+1))
                    del node.attrib['NAF']

        # for node in nodes_with_attribute:
        #     if node.attrib['class'].split('.')[-1] in page_criteria[page_type]:
        #         node.attrib['text'] = page_criteria[page_type][node.attrib['class'].split('.')[-1]].format(num=(int(node.attrib['index'])+1))
        #         del node.attrib['NAF']

    def get_home_base_node(self, node, page_type):
        page_criteria = {
            "首页": [("搜索框", 1)]
        }

        pattern_need_fuzzy = ["搜索框"]

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if (pattern in pattern_need_fuzzy and (pattern in content_desc or pattern in text)) or \
                   (pattern not in pattern_need_fuzzy and (pattern == content_desc or pattern == text)):
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'], node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break


        for child in list(node):
            self.get_home_base_node(child, page_type)

    def check_home(self, page_type):
        self.get_home_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        for ind, child in reversed(list(enumerate(parent))):
            if child != node and check_bounds_intersection(child.attrib['bounds'], node.attrib['bounds']):
                parent.remove(child)

    def get_favourite_base_node(self, node, page_type):
        page_criteria = {
            "全部服务": [("全部服务", 3)],
            "全部地区": [("全部地区", 3)],
        }

        pattern_need_fuzzy = [""]

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if (pattern in pattern_need_fuzzy and (pattern in content_desc or pattern in text)) or \
                   (pattern not in pattern_need_fuzzy and (pattern == content_desc or pattern == text)):
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'], node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_favourite_base_node(child, page_type)

    def check_favourite(self, page_type):
        self.get_favourite_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        if parent is not None:
            delete_ind = parent.index(node) + 1
            try:
                parent.remove(list(parent)[delete_ind])
            except Exception:
                pass

    def get_search_base_node(self, node, page_type):
        page_criteria = {
            "综合排序": [("综合排序", 3)],
            "筛选": [("综合排序", 3)],
            "优惠筛选":[("美团专送",5)],
        }

        pattern_need_fuzzy = [""]

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if (pattern in pattern_need_fuzzy and (pattern in content_desc or pattern in text)) or \
                   (pattern not in pattern_need_fuzzy and (pattern == content_desc or pattern == text)):
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(node.attrib['bounds'], self.base_node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_search_base_node(child, page_type)

    def check_search(self, page_type):
        self.get_search_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        if parent is not None:
            delete_ind = parent.index(node) + 1
            try:
                for child in list(parent)[delete_ind:]:
                    parent.remove(child)
            except Exception:
                pass

    def get_choose_base_node(self, node, page_type):
        page_criteria = {
            "美团优选": [("蔬菜豆品", 1)],
        }

        pattern_need_fuzzy = [""]

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if (pattern in pattern_need_fuzzy and (pattern in content_desc or pattern in text)) or \
                   (pattern not in pattern_need_fuzzy and (pattern == content_desc or pattern == text)):
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'], node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_choose_base_node(child, page_type)

    def check_choose(self, page_type):
        self.get_choose_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        if parent is not None:
            for i in range(6):
                delete_ind = parent.index(node) - 3
                try:
                    parent.remove(list(parent)[delete_ind])
                except Exception:
                    pass     
    def get_dingdan_base_node(self, node, page_type):
        page_criteria = {
            "订单筛选":[("按时间选择",1)],
        }

        pattern_need_fuzzy = [""]

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if (pattern in pattern_need_fuzzy and (pattern in content_desc or pattern in text)) or \
                   (pattern not in pattern_need_fuzzy and (pattern == content_desc or pattern == text)):
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'], node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_dingdan_base_node(child, page_type)

    def check_dingdan(self, page_type):
        self.get_dingdan_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        if parent is not None:
            for i in range(5):
                delete_ind = parent.index(node) - 1
                try:
                    parent.remove(list(parent)[delete_ind])
                except Exception:
                    pass
    
    def get_waimai_base_node(self, node, page_type):
        page_criteria = {
            "选择规格": [("总计", 2)],
        }

        pattern_need_fuzzy = [""]

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if (pattern in pattern_need_fuzzy and (pattern in content_desc or pattern in text)) or \
                   (pattern not in pattern_need_fuzzy and (pattern == content_desc or pattern == text)):
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'], node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_waimai_base_node(child, page_type)

    def check_waimai(self, page_type):
        self.get_waimai_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        if parent is not None:
            for ch in list(parent):
                if ch != node:
                    try:
                        parent.remove(ch)
                    except Exception:
                        pass
                    
                    
class TaoBaoSpecialCheck:
    def __init__(self, xml_string, root):
        self.xml_string = xml_string
        self.root = root

    def check(self):
        self.remove_duplicate_text()

        page, page_type = self.check_page()
        self.base_node = None
        self.retrieve_times = 0
        check_type = ''
        if page == "commodity":
            self.check_commodity(page_type)
            check_type = "remove"
        elif page == "filter":
            self.check_filter(page_type)
            check_type = "remove"
        elif page == "comment":
            self.check_comment(page_type)
            check_type = "remove"
        elif page == "sort":
            self.check_sort(page_type)
            check_type = "remove"
        elif page == "search":
            self.check_search(page_type)
            check_type = "remove"
        return page_type, check_type

    def remove_duplicate_text(self):
        text_itered = []
        for node in self.root.iter():
            if "text" not in node.attrib:
                continue

            node_text = node.attrib["text"] + node.attrib["content-desc"]
            if node_text == "":
                continue
            if node_text in text_itered and node.attrib["clickable"] == "false":
                node.getparent().remove(node)
            else:
                text_itered.append(node_text)

    def check_page(self):
        page_map = {
            "commodity": [(["店铺", "客服", "收藏", "加入购物车", "购买"], "商品详情")],
            "filter": [
                (["物流与权益null", "价格区间(元)null"], "商品筛选"),
                (["订单筛选", "下单时间", "来源", "常买的类目"], "订单筛选"),
            ],
            "comment": [(["公开并分享", "公开发布", "匿名评价"], "评价选项")],
            "sort": [(["综合", "价格从高到低", "价格从低到高"], "排序")],
            "search": [(["搜索", "关闭搜索"], "购物车搜索")],
        }

        for key, values in page_map.items():
            for keywords, page_type in values:
                if all(k in self.xml_string for k in keywords):
                    return key, page_type
        return None, None

    def check_commodity(self, page_type):
        for node in self.root.iter():
            if "text" not in node.attrib:
                continue
            if (
                node.attrib["text"] == "삊"
                or node.attrib["text"] == "쁪"
                or node.attrib["text"] == "뀚"
                or node.attrib["text"] == "넻"
            ):
                node.getparent().remove(node)

    def get_filter_base_node(self, node, page_type):
        page_criteria = {
            "商品筛选": [
                ("物流与权益null", 3),
                ("价格区间(元)null", 3),
                ("发货地null", 3),
                ("收货地null", 3),
            ],
            "订单筛选": [("订单筛选", 2)],
        }

        if "content-desc" in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib["content-desc"]
                text = node.attrib["text"]
                # find the specialCheck base node
                if pattern == content_desc or pattern == text:
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(
                        self.base_node.attrib["bounds"], node.attrib["bounds"]
                    ):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_filter_base_node(child, page_type)

    def check_filter(self, page_type):
        self.get_filter_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        for ind, child in reversed(list(enumerate(parent))):
            if child != node:
                parent.remove(child)

    def get_comment_base_node(self, node, page_type):
        page_criteria = {
            "评价选项": [("公开发布", 3)],
        }

        if "content-desc" in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib["content-desc"]
                text = node.attrib["text"]
                # find the specialCheck base node
                if pattern == content_desc or pattern == text:
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(
                        self.base_node.attrib["bounds"], node.attrib["bounds"]
                    ):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_comment_base_node(child, page_type)

    def check_comment(self, page_type):
        self.get_comment_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        for ind, child in reversed(list(enumerate(parent))):
            if child != node:
                parent.remove(child)

    def get_sort_base_node(self, node, page_type):
        page_criteria = {
            "排序": [("价格从高到低，未选中", 2), ("价格从低到高，未选中", 2)],
        }

        if "content-desc" in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib["content-desc"]
                text = node.attrib["text"]
                # find the specialCheck base node
                if pattern == content_desc or pattern == text:
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(
                        self.base_node.attrib["bounds"], node.attrib["bounds"]
                    ):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_sort_base_node(child, page_type)

    def check_sort(self, page_type):
        self.get_sort_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        for ind, child in reversed(list(enumerate(parent))):
            if child != node:
                parent.remove(child)

    def get_search_base_node(self, node, page_type):
        page_criteria = {
            "购物车搜索": [("关闭搜索", 1)],
        }

        if "content-desc" in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib["content-desc"]
                text = node.attrib["text"]
                # find the specialCheck base node
                if pattern == content_desc or pattern == text:
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(
                        self.base_node.attrib["bounds"], node.attrib["bounds"]
                    ):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_search_base_node(child, page_type)

    def check_search(self, page_type):
        self.get_search_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        for ind, child in reversed(list(enumerate(parent))):
            if child != node:
                parent.remove(child)


class DzdpSpecialCheck:
    def __init__(self, xml_string, root):
        self.xml_string = xml_string
        self.root = root

    def check(self):
        page, page_type = self.check_page()
        self.base_node = None
        self.retrieve_times = 0
        check_type = ''
        if page_type == "点评-地区":
            self.check_filter(page_type)
            check_type = "add"
        elif page_type == "点评-评价":
            self.check_rating(page_type)
            check_type = "add"
        return page_type, check_type

    def check_page(self):
        page_map = {
            "rating": [
                (["匿名评价", "写评价", "保存", "发布"], "点评-评价"),
                (["很糟糕", "较差", "一般", "还可以", "很棒", "总体"], "点评-评价")
            ],
            "filter": [
                (["指定地点", "热门", "商区"], "点评-地区"),
            ],
        }

        for key, values in page_map.items():
            for keywords, page_type in values:
                if all(k in self.xml_string for k in keywords):
                    return key, page_type
        return None, None

    def get_base_node(self, node, page_type):
        page_criteria = {
            "点评-地区": [("商区", 4)],
        }

        pattern_need_fuzzy = ["出发站点"]

        if 'text' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if (pattern in pattern_need_fuzzy and (pattern in content_desc or pattern in text)) or \
                        (pattern not in pattern_need_fuzzy and (pattern == content_desc or pattern == text)):
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'],
                                                                     node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_base_node(child, page_type)

    def get_rate_node(self, node, page_type):
        page_criteria = {
            "点评-评价": [("总体", 2)],
        }

        # pattern_need_fuzzy = ["出发站点"]

        if 'text' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if (pattern == content_desc or pattern == text):
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'],
                                                                     node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_rate_node(child, page_type)

    def check_filter(self, page_type):
        self.get_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        # 删兄弟节点
        parent = node.getparent()
        if parent is not None:
            delete_ind = parent.index(node) - 1
            try:
                while 'RecyclerView' not in list(parent)[delete_ind].attrib['class']:
                    parent.remove(list(parent)[delete_ind])
                    delete_ind -= 1

                delete_parent = list(parent)[delete_ind]
                for n in list(delete_parent)[:-1]:
                    delete_parent.remove(n)

                for n in list(delete_parent.iter())[2:]:
                    if 'RecyclerView' in n.attrib['class']:
                        n.getparent().remove(n)
                        break
            except Exception:
                pass

        recyclers = []
        for n in node.iter():
            if 'RecyclerView' in n.attrib['class']:
                recyclers.append(n)
        recylers = sorted(recyclers, key=lambda x: bounds_to_coords(x.attrib['bounds'])[0])
        for i in range(len(recyclers) - 1):
            rbound = bounds_to_coords(recyclers[i + 1].attrib['bounds'])[0]
            for n in list(recyclers[i]):
                coords = bounds_to_coords(n.attrib['bounds'])
                coords[2] = rbound
                n.attrib['bounds'] = coords_to_bounds(coords)

    def check_rating(self, page_type):
        try:
            nodes_with_attribute = self.root.xpath('//*[@resource-id="com.dianping.v1:id/ugc_write_star_input_view"]')[0]
            for parent in list(nodes_with_attribute):
                text_node = None
                for ch in list(parent):
                    if ch.attrib['text'] != '':
                        text_node = ch
                        break
                if text_node is not None:
                    attrib_dict = copy.deepcopy(text_node.attrib)

                    text_node_bounds = bounds_to_coords(text_node.attrib['bounds'])
                    interval = text_node_bounds[2] - text_node_bounds[0]
                    text_node_bounds = [text_node_bounds[0] + interval // 4,
                                        text_node_bounds[1],
                                        text_node_bounds[2] - interval // 9,
                                        text_node_bounds[3]]
                    text_node.attrib['bounds'] = coords_to_bounds(text_node_bounds)
                    parent_bounds = bounds_to_coords(parent.attrib['bounds'])
                    base_bounds = [text_node_bounds[2],
                                   parent_bounds[1],
                                   parent_bounds[2] - interval + (
                                               bounds_to_coords(parent.getparent().attrib['bounds'])[2] - parent_bounds[
                                           2]) * 3,
                                   parent_bounds[3]]
                    base_interval = (base_bounds[2] - base_bounds[0]) / 5

                    for i, text in enumerate(
                            ['半星/一星', '一星半或二星', '二星半/三星', '三星半/四星', '四星半/五星']):
                        attrib_dict['text'] = text
                        attrib_dict['clickable'] = 'true'
                        attrib_dict['index'] = str(int(attrib_dict['index']) + i + 1)
                        attrib_dict['bounds'] = coords_to_bounds([
                            int(text_node_bounds[2] + i * base_interval),
                            parent_bounds[1],
                            int(text_node_bounds[2] + (i + 1) * base_interval),
                            parent_bounds[3]])
                        
                        if i == 4:
                            attrib_dict['bounds'] = coords_to_bounds([
                                int(text_node_bounds[2] + (i+0.5) * base_interval), 
                                parent_bounds[1], 
                                int(text_node_bounds[2] + (i+1) * base_interval), 
                                parent_bounds[3]])
                        
                        append_node(parent, attrib_dict)
            # all_bounds = []
            # for node in nodes_with_attribute:
            #     min_bounds = "[0,0][10000,10000]"
            #     for ch in node.iter():
            #         if get_bounds_area(ch.attrib['bounds']) < get_bounds_area(min_bounds):
            #             min_bounds = ch.attrib['bounds']
            #     all_bounds.append(min_bounds)
            # return page_type, all_bounds

        except Exception as e:
            # import traceback
            # traceback.print_exc()
            self.get_rate_node(self.root, page_type)
            node = self.base_node
            if node is None:
                return

            while self.retrieve_times > 0:
                if node.getparent() is not None:
                    node = node.getparent()
                    self.retrieve_times -= 1
                else:
                    return

            # 删兄弟节点
            parent = node.getparent()
            for ind, child in reversed(list(enumerate(parent))):
                if child != node:
                    parent.remove(child)
            return


class WeiboSpecialCheck:
    def __init__(self, xml_string, root):
        self.xml_string = xml_string
        self.root = root

    def check(self):
        
        page, page_type = self.check_page()
        self.base_node = None
        self.retrieve_times = 0
        check_type = ''
        if page == "discover":
            # self.check_filter(page_type)
            check_type = "add"
        return page_type, check_type

    def check_page(self):
        page_map = {
            "discover": [
                (["发现", "趋势", "榜单", "更多热搜"], "微博-发现")
            ],
        }

        for key, values in page_map.items():
            for keywords, page_type in values:
                if all(k in self.xml_string for k in keywords):
                    return key, page_type
        return None, None


class AlipaySpecialCheck:
    def __init__(self, xml_string, root):
        self.xml_string = xml_string
        self.root = root

    def check(self):
        
        page, page_type = self.check_page()
        self.base_node = None
        self.retrieve_times = 0
        check_type = ''
        if page == "money":
            # self.check_filter(page_type)
            check_type = "add"
        return page_type, check_type

    def check_page(self):
        page_map = {
            "money": [
                (["口令红包", "自定义祝福口令"], "支付宝-口令红包")
            ],
        }

        for key, values in page_map.items():
            for keywords, page_type in values:
                if all(k in self.xml_string for k in keywords):
                    return key, page_type
        return None, None


class RedBookSpecialCheck:
    def __init__(self, xml_string, root):
        self.xml_string = xml_string
        self.root = root

    def check(self):
        self.remove_duplicate_text()
        
        page, page_type = self.check_page()
        self.base_node = None
        self.retrieve_times = 0
        check_type = ''
        if page == "filter":
            self.check_filter(page_type)
            check_type = "remove"
        return page_type, check_type

    def remove_duplicate_text(self):
        text_itered = []
        for node in self.root.iter():
            if 'text' not in node.attrib:
                continue
    
            node_text = node.attrib['text'] + node.attrib['content-desc']
            if node_text == "":
                continue
            if node_text in text_itered and node.attrib['clickable'] == 'false':
                node.getparent().remove(node)
            else:
                text_itered.append(node_text)

    def check_page(self):
        page_map = {
            "filter": [
                (["笔记类型", "视频", "图文"], "笔记筛选")
            ],
        }

        for key, values in page_map.items():
            for keywords, page_type in values:
                if all(k in self.xml_string for k in keywords):
                    return key, page_type
        return None, None
    
    def get_filter_base_node(self, node, page_type):
        page_criteria = {
            "笔记筛选": [("笔记类型", 2)]
        }

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if pattern == content_desc or pattern == text:
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'], node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_filter_base_node(child, page_type)

    def check_filter(self, page_type):
        self.get_filter_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        parent = node.getparent()
        if parent is None:
            return
        for ind, child in list(enumerate(parent)):
            # print(child.attrib['bounds'])
            if child != node:
                parent.remove(child)


class XieChengSpecialCheck:
    def __init__(self, xml_string, root):
        self.xml_string = xml_string
        self.root = root

    def check(self):
        self.remove_duplicate_text()

        page, page_type = self.check_page()
        self.base_node = None
        self.retrieve_times = 0
        check_type = ''
        if page == "filter":
            self.check_filter(page_type)
            check_type = "remove"
        elif page == "date":
            check_type = "unchanged"
        return page_type, check_type

    def remove_duplicate_text(self):
        text_itered = []
        for node in self.root.iter():
            if 'text' not in node.attrib:
                continue
    
            node_text = node.attrib['text'] + node.attrib['content-desc']
            if node_text == "":
                continue
            if node_text in text_itered and node.attrib['clickable'] == 'false':
                node.getparent().remove(node)
            else:
                text_itered.append(node_text)

    def check_page(self):
        page_map = {
            "filter": [
                (["欢迎度排序", "好评优先", "点评数", "低价优先"], "排序"),
                (["直线距离", "热门", "景点", "机场车站"], "位置距离"),
                (["价格", "钻级"], "价格星级"),
                (["热门筛选", "品牌", "设施", "点评"], "筛选"),
            ],
            "date": [
                (["选择日期"], "携程-选择日期"),
                (["选择出发日期"], "携程-选择日期"),
                (["选择往返日期"], "携程-选择日期"),
                (["指定日期", "灵活日期"], "携程-选择日期"),
            ]
        }

        for key, values in page_map.items():
            for keywords, page_type in values:
                if all(k in self.xml_string for k in keywords):
                    return key, page_type
        return None, None
    
    def get_filter_base_node(self, node, page_type):
        page_criteria = {
            "排序": [("低价优先", 0)],
            "位置距离": [("直线距离", 0)],
            "价格星级": [("价格  ", 0)],
            "筛选": [("热门筛选", 0)]
        }

        if 'content-desc' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if pattern == content_desc or pattern == text:
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'], node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_filter_base_node(child, page_type)

    def check_filter(self, page_type):
        self.get_filter_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return
            
        stop_word = self.get_stop_word(page_type)
        if stop_word == "":
            return

        parent = node.getparent()
        for child in list(parent):
            if child.tag == "node":
                content_desc = child.attrib.get('content-desc')
                child_class = child.attrib.get('class')
                if content_desc != stop_word or child_class == "android.widget.ImageView":
                    parent.remove(child)
                else:
                    break

    def get_stop_word(self, page_type):
        stop_word = {
            "排序": "欢迎度排序",
            "位置距离": "直线距离",
            "价格星级": "价格  ",
            "筛选": "热门筛选"
        }
        return stop_word.get(page_type, "")


class MobileTicketSpecialCheck:
    def __init__(self, xml_string, root):
        self.xml_string = xml_string
        self.root = root

    def check(self):
        page, page_type = self.check_page()
        self.base_node = None
        self.retrieve_times = 0
        check_type = ''
        # print(page, page_type)
        if page == "filter":
            self.check_filter(page_type)
            check_type = "remove"
        elif page == "date":
            self.check_date(page_type)
            check_type = "remove"
        elif page == "city":
            self.check_city(page_type)
            check_type = "remove"
        return page_type, check_type

    def check_page(self):
        page_map = {
            "filter": [
                (["车次类型", "车组类型", "经停详情"], "筛选-火车票"),
                # 飞机票和汽车票，训练数据中很少筛选，暂未检查是否需特判
            ],
            "date": [
                (["选择日期", "日", "五", "六", "年"], "选择日期-飞机票"),
            ],
            "city": [
                (["更多", "出发站点"], "选择城市-飞机票"),
            ]
        }

        for key, values in page_map.items():
            for keywords, page_type in values:
                if all(k in self.xml_string for k in keywords):
                    return key, page_type
        return None, None
    
                
    # 各种 page 共用
    def get_base_node(self, node, page_type):
        page_criteria = {
            "筛选-火车票": [("车次类型", 3)],
            "选择日期-飞机票": [("选择日期", 2)],
            "选择城市-飞机票": [("出发站点", 2)],
        }

        pattern_need_fuzzy = ["出发站点"]

        if 'text' in node.attrib:
            for pattern, retrieve_times in page_criteria.get(page_type, []):
                content_desc = node.attrib['content-desc']
                text = node.attrib['text']
                # find the specialCheck base node
                if (pattern in pattern_need_fuzzy and (pattern in content_desc or pattern in text)) or \
                   (pattern not in pattern_need_fuzzy and (pattern == content_desc or pattern == text)):
                    # If the base node is not unique, find the one that is lower.
                    if self.base_node is None or compare_y_in_bounds(self.base_node.attrib['bounds'], node.attrib['bounds']):
                        self.base_node = node
                        self.retrieve_times = retrieve_times
                        break

        for child in list(node):
            self.get_base_node(child, page_type)

    def check_filter(self, page_type):
        self.get_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        # 删兄弟节点
        parent = node.getparent() 
        if parent is not None:
            for ind, child in reversed(list(enumerate(parent))):
                if child != node:
                    parent.remove(child)

    def check_date(self, page_type):
        self.get_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        # 删兄弟节点
        parent = node.getparent() 
        if parent is not None:
            for ind, child in reversed(list(enumerate(parent))):
                if child != node:
                    parent.remove(child)
    
    def check_city(self, page_type):
        self.get_base_node(self.root, page_type)
        node = self.base_node
        if node is None:
            return

        while self.retrieve_times > 0:
            if node.getparent() is not None:
                node = node.getparent()
                self.retrieve_times -= 1
            else:
                return

        # 删兄弟节点
        parent = node.getparent() 
        if parent is not None:
            for ind, child in reversed(list(enumerate(parent))):
                if child != node:
                    parent.remove(child)

SpecialCheck = {
    "com.autonavi.minimap": MiniMapSpecialCheck, # 高德地图
    "com.tencent.mm": WeiXinSpecialCheck, # 微信
    "com.sankuai.meituan": MeituanSpecialCheck, # 美团
    "me.ele": ElemeSpecialCheck, # 饿了么
    "com.taobao.taobao": TaoBaoSpecialCheck, # 淘宝
    "com.dianping.v1": DzdpSpecialCheck, # 大众点评
    "com.MobileTicket": MobileTicketSpecialCheck, # 12306
    "com.xingin.xhs": RedBookSpecialCheck, # 小红书
    "ctrip.android.view": XieChengSpecialCheck, # 携程
    "com.sina.weibo": WeiboSpecialCheck, # 微博
    "com.eg.android.AlipayGphone": AlipaySpecialCheck, # 支付宝
}
