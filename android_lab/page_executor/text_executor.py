import inspect
import json
import re
import time
from functools import partial

from android_lab.templates.packages import find_package
from .utils import call_dino, plot_bbox


def remove_leading_zeros_in_string(s):
    # 使用正则表达式匹配列表中的每个数值并去除前导零
    return re.sub(r'\b0+(\d)', r'\1', s)


class TextOnlyExecutor:
    def __init__(self, controller, config):
        self.config = config
        self.controller = controller
        self.device = controller.device
        self.screenshot_dir = config.screenshot_dir
        self.task_id = int(time.time())

        self.new_page_captured = False
        self.current_screenshot = None
        self.current_return = None

        self.last_turn_element = None
        self.last_turn_element_tagname = None
        self.is_finish = False
        self.device_pixel_ratio = None
        self.latest_xml = None
        # self.glm4_key = config.glm4_key

        # self.device_pixel_ratio = self.page.evaluate("window.devicePixelRatio")

    def __get_current_status__(self):
        page_position = None
        scroll_height = None
        status = {
            "Current URL": self.controller.get_current_activity(),
        }
        return json.dumps(status, ensure_ascii=False)

    def modify_relative_bbox(self, relative_bbox):
        viewport_width, viewport_height = self.controller.viewport_size
        modify_x1 = relative_bbox[0] * viewport_width / 1000
        modify_y1 = relative_bbox[1] * viewport_height / 1000
        modify_x2 = relative_bbox[2] * viewport_width / 1000
        modify_y2 = relative_bbox[3] * viewport_height / 1000
        return [modify_x1, modify_y1, modify_x2, modify_y2]

    def __call__(self, code_snippet):
        '''
        self.new_page_captured = False
        self.controller.on("page", self.__capture_new_page__)
        self.current_return = None'''

        local_context = self.__get_class_methods__()
        local_context.update(**{'self': self})
        print(code_snippet.strip())
        if len(code_snippet.split("\n")) > 1:
            for code in code_snippet.split("\n"):
                if "Action: " in code:
                    code_snippet = code
                    break
        if "do(action=\"Tap\"" in code_snippet or "do(action=\"Swipe\"" in code_snippet or "do(action=\"Long Press\"" in code_snippet:
            code = remove_leading_zeros_in_string(code_snippet.strip())
        else:
            code = code_snippet.strip()
        exec(code, {}, local_context)
        return self.current_return

    def __get_class_methods__(self, include_dunder=False, exclude_inherited=True):
        """
        Returns a dictionary of {method_name: method_object} for all methods in the given class.

        Parameters:
        - cls: The class object to inspect.
        - include_dunder (bool): Whether to include dunder (double underscore) methods.
        - exclude_inherited (bool): Whether to exclude methods inherited from parent classes.
        """
        methods_dict = {}
        cls = self.__class__
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if exclude_inherited and method.__qualname__.split('.')[0] != cls.__name__:
                continue
            if not include_dunder and name.startswith('__'):
                continue
            methods_dict[name] = partial(method, self)
        return methods_dict

    def update_screenshot(self, prefix=None, suffix=None):
        # time.sleep(2)
        if prefix is None and suffix is None:
            self.current_screenshot = f"{self.screenshot_dir}/screenshot-{time.time()}.png"
        elif prefix is not None and suffix is None:
            self.current_screenshot = f"{self.screenshot_dir}/screenshot-{prefix}-{time.time()}.png"
        elif prefix is None and suffix is not None:
            self.current_screenshot = f"{self.screenshot_dir}/screenshot-{time.time()}-{suffix}.png"
        else:
            self.current_screenshot = f"{self.screenshot_dir}/screenshot-{prefix}-{time.time()}-{suffix}.png"
        self.controller.save_screenshot(self.current_screenshot)

    def do(self, action=None, element=None, **kwargs):
        assert action in ["Tap", "Type", "Swipe", "Enter", "Home", "Back", "Long Press", "Wait", "Launch",
                          "Call_API", "Press Back"], "Unsupported Action"
        if self.config.is_relative_bbox:
            if element is not None:
                element = self.modify_relative_bbox(element)
        if action == "Tap":
            self.tap(element)
        elif action == "Type":
            self.type(**kwargs)
        elif action == "Swipe":
            self.swipe(element, **kwargs)
        elif action == "Enter":
            self.press_enter()
        elif action == "Home":
            self.press_home()
        elif action == "Back" or action == "Press Back":
            self.press_back()
        elif action == "Long Press":
            self.long_press(element)
        elif action == "Wait":
            self.wait()
        elif action == "Launch":
            self.launch(**kwargs)
        elif action == "Call_API":
            self.call_api(**kwargs)
        else:
            raise NotImplementedError()
        # self.__update_screenshot__() # update screenshot 全部移到recoder内

    def get_relative_bbox_center(self, instruction, screenshot):
        # 获取相对 bbox
        relative_bbox = call_dino(instruction, screenshot)

        viewport_width, viewport_height = self.controller.get_device_size()

        center_x = (relative_bbox[0] + relative_bbox[2]) / 2 * viewport_width / 1000
        center_y = (relative_bbox[1] + relative_bbox[3]) / 2 * viewport_height / 1000
        width_x = (relative_bbox[2] - relative_bbox[0]) * viewport_width / 1000
        height_y = (relative_bbox[3] - relative_bbox[1]) * viewport_height / 1000

        # 点击计算出的中心点坐标
        # print(center_x, center_y)
        plot_bbox([int(center_x - width_x / 2), int(center_y - height_y / 2), int(width_x), int(height_y)], screenshot,
                  instruction)

        return (int(center_x), int(center_y)), relative_bbox

    def tap(self, element):
        if isinstance(element, list) and len(element) == 4:
            center_x = (element[0] + element[2]) / 2
            center_y = (element[1] + element[3]) / 2
        elif isinstance(element, list) and len(element) == 2:
            center_x, center_y = element
        else:
            raise ValueError("Invalid element format")
        self.controller.tap(center_x, center_y)
        self.current_return = {"operation": "do", "action": 'Tap', "kwargs": {"element": element}}

    def long_press(self, element):
        if isinstance(element, list) and len(element) == 4:
            center_x = (element[0] + element[2]) / 2
            center_y = (element[1] + element[3]) / 2
        elif isinstance(element, list) and len(element) == 2:
            center_x, center_y = element
        else:
            raise ValueError("Invalid element format")
        self.controller.long_press(center_x, center_y)
        self.current_return = {"operation": "do", "action": 'Long Press', "kwargs": {"element": element}}

    def swipe(self, element=None, **kwargs):
        if element is None:
            center_x, center_y = self.controller.width // 2, self.controller.height // 2
        elif element is not None:
            if isinstance(element, list) and len(element) == 4:
                center_x = (element[0] + element[2]) / 2
                center_y = (element[1] + element[3]) / 2
            elif isinstance(element, list) and len(element) == 2:
                center_x, center_y = element
            else:
                raise ValueError("Invalid element format")
        assert "direction" in kwargs, "direction is required for swipe"
        direction = kwargs.get("direction")
        dist = kwargs.get("dist", "medium")
        self.controller.swipe(center_x, center_y, direction, dist)
        self.current_return = {"operation": "do", "action": 'Swipe',
                               "kwargs": {"element": element, "direction": direction, "dist": dist}}
        time.sleep(1)

    def type(self, **kwargs):
        assert "text" in kwargs, "text is required for type"
        instruction = kwargs.get("text")
        clear = kwargs.get("clear")
        self.controller.text(instruction, clear)
        self.controller.enter()
        self.current_return = {"operation": "do", "action": 'Type',
                               "kwargs": {"text": instruction}}

    def press_enter(self):
        self.controller.enter()
        self.current_return = {"operation": "do", "action": 'Press Enter'}

    def press_back(self):
        self.controller.back()
        self.current_return = {"operation": "do", "action": 'Press Back'}

    def press_home(self):
        self.controller.home()
        self.current_return = {"operation": "do", "action": 'Press Home'}

    def finish(self, message=None):
        self.is_finish = True
        self.current_return = {"operation": "finish", "action": 'finish', "kwargs": {"message": message}}

    def wait(self):
        time.sleep(5)
        self.current_return = {"operation": "do", "action": 'Wait'}

    def launch(self, **kwargs):
        assert "app" in kwargs, "app is required for launch"
        app = kwargs.get("app")
        try:
            package = find_package(app)
        except:
            import traceback
            traceback.print_exc()
        self.controller.launch_app(package)
        self.current_return = {"operation": "do", "action": 'Launch',
                               "kwargs": {"package": package}}


