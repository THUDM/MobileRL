import logging

import android_lab.templates.seeact_screenshot_prompts as SeeActPrompts
import android_lab.templates.seeact_xml_prompts as SeeActPrompts_xml
from android_lab.evaluation.definition import *
from android_lab.evaluation.utils import *
from android_lab.templates import *
from android_lab.templates.packages import package_dict_en
import traceback

class AutoTask():
    def __init__(self, instruction, controller, page_executor, agent, record, command_per_step, config = None, **kwargs):
        self.config = config
        self.controller = controller
        self.page_executor = page_executor
        self.agent = agent
        self.record = record
        self.kwargs = kwargs
        self.set_system_prompt()
        self.record.command_per_step = [command_per_step]
        # pimusic and map.me need ac to fetch xml
        if "map.me" in instruction or "pimusic" in instruction:
            self.accessibility = self.controller.check_ac_survive()
        else:
            self.accessibility = False

    def set_system_prompt(self):
        if self.config.system_prompt is not None:
            sys_prompt = globals().get(self.config.system_prompt)
            if sys_prompt is None or not isinstance(sys_prompt, str):
                raise AttributeError(f"{self.config.system_prompt} not found. Please check the name in the config file.")
            
            self.record.history = [{
                "role": "system",
                "content": sys_prompt
            }]

    def run_step(self, instruction):
        self.record.update_before(controller=self.controller, need_screenshot=True, ac_status=self.accessibility)
        round_count = self.record.get_round_count()
        compressed_xml_json = self.record.get_latest_xml()

        prompt = f"" if round_count == 0 else "** XML **\n"
        try:
            current_message = {"role": "user", "content": prompt + compressed_xml_json}
            if self.agent.name == "GLMModelAgent":
                current_message["current_app"] = self.controller.get_current_activity()
            rsp = self.agent.act([*self.record.history, current_message])
        except Exception as e:
            print_with_color(f"Error: {e}", "red")
            self.record.update_error(output=rsp, error_message=str(e))

        exe_res = self.page_executor(get_code_snippet(rsp))
        self.record.update_after(exe_res, rsp)
        self.record.turn_number += 1



