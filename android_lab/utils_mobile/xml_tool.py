from collections import deque
from typing import Dict
from lxml import etree
from lxml.etree import XMLParser
import xmltodict
import json
import uuid
import copy
import re
from android_lab.utils_mobile.specialCheck import *
from android_lab.utils_mobile.ocr_tools import XML_OCR_Matcher
import argparse
import traceback
import time


def get_compressed_xml(xml_path, xml_version='v2', height=None, width=None, call_api=False, use_ocr=False, image_path=None, use_xml_id=False, check_special=True):
    xml_parser = UIXMLTree(xml_version=xml_version)
    with open(xml_path, 'r', encoding='utf-8') as f:
        xml_str = f.read()
    error_log = None
    try:
        compressed_xml, _, _, id2bounds, scaling_map = xml_parser.process(xml_str, 
                                                                          level=1, 
                                                                          str_type="plain_text",
                                                                          call_api=call_api, 
                                                                          use_xml_id=use_xml_id, 
                                                                          use_ocr=use_ocr, 
                                                                          image_path=image_path, 
                                                                          check_special=check_special,
                                                                          width=width,
                                                                          height=height)
        compressed_xml = compressed_xml.strip()
    except Exception as e:
        compressed_xml = None
        error_log = traceback.format_exc()
    if use_ocr:
        ocr_labels = xml_parser.get_ocr_labels()
    else:
        ocr_labels = None
    return compressed_xml, id2bounds, scaling_map, error_log, ocr_labels


def get_words_in_certain_length(text, length=10):
    words = text.split()
    if len(words) > length:
        return ' '.join(words[:length])
    else:
        return ' '.join(words)


def replace_string_between_angle_brackets(text):
    return re.sub(r'<.*?>', '', text)


def check_version_size(v1, v2):
    v1 = v1[1:]
    v2 = v2[1:]
    if '.' in v2:
        if v1 == v2:
            return True
        else:
            return False
    else:
        return float(v1) >= float(v2)