class TextOnlyExecutor_v4(TextOnlyExecutor):
    def __call__(self, code_snippet):
        '''
        self.new_page_captured = False
        self.controller.on("page", self.__capture_new_page__)
        self.current_return = None'''
        
        local_context = self.__get_class_methods__()
        local_context.update(**{'self': self})
        if len(code_snippet.split("\n")) > 1:
            for code in code_snippet.split("\n"):
                if "Action: " in code:
                    code_snippet = code
                    break

        # Add escape characters to nested quotes
        if "do(action=\"Tap\"" in code_snippet or "do(action=\"Swipe\"" in code_snippet or "do(action=\"Long Press\"" in code_snippet:
            code = remove_leading_zeros_in_string(code_snippet.strip())
        else:
            code = code_snippet.strip()

        if 'message=' in code or 'text=' in code:
            # Find the content between quotes after message= or text=
            pattern = r'(message|text)="(.*?)"\)'
            match = re.search(pattern, code, re.S)
            if match:
                content = match.group(2)
                # Escape any quotes within the content
                escaped_content = content.replace('"', '\\"')
                # Replace the original content with the escaped version
                code = re.sub(r'(message|text)=".*?"\)', f'{match.group(1)}="{escaped_content}")', code)
        if "\n" in code:
            code = code.replace("\n", "\\n")
        exec(code, {}, local_context)
        return self.current_return
        
    def modify_relative_bbox(self, relative_bbox):
        if any([bound > 999 for bound in relative_bbox]):
            return relative_bbox
        viewport_width, viewport_height = self.controller.viewport_size
        modify_x1 = relative_bbox[0] * viewport_width / 999
        modify_y1 = relative_bbox[1] * viewport_height / 999
        modify_x2 = relative_bbox[2] * viewport_width / 999
        modify_y2 = relative_bbox[3] * viewport_height / 999
        return [modify_x1, modify_y1, modify_x2, modify_y2]
    
    def do(self, action=None, element=None, **kwargs):
        assert action in ["Tap", "Type", "Swipe", "Enter", "Home", "Back", "Press Back","Long Press", "Wait", "Launch",
                          "Call_API"], "Unsupported Action"
        if element is not None:
            predict_element = element
            if self.config.is_relative_bbox:
                element = self.modify_relative_bbox(element)
        if action == "Tap":
            self.tap(element, predict_element)
        elif action == "Type":
            self.type(**kwargs)
        elif action == "Swipe":
            self.swipe(element, predict_element, **kwargs)
        elif action == "Enter":
            self.press_enter()
        elif action == "Home":
            self.press_home()
        elif action == "Back" or action == "Press Back":
            self.press_back()
        elif action == "Long Press":
            self.long_press(element, predict_element)
        elif action == "Wait":
            self.wait()
        elif action == "Launch":
            self.launch(**kwargs)
        elif action == "Call_API":
            self.call_api(**kwargs)
        else:
            raise NotImplementedError()
        # self.__update_screenshot__() # update screenshot 全部移到recoder内
    
    def tap(self, element, predict_element):
        if isinstance(element, list) and len(element) == 4:
            center_x = (element[0] + element[2]) / 2
            center_y = (element[1] + element[3]) / 2
        elif isinstance(element, list) and len(element) == 2:
            center_x, center_y = element
        else:
            raise ValueError("Invalid element format")
        self.controller.tap(center_x, center_y)
        self.current_return = {"operation": "do", "action": 'Tap', "kwargs": {"element": predict_element, "relative_element": element}}

    def long_press(self, element, predict_element):
        if isinstance(element, list) and len(element) == 4:
            center_x = (element[0] + element[2]) / 2
            center_y = (element[1] + element[3]) / 2
        elif isinstance(element, list) and len(element) == 2:
            center_x, center_y = element
        else:
            raise ValueError("Invalid element format")
        self.controller.long_press(center_x, center_y)
        self.current_return = {"operation": "do", "action": 'Long Press', "kwargs": {"element": predict_element, "relative_element": element}}

    def swipe(self, element=None, predict_element=None, **kwargs):
        if element is None:
            center_x, center_y = self.controller.width // 2, self.controller.height // 2
        elif element is not None:
            if isinstance(element, list) and len(element) == 4:
                center_x = (element[0] + element[2]) / 2
                center_y = (element[1] + element[3]) / 2
            elif isinstance(element, list) and len(element) == 2:
                center_x, center_y = element
            else:
                raise ValueError("Invalid element format")
        assert "direction" in kwargs, "direction is required for swipe"
        direction = kwargs.get("direction")
        dist = kwargs.get("dist", "medium")
        self.controller.swipe(center_x, center_y, direction, dist)
        self.current_return = {"operation": "do", "action": 'Swipe',
                               "kwargs": {"element": predict_element, 'relative_element': element, "direction": direction, "dist": dist}}
        time.sleep(1)
    
    def finish(self, message=None):
        self.is_finish = True
        self.current_return = {"operation": "finish", "action": 'finish', "kwargs": {"message": message}}
        

