from fuzzywuzzy import fuzz

from android_lab.evaluation.task import *


def get_type_task_ddl(xml_compressed_tree, doing):
    assert doing in ["create", "edit"]
    type = task = ddl = None

    try:
        TV_list = find_matching_subtrees(xml_compressed_tree, "TextView ;; ;;")
        type, ddl, _ = (list(TV.keys())[0].split(";;")[-1].strip() for TV in TV_list)
    except:
        pass

    if doing == "create":
        try:
            task = find_matching_subtrees(xml_compressed_tree, "EditText ;click")[0]
            task = list(task.keys())[0].split(";;")[-1].strip()
        except:
            pass
    else:
        try:
            task = find_matching_subtrees(xml_compressed_tree, "TextView ;click")[1]
            task = list(task.keys())[0].split(";;")[-1].strip()
        except:
            pass

    return type, task, ddl


class SingleTask_tasks_1(SingleTask):

    def judge_page(self, line):
        if line["parsed_action"]["action"] != "finish":
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(line):
            return {"judge_page": False}

        answer = "2 important and urgent tasks"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_tasks_2(SingleTask):

    def judge_page(self, line):
        if line["parsed_action"]["action"] != "finish":
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(line):
            return {"judge_page": False}

        answer = "12 May 2024, 03:45 PM"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_tasks_3(SingleTask):

    def judge_page(self, line):
        if line["parsed_action"]["action"] != "finish":
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(line):
            return {"judge_page": False}

        answer = "1 item is completed"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_tasks_4(SingleTask):
    target = "Prepare materials for next week's meeting"

    def judge_page(self, xml_compressed_tree):
        type, task, ddl = get_type_task_ddl(xml_compressed_tree, "create")
        return type and task and ddl

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        type, task, ddl = get_type_task_ddl(xml_compressed_tree, "create")
        judge_type = judge_task = judge_ddl = False
        judge_type = type == "IMPORTANT URGENT"
        judge_task = fuzz.partial_ratio(self.target, task) > 85
        judge_ddl = ddl == "12 May 2024, 10:00 AM"

        return {
            "judge_page": True,
            "1": judge_type,
            "2": judge_task,
            "3": judge_ddl,
            "complete": judge_type & judge_task & judge_ddl
        }


class SingleTask_tasks_5(SingleTask):
    target = "Reply to client emails"

    def judge_page(self, xml_compressed_tree):
        type, task, ddl = get_type_task_ddl(xml_compressed_tree, "create")
        return type and task and ddl

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        type, task, ddl = get_type_task_ddl(xml_compressed_tree, "create")
        judge_type = judge_task = judge_ddl = False
        judge_type = type == "IMPORTANT URGENT"
        judge_task = fuzz.partial_ratio(self.target, task) > 85
        judge_ddl = ddl == "10 May 2024, 05:00 PM"

        return {
            "judge_page": True,
            "1": judge_type,
            "2": judge_task,
            "3": judge_ddl,
            "complete": judge_type & judge_task & judge_ddl
        }


class SingleTask_tasks_6(SingleTask):
    target = "Update company website content"

    def judge_page(self, xml_compressed_tree):
        type, task, ddl = get_type_task_ddl(xml_compressed_tree, "create")
        return type and task and ddl

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        type, task, ddl = get_type_task_ddl(xml_compressed_tree, "create")
        judge_type = judge_task = judge_ddl = False
        judge_type = type == "IMPORTANT NOT URGENT"
        judge_task = fuzz.partial_ratio(self.target, task) > 85
        judge_ddl = "01 Jun 2024" in ddl

        return {
            "judge_page": True,
            "1": judge_type,
            "2": judge_task,
            "3": judge_ddl,
            "complete": judge_type & judge_task & judge_ddl
        }


class SingleTask_tasks_7(SingleTask):
    target = "Learn a new programming language"

    def judge_page(self, xml_compressed_tree):
        type, task, ddl = get_type_task_ddl(xml_compressed_tree, "create")
        return type and task and ddl

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        type, task, ddl = get_type_task_ddl(xml_compressed_tree, "create")
        judge_type = judge_task = judge_ddl = False
        judge_type = type == "IMPORTANT NOT URGENT"
        judge_task = fuzz.partial_ratio(self.target, task) > 85
        judge_ddl = "15 Jun 2024" in ddl

        return {
            "judge_page": True,
            "1": judge_type,
            "2": judge_task,
            "3": judge_ddl,
            "complete": judge_type & judge_task & judge_ddl
        }