class UIXMLTree:
    def __init__(self, debug=False, xml_version='v2', ablation="None"):
        self.root = None
        self.cnt = None
        self.node_to_xpath: Dict[str, list[str]] = {}
        self.node_to_name = None
        self.remove_system_bar = None
        self.processors = None
        self.app_name = None
        self.myTree = None
        self.xml_dict = None  # dictionary: processed xml
        self.processors = [self.xml_sparse, self.merge_none_act]
        self.lastTree = None
        self.mapCount = {}
        self.use_bounds = False
        self.merge_switch = False
        self.all_bounds = {}
        self.xml_version = xml_version
        self.ablation = ablation
        # self.ocr_tool = XML_OCR_Matcher(print_intermediates=debug)
        # self.ocr_tool = None

    def process(self, xml, app_info=None, level=1, str_type="json",
                remove_system_bar=True, use_bounds=False, merge_switch=False,
                image_path=None,
                use_ocr=False,
                call_api=False,
                check_special=True,
                use_xml_id=False,
                height=None,
                width=None,
                max_limit=999):
        if isinstance(xml, str):
            self.xml_string = xml
            self.root = etree.fromstring(xml.encode('utf-8'))
        elif isinstance(xml, bytes):
            huge_parser = XMLParser(huge_tree=True)
            self.root = etree.fromstring(xml, parser=huge_parser)
            self.xml_string = etree.tostring(self.root, pretty_print=True, encoding='utf-8').decode()
            self.xml_string = "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>\n" + self.xml_string
        else:
            self.xml_string = etree.tostring(xml, pretty_print=True, encoding='utf-8').decode()
            self.root = xml
        self.image_path = image_path
        if self.root.attrib.get('height') is not None:
            self.height = int(self.root.attrib.pop('height'))
            self.width = int(self.root.attrib.pop('width'))
        else:
            self.height = height
            self.width = width
        self.max_limit = max_limit
        self.use_ocr = use_ocr
        self.call_api = call_api
        self.cnt = 0
        self.node_to_xpath: Dict[str, list[str]] = {}
        self.node_to_name = {}
        self.remove_system_bar = remove_system_bar
        self.check_special = check_special

        self.app_name = None
        self.lastTree = self.myTree
        self.myTree = None
        self.use_bounds = use_bounds
        self.merge_switch = merge_switch
        
        self.focused_edittext_nodes = []
        
        self.output_root = None
        self.special_check_infer = False
        self.use_xml_id = use_xml_id
        
        self.max_bounds = "[0,0][0,0]"
        for node in self.root.iter():
            if 'bounds' in node.attrib and get_bounds_area(node.attrib['bounds']) > get_bounds_area(self.max_bounds):
                self.max_bounds = node.attrib['bounds']
        
        for node in self.root.iter():
            if 'package' in node.attrib:
                self.current_app = node.attrib['package']
                break

        # from fine-grained to coarse-grained observation
        for processor in self.processors[:level]:
            processor()
        processed_root = copy.deepcopy(self.root)
        if self.special_check_infer:
            ret_result = self.root_to_compressed_xml(self.root, str_type)
            if check_version_size(self.xml_version, 'v4'):
                return ret_result, self.output_root, processed_root, self.root_id2bounds, self.scaling_map
            return ret_result, self.output_root, processed_root, self.root_id2bounds, None
        else:
            output_root = copy.deepcopy(self.output_root)
            ret_result = self.root_to_compressed_xml(self.output_root, str_type)
            if check_version_size(self.xml_version, 'v4'):
                return ret_result, output_root, processed_root, self.root_id2bounds, self.scaling_map
            return ret_result, output_root, processed_root, self.output_root_id2bounds, None

    def get_current_app(self):
        return self.current_app

    def root_to_compressed_xml(self, root, str_type):
        self.reindex(root)
        
        self.xml_dict = xmltodict.parse(etree.tostring(root, encoding='utf-8'), attr_prefix="")
        self.traverse_dict(self.xml_dict)
        if "json" == str_type:
            return json.dumps(self.xml_dict, indent=4, ensure_ascii=False).replace(": {},", "").replace(": {}", "")
        elif "plain_text" == str_type:
            return self.dict_to_plain_text(self.xml_dict)
        else:
            raise NotImplementedError
    
    def get_edittext_bounds(self):
        nodes_bounds = [node.attrib['bounds'] for node in self.focused_edittext_nodes]
        return None if len(nodes_bounds) == 0 else nodes_bounds
    
    def traverse_dict(self, _dict):
        key_replace = []

        for key, value in _dict.items():
            # value is also a dict
            if isinstance(value, dict):
                if "rotation" in value:
                    if not self.app_name:
                        # The current screenshot's description is shown:
                        if check_version_size(self.xml_version, 'v4'):
                            if check_version_size(self.xml_version, 'v4.1'):
                                width = self.width
                                height = self.height
                            else:
                                width = self.max_limit
                                height = self.max_limit
                            app_name = f"The screenshot's size is {width}x{height}. The value in bounds is relative to the screenshot's size.\n"
                            app_name += f"The tree structure description of the current screenshot is shown:"
                        elif check_version_size(self.xml_version, 'v3'):
                            app_name = f"The tree structure description of the current screenshot is shown:"
                        else:
                            app_name = f"The current screenshot's description is shown:"
                    elif self.app_name == "home":
                        app_name = f"This is the home screen view."
                    else:
                        app_name = f"The current APP is {self.app_name}."
                    key_replace.append([key, app_name])
                    del value['rotation']
                elif "description" in value:
                    if check_version_size(self.xml_version, 'v3'):
                        new_key = f"[{key}]{value['description']}"
                    else:
                        new_key = f"[{key}] {value['description']}"
                    key_replace.append([key, new_key])
                    del value['description']

        for key_pr in key_replace:
            _dict[key_pr[1]] = _dict[key_pr[0]]
            del _dict[key_pr[0]]

        for key, value in _dict.items():
            if isinstance(value, dict):
                self.traverse_dict(value)
    
    def dict_to_plain_text(self, xml_dict, indent=0):
        def replace_node_tag(text):
            if self.use_xml_id:
                return re.sub(r'\[n(\d+)\]', r'[\1]', text)
            else:
                if self.ablation == 'v2':
                    return text
                if check_version_size(self.xml_version, 'v4'):
                    return re.sub(r'\[n[0-9a-f]*\]', '', text)
                elif check_version_size(self.xml_version, 'v2'):
                    return re.sub(r'\[n[0-9a-f]*\]', '[n]', text)
                else:
                    return text
        
        result = ""
        for key, value in xml_dict.items():
            result += " " * indent + replace_node_tag(str(key))
            if isinstance(value, dict):
                result += "\n" + self.dict_to_plain_text(value, indent + 4)
            else:
                result += str(value) + "\n"
        return result
    
    def insert_node(self, parent, index, attrib_dict):
        new_node = etree.Element('node')

        for k, v in attrib_dict.items():
            new_node.set(k, v)

        parent.insert(index, new_node)
    
    def find_smallest_enclosing_node(self, node, bounds):
        smallest_node = None

        def update_smallest_node(candidate):
            nonlocal smallest_node
            if smallest_node is None:
                smallest_node = candidate
            elif candidate is not None and get_bounds_area(candidate.attrib['bounds']) < get_bounds_area(smallest_node.attrib['bounds']):
                smallest_node = candidate

        containing_flag = False
        if 'bounds' in node.attrib and check_bounds_containing(bounds, node.attrib['bounds']):
            smallest_node = node
            containing_flag = True

        if 'bounds' not in node.attrib or containing_flag:
            for child in node:
                candidate = self.find_smallest_enclosing_node(child, bounds)
                update_smallest_node(candidate)

        return smallest_node

    def get_ocr_labels(self):
        assert self.use_ocr, "OCR is not enabled, please set use_ocr to True."
        if self.ocr_labels is None:
            return []
        return self.ocr_labels

    def add_ocr_nodes(self):
        _, _, bounds_dict = self.ocr_tool.run(self.output_root, self.image_path)
        if bounds_dict is None or len(bounds_dict) == 0:
            return []

        result = []
        for label, all_bounds in bounds_dict.items():
            for bounds in all_bounds:
                parent_root = self.find_smallest_enclosing_node(self.root, coords_to_bounds(bounds))
                parent_output_root = self.find_smallest_enclosing_node(self.output_root, coords_to_bounds(bounds))
                result.append([label, bounds, parent_root])
                result.append([label, bounds, parent_output_root])
        
        # add new nodes
        node_id_count = 0
        for label, bounds, parent in result:
            if parent is None:
                continue
            
            # special check by ocr
            if self.page_type == "朋友圈-全部" and label in ['赞', '评论']:
                click = 'true'
                class_name = 'TextView'
            elif self.page_type == "文章搜索-筛选" and label in ['不限范围', '最近读过', '综合排序', '最新发布', '按阅读量']:
                click = 'true'
                class_name = 'Button'
            elif self.page_type == "点评-评价" and label in \
                    ["0.5星", "1星", "1.5星", "2星", "2.5星", "3星", "3.5星", "4星", "4.5星", "5星"]:
                click = 'true'
                class_name = 'TextView'
                bounds = [bounds[0], bounds[1] - (bounds[3] - bounds[1]) * 3, bounds[2], bounds[3]]
            elif self.page_type == "携程-选择日期" and len(label) in [1,2,3]: # in [str(date+1) for date in range(31)] + ["休" + str(date+1) for date in range(31)] :
                click = 'true'
                class_name = 'TextView'
                parent_bounds = bounds_to_coords(parent.attrib['bounds'])
                
                for i in range(7):
                    parent_left_bound = (parent_bounds[2] - parent_bounds[0]) // 7 * i + parent_bounds[0]
                    parent_right_bound = (parent_bounds[2] - parent_bounds[0]) // 7 * (i+1) + parent_bounds[0]
                    if parent_left_bound <= bounds[0] and parent_right_bound >= bounds[2] and parent_bounds[1] <= bounds[1] and parent_bounds[3] >= bounds[3]:
                        bounds = [parent_left_bound, parent_bounds[1], parent_right_bound, parent_bounds[3]]
                        break
            elif self.page_type == "饿了么-搜索筛选":
                if label in ["综合排序", "人均价低到高", "距离优先", "商家好评优先", "起送低到高"]:
                    click = 'true'
                    class_name = 'TextView'
                    parent_bounds = bounds_to_coords(parent.attrib['bounds'])
                    bounds[2] = parent_bounds[2]
                else:
                    continue
            elif self.page_type == "微博-发现":
                if "更多热搜" in label:
                    click = 'true'
                    class_name = 'TextView'
                    parent_bounds = bounds_to_coords(parent.attrib['bounds'])
                    bounds[2] = parent_bounds[2]
                else:
                    continue
            elif self.page_type == "支付宝-口令红包":
                if "数字" in label:
                    click = 'true'
                    class_name = 'TextView'
                else:
                    click = 'true'
                    class_name = 'TextView'
            else:
                click = 'false'
                class_name = 'TextView'
                
            attrib_dict = {
                "index": str(len(list(parent))),
                "text": label,
                "resource-id": "",
                "class": class_name,
                "package": parent.attrib['package'],
                "content-desc": "",
                "checkable": "false", 
                "checked": "false",
                "clickable": click,
                "enabled": "false",
                "focusable": "false",
                "focused": "false",
                "scrollable": "false",
                "long-clickable": "false",
                "password": "false",
                "selected": "false",
                "bounds": coords_to_bounds(bounds),
                "xpath1": parent.attrib['xpath1'] + '/' + "android.widget." + class_name + f"[{len(list(parent))}]",
                "xpath2": parent.attrib['xpath2'] + '/' + "android.widget." + class_name + f"[{len(list(parent))}]",
                "name": get_words_in_certain_length(label) + " " + class_name,
                "func-desc": label + " ",
                "action": "",
            }
            append_node(
                parent=parent,
                attrib_dict=attrib_dict,
                node_id=f"ocr{node_id_count}",
            )
        return [label for label, all_bounds in bounds_dict.items()]
    
    def is_valid_node(self, node):
        if not check_valid_bounds(node.attrib["bounds"]):
            return False

        # remove non-visible element
        parent = node.getparent()
        if parent is not None and 'bounds' in parent.attrib:
            if not check_bounds_containing(node.attrib['bounds'], parent.attrib['bounds']):
                return False
        return True

    def child_index(self, parent, node):
        # find the index of a given node in its sibling nodes
        for i, v in enumerate(list(parent)):
            if v == node:
                return i
        return -1

    def merge_attribute_in_one_line(self, node):
        node.attrib['description'] = ""
        # text description

        # function description in resource-id and class
        if node.attrib['class'] != "":
            if check_version_size(self.xml_version, 'v2'):
                node.attrib['description'] += node.attrib['class'] + ";"
            else:
                node.attrib['description'] += node.attrib['class'] + " "
        # if node.attrib['resource-id'] != "":
        #     node.attrib['description'] += node.attrib['resource-id'] + " "

        # action
        if check_version_size(self.xml_version, 'v2'):
            if node.attrib['action'] != "":
                if not check_version_size(self.xml_version, 'v3'):
                    node.attrib['description'] += ' '
                node.attrib['description'] += node.attrib['action']
            if not check_version_size(self.xml_version, 'v3'):
                node.attrib['description'] += ';'
        else:
            node.attrib['description'] += ';' + node.attrib['action'] + '; '

        # status
        if check_version_size(self.xml_version, 'v2'):
            if node.attrib['checkable'] == "true":
                if node.attrib['checked'] == "false":
                    node.attrib['description'] += ' unchecked'
                else:
                    node.attrib['description'] += ' checked'
            # extend status
            if node.attrib['password'] == "true":
                node.attrib['description'] += ' password'
            if node.attrib['selected'] == "true":
                node.attrib['description'] += ' selected'
            node.attrib['description'] += ';'
        else:
            for attrib in ['checked', 'password', 'selected']:
                if node.attrib[attrib] == "true":
                    node.attrib['description'] += attrib + ' '
            if node.attrib['checkable'] == "true" and node.attrib['checked'] == "false":
                node.attrib['description'] += 'unchecked '
                
            extend_status = ";"
            if node.attrib['password'] == "true":
                extend_status += ' you can input password, '
            if node.attrib['selected'] == "true":
                extend_status += ' selected, '
            node.attrib['description'] += extend_status

        # func-desc
        if check_version_size(self.xml_version, 'v2'):
            if node.attrib['func-desc'] != "":
                if not check_version_size(self.xml_version, 'v3'):
                    node.attrib['description'] += ' '
                node.attrib['description'] += node.attrib['func-desc']
        else:
            node.attrib['description'] += ";" + node.attrib['func-desc']
            node.attrib['description'] = node.attrib['description'].replace("\n", "")

        # bounds
        # node.attrib['description'] += " bounds: " + node.attrib['bounds']
        if self.ablation != 'v2':
            if check_version_size(self.xml_version, 'v2'):
                if not self.use_xml_id:
                    if check_version_size(self.xml_version, 'v4'):
                        bound_coords = bounds_to_coords(node.attrib['bounds'])
                        bounds_desc = f"[{bound_coords[0]},{bound_coords[1]},{bound_coords[2]},{bound_coords[3]}]"
                        node.attrib['description'] += ';' + bounds_desc
                    elif check_version_size(self.xml_version, 'v3'):
                        node.attrib['description'] += ';' + node.attrib['bounds']
                    else:
                        node.attrib['description'] += ';' + ' ' + node.attrib['bounds']
        else:
            if check_version_size(self.xml_version, 'v4'):
                bound_coords = bounds_to_coords(node.attrib['bounds'])
                bounds_desc = f"[{bound_coords[0]},{bound_coords[1]},{bound_coords[2]},{bound_coords[3]}]"
                node.attrib['bounds'] = bounds_desc
                    
            node.attrib['description'] = replace_string_between_angle_brackets(node.attrib['description'].replace("\n", ""))

        # clean attribute
        for attrib in ['index', 'text', 'resource-id', 'package', 'content-desc', 'enabled', 'focused',
                       'class', 'checkable', 'checked', 'clickable', 'focusable',
                       'scrollable', 'long-clickable', 'password',
                       'selected', 'func-desc', 'action']:
            del node.attrib[attrib]
        if self.ablation != 'v2':
            if check_version_size(self.xml_version, 'v2'):
                del node.attrib['bounds']
        if 'NAF' in node.attrib:
            del node.attrib['NAF']

    def get_xpath(self, node):
        if node.tag == 'hierarchy':
            return '/'
        else:
            if node.attrib['resource-id'] != "":
                transfer_resource_id = node.attrib['resource-id']
                my_path = f'//*[@resource-id=\'{transfer_resource_id}\']'
                try:
                    candi_nodes = self.root.xpath(my_path)
                except etree.XPathEvalError as e:
                    # traceback.print_exc()
                    # print(my_path)
                    return my_path
                if len(candi_nodes) == 1:
                    return my_path

            parent = node.getparent()
            children = parent.xpath(f'./*[@class="{node.attrib["class"]}"]')
            index = children.index(node) + 1
            return parent.attrib['xpath2'] + '/' + node.attrib['class'] + f'[{index}]'

    def get_attr_count(self, collection_key, key):
        if collection_key not in self.mapCount:
            return 0
        if key not in self.mapCount[collection_key]:
            return 0
        return self.mapCount[collection_key][key]

    def inc_attr_count(self, collection_key, key):

        if collection_key not in self.mapCount:
            self.mapCount[collection_key] = {key: 1}
        elif key not in self.mapCount[collection_key]:
            self.mapCount[collection_key][key] = 1
        else:
            self.mapCount[collection_key][key] += 1

    def get_xpath_new(self, node):
        array = []
        while node is not None:
            if node.tag != "node":
                break

            parent = node.getparent()
            if self.get_attr_count("tag", node.tag) == 1:
                array.append(f'*[@label="{node.tag}"]')
                break
            elif self.get_attr_count("resource-id", node.attrib["resource-id"]) == 1:
                array.append(f'*[@resource-id="{node.attrib["resource-id"]}"]')
                break
            elif self.get_attr_count("text", node.attrib["text"]) == 1:
                array.append(f'*[@text="{node.attrib["text"]}"]')
                break
            elif self.get_attr_count("content-desc", node.attrib["content-desc"]) == 1:
                array.append(f'*[@content-desc="{node.attrib["content-desc"]}"]')
                break
            elif self.get_attr_count("class", node.attrib["class"]) == 1:
                array.append(f'{node.attrib["class"]}')
                break
            elif parent is None:
                array.append(f'{node.tag}')
            else:
                index = 0
                children = list(parent)
                node_id = children.index(node)
                for _id, child in enumerate(children):
                    if child.attrib["class"] == node.attrib["class"]:
                        index += 1
                    if node_id == _id:
                        break
                array.append(f'{node.attrib["class"]}[{index}]')
            node = parent

        array.reverse()
        xpath = "//" + "/".join(array)
        return xpath

    def get_xpath_all_new(self, node):
        node.attrib['xpath1'] = self.get_xpath_new(node)
        node.attrib['xpath2'] = self.get_xpath(node)
        for child in list(node):
            self.get_xpath_all_new(child)
    
    def should_remove_node(self, node):
        # remove system ui elements, e.g, battery, wifi and notifications
        # if self.remove_system_bar and node.attrib['package'] == "com.android.systemui":
        #     return True
        
        #  remove invalid element
        if not self.call_api:
            if not self.is_valid_node(node):
                # if not (self.current_app == 'com.tencent.mm' and check_bounds_containing(node.attrib['bounds'], self.max_bounds)):
                #     return True
                return True
                
            # remove too small element
            bbox = bounds_to_coords(node.attrib['bounds'])
            maxbbox = bounds_to_coords(self.maxBounds)
            if (bbox[2] - bbox[0]) <= (maxbbox[2] - maxbbox[0]) * 0.005 or (bbox[3] - bbox[1]) <= (maxbbox[3] - maxbbox[1]) * 0.005:
                return True

        # don't remove functional element
        for p in ["checkable", "checked", "clickable", "focusable", "scrollable", "long-clickable", "password",
                  "selected"]:
            if node.attrib[p] == "true":
                return False

        # don't remove element with description
        for p in ['text', "content-desc"]:
            if node.attrib[p] != "":
                return False
        return True

    def mid_order_remove(self, node):
        def set_clickable(node, iter=True):
            if iter:
                for child in node.iter():
                    child.attrib['clickable'] = "true"
            else:
                for child in list(node):
                    child.attrib['clickable'] = "true"
        
        def get_node_text(node, path, field):
            try:
                for index in path:
                    node = list(node)[index]
                return node.attrib.get(field, None)
            except Exception:
                return None

        def handle_autonavi(node):
            if node.attrib['content-desc'] == "选择出发时间弹窗":
                set_clickable(node)
                return True
            elif node.attrib['text'] == "选择出发时间":
                parent = node.getparent().getparent()
                set_clickable(parent)
                return True
            elif get_node_text(node, [0, 0], "text") in ["公交地铁", "新能源", "驾车", "打车", "骑行", "步行", "代驾", "拼车", "飞机", "火车", "客车", "货车", "摩托车"] or \
                get_node_text(node, [0, 0, 1], "text") in ["公交地铁", "新能源", "驾车", "打车", "骑行", "步行", "代驾", "拼车", "飞机", "火车", "客车", "货车", "摩托车"]:
                set_clickable(node, False)
                return True
            return False

        def handle_tencent(node):
            if get_node_text(node, [0, 1, 0, 0], "text") == "发起群聊":
                set_clickable(node, False)
                return True
            elif get_node_text(node, [3, 1, 0, 0, 0, 0, 0], "text") == "查找聊天记录":
                set_clickable(node, False)
                return True
            # # add moment icon
            # elif get_node_text(node, [1], "resource-id") == "com.tencent.mm:id/r2":
            elif node.attrib['resource-id'] == "com.tencent.mm:id/n93":
                children = list(node)
                if len(children) > 1 and children[1].attrib['resource-id'] == "com.tencent.mm:id/r2":
                    child = children[1]
                    if child.attrib['class'] != "android.widget.ImageView":
                        child.attrib['class'] = "android.widget.ImageView"
                        node_coords = bounds_to_coords(node.attrib['bounds'])
                        child_coords = bounds_to_coords(child.attrib['bounds'])
                        child.attrib['bounds'] = coords_to_bounds([child_coords[0]] + node_coords[1:])
                        child.attrib['content-desc'] = ""
                        child.attrib['NAF'] = "true"
                        # child.attrib['text'] = '选项' 
                else:
                    pass
                    # 目前数据都有id/r2节点，若没有则要额外添加节点，要改此函数外的逻辑
                return False
            elif get_node_text(node, [1, 0 ,1], "text") and all(keyword in get_node_text(node, [1, 0 ,1], "text") for keyword in ["阅读", "赞"]):
                node.attrib['clickable'] = "true"
                return True
            elif node.attrib['class'].split('.')[-1] == "EditText":
                node_coords = bounds_to_coords(node.attrib['bounds'])
                parent_coords = bounds_to_coords(node.getparent().attrib['bounds'])
                if 0 < parent_coords[1] - node_coords[1] <= 8:
                    node_coords[1] = parent_coords[1]
                if 0 < node_coords[3] - parent_coords[3] <= 16:
                    node_coords[3] = parent_coords[3]
                node.attrib['bounds'] = coords_to_bounds(node_coords)
                return True
            return False

        def handle_meituan(node):
            if "EditText" in node.attrib['class']:
                node.attrib['clickable'] = "true"
                # node.attrib['click'] = True
                return True
            return False
        
        def handle_12306(node):
            if get_node_text(node, [0], "text") == "lX5f5unNNXjLGEYAAAAAElFTkSuQmCC":
                set_clickable(node, False)
                return True
            return False

        def handle_dzdp(node):
            if node.attrib['content-desc'] == "写评价打分控件":
                set_clickable(node, False)
                self.rate_element = True
                return True

            if not self.rate_element:
                if node.attrib['class'] == "android.widget.FrameLayout" and list(node)[0].attrib['text'] in ["总体", "口味", "环境", "服务", "食材", "性价比"]:
                    for idx, child in enumerate(node[1:6]):
                        child.attrib['clickable'] = "true"
                        child.attrib['text'] = ['半星/一星', '一星半或二星', '二星半/三星', '三星半/四星', '四星半/五星'][idx]
                        child.attrib['class'] = "TextView"
                    return True
            return False

        children = list(node)
        node.attrib['name'] = ""
        if node.tag == 'node':
            package = node.get("package", "")
            try:
                if package == "com.autonavi.minimap":
                    is_handle = handle_autonavi(node)
                elif package == "com.tencent.mm":
                    is_handle = handle_tencent(node)
                elif package == "com.sankuai.meituan":
                    is_handle = handle_meituan(node)
                elif package == "com.MobileTicket":
                    is_handle = handle_12306(node)
                elif package == "com.dianping.v1":
                    is_handle = handle_dzdp(node)
                else:
                    is_handle = False
                if is_handle:
                    if not self.is_valid_node(node):
                        node.getparent().remove(node)
                    return
            except:
                pass

            if self.should_remove_node(node):
                parent = node.getparent()
                index = self.child_index(parent, node)
                for i, v in enumerate(children):
                    parent.insert(index + i, v)
                parent.remove(node)

        for child in children:
            self.mid_order_remove(child)

    def preprocess_attribute(self, node):
        if node.tag == 'node':
            # pre-process attribute
            # content-desc text
            node.attrib['func-desc'] = ""
            node.attrib['action'] = ""

            # pre desc
            if node.attrib['text'] != "":
                if check_version_size(self.xml_version, 'v2'):
                    node.attrib['func-desc'] += node.attrib['text']
                else:
                    node.attrib['func-desc'] += node.attrib['text'] + ' '
            if node.attrib['content-desc'] != "":
                if check_version_size(self.xml_version, 'v2'):
                    node.attrib['func-desc'] += ' ' + node.attrib['content-desc']
                else:
                    node.attrib['func-desc'] += node.attrib['content-desc'] + ' '

            if "EditText" in node.attrib['class'] and node.attrib['focused'] == 'true':
                self.focused_edittext_nodes.append(copy.deepcopy(node))
                
            # pre name
            if node.attrib['class'] != "":
                if node.attrib['text'] != "":
                    node.attrib['name'] = get_words_in_certain_length(node.attrib['text']) + " " + \
                                        node.attrib['class'].split('.')[-1]
                elif node.attrib['content-desc'] != "":
                    node.attrib['name'] = get_words_in_certain_length(node.attrib['content-desc']) + " " + \
                                        node.attrib['class'].split('.')[-1]
                else:
                    node.attrib['name'] = node.attrib['class'].split('.')[-1]

            # pre class
            if node.attrib['class'] != "":
                if check_version_size(self.xml_version, 'v2'):
                    node.attrib['class'] = node.attrib['class'].split('.')[-1]
                else:
                    if node.attrib['class'].split('.')[-1] in ["View", "FrameLayout", "LinearLayout", "RelativeLayout"]:
                        node.attrib['class'] = ""
                    else:
                        node.attrib['class'] = node.attrib['class'].split('.')[-1]
            
            # pre resource-id
            if not check_version_size(self.xml_version, "v2"):
                if node.attrib['resource-id'] != "":
                    if ":id/" in node.attrib['resource-id']:
                        resrc = node.attrib['resource-id']
                        substring = resrc[resrc.index(":id/") + 4:]
                        node.attrib['resource-id'] = substring
                    else:
                        node.attrib['resource-id'] = ""

            # pre action
            for k, v in {'clickable': 'click', 'scrollable': 'scroll', 'long-clickable': 'long-click',
                        'checkable': 'check'}.items():
                if node.attrib[k] == "true":
                    node.attrib['action'] += v + ' '
            node.attrib['action'] = node.attrib['action'].strip()
            if node.attrib['action'] == "" and node.attrib['focusable'] == "true":
                node.attrib['action'] += "focusable"

            # for material_clock_face
            parent = node.getparent()
            if parent.tag == 'node' and "material_clock_face" in parent.attrib['resource-id']:
                node.attrib['action'] += ' click' 
        
        for child in list(node):
            self.preprocess_attribute(child)

    def get_all_bounds(self, node, parent_keys):
        parent_keys = copy.deepcopy(parent_keys)
        if 'bounds' in node.attrib:
            key = node.attrib['xpath1'] + "_" + node.attrib['xpath2']
            if parent_keys == []:
                self.all_bounds[key] = {'bounds': node.attrib['bounds'], 'children': {}}
            else:
                bounds_dict = self.all_bounds
                for parent_key in parent_keys:
                    bounds_dict = bounds_dict[parent_key]['children']
                bounds_dict[key] = {'bounds': node.attrib['bounds'], 'children': {}}
            parent_keys.append(key)

        for child in list(node):
            self.get_all_bounds(child, parent_keys)

    def dump_tree(self):
        xml_str = etree.tostring(self.root, encoding='unicode')
        print(xml_str)

    def mid_order_reindex(self, node):
        if node.tag == 'node':
            self.merge_attribute_in_one_line(node)
        
        if self.ablation != 'v2':
            if check_version_size(self.xml_version, 'v2'):
                node.tag = 'n' + node.attrib['id']
            else:
                node.tag = 'n' + str(uuid.uuid4().hex[:4])
        else:
            node.tag = 'n' + str(uuid.uuid4().hex[:4])

        if node.tag in self.node_to_xpath:
            self.node_to_xpath[node.tag].append(node.attrib['xpath1'])
            self.node_to_xpath[node.tag].append(node.attrib['xpath2'])
        else:
            self.node_to_xpath[node.tag] = [node.attrib['xpath1'], node.attrib['xpath2']]
        self.node_to_xpath[node.tag].append([])
        if node.getparent() is not None:
            parent = node.getparent()
            # check if has xpath
            if parent.tag in self.node_to_xpath:
                self.node_to_xpath[parent.tag][2].append(node.attrib['xpath1'])
                self.node_to_xpath[parent.tag][2].append(node.attrib['xpath2'])
            # add parent xpath to node
            if 'xpath1' in parent.attrib and 'xpath2' in parent.attrib:
                if parent.attrib['xpath1'] != "//" and parent.attrib['xpath2'] != "//":
                    if node.tag in self.node_to_xpath:
                        self.node_to_xpath[node.tag][2].append(parent.attrib['xpath1'])
                        self.node_to_xpath[node.tag][2].append(parent.attrib['xpath2'])
                    else:
                        self.node_to_xpath[node.tag][2] = [parent.attrib['xpath1'], parent.attrib['xpath2']]
            # add sibling node
            children = list(parent)
            for _id, child in enumerate(children):
                if 'xpath1' in child.attrib and 'xpath2' in child.attrib:
                    if node.tag in self.node_to_xpath:
                        self.node_to_xpath[node.tag][2].append(child.attrib['xpath1'])
                        self.node_to_xpath[node.tag][2].append(child.attrib['xpath2'])
                    else:
                        self.node_to_xpath[node.tag][2] = [child.attrib['xpath1'], child.attrib['xpath2']]

        self.node_to_name[node.tag] = node.attrib['name']

        self.cnt = self.cnt + 1
        
        children = list(node)
        for child in children:
            self.mid_order_reindex(child)
        
        del node.attrib['xpath1']
        del node.attrib['xpath2']
        del node.attrib['name']
        del node.attrib['id']
        if 'raw_bounds' in node.attrib:
            del node.attrib['raw_bounds']

    def merge_description(self, p_desc, c_desc):
        p_list = p_desc.replace(";", " ").replace(",", " ").replace(".", " ").split()
        c_list = c_desc.replace(";", " ").replace(",", " ").replace(".", " ").split(";")
        candi_str = p_desc
        for sub_str in c_list:
            for word in sub_str.split():
                if word not in p_list:
                    candi_str += " " + word

        return candi_str.replace(";", ". ")

    def can_merge_bounds(self, parent_bounds, child_bounds):
        # get bounds
        match_parent = re.findall(r'(\d+)', parent_bounds)
        match_child = re.findall(r'(\d+)', child_bounds)
        x_len_parent = int(match_parent[2]) - int(match_parent[0])
        y_len_parent = int(match_parent[3]) - int(match_parent[1])
        x_len_child = int(match_child[2]) - int(match_child[0])
        y_len_child = int(match_child[3]) - int(match_child[1])

        if y_len_child / y_len_parent > 0.8 and x_len_child / x_len_parent > 0.8:
            return True

        return False

    def mid_order_merge(self, node):
        children = list(node)
        # merge child conditions
        can_merge = False
        if node.tag == 'node' and node.attrib['action'] == "":
            can_merge = True
        if self.use_bounds and node.tag == 'node' and self.can_merge_bounds(node.attrib['bounds'], node.attrib['bounds']):
            can_merge = True
        if self.merge_switch and node.tag == 'node' and node.attrib['checked'] == "true":
            node.attrib['func-desc'] = ', it has a switch and the switch is currently on,'
            can_merge = True
        if self.merge_switch and node.tag == 'node' and node.attrib['checkable'] == "true" and node.attrib['checked'] == "false":
            node.attrib['func-desc'] = ', it has a switch and the switch is currently off,'
            can_merge = True

        if can_merge:
            # add child to parent
            parent = node.getparent()
            if parent.tag == 'node':
                index = self.child_index(parent, node)
                for i, v in enumerate(children):
                    parent.insert(index + i, v)
                # merge desc
                parent.attrib['func-desc'] = self.merge_description(parent.attrib['func-desc'],
                                                                    node.attrib['func-desc'])

                parent.remove(node)
        for child in children:
            self.mid_order_merge(child)

    def merge_none_act(self):
        self.mid_order_merge(self.root)

    def reindex(self, root):
        # self.cnt = 0
        self.mid_order_reindex(root)
    
    def add_nodes_id(self):
        root_nodes = list(self.root.iter())
        output_nodes = list(self.output_root.iter())
        for ind, (root_node, output_node) in enumerate(zip(root_nodes, output_nodes)):
            root_node.attrib['id'] = str(ind)
            output_node.attrib['id'] = str(ind)

    def special_check(self):
        self.page_type = ""
        try:
            current_app = list(self.root)[0].attrib['package']
        except Exception:
            return
        try:
            specialcheck = SpecialCheck[current_app](self.xml_string, self.root)
            self.page_type, check_type = specialcheck.check()
            # print(self.page_type, check_type)
            if check_type != 'remove':
                self.output_root = copy.deepcopy(self.root)
                self.add_nodes_id()
        except KeyError:
            pass
            # import traceback
            # traceback.print_exc()

    def merge_clickable_subtree(self, root):
        assert self.height is not None and self.width is not None
        
        def combine_texts(clickable_node):
            ch_clickable_nodes = []
            def traverse(node):
                text = node.attrib['func-desc']
                for child in node:
                    if child.attrib['clickable'] == 'true' or child.attrib['long-clickable'] == 'true' or child.attrib['scrollable'] == 'true':
                        ch_clickable_nodes.append(child)
                    else:
                        child_text = traverse(child)
                        if child_text != "":
                            text += '|' + child_text
                return text

            func_desc = traverse(clickable_node)
            if func_desc != '' and func_desc[0] == '|':
                func_desc = func_desc[1:]
            clickable_node.attrib['func-desc'] = func_desc
            
            for ch in clickable_node:
                clickable_node.remove(ch)
            for node in ch_clickable_nodes:
                clickable_node.append(node)

        clickable_nodes = root.xpath('//*[@clickable="true"]')
        clickable_nodes.extend(root.xpath('//*[@long-clickable="true"]'))
        clickable_nodes = [node for node in clickable_nodes if get_bounds_area(node.get('raw_bounds')) <= 0.5 * self.height * self.width]
        
        for node in clickable_nodes:
            combine_texts(node)
        return root

    def remove_redundant_huge_node(self, node, parents):
        if node.tag == 'node':
            not_delete = False
            if len(list(node)) > 1:
                not_delete = True

            for p in ["checkable", "checked", "scrollable", "long-clickable", "password", "selected"]:
                if node.attrib[p] == "true":
                    not_delete = True
                    break

            for p in ['text', "content-desc"]:
                if node.attrib[p] != "":
                    not_delete = True
                    break

            if not_delete:
                new_parents = []
                for parent, p_not_delete in parents[:-1]:
                    if not p_not_delete and 'removed' not in parent.attrib:
                        grandp = parent.getparent()
                        index = self.child_index(grandp, node)
                        for i, v in enumerate(parent):
                            grandp.insert(index + i, v)
                        grandp.remove(parent)
                        parent.attrib['removed'] = 'True'
                    elif not p_not_delete:
                        new_parents.append((parent, True))
                parents = new_parents + [parents[-1]]
                
            for child in node:
                self.remove_redundant_huge_node(
                    child,
                    parents+[(node, not_delete)]
                )
        else:
            for child in node:
                self.remove_redundant_huge_node(
                    child,
                    parents+[(node, True)]
                )
    
    def scale_bound_both_side(self, root, max_limit=999):
        assert self.height is not None and self.width is not None
        
        def check_is_matchable(node):
            if node.attrib['clickable'] == 'true' or node.attrib['long-clickable'] == 'true':
                if get_bounds_area(node.get('raw_bounds')) <= 0.5 * self.height * self.width:
                    return True
            elif node.attrib['scrollable'] == 'true':
                return True
            return False
        
        scale_factor_width = max_limit / self.width
        scale_factor_height = max_limit / self.height
        
        map_for_scaling = {'scaled2raw': {}, 'raw2scaled': {}}
        is_matchable_nodes = {}
        for node in root.iter():
            if 'bounds' not in node.attrib:
                continue
            bound = bounds_to_coords(node.attrib['bounds'])
            x1, y1, x2, y2 = bound
            
            if check_version_size(self.xml_version, 'v4.1'):
                scaled_x1 = round(x1 / self.width, 3) if x1 not in [0, self.width] else x1 // self.width
                scaled_y1 = round(y1 / self.height, 3) if y1 not in [0, self.height] else y1 // self.height 
                scaled_x2 = round(x2 / self.width, 3) if x2 not in [0, self.width] else x2 // self.width
                scaled_y2 = round(y2 / self.height, 3) if y2 not in [0, self.height] else y2 // self.height
            else:
                scaled_x1 = int(x1 * scale_factor_width)
                scaled_y1 = int(y1 * scale_factor_height)
                scaled_x2 = int(x2 * scale_factor_width)
                scaled_y2 = int(y2 * scale_factor_height)
            scaled_bounds = coords_to_bounds([scaled_x1, scaled_y1, scaled_x2, scaled_y2])
            scaled_bbox = f"[{scaled_x1},{scaled_y1},{scaled_x2},{scaled_y2}]"
            
            if scaled_bbox in map_for_scaling['scaled2raw'] and map_for_scaling['scaled2raw'][scaled_bbox] != node.attrib['bounds']:
                exist_bound = bounds_to_coords(map_for_scaling['scaled2raw'][scaled_bbox])
                new_bound = bounds_to_coords(node.attrib['bounds'])
                for a, b in zip(exist_bound, new_bound):
                    difference = abs(a - b)
                    if difference > 3:
                        warning = f"Warning: {scaled_bbox} already exists in map_for_scaling, original bound: {node.attrib['bounds']}, existing bound: {map_for_scaling['scaled2raw'][scaled_bbox]}"
                        # print(warning)
                        # write_jsonl([warning], 'xml_v4_warning.txt', append=True)
                        break
            
            if scaled_bbox in map_for_scaling['scaled2raw']:
                if check_is_matchable(node):
                    if is_matchable_nodes[map_for_scaling['scaled2raw'][scaled_bbox]] and node.attrib['bounds'] != map_for_scaling['scaled2raw'][scaled_bbox]:
                        if get_bounds_area(node.get('raw_bounds')) > get_bounds_area(map_for_scaling['scaled2raw'][scaled_bbox]):
                            continue
                        # warning = f"Warning: {scaled_bbox} already exists in is_matchable_nodes, original bound: {node.attrib['bounds']}, existing bound: {map_for_scaling['scaled2raw'][scaled_bbox]}"
                        # # print(warning, get_bounds_area(node.get('raw_bounds')), 0.5 * self.height * self.width)
                        # # raise Exception(warning)
                        # write_jsonl([warning], 'xml_v4_matchable_warning.txt', append=True)
                        # break  
                else:
                    continue
                
            is_matchable_nodes[node.attrib['bounds']] = check_is_matchable(node)
            map_for_scaling['scaled2raw'][scaled_bbox] = node.attrib['bounds']
            map_for_scaling['raw2scaled'][node.attrib['bounds']] = scaled_bbox
            node.attrib['bounds'] = scaled_bounds
        return root, map_for_scaling
    
    def xml_sparse(self):
        # get all attribute count
        self.mapCount = {}
        self.maxBounds = "[0,0][0,0]"
        self.maxArea = 0
        self.rate_element = False
        for element in self.root.iter():
            self.inc_attr_count("tag", element.tag)
            if element.tag != "node":
                continue
            self.inc_attr_count("resource-id", element.attrib["resource-id"])
            self.inc_attr_count("text", element.attrib["text"])
            self.inc_attr_count("class", element.attrib["class"])
            self.inc_attr_count("content-desc", element.attrib["content-desc"])

            area = get_bounds_area(element.attrib['bounds'])
            if area > self.maxArea:
                self.maxArea = area
                self.maxBounds = element.attrib['bounds']

        # self.get_xpath_all(self.root)
        self.get_xpath_all_new(self.root)
        self.mid_order_remove(self.root)
        
        self.output_root = copy.deepcopy(self.root)
        self.add_nodes_id()
        if not self.call_api and self.check_special:
            self.special_check()
        elif self.call_api:
            self.page_type = None

        if self.use_ocr:
            # self.ocr_labels = None
            self.ocr_tool = XML_OCR_Matcher(print_intermediates=False)
            self.ocr_labels = self.add_ocr_nodes()
        
        for node in self.root.iter():
            if 'bounds' in node.attrib:
                node.attrib['raw_bounds'] = node.attrib['bounds']
        for node in self.output_root.iter():
            if 'bounds' in node.attrib:
                node.attrib['raw_bounds'] = node.attrib['bounds']
        
        self.preprocess_attribute(self.root)
        self.preprocess_attribute(self.output_root)
        
        if self.ablation != 'v3':
            if check_version_size(self.xml_version, 'v3'):
                self.root = self.merge_clickable_subtree(self.root)
                self.output_root = self.merge_clickable_subtree(self.output_root)

                self.remove_redundant_huge_node(self.root, [])
                self.remove_redundant_huge_node(self.output_root, [])
        
        if check_version_size(self.xml_version, 'v4'):
            scale_func = self.scale_bound_both_side
            self.root, self.scaling_map = scale_func(self.root, max_limit=999)
            self.output_root, self.output_scaling_map = scale_func(self.output_root, max_limit=999)
        
        mid_id_map = {}
        self.output_root_id2bounds = {}
        for ind, node in enumerate(list(self.output_root.iter())):
            mid_id_map[node.attrib['id']] = str(ind)
            node.attrib['id'] = str(ind)
            if 'bounds' in node.attrib:
                self.output_root_id2bounds[node.attrib['id']] = node.attrib['raw_bounds']
                
        self.root_id2bounds = {}
        for node in self.root.iter():
            try:
                node.attrib['id'] = mid_id_map[node.attrib['id']]
            except KeyError:
                node.attrib['id'] = f"nf{uuid.uuid4().hex[:4]}"
            if 'bounds' in node.attrib:
                self.root_id2bounds[node.attrib['id']] = node.attrib['raw_bounds']

    def dump_xpath(self):
        json_data = json.dumps(self.node_to_xpath, indent=4, ensure_ascii=False)
        print(json_data)

    def dump_name(self):
        json_data = json.dumps(self.node_to_name, indent=4, ensure_ascii=False)
        print(json_data)

    def get_recycle_nodes(self, root):
        node_list = []
        for element in root.iter():
            if 'scrollable' in element.attrib and element.attrib['scrollable'] == 'true':
                node_list.append(element)
                print(element.attrib['class'], element.attrib['resource-id'], element.attrib['func-desc'])
        return node_list

    def same_subtree(self, tree1, tree2):
        if tree1.attrib['class'] != tree2.attrib['class'] or \
           tree1.attrib['resource-id'] != tree2.attrib['resource-id'] or \
           tree1.attrib['func-desc'] != tree2.attrib['func-desc']:
            return False
        children1 = list(tree1)
        children2 = list(tree2)
        if len(children1) != len(children2):
            return False
        for i in range(len(children1)):
            if not self.same_subtree(children1[i], children2[i]):
                return False
        return True

    def check_unique(self, node, node_list):
        for element in node_list:
            if self.same_subtree(node, element):
                return False
        return True

    def merge_recycle_list(self, recycle_nodes):
        for element in self.root.iter():
            if 'scrollable' in element.attrib and element.attrib['scrollable'] == 'true':
                # find same recycle node
                for node in recycle_nodes:
                    if element.attrib['class'] == node.attrib['class'] and \
                       element.attrib['resource-id'] == node.attrib['resource-id'] and \
                       element.attrib['func-desc'] == node.attrib['func-desc']:
                        # merge
                        for child in list(node):
                            if self.check_unique(child, list(element)):
                                element.append(child)

    def check_scroll_bottom(self, tree1, tree2):
        child1 = list(tree1)
        child2 = list(tree2)
        for i in range(len(child1)):
            if not self.same_subtree(child1[i], child2[i]):
                return False
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--xml_path', type=str, required=True, help='Path of xml that will be parsed')
    parser.add_argument('--xml_version', type=str, default='v2', help='Version of xml')
    parser.add_argument('--call_api', action='store_true', help='whether to call api')
    parser.add_argument('--use_ocr', action='store_true', help='whether to use ocr')
    parser.add_argument('--use_xml_id', action='store_true', help='whether to use xml id')
    parser.add_argument('--image_path', type=str, default=None, help='Path of image, only used when use_ocr is true')
    parser.add_argument('--width', type=int, default=None, help='Width of image, only used when use_ocr is true')
    parser.add_argument('--height', type=int, default=None, help='Height of image, only used when use_ocr is true')
    parser.add_argument('--output_path', type=str, required=True, help='Path of output')
    args = parser.parse_args()
    
    def save_json(obj, path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    
    compressed_xml, id2bounds, scaling_map, error_log, ocr_labels = get_compressed_xml(xml_path=args.xml_path, 
                                                                                       xml_version=args.xml_version, 
                                                                                       width=args.width,
                                                                                       height=args.height,
                                                                                       call_api=args.call_api, 
                                                                                       use_ocr=args.use_ocr, 
                                                                                       image_path=args.image_path, 
                                                                                       use_xml_id=args.use_xml_id)
    if compressed_xml is None:
        save_json({
            "status": "error",
            "response": error_log,
            "id2bounds": None,
            "scaling_map": None,
            "ocr_labels": None,
        }, args.output_path)
    else:
        save_json({
            "status": "success",
            "response": compressed_xml,
            "id2bounds": id2bounds,
            "scaling_map": scaling_map,
            "ocr_labels": ocr_labels,
        }, args.output_path)