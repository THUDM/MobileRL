import json
import os

import jsonlines

from android_lab.utils_mobile.utils import draw_bbox_multi
from android_lab.utils_mobile.xml_tool import UIXMLTree
from android_lab.utils_mobile.xml_tool_v2 import UIXMLTree as UIXMLTree_v2
from android_lab.templates.packages import package_dict_en
# from utils_mobile.xml_tool_v2 import UIXMLTree


def get_compressed_xml(xml_path, type="plain_text", version="v1", use_ocr=False, image_path=None, width=None, height=None, xml_parser=None):
    assert version in ["v1", "v2"] or (version in ["v3", "v4", "v4.1", "v5"] and width is not None and height is not None)
    assert use_ocr is False or (use_ocr is True and image_path is not None)
    
    if xml_parser is None:
        xml_parser = UIXMLTree(xml_version=version)
        
    with open(xml_path, 'r', encoding='utf-8') as f:
        xml_str = f.read()
    try:
        compressed_xml, output_root, processed_root, id2bounds, scaling_map = xml_parser.process(xml_str, 
                                                                                                 level=1, 
                                                                                                 str_type=type,
                                                                                                 call_api=False, 
                                                                                                 use_xml_id=False, 
                                                                                                 use_ocr=use_ocr, 
                                                                                                 image_path=image_path, 
                                                                                                 check_special=True,
                                                                                                 width=width,
                                                                                                 height=height)
        if type == "plain_text":
            compressed_xml = compressed_xml.strip()
    except Exception as e:
        import traceback
        print(f"XML compressed failure: {e}, xml_path: {xml_path}")
        traceback.print_exc()
        compressed_xml = None
        output_root = None
        scaling_map = None
        
    return compressed_xml, output_root, scaling_map

def get_compressed_xml_v2(xml_path, type="plain_text", version="v2", **kwargs):
    assert version in ["v1", "v2"]
    if version=="v2":
        xml_parser = UIXMLTree_v2()
        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_str = f.read()
        try:
            compressed_xml = xml_parser.process(xml_str, level=1, str_type=type)
            if isinstance(compressed_xml, tuple):
                compressed_xml = compressed_xml[0]

            if type == "plain_text":
                compressed_xml = compressed_xml.strip()
        except Exception as e:
            compressed_xml = None
            print(f"XML compressed failure: {e}")
    return compressed_xml

def get_tap_desc(xml_parser, output_root, bound, scaling_map):
    if output_root is None:
        return ""
    if scaling_map is None:
        raw_bound = f"[{bound[0]},{bound[1]}][{bound[2]},{bound[3]}]"
    else:
        bound_str = f"[{bound[0]},{bound[1]},{bound[2]},{bound[3]}]"
        raw_bound = scaling_map['scaled2raw'][bound_str]
    
    matched_nodes = []
    for node in output_root.iter():
        if 'raw_bounds' not in node.attrib:
            continue
        if node.attrib['raw_bounds'] == raw_bound:
            matched_nodes.append(node)
            
    if len(matched_nodes) == 0:
        return ""
    elif len(matched_nodes) == 1:
        return xml_parser.root_to_compressed_xml(matched_nodes[0], "plain_text")
    else:
        for node in matched_nodes:
            if node.attrib['clickable'] == "true" or node.attrib['long-clickable'] == "true":
                return xml_parser.root_to_compressed_xml(node, "plain_text")