class SingleTask_tasks_8(SingleTask):
    target = "Attend team building activity"

    def judge_page(self, xml_compressed_tree):
        type, task, ddl = get_type_task_ddl(xml_compressed_tree, "create")
        return type and task and ddl

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        type, task, ddl = get_type_task_ddl(xml_compressed_tree, "create")
        judge_type = judge_task = judge_ddl = False
        judge_type = type == "NOT IMPORTANT URGENT"
        judge_task = fuzz.partial_ratio(self.target, task) > 85
        judge_ddl = ddl == "13 May 2024, 09:00 AM"

        return {
            "judge_page": True,
            "1": judge_type,
            "2": judge_task,
            "3": judge_ddl,
            "complete": judge_type & judge_task & judge_ddl
        }


class SingleTask_tasks_9(SingleTask):
    target = "Order office supplies"

    def judge_page(self, xml_compressed_tree):
        type, task, ddl = get_type_task_ddl(xml_compressed_tree, "create")
        return type and task and ddl

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        type, task, ddl = get_type_task_ddl(xml_compressed_tree, "create")
        judge_type = judge_task = judge_ddl = False
        judge_type = type == "NOT IMPORTANT URGENT"
        judge_task = fuzz.partial_ratio(self.target, task) > 85
        judge_ddl = ddl == "10 May 2024, 03:00 PM"

        return {
            "judge_page": True,
            "1": judge_type,
            "2": judge_task,
            "3": judge_ddl,
            "complete": judge_type & judge_task & judge_ddl
        }


class SingleTask_tasks_10(SingleTask):
    target = "Read Kongres Futurologiczny"

    def judge_page(self, xml_compressed_tree):
        type, task, ddl = get_type_task_ddl(xml_compressed_tree, "create")
        return type and task and ddl

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        type, task, ddl = get_type_task_ddl(xml_compressed_tree, "create")
        judge_type = judge_task = judge_ddl = False
        judge_type = type == "NOT IMPORTANT NOT URGENT"
        judge_task = fuzz.partial_ratio(self.target, task) > 85
        judge_ddl = "03 Jul 2024" in ddl

        return {
            "judge_page": True,
            "1": judge_type,
            "2": judge_task,
            "3": judge_ddl,
            "complete": judge_type & judge_task & judge_ddl
        }


class SingleTask_tasks_11(SingleTask):
    target = "Organize personal files"

    def judge_page(self, xml_compressed_tree):
        type, task, ddl = get_type_task_ddl(xml_compressed_tree, "create")
        return type and task and ddl

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        type, task, ddl = get_type_task_ddl(xml_compressed_tree, "create")
        judge_type = judge_task = judge_ddl = False
        judge_type = type == "NOT IMPORTANT NOT URGENT"
        judge_task = fuzz.partial_ratio(self.target, task) > 85
        judge_ddl = "30 Jun 2024" in ddl

        return {
            "judge_page": True,
            "1": judge_type,
            "2": judge_task,
            "3": judge_ddl,
            "complete": judge_type & judge_task & judge_ddl
        }


class SingleTask_tasks_12(SingleTask):
    target = "Check final documents"

    def judge_page(self, xml_compressed_tree):
        type, task, ddl = get_type_task_ddl(xml_compressed_tree, "create")
        return type and task and ddl

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        type, task, ddl = get_type_task_ddl(xml_compressed_tree, "create")
        judge_type = judge_task = judge_ddl = False
        judge_type = type == "IMPORTANT URGENT"
        judge_task = fuzz.partial_ratio(self.target, task) > 85
        judge_ddl = ddl == "11 May 2024, 03:45 PM"

        return {
            "judge_page": True,
            "1": judge_type,
            "2": judge_task,
            "3": judge_ddl,
            "complete": judge_type & judge_task & judge_ddl
        }


class SingleTask_tasks_13(SingleTask):
    def judge_page(self, xml_compressed_tree):
        type, task, ddl = get_type_task_ddl(xml_compressed_tree, "edit")
        return type and task and ddl

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        type, task, ddl = get_type_task_ddl(xml_compressed_tree, "edit")
        try:
            checklist = find_matching_subtrees(xml_compressed_tree, "TextView ;; ;;")[-1]
            checklist = next(iter(checklist)).split(";;")[-1].strip()
        except:
            return {"judge_page": False}

        judge_type = judge_task = judge_ddl = judge_checklist = False
        judge_type = type == "IMPORTANT NOT URGENT"
        judge_task = task == "Qwen2 DPO training"
        judge_ddl = ddl == "27 May 2024, 04:10 PM"
        judge_checklist = checklist == "Checklist [3 / 3]"

        return {
            "judge_page": True,
            "1": judge_type,
            "2": judge_task,
            "3": judge_ddl,
            "4": judge_checklist,
            "complete": judge_type & judge_task & judge_ddl & judge_checklist
        }
