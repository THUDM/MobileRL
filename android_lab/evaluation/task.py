from collections import defaultdict
from os.path import dirname, join
from typing import Generic, TypeVar
from PIL import Image

import traceback
import jsonlines
import numpy as np
from android_lab.evaluation.definition import *
from android_lab.evaluation.utils import *
from android_lab.utils_mobile.utils import get_compressed_xml


T_INPUT = TypeVar('T_INPUT')
T_OUTPUT = TypeVar('T_OUTPUT')
T_TARGET = TypeVar('T_TARGET')


def dump_xml(xml_path):
    xml_compressed = get_compressed_xml(xml_path)
    if xml_compressed is None:
        return None
    return json.loads(xml_compressed)


def calculate_partial_acc(dict):
    tt = 0
    acc = 0
    for key, values in dict.items():
        if key != "complete" and key != "judge_page":
            tt += 1
            if values:
                acc += 1
    if tt == 0:
        return 0
    return acc / tt


def compute_image_similarity(image_paths):
    if len(image_paths) <= 2:
        return [], 0
    image_paths = image_paths[:-1]
    image_list = []
    for path in image_paths:
        try:
            image_list.append(np.array(Image.open(path)))
        except Exception as e:
            image_list.append(np.zeros((1, 1, 3)))

    simi = []
    sum_simi = 0

    for i in range(len(image_list) - 1):
        try:
            either_not_255 = np.logical_or(np.not_equal(image_list[i], 255), np.not_equal(image_list[i + 1], 255))
            values_match = np.equal(image_list[i], image_list[i + 1])
            match_in_either_not_255 = np.logical_and(values_match, either_not_255)

            similarity = np.sum(match_in_either_not_255.astype(np.float32)) / np.sum(either_not_255.astype(np.float32))
            simi.append(float(similarity))

            if similarity > 0.999:
                sum_simi += 1
        except Exception as e:
            simi.append(0)

    return simi, sum_simi


