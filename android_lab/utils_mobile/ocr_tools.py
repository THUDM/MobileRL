import base64
from datasketch import MinHash, MinHashLSH
import Levenshtein
import copy
import os
import re
from rapidocr_onnxruntime import RapidOCR


def remove_punctuation(input_string):
    # 定义一个正则表达式来匹配中文标点符号
    punc = u'[\u3002\uff1b\uff0c\uff1a\u201c\u201d\uff08\uff09\u3001\uff1f\u300a\u300b]'
    punc_en = r"[!\"#$%&\'()*+,-./:;<=>?@\[\\\]^_`{|}~\n]"
    # 使用 sub() 函数把所有匹配的标点符号都替换成空字符串
    st = re.sub(punc, ' ', input_string)
    st = re.sub(punc_en, " ", st)
    return st


class XML_OCR_Matcher:
    def __init__(self, num_perm=128, cov_threshold=0.7, threshold=0.7, print_intermediates=False, use_gpu=False, paddleocr_dir="/workspace/shudan/.paddleocr"):
        self.engine = RapidOCR(
            text_score=0.86, 
            min_height=20, 
            # det_limit_side_len=960, 
            det_limit_type="max",
            inter_op_num_threads=-1,
            intra_op_num_threads=3,)
        # det_model_dir = os.path.join(paddleocr_dir, "whl/det/ch/ch_PP-OCRv4_det_infer")
        # rec_model_dir = os.path.join(paddleocr_dir, "whl/rec/ch/ch_PP-OCRv4_rec_infer")
        # cls_model_dir = os.path.join(paddleocr_dir, "whl/cls/ch_ppocr_mobile_v2.0_cls_infer")
        # self.ocr = PaddleOCR(use_angle_cls=True,
        #                      lang="ch",
        #                      use_gpu=use_gpu,
        #                      use_space_char=True,
        #                      show_log=False,
        #                      enable_mkldnn=False,
        #                      cpu_threads=10,
        #                      det_limit_side_len=896,
        #                     det_model_dir = det_model_dir,
        #                     rec_model_dir = rec_model_dir,
        #                     cls_model_dir = cls_model_dir
        #                     )

        self.num_perm = num_perm
        self.cov_threshold = cov_threshold
        self.threshold = threshold
        self.print_intermediates = print_intermediates
        self.xml_descs = []
        self.ocr_texts = []
        self.ocr_dict = {}
        self.unmatch_dict = {}

    def create_minhash(self, text):
        m = MinHash(num_perm=self.num_perm)
        for d in remove_punctuation(text).replace(" ", ""):
            m.update(d.encode('utf8'))
        return m

    def contains_most_information(self):
        lsh = MinHashLSH(threshold=self.threshold, num_perm=self.num_perm)
        minhashes_a = {}
        for i, text in enumerate(self.xml_descs):
            minhash = self.create_minhash(text)
            lsh.insert(f"{text}_{i}", minhash)
            minhashes_a[f"{text}_{i}"] = remove_punctuation(text).replace(" ", "")

        unmatched_items = []
        matched_count = 0
        for text in self.ocr_texts:
            origin_text = copy.deepcopy(text)
            query_minhash = self.create_minhash(text)
            result = lsh.query(query_minhash)
            if self.print_intermediates:
                print(text, result)
            matched = False
            if result:
                matched_count += 1
                matched = True
            else:
                text = text.replace(" ", "")
                if 2 <= len(text) <= 4:
                    for key, value in minhashes_a.items():
                        if Levenshtein.distance(text, value) <= 1:
                            matched_count += 1
                            matched = True
                            if self.print_intermediates:
                                print(f"Edit distance matched: {text} -> {value}")
                            break
                elif len(text) == 1:
                    for key, value in minhashes_a.items():
                        if text == value:
                            matched_count += 1
                            matched = True
                            if self.print_intermediates:
                                print(f"Single character matched: {text} -> {value}")
                            break
            if not matched:
                unmatched_items.append(origin_text)

        coverage = matched_count / len(self.ocr_texts)
        return coverage >= self.cov_threshold, coverage, unmatched_items

    def delete_xml_format(self, xml_string):
        start = -1
        xml_formats = []
        for i in range(len(xml_string)):
            if xml_string[i] == '<':
                start = i
            elif xml_string[i] == '>' and start != -1:
                xml_formats.append(xml_string[start:i+1])
                start = -1

        for _str in xml_formats:
            xml_string = xml_string.replace(_str, '')
        return xml_string

    def get_all_desc_in_xml(self, root):
        node_desc = root.get('content-desc', '')
        node_text = root.get('text', '')
        if node_desc != '':
            self.xml_descs.append(self.delete_xml_format(node_desc))
        if node_text != '':
            self.xml_descs.append(self.delete_xml_format(node_text))
        for child in list(root):
            self.get_all_desc_in_xml(child)


    def get_ocr_texts(self, image_path):
        # result = self.ocr.ocr(image_path, cls=True)
        # for idx in range(len(result)):
        #     res = result[idx]
        #     for line in res:
        #         if line[1][1] > 0.86:
        #             if line[1][0] not in self.ocr_dict:
        #                 self.ocr_dict[line[1][0]] = [line[0]]
        #                 self.ocr_texts.append(line[1][0])
        #             else:
        #                 self.ocr_dict[line[1][0]].append(line[0])
        #         elif '口评论' in line[1][0]:
        #             self.ocr_dict["评论"] = [line[0]]
        #             self.ocr_texts.append("评论")

        result = self.engine(image_path)
        if result is None:
            return
        for line in result[0]:

            if '口评论' in line[1]:
                self.ocr_dict["评论"] = [line[0]]
                self.ocr_texts.append("评论")
            elif line[1] not in self.ocr_dict: 
                self.ocr_dict[line[1]] = [line[0]]
                self.ocr_texts.append(line[1])
            else:
                self.ocr_dict[line[1]].append(line[0])


    def convert_ocr_bbox_to_bounds(self, ocr_bbox):
        return list(map(int, ocr_bbox[0] + ocr_bbox[2]))

    def run(self, xml_root, image_path):
        self.xml_descs = []
        self.ocr_texts = []
        self.ocr_dict = {}
        self.unmatch_dict = {}
        self.get_all_desc_in_xml(xml_root)
        self.get_ocr_texts(image_path)
        if self.print_intermediates:
            print("XML Descriptions:", self.xml_descs)
            print("OCR Texts:", self.ocr_texts)
        match_result, coverage, unmatched_items = self.contains_most_information()
        for item in unmatched_items:
            self.unmatch_dict[item] = [self.convert_ocr_bbox_to_bounds(bbox) for bbox in self.ocr_dict[item]]
        if self.print_intermediates:
            print("Matching Result:", match_result)
            print("Coverage:", coverage)
            print("Unmatched Items:", self.unmatch_dict)
        return match_result, coverage, self.unmatch_dict

