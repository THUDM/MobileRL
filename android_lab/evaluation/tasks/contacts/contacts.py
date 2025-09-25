from android_lab.evaluation.task import *


class SingleTask_Contacts_1(SingleTask):

    def judge_page(self, xml_compressed_tree):
        # 判断是否包含 "Contact" 和 "John"
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Contact"):
            return False
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "John"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        outcome = {"judge_page": False, "1": False, "2": False, "complete": False}

        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome["judge_page"] = True

        # 检查 "John"
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "John")
        if outs:
            outcome["1"] = True

        # 检查 "1 (234) 567-8"
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "1 (234) 567-8")
        if outs:
            outcome["2"] = True

        # 判断 complete
        if outcome["1"] and outcome["2"]:
            outcome["complete"] = True

        return outcome


class SingleTask_Contacts_2(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Contact"):
            return False
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "John Smith"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        

        outcome = {"judge_page": True, "1": False, "2": False, "complete": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "1 (234) 567-8")
        
        for out in outs:
            for single_out in out.values():
                for key in single_out.keys():
                    key = key.split(";")[-1]
                    if "Call Mobile 1 (234) 567-8 " in key:
                        outcome["1"] = True
    
                    if "123456@gmail.com " in key:
                        outcome["2"] = True
                    if outcome["1"] and outcome["2"]:
                        outcome["complete"] = True
                        return outcome

        return outcome


class SingleTask_Contacts_3(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Contact"):
            return False
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Xu"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "2": False, "complete": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "1 (234) 567-8")
        for out in outs:
            for single_out in out.values():
                for key in single_out.keys():
                    key = key.split(";")[-1]
                    if "Call Work 1 (234) 567-8 " in key:
                        outcome["1"] = True
                    if "Call Mobile (876) 543-21 " in key:
                        outcome["2"] = True
                    if outcome["1"] and outcome["2"]:
                        outcome["complete"] = True
                        return outcome

        return outcome


class SingleTask_Contacts_4(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Contact"):
            return False
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Chen"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "complete": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Contact photo ")

        for out in outs:
            for single_out in out.values():
                for key in single_out.keys():
                    key = key.split(";")[-1]
                    if "Tsinghua University " in key:
                        outcome["1"] = True
                        outcome["complete"] = True
                        return outcome

        return outcome


class SingleTask_Contacts_5(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "work • l"):
            return False
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Add contacts"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "2": False, "3": False, "complete": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "work • ")

        for out in outs:
            for single_out in out.values():
                for key, value in single_out.items():
                    if "work • " in key:
                        key = key.split(";")[-1]
                        if "contacts" in key and not "3 contacts " in key:
                            return {"judge_page": True, "1": False}
                    try:
                        for it in value.keys():
                            key = it.split(";")[-1]
                            if "Chen Chen " in key:
                                outcome["1"] = True
                            elif "Lee Lee " in key:
                                outcome["2"] = True
                            elif "Xu Xu " in key:
                                outcome["3"] = True
                            if outcome["1"] and outcome["2"] and outcome["3"]:
                                outcome["complete"] = True
                                return outcome
                    except:
                        pass

        return outcome


class SingleTask_Contacts_6(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Contact"):
            return False
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "ABC"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "complete": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "00112233 ")

        if len(outs) > 0:
            outcome["1"] = True
            outcome["complete"] = True

        return outcome


class SingleTask_Contacts_7(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Contact"):
            return False
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "ABC"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "complete": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Birthday ")

        for out in outs:
            for single_out in out.values():
                for key in single_out.keys():
                    key = key.split(";")[-1]
                    if "October 24, 1996 " in key:
                        outcome["1"] = True
                        outcome["complete"] = True
                        return outcome

        return outcome


class SingleTask_Contacts_8(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Contact"):
            return False
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "ABC"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outcome = {"judge_page": True, "1": False, "complete": False}

        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "abc.github.com")
        if len(outs) > 0:
            outcome["1"] = True
            outcome["complete"] = True

        return outcome


class SingleTask_Contacts_9(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Texting with ABC"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        key_1 = False
        key_2 = False
        outcome = {"judge_page": True, "1": False, "2": False, "complete": False}

        if find_subtrees_of_parents_with_key(xml_compressed_tree, "Texting with ABC"):
            key_1 = True
            if find_subtrees_of_parents_with_key(xml_compressed_tree, "Nice to meet you"):
                key_2 = True

        outcome["1"] = key_1
        outcome["2"] = key_2
        outcome["complete"] = key_1 and key_2

        return outcome


class SingleTask_Contacts_10(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "End call"):
            return False
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "ABC"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        return {"judge_page": True, "1": True, "complete": True}


class SingleTask_Contacts_11(SingleTask):
    step1_go_to_delete_page = False
    step2_delete_contact = False
    step3_delete_contact_confirm = False

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "AAA"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.step1_go_to_delete_page:
            if not self.judge_page(xml_compressed_tree):
                return {"judge_page": False}
            else:
                self.step1_go_to_delete_page = True

        if self.step1_go_to_delete_page:
            if find_subtrees_of_parents_with_key(xml_compressed_tree, "Delete contact?"):
                self.step2_delete_contact = True
        
        if self.step1_go_to_delete_page and self.step2_delete_contact:
            if find_subtrees_of_parents_with_key(xml_compressed_tree, "No results"):
                self.step3_delete_contact_confirm = True
        
        if self.step1_go_to_delete_page and self.step2_delete_contact and self.step3_delete_contact_confirm:
            return {"judge_page": True, "1": True, "2": True, "3": True, "complete": True}

        return {"judge_page": True, "1": self.step1_go_to_delete_page, "2": self.step2_delete_contact, "3": self.step3_delete_contact_confirm, "complete": self.step1_go_to_delete_page and self.step2_delete_contact and self.step3_delete_contact_confirm}


class SingleTask_Contacts_12(SingleTask):

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        answer = "22331144 or (223) 311-44"
        self.save_answer(answer)
        if self.check_answer(line):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_Contacts_13(SingleTask):

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        answer = "22334455@gmail.com"
        if find_subtrees_of_parents_with_key(xml_compressed_tree, "22334455@gmail.com"):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            self.save_answer(answer)
            if self.check_answer(line):
                outcome = {"judge_page": True, "1": True, "complete": True}
            else:
                outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_Contacts_14(SingleTask):

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        answer = "October 24, 1996"
        if find_subtrees_of_parents_with_key(xml_compressed_tree, "October 24, 1996"):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            self.save_answer(answer)
            if self.check_answer(line):
                outcome = {"judge_page": True, "1": True, "complete": True}
            else:
                outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_Contacts_15(SingleTask):

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        answer = "Tsinghua university"
        if find_subtrees_of_parents_with_key(xml_compressed_tree, "Tsinghua university"):
            outcome = {"judge_page": True, "1": True, "complete": True}
        else:
            self.save_answer(answer)
            if self.check_answer(line):
                outcome = {"judge_page": True, "1": True, "complete": True}
            else:
                outcome = {"judge_page": True, "1": False, "complete": False}
        return outcome


class SingleTask_Contacts_16(SingleTask):

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}

        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Search contacts ")
        if len(outs) == 0:
            return {"judge_page": True, "1": False, "complete": False}

        return {"judge_page": True, "1": True, "complete": True}