class JSONRecorder:
    def __init__(self, id, instruction, page_executor, config):
        self.id = id
        self.instruction = instruction
        self.page_executor = page_executor

        self.turn_number = 0
        trace_dir = os.path.join(config.task_dir, 'traces')
        xml_dir = os.path.join(config.task_dir, 'xml')
        log_dir = config.task_dir
        if not os.path.exists(trace_dir):
            os.makedirs(trace_dir)
        if not os.path.exists(xml_dir):
            os.makedirs(xml_dir)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        self.trace_file_path = os.path.join(trace_dir, 'trace.jsonl')
        self.xml_file_path = os.path.join(xml_dir)
        self.log_dir = log_dir
        self.contents = []
        self.xml_history = []
        self.history = []
        self.command_per_step = []
        if config.version is None:
            self.xml_compressed_version = "v1"
        else:
            self.xml_compressed_version = config.version
        if config.version is None:
            self.xml_parser = UIXMLTree(xml_version="v1", ablation=config.ablation)
        else:
            self.xml_parser = UIXMLTree(xml_version=config.version, ablation=config.ablation)
        self.ablation = config.ablation
        self.use_ocr = config.use_ocr
        self.tap_desc = config.tap_desc
        self.output_root = None
        self.scaling_map = None

    def update_response_deprecated(self, controller, response=None, prompt="** screenshot **", need_screenshot=False,
                                   ac_status=False):
        if need_screenshot:
            self.page_executor.update_screenshot(prefix=str(self.turn_number), suffix="before")
        xml_path = None
        ac_xml_path = None

        if not ac_status:
            xml_status = controller.get_xml(prefix=str(self.turn_number), save_dir=self.xml_file_path)
            if "ERROR" in xml_status:
                xml_path = "ERROR"
            else:
                xml_path = os.path.join(self.xml_file_path, str(self.turn_number) + '.xml')
        else:
            xml_status = controller.get_ac_xml(prefix=str(self.turn_number), save_dir=self.xml_file_path)
            if "ERROR" in xml_status:
                ac_xml_path = "ERROR"
            else:
                ac_xml_path = os.path.join(self.xml_file_path, 'ac_' + str(self.turn_number) + '.xml')
        step = {
            "trace_id": self.id,
            "index": self.turn_number,
            "prompt": prompt if self.turn_number > 0 else f"{self.instruction}",
            "image": self.page_executor.current_screenshot,
            "xml": xml_path,
            "ac_xml": ac_xml_path,
            "response": response,
            # "url": map_url_to_real(page.url),
            "window": controller.viewport_size,
            "target": self.instruction,
            "current_activity": controller.get_current_activity()
        }
        step = self.test_per_step(step, controller)
        self.contents.append(step)

        return xml_status

    def test_per_step(self, step, controller):
        if len(self.command_per_step) == 0 or self.command_per_step[0] is None:
            return step
        step["command"] = {}
        for command in self.command_per_step:
            if "adb" not in command:
                continue
            result = controller.run_command(command)
            step["command"][command] = result
        return step

    def update_before(self, controller, prompt="** XML **", need_screenshot=False, ac_status=False, need_labeled=False):
        if need_screenshot:
            self.page_executor.update_screenshot(prefix=str(self.turn_number), suffix="before")
        xml_path = None
        ac_xml_path = None

        if not ac_status:
            xml_status = controller.get_xml(prefix=str(self.turn_number), save_dir=self.xml_file_path)
            if "ERROR" in xml_status:
                xml_path = "ERROR"
            else:
                xml_path = os.path.join(self.xml_file_path, str(self.turn_number) + '.xml')
        else:
            xml_status = controller.get_ac_xml(prefix=str(self.turn_number), save_dir=self.xml_file_path)
            if "ERROR" in xml_status:
                ac_xml_path = "ERROR"
            else:
                ac_xml_path = os.path.join(self.xml_file_path, str(self.turn_number) + '.xml')

        step = {
            "trace_id": self.id,
            "index": self.turn_number,
            "prompt": prompt if self.turn_number > 0 else f"{self.instruction}",
            "image": self.page_executor.current_screenshot,
            "xml": xml_path,
            "ac_xml": ac_xml_path,
            "current_activity": controller.get_current_activity(),
            "window": controller.viewport_size,
            "target": self.instruction
        }
        step = self.test_per_step(step, controller)
        if need_labeled:
            try:
                if xml_path != "ERROR" and xml_path is not None:
                    self.page_executor.set_elem_list(xml_path)
                else:
                    self.page_executor.set_elem_list(ac_xml_path)
            except:
                print("xml_path:", xml_path)
                print("ac_xml_path:", ac_xml_path)
                import traceback
                print(traceback.print_exc())
            draw_bbox_multi(self.page_executor.current_screenshot,
                            self.page_executor.current_screenshot.replace(".png", "_labeled.png"),
                            self.page_executor.elem_list)
            self.labeled_current_screenshot_path = self.page_executor.current_screenshot.replace(".png", "_labeled.png")
            step["labeled_image"] = self.labeled_current_screenshot_path

        self.contents.append(step)

    def dectect_auto_stop(self):
        if len(self.contents) <= 5:
            return
        should_stop = True
        parsed_action = self.contents[-1]['parsed_action']
        for i in range(1, 6):
            if "parsed_action" not in self.contents[-i]:
                break
            if self.contents[-i]['parsed_action'] != parsed_action:
                should_stop = False
                break
        if should_stop:
            self.page_executor.is_finish = True
    
    def get_current_activity(self):
        return self.xml_parser.get_current_app()

    def get_latest_xml(self, controller=None):
        if len(self.contents) == 0:
            return None
        # print(self.contents[-1])
        if self.contents[-1]['xml'] == "ERROR" or self.contents[-1]['xml'] is None:
            xml_path = self.contents[-1]['ac_xml']
        else:
            xml_path = self.contents[-1]['xml']
        
        if self.xml_compressed_version in ["v1", "v2"]:
            xml_compressed = get_compressed_xml_v2(xml_path, version=self.xml_compressed_version)
        else:
            if controller is not None:
                width = controller.viewport_size[0]
                height = controller.viewport_size[1]
            else:
                width = None
                height = None
           
            xml_compressed, output_root, scaling_map = get_compressed_xml(xml_path=xml_path, 
                                                                        version=self.xml_compressed_version,
                                                                        image_path=self.page_executor.current_screenshot,
                                                                        width=width,
                                                                        height=height,
                                                                        use_ocr=self.use_ocr,
                                                                        xml_parser=self.xml_parser)
            self.output_root = output_root
            self.scaling_map = scaling_map
        
        
        with open(os.path.join(self.xml_file_path, f"{self.turn_number}_compressed_xml.txt"), 'w',
                  encoding='utf-8') as f:
            f.write(xml_compressed)
        self.page_executor.latest_xml = xml_compressed
        return xml_compressed

    def get_latest_xml_tree(self):
        if len(self.contents) == 0:
            return None
        print(self.contents[-1])
        if self.contents[-1]['xml'] == "ERROR" or self.contents[-1]['xml'] is None:
            xml_path = self.contents[-1]['ac_xml']
        else:
            xml_path = self.contents[-1]['xml']
        xml_compressed = get_compressed_xml(xml_path, type="seeact-json")
        return json.loads(xml_compressed)

    def update_execution(self, exe_res):
        if len(self.contents) == 0:
            return
        self.contents[-1]['parsed_action'] = exe_res
        with jsonlines.open(self.trace_file_path, 'a') as f:
            f.write(self.contents[-1])

    def update_error(self, error_message, rsp, format_prompt=None, prompt="** XML **"):
        if len(self.contents) == 0:
            return
        self.contents[-1]['error_message'] = error_message
        if rsp is None:
            self.contents[-1]["current_response"] = "Error in response. no response."
            return

        self.history.append({"role": "user", "content": prompt})

        if self.xml_compressed_version in ["v1", "v2"]:
            self.history.append({"role": "assistant", "content": rsp})
            self.contents[-1]["current_response"] = rsp  
        else:
            self.history.append({"role": "assistant", "content": rsp, "current_app": package_dict_en[self.get_current_activity()]})
            self.contents[-1]["current_app"] = package_dict_en[self.get_current_activity()]
            self.contents[-1]["current_response"] = rsp
            
        with jsonlines.open(self.trace_file_path, 'a') as f:
            f.write(self.contents[-1])
        if format_prompt is not None:
            if isinstance(format_prompt, list):
                format_prompt.append({"role": "assistant", "content": rsp})
                format_prompt = json.dumps(format_prompt, ensure_ascii=False, indent=4)
            else:
                format_prompt = format_prompt + rsp
            
            with open(os.path.join(self.xml_file_path, f"{self.turn_number}_format_prompt.txt"), 'w',
                  encoding='utf-8') as f:
                f.write(format_prompt + rsp)
        if self.scaling_map is not None:
            with open(os.path.join(self.xml_file_path, f"{self.turn_number}_scaling_map.txt"), 'w',
                  encoding='utf-8') as f:
                f.write(json.dumps(self.scaling_map, indent=4, ensure_ascii=False))
        self.dectect_auto_stop()

    def update_after(self, exe_res, rsp, format_prompt=None, prompt="** XML **"):
        if len(self.contents) == 0:
            return
        self.contents[-1]['parsed_action'] = exe_res
        self.history.append({"role": "user", "content": prompt})
        if exe_res["action"] == "Call_API":
            call_instruction = exe_res["kwargs"]["instruction"]
            call_response = exe_res["kwargs"]["response"]
            rsp = rsp + f"\n\nQuery:{call_instruction}\nResponse:{call_response}"
        if self.tap_desc:
            try:
                if exe_res["action"] == "Tap" or exe_res["action"] == "Long Press":
                    bound = exe_res["kwargs"]["element"]
                    tap_desc = get_tap_desc(self.xml_parser, self.output_root, bound, self.scaling_map)
                    rsp = f"Tap:{tap_desc}" + rsp
            except:
                import traceback
                traceback.print_exc()
                with open(os.path.join(self.xml_file_path, f"{self.turn_number}_error.txt"), 'w',
                  encoding='utf-8') as f:
                    f.write(traceback.format_exc())

        if self.xml_compressed_version in ["v1", "v2"]:
            self.history.append({"role": "assistant", "content": rsp})
            self.contents[-1]["current_response"] = rsp  
        else:
            self.history.append({"role": "assistant", "content": rsp, "current_app": package_dict_en[self.get_current_activity()]})
            self.contents[-1]["current_app"] = package_dict_en[self.get_current_activity()]
            self.contents[-1]["current_response"] = rsp
            
        with jsonlines.open(self.trace_file_path, 'a') as f:
            f.write(self.contents[-1])
        if format_prompt is not None:
            if isinstance(format_prompt, list):
                format_prompt.append({"role": "assistant", "content": rsp})
                format_prompt = json.dumps(format_prompt, ensure_ascii=False, indent=4)
            else:
                format_prompt = format_prompt + rsp
            
            with open(os.path.join(self.xml_file_path, f"{self.turn_number}_format_prompt.txt"), 'w',
                  encoding='utf-8') as f:
                f.write(format_prompt + rsp)
        if self.scaling_map is not None:
            with open(os.path.join(self.xml_file_path, f"{self.turn_number}_scaling_map.txt"), 'w',
                  encoding='utf-8') as f:
                f.write(json.dumps(self.scaling_map, indent=4, ensure_ascii=False))
        self.dectect_auto_stop()

    def get_round_count(self):
        return self.turn_number

    def get_latest_parsed_action(self):
        return self.contents[-1]['parsed_action']