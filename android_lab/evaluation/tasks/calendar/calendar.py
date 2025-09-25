from android_lab.evaluation.task import *


class SingleTask_calendar_1(SingleTask):

    def judge_page(self, xml_compressed_tree):
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "work") or not find_subtrees_of_parents_with_key(xml_compressed_tree, "SAVE"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        key_1 = True
        key_2 = True
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Today")
        if (len(outs) == 0):
            key_1 = False
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "5:00 PM")
        if ((len(outs) == 0)):
            key_2 = False
        return {"judge_page": True, "1": True, "2": key_1, "3": key_2, "complete": key_1 and key_2}


class SingleTask_calendar_2(SingleTask):

    def judge_page(self, xml_compressed_tree):
        
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "homework") or not find_subtrees_of_parents_with_key(xml_compressed_tree, "SAVE"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        key_2 = True
        key_3 = True
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "May 21")
        if ((len(outs) == 0)):
            key_2 = False
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "10 minutes before ")
        if ((len(outs) == 0)):
            key_3 = False
        return {"judge_page": True, "1": True, "2": key_2, "3": key_3, "complete": key_2 and key_3}


class SingleTask_calendar_3(SingleTask):

    def judge_page(self, xml_compressed_tree):
        
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "meeting") or not find_subtrees_of_parents_with_key(xml_compressed_tree, "SAVE"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        key_2 = True
        key_3 = True
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "May 13")
        if ((len(outs) == 0)):
            key_2 = False
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "conference room B202 ")
        if ((len(outs) == 0)):
            key_3 = False
        return {"judge_page": True, "1": True, "2": key_2, "3": key_3, "complete": key_2 and key_3}


class SingleTask_calendar_4(SingleTask):

    def judge_page(self, xml_compressed_tree):
        
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "new month") or not find_subtrees_of_parents_with_key(xml_compressed_tree, "SAVE"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        key_1 = True
        key_2 = True
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Jun 01")
        if (len(outs) == 0):
            key_1 = False
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Monthly")
        if ((len(outs) == 0)):
            key_2 = False
        return {"judge_page": True, "1": True, "2": key_1, "3": key_2, "complete": key_1 and key_2}


class SingleTask_calendar_5(SingleTask):

    def judge_page(self, xml_compressed_tree):
        
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "work") or not find_subtrees_of_parents_with_key(xml_compressed_tree, "SAVE"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        key_1 = True
        key_2 = True
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Today")
        if (len(outs) == 0):
            key_1 = False
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "7:00 PM")
        if ((len(outs) == 0)):
            key_2 = False
        return {"judge_page": True, "1": True, "2": key_1, "3": key_2, "complete": key_1 and key_2}


class SingleTask_calendar_6(SingleTask):

    def judge_page(self, xml_compressed_tree):
        
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "homework") or not find_subtrees_of_parents_with_key(xml_compressed_tree, "SAVE"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        self.edit_started_correctly = False
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        key = True
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "homework")
        if (len(outs) == 0):
            key = False
        if (key):
            self.edit_started_correctly = True
        key_1 = True
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "classroom 101")
        if (len(outs) == 0):
            key_1 = False
        return {"judge_page": True, "1": True, "2": self.edit_started_correctly, "3": key_1,
                "complete": self.edit_started_correctly and key_1}


class SingleTask_calendar_7(SingleTask):

    def judge_page(self, xml_compressed_tree):
        
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "meeting") or not find_subtrees_of_parents_with_key(xml_compressed_tree, "SAVE"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        self.edit_started_correctly = False
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        key = True
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "meeting")
        if (len(outs) == 0):
            return False
        #outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "May 13")
        #if (len(outs) == 0):
            #key = False
        #outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "conference room B202 ")
        #if ((len(outs) == 0)):
            #key = False
        if (key):
            self.edit_started_correctly = True
        key_1 = True
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "10 minutes before")
        if (len(outs) == 0):
            key_1 = False
        return {"judge_page": True, "1": True, "2": self.edit_started_correctly, "3": key_1,
                "complete": self.edit_started_correctly and key_1}


class SingleTask_calendar_8(SingleTask):

    def judge_page(self, xml_compressed_tree):
        
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "work"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        self.edit_started_correctly = False
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        key = True
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "work")
        if (len(outs) == 0):
            key = False
        key_1 = True
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "computer")
        if (len(outs) == 0):
            key_1 = False
        return {"judge_page": True, "1": key, "2": key_1, "complete": key and key_1}


class SingleTask_calendar_9(SingleTask):

    def judge_page(self, xml_compressed_tree):
        
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "work"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        self.edit_started_correctly = False
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        key = True
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "work")
        if (len(outs) == 0):
            key = False
        key_1 = True
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Daily")
        if (len(outs) == 0):
            key_1 = False
        return {"judge_page": True, "1": key, "2": key_1,
                "complete": key and key_1}


class SingleTask_calendar_10(SingleTask):

    def judge_page(self, xml_compressed_tree):
        
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "this day") or not find_subtrees_of_parents_with_key(xml_compressed_tree, "SAVE"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        return {"judge_page": True, "1": True, "complete": True}


class SingleTask_calendar_11(SingleTask):

    def judge_page(self, xml_compressed_tree):
        
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "this day") or not find_subtrees_of_parents_with_key(xml_compressed_tree, "SAVE"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        self.edit_started_correctly = True
        key_1 = True
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Weekly")
        if (len(outs) == 0):
            key_1 = False
        return {"judge_page": True, "1": True, "2": self.edit_started_correctly, "3": key_1,
                "complete": self.edit_started_correctly and key_1}


class SingleTask_calendar_12(SingleTask):

    def judge_page(self, xml_compressed_tree):
        
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "Today"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Today")
        if (len(outs) > 0):
            self.edit_started_correctly = True
        key_1 = True
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "Hello")
        if (len(outs) == 0):
            key_1 = False
        return {"judge_page": True, "1": True, "2": self.edit_started_correctly, "3": key_1,
                "complete": self.edit_started_correctly and key_1}


class SingleTask_calendar_13(SingleTask):

    def judge_page(self, xml_compressed_tree):
        
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "exam") or not find_subtrees_of_parents_with_key(xml_compressed_tree, "SAVE"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        return {"judge_page": True, "1": True, "complete": True}


class SingleTask_calendar_14(SingleTask):

    def judge_page(self, xml_compressed_tree):
        
        if not find_subtrees_of_parents_with_key(xml_compressed_tree, "exam"):
            return False
        return True

    def judge(self, xml_compressed_tree, line, xml_path):
        if not self.judge_page(xml_compressed_tree):
            return {"judge_page": False}
        self.edit_started_correctly = True
        key_1 = True
        outs = find_subtrees_of_parents_with_key(xml_compressed_tree, "All-day")
        if (len(outs) == 0):
            key_1 = False
        return {"judge_page": True, "1": True, "2": self.edit_started_correctly, "3": key_1,
                "complete": self.edit_started_correctly and key_1}