class TextOnlyExecutor_v41(TextOnlyExecutor):
    def modify_relative_bbox(self, relative_bbox):
        viewport_width, viewport_height = self.controller.viewport_size
        modify_x1 = relative_bbox[0] * viewport_width
        modify_y1 = relative_bbox[1] * viewport_height
        modify_x2 = relative_bbox[2] * viewport_width
        modify_y2 = relative_bbox[3] * viewport_height
        return [modify_x1, modify_y1, modify_x2, modify_y2]
    
    def do(self, action=None, element=None, **kwargs):
        assert action in ["Tap", "Type", "Swipe", "Enter", "Home", "Back", "Long Press", "Wait", "Launch",
                          "Call_API", "Press Back"], "Unsupported Action"
        if element is not None:
            predict_element = element
            element = self.modify_relative_bbox(element)
        if action == "Tap":
            self.tap(element, predict_element)
        elif action == "Type":
            self.type(**kwargs)
        elif action == "Swipe":
            self.swipe(element, predict_element, **kwargs)
        elif action == "Enter":
            self.press_enter()
        elif action == "Home":
            self.press_home()
        elif action == "Back" or action == "Press Back":
            self.press_back()
        elif action == "Long Press":
            self.long_press(element, predict_element)
        elif action == "Wait":
            self.wait()
        elif action == "Launch":
            self.launch(**kwargs)
        elif action == "Call_API":
            self.call_api(**kwargs)
        else:
            raise NotImplementedError()
        # self.__update_screenshot__() # update screenshot 全部移到recoder内
    
    def tap(self, element, predict_element):
        if isinstance(element, list) and len(element) == 4:
            center_x = (element[0] + element[2]) / 2
            center_y = (element[1] + element[3]) / 2
        elif isinstance(element, list) and len(element) == 2:
            center_x, center_y = element
        else:
            raise ValueError("Invalid element format")
        self.controller.tap(center_x, center_y)
        self.current_return = {"operation": "do", "action": 'Tap', "kwargs": {"element": predict_element, "relative_element": element}}

    def long_press(self, element, predict_element):
        if isinstance(element, list) and len(element) == 4:
            center_x = (element[0] + element[2]) / 2
            center_y = (element[1] + element[3]) / 2
        elif isinstance(element, list) and len(element) == 2:
            center_x, center_y = element
        else:
            raise ValueError("Invalid element format")
        self.controller.long_press(center_x, center_y)
        self.current_return = {"operation": "do", "action": 'Long Press', "kwargs": {"element": predict_element, "relative_element": element}}

    def swipe(self, element=None, predict_element=None, **kwargs):
        if element is None:
            center_x, center_y = self.controller.width // 2, self.controller.height // 2
        elif element is not None:
            if isinstance(element, list) and len(element) == 4:
                center_x = (element[0] + element[2]) / 2
                center_y = (element[1] + element[3]) / 2
            elif isinstance(element, list) and len(element) == 2:
                center_x, center_y = element
            else:
                raise ValueError("Invalid element format")
        assert "direction" in kwargs, "direction is required for swipe"
        direction = kwargs.get("direction")
        dist = kwargs.get("dist", "medium")
        self.controller.swipe(center_x, center_y, direction, dist)
        self.current_return = {"operation": "do", "action": 'Swipe',
                               "kwargs": {"element": predict_element, 'relative_element': element, "direction": direction, "dist": dist}}
        time.sleep(1)
    
    def finish(self, message=None):
        self.is_finish = True
        self.current_return = {"operation": "finish", "action": 'finish', "kwargs": {"message": message}}