class Multi_ScreenshotTask(AutoTask):
    def run_step(self, instruction):
        prompt = "** Screen Info **"
        
        round_count = self.record.get_round_count()

        self.record.update_before(controller=self.controller, need_screenshot=True, ac_status=self.accessibility, need_labeled=False, prompt=prompt)
        try:
            xml = self.record.get_latest_xml(self.controller)
        except Exception as e:
            state = False
            print_with_color(f"Error: {e}", "red")
            traceback.print_exc()
        current_app = package_dict_en[self.record.get_current_activity()]
        prompt += f"\n\n{json.dumps({'current_app': current_app}, ensure_ascii=False)}" 
        instruction += f"\n\n{json.dumps({'current_app': current_app}, ensure_ascii=False)}"
        
        rsp = None
        format_prompt = None
        try:
            edittext_empty = True
            for line in xml.split('\n'):
                if 'EditText' in line:
                    text = line.split(';')[-2]
                    if text != "":
                        edittext_empty = False
                        break

            image_path = self.record.contents[-1]['image']
            if self.record.get_current_activity() not in package_dict_en:
                print_with_color(f"Current activity: {self.record.get_current_activity()} not in package_dict_en, task dir {self.record.xml_file_path}", "red")

            
            if round_count == 0:
                if self.config.with_xml:
                    current_message = self.agent.prompt_to_message(instruction, [image_path], xml=xml)
                else:
                    current_message = self.agent.prompt_to_message(instruction, [image_path])
            else:
                if self.config.with_xml:
                    current_message = self.agent.prompt_to_message(prompt, [image_path], xml=xml)
                else:
                    current_message = self.agent.prompt_to_message(prompt, [image_path])
            
            
            if len(self.record.contents) > 1 and self.config.picture_round == 2:    
                image_path = self.record.contents[-2]['image']
                if self.record.contents[-2]["index"] == 0:
                    last_user = self.agent.prompt_to_message(instruction, [image_path])
                else:
                    last_user = self.agent.prompt_to_message(prompt, [image_path])
                
                state, rsp = self.agent.act([*self.record.history[:-2], last_user, self.record.history[-1], current_message])
                format_prompt = self.agent.format_prompt([*self.record.history[:-2], last_user, self.record.history[-1], current_message])
            else:
                state, rsp = self.agent.act([*self.record.history, current_message]) 
                format_prompt = self.agent.format_prompt([*self.record.history, current_message])
        except Exception as e:
            state = False
            print_with_color(f"Error: {e}", "red")
            traceback.print_exc()

        logging.debug(f'{state=}, {rsp=}, {format_prompt=}')
        if not state:
            return False

        try:
            is_think_ans, think, ans = extract_think_ans(rsp)
            if not is_think_ans:
                code_line = rsp
            else:
                code_line = ans
            if 'element=' in code_line:
                element = re.search(r'element=\[(.*?)\]', code_line)
                if element:
                    element = element.group(1)
                    new_element = element.split(',')
                    if len(new_element) == 2:
                        new_element = [int(e) for e in new_element]
                        # width, height = self.controller.viewport_size
                        # new_element = [int(new_element[0] * 999 / width), int(new_element[1] * 999 / height)]
                        new_element = ','.join([str(new_element[0]), str(new_element[1]), str(new_element[0]), str(new_element[1])])
                        code_line = code_line.replace(element, new_element)
                        # print(f'{element} => {new_element}')

            if code_line is None:
                return False
            code_snippet = get_code_snippet(code_line) if 'claude' not in self.agent.model_name else get_code_snippet(code_line.replace('\\n', '<|newline|>').split('\n')[-1].replace('<|newline|>', '\\n'))
            if 'action="Type"' in code_snippet and not edittext_empty:
                code_snippet = code_snippet[:-1] + ", clear=True)"

            exe_res = self.page_executor(code_snippet)
            if round_count == 0:
                self.record.update_after(exe_res, rsp, format_prompt, instruction)
            else:   
                self.record.update_after(exe_res, rsp, format_prompt, prompt)
            self.record.turn_number += 1
            return True
        except Exception as e:
            print_with_color(f"Error: {e}", "red")
            error_message = traceback.format_exc()
            self.record.update_error(error_message, rsp, format_prompt, prompt)
            return False


class TextOnlyTask(AutoTask):
    def set_system_prompt(self, instruction):
        self.record.history = [{
            "role": "system",
            "content": SYSTEM_PROMPT_ANDROID_TEXT_GPT + f"\n\nTask Instruction: {instruction}"
        }]


class ScreenshotTask(TextOnlyTask):
    def run_step(self):
        self.record.update_before(controller=self.controller, need_screenshot=True, ac_status=self.accessibility,
                                  need_labeled=True)
        round_count = self.record.get_round_count()
        prompt = json.dumps({"current_app": self.controller.get_current_app()},
                                                         ensure_ascii=False)
        try:
            xml = self.record.get_latest_xml()
            image_path = self.record.labeled_current_screenshot_path
            current_message = self.agent.prompt_to_message(prompt, [image_path])
            rsp = self.agent.act([*self.record.history, current_message])

            print("Model Response: ", rsp)
            
            #rsp = input("Please input the response: ")
        except Exception as e:
            import traceback
            print(traceback.print_exc())
            # print_with_color(f"Error: {e}", "red")

        exe_res = self.page_executor(get_code_snippet(rsp))
        self.record.update_after(exe_res, rsp)
        self.record.turn_number += 1

    def set_system_prompt(self, instruction):
        self.record.history = [{
            "role": "system",
            "content": SYSTEM_PROMPT_ANDROID_MLLM_DIRECT + f"\n\nTask Instruction: {instruction}"
        }]