class Evaluation_Task(Generic[T_INPUT, T_OUTPUT, T_TARGET]):
    def __init__(self, config, traces, args, detail=False):
        self.config = config
        self.args = args
        assert self.config is not None, "Task config is required."
        self.name = self.config.APP
        self.task_list = self.config.get_tasks()
        self.check_task_id_list = []
        self.metrics = self.config.get_metrics()
        self.traces = traces
        self.all_result = []
        self.show_detail_metrics = detail
        self.total_tasks_num = 138
        if self.show_detail_metrics:
            self.additional_metrics = defaultdict(dict)
            with open(join(dirname(__file__), "tasks/human_ground_turth/ground_truth_length.json")) as f:
                self.length_gt = json.load(f)
        
    def task_list_delete(self, task_ids):
        for taskid in task_ids:
            self.check_task_id_list.append(taskid)

    def evaluate(self) -> Dict[str, Any]:
        for task in self.task_list:
            if self.check_task_id_list == []:
                pass
            elif task.get('task_id') not in self.check_task_id_list:
                continue
            print(f"Evaluating task '{task.get('task_id')}'")
            try:
                assert task.get('task_id') in self.metrics, f"No valid function mapped for {task.get('task_id')}"
            except:
                print(f"No valid function mapped for {task.get('task_id')}")
                continue
            task_id = task.get('task_id')
            metric = self.metrics[task_id](self.args)
            final_result = {"complete": False}
            if task_id not in self.traces:
                print(f"Trace for task '{task_id}' not found.")
                continue
            if not os.path.exists(self.traces[task_id]['trace_file']):
                print(f"Trace file not found: {self.traces[task_id]['trace_file']}")
                continue
            all_operation_trace = []
            all_images = []
            agent_name = self.traces[task_id]["trace_root"].split("/")[-2]

            num_repeat = 0
            last_action = None
            with jsonlines.open(self.traces[task_id]['trace_file']) as reader:
                trace_root = self.traces[task_id]['trace_root']
                for line in reader:
                    if "parsed_action" not in line:
                        continue
                    current_action = json.dumps(line["parsed_action"])
                    if current_action == last_action:
                        num_repeat += 1
                        if num_repeat > 5:
                            break
                    else:
                        num_repeat = 0
                        last_action = current_action

                    if line["ac_xml"] is None:
                        xml_path = line["xml"]
                    else:
                        xml_path = line["ac_xml"]
                    xml_path = os.path.join(self.traces[task_id]['xml_path'], xml_path.split("/")[-1])
                    metric_type = self.config.metrics_type[task.get('task_id')]
                    if not os.path.exists(xml_path):
                        #print(f"XML file not found: {xml_path}")
                        continue
                    xml_compressed = dump_xml(xml_path)
                    try:
                        result = metric.judge(xml_compressed, line, xml_path)
                        all_operation_trace.append(line)
                        image_path = line["image"]
                        image_filename = image_path.split("/")[-1]
                        image_path = os.path.join(trace_root, "Screen", image_filename)
                        if image_path.split('/')[-4] != agent_name:
                            image_path = image_path.replace(image_path.split('/')[-4], agent_name)
                        all_images.append(image_path)
                        if "judge_page" in result.keys() and not result.get("judge_page"):
                            continue
                        else:
                            final_result = result
                    except:
                        result = {"complete": False}
            if self.show_detail_metrics:
                self.add_metrics(task, all_operation_trace, all_images, final_result)

            self.save_single(task, final_result)
        self.print_metric()


    def evaluate_result(self, task_id, env_name='') -> Dict[str, Any]:
        if 'android_long-train' in env_name:
            # app = self.name
            task_config = self.traces[task_id]["long_config"]
            judger =  train_judger_mapping[task_id.rsplit('_', 1)[0]](task_config, self.traces[task_id]["trace_root"])
            self.metrics[task_id] = judger.get_map(task_id)
            metric = self.metrics[task_id](task_config, self.traces[task_id]["trace_root"])
            
        elif 'android_long' in env_name:
            app = self.name
            task_config = self.traces[task_id]["long_config"]
            judger =  judger_mapping[app](task_config, self.traces[task_id]["trace_root"])
            self.metrics[task_id] = judger.get_map(task_id)
            metric = self.metrics[task_id](task_config, self.traces[task_id]["trace_root"])

        
        if 'android_long' not in env_name:
            metric = self.metrics[task_id](self.args)
            
        final_result = {"complete": False}
        
        
        all_operation_trace = []
        all_images = []
        agent_name = self.traces[task_id]["trace_root"].split("/")[-2]

        num_repeat = 0
        last_action = None
        if 'android_long' in env_name:
            try:
                result_list, useful_data = metric.judge()
                final_result = {
                    "complete": useful_data['is_completed'],
                    **useful_data
                }
            except:
                traceback.print_exc()
                final_result = {"complete": False, "error": traceback.format_exc()}
        else:
            with jsonlines.open(self.traces[task_id]['trace_file']) as reader:
                trace_root = self.traces[task_id]['trace_root']
                for line in reader:
                    if "parsed_action" not in line:
                        continue
                    current_action = json.dumps(line["parsed_action"])
                    if current_action == last_action:
                        num_repeat += 1
                        if num_repeat > 5:
                            break
                    else:
                        num_repeat = 0
                        last_action = current_action

                    if line["ac_xml"] is None:
                        xml_path = line["xml"]
                    else:
                        xml_path = line["ac_xml"]
                    xml_path = os.path.join(self.traces[task_id]['xml_path'], xml_path.split("/")[-1])
                    # metric_type = self.config.metrics_type[task.get('task_id')]

                    if not os.path.exists(xml_path):
                        #print(f"XML file not found: {xml_path}")
                        continue
                    xml_compressed = dump_xml(xml_path)
                    try:
                        result = metric.judge(xml_compressed, line, xml_path)
                        all_operation_trace.append(line)
                        image_path = line["image"]
                        image_filename = image_path.split("/")[-1]
                        image_path = os.path.join(trace_root, "Screen", image_filename)
                        if image_path.split('/')[-4] != agent_name:
                            image_path = image_path.replace(image_path.split('/')[-4], agent_name)
                        all_images.append(image_path)
                        if "judge_page" in result.keys() and not result.get("judge_page"):
                            continue
                        else:
                            final_result = result
                    except:
                        traceback.print_exc()
                        final_result = {"complete": False, "error": traceback.format_exc()}
            
        with jsonlines.open(os.path.join(self.traces[task_id]['trace_root'], 'result.jsonl'), 'w') as fw:
            fw.write(final_result)
        return final_result

    

    def add_metrics(self, task, traces, all_images, final_result):
        # Reversed Redundancy Ratio
        length = len(traces)
        if not final_result.get("complete") or length == 0:
            RRR = None
        else:
            RRR = self.length_gt[task["task_id"]] / length if task["task_id"] in self.length_gt else None
        self.additional_metrics["RRR"][task["task_id"]] = RRR


        # Reasonable Operation Ratio
        
        simi, sum_simi = compute_image_similarity(all_images)
        if length - 1 == 0:
            self.additional_metrics["reasonable_operation_ratio"][task["task_id"]] = 1
        else:
            self.additional_metrics["reasonable_operation_ratio"][task["task_id"]] = 1 - (sum_simi / (length - 1))

    def save_single(self, task, result):
        save_dir = self.config.output_dir
        with jsonlines.open(os.path.join(save_dir, "results.jsonl"), mode='a') as writer:
            output_dict = {}
            output_dict["task_id"] = task.get('task_id')
            output_dict["task"] = self.config.task_name[task.get('task_id')]
            output_dict["metric_type"] = self.config.metrics_type[task.get('task_id')]
            output_dict["result"] = result
            if self.show_detail_metrics:
                for metric, metric_value in self.additional_metrics.items():
                    output_dict[metric] = metric_value[task.get('task_id')]
            # print(f"Task '{task.get('task_id')}' evaluated.")
            # print(f"Result: {result}")
            writer.write(output_dict)
            self.all_result.append(output_dict)

    def print_metric(self):
        complete_metric = defaultdict(list)
        partial_metric = defaultdict(list)

        for result in self.all_result:
            app = result["task_id"].split("_")[0]
            if result["result"].get("complete") == True:
                complete_metric[app].append(1)
                partial_metric[app].append(1)
            else:
                complete_metric[app].append(0)
                partial_metric[app].append(calculate_partial_acc(result["result"]))
        for key, values in complete_metric.items():
            with jsonlines.open(os.path.join(self.config.output_dir, "total.jsonl"), mode='a') as writer:
                output_dir = {"App": key, "Acc": sum(values) / len(values), "Total": len(values),
                              "Complete_Correct": sum(values), "Sum_Partial_Acc": sum(partial_metric[key]),
                              "Partial_Acc": sum(partial_metric[key]) / len(values)}
                if self.show_detail_metrics:
                    for metric, metric_value in self.additional_metrics.items():
                        values_set = [i for i in metric_value.values() if i is not None]
                        try:
                            output_dir[metric] = sum(values_set) / len(values_set)
                            output_dir["Sum_" + metric] = sum(values_set)
                        except:
                            output_dir[metric] = 0
                            output_dir["Sum_" + metric] = 0
                writer.write(output_dir)


class SingleTask():
    def __init__(self, args):
        self.metric_type = ""
        self.final_ground_truth = None
        self.args = args

    def check_answer(self, line):
        if line["parsed_action"].get("action") != "finish" and line["parsed_action"].get("type") != "finish":
            return False
        if self.final_ground_truth is None:
            return False

        try:
            question = line["target"]
            if "kwargs" in line["parsed_action"]:
                model_answer = line["parsed_action"]["kwargs"]["message"]
            else:
                model_answer = line["parsed_action"]["input"]
            ground_truth = self.final_ground_truth
            if detect_answer(question, model_answer, ground_truth,self.args):
                return True
            else:
                return False
        except:
            return False

    def judge_page(self, xml_compressed_tree):
        return True

    def judge(self, xml_compressed_tree, line):
        raise NotImplementedError

    def save_answer(self, answer):
        self.final_ground_truth = answer