class TextOnlyExecutor_android_world(TextOnlyExecutor_v4):
    def do(self, action=None, element=None, **kwargs):
        assert action in ["Tap", "Type", "Swipe", "Enter", "Home", "Back", "Press Back", "Long Press", "Wait", "Launch",
                          "Call_API"], "Unsupported Action"
        if element is not None:
            predict_element = element
            if self.config.is_relative_bbox:
                element = self.modify_relative_bbox(element)
        if action == "Tap":
            self.tap(element, predict_element)
        elif action == "Type":
            self.type(**kwargs)
        elif action == "Swipe":
            self.swipe(element, predict_element, **kwargs)
        elif action == "Enter":
            self.press_enter()
        elif action == "Home":
            self.press_home()
        elif action == "Back" or action == "Press Back":
            self.press_back()
        elif action == "Long Press":
            self.long_press(element, predict_element)
        elif action == "Wait":
            self.wait()
        elif action == "Launch":
            self.launch(**kwargs)
        elif action == "Call_API":
            self.call_api(**kwargs)
        else:
            raise NotImplementedError()

    def type(self, **kwargs):
        assert "text" in kwargs, "text is required for type"
        instruction = kwargs.get("text")
        clear = kwargs.get("clear")
        self.controller.text_android_world(instruction, clear)
        self.current_return = {"operation": "do", "action": 'Type',
                               "kwargs": {"text": instruction}}

    def finish(self, message=None):
        self.is_finish = True
        self.current_return = {"operation": "finish", "action": 'finish', "kwargs": {"message": message}}