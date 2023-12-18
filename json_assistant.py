import json
import os
import shutil
import datetime
from string import hexdigits
from random import choice

file_dir = os.path.abspath(os.path.dirname(__file__))


class User:
    def __init__(self, user_id: int):
        self.user_id = user_id

    # @staticmethod
    # def __index_using_real_name():
    #     index_dict = {}
    #     for user in os.listdir(os.path.join(file_dir, "member_data")):
    #         user_id = user.split(".")[0]
    #         user = User(int(user_id))
    #         index_dict[user.get_real_name()] = user_id
    #     return index_dict
    #
    # @staticmethod
    # def real_name_index():
    #     return User.__index_using_real_name()

    @staticmethod
    def __get_all_user_id():
        file = os.path.join(file_dir, "member_data")
        return [i.split(".")[0] for i in os.listdir(file)]

    @staticmethod
    def convert_big5_to_utf8():
        user_list = User.__get_all_user_id()
        for user in user_list:
            try:
                file = os.path.join(file_dir, "member_data", user + ".json")
                with open(file, "r", encoding="big5") as f:
                    raw_data = f.read()
                with open(file, "w", encoding="utf-8") as f:
                    f.write(raw_data)
            except UnicodeDecodeError:
                print(f"Error occurred when converting {user}.json from big5 to utf-8.")
                pass

    def get_raw_info(self):
        file = os.path.join(file_dir, "member_data", str(self.user_id) + ".json")
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                user_info = json.loads(f.read())
                return user_info
        else:
            empty_data = {"real_name": None,
                          "total_meeting_time": 0,
                          "jobs": [],
                          "warning_points": 0,
                          "warning_history":
                              [["time", "reason", "points", "note"]],
                          }
            return empty_data

    def write_raw_info(self, data):
        file = os.path.join(file_dir, "member_data", str(self.user_id) + ".json")
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_real_name(self):
        user_info = self.get_raw_info()
        return user_info["real_name"]

    def set_real_name(self, name):
        user_info = self.get_raw_info()
        user_info["real_name"] = name
        self.write_raw_info(user_info)

    def get_jobs(self):
        user_info = self.get_raw_info()
        return user_info["jobs"]

    def add_job(self, job):
        user_info = self.get_raw_info()
        user_info["jobs"].append(job)
        self.write_raw_info(user_info)

    def remove_job(self, job):
        user_info = self.get_raw_info()
        user_info["jobs"].remove(job)
        self.write_raw_info(user_info)

    def clear_jobs(self):
        user_info = self.get_raw_info()
        user_info["jobs"] = []
        self.write_raw_info(user_info)

    def get_total_meeting_time(self):
        user_info = self.get_raw_info()
        return user_info["total_meeting_time"]

    def add_meeting_time(self, time):
        user_info = self.get_raw_info()
        user_info["total_meeting_time"] += time
        self.write_raw_info(user_info)

    def get_warning_points(self):
        user_info = self.get_raw_info()
        return user_info["warning_points"]

    def add_warning_points(self, points: [float, int], reason: str, note: str = None):

        user_info = self.get_raw_info()
        user_info["warning_points"] += points
        user_info["warning_history"].append(
            [datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), reason, points, note])
        self.write_raw_info(user_info)
        self.add_warning_history(self.user_id, points, reason, note)

    def get_raw_warning_history(self):
        user_info = self.get_raw_info()
        raw_history = user_info["warning_history"]
        del raw_history[0]
        return raw_history

    def get_formatted_str_warning_history(self) -> str:
        raw_history = self.get_raw_warning_history()
        formatted_history = ""
        for i in raw_history:
            add_or_subtract = "記點" if i[2] > 0 else "銷點"
            if i[3] is None:
                formatted_history += f"{i[0]}: {add_or_subtract} {abs(i[2])} 點 ({i[1]})\n"
            else:
                formatted_history += f"{i[0]}: {add_or_subtract} {abs(i[2])} 點 ({i[1]}) - {i[3]}\n"
            formatted_history += "\n"
        return formatted_history

    @staticmethod
    def get_all_warning_history():
        file = os.path.join(file_dir, "member_data", "warning_points_history.json")
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                return json.loads(f.read())
        else:
            return []

    @staticmethod
    def add_warning_history(user_id, points: [float, int], reason: str, note: str = None):
        file = os.path.join(file_dir, "member_data", "warning_points_history.json")
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                history = json.loads(f.read())
        else:
            history = []
        history.append([user_id, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), reason, points, note])
        with open(file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)


class Meeting:
    def __init__(self, event_id):
        self.event_id = event_id

    @staticmethod
    def create_new_meeting():
        while True:
            random_char_list = [choice(hexdigits) for i in range(5)]
            random_char = "".join(random_char_list)
            file = os.path.join(file_dir, "meeting_data", random_char + ".json")
            if not os.path.exists(file):
                break
        empty_data = Meeting(random_char).get_raw_info()
        Meeting(random_char).write_raw_info(empty_data)
        return random_char

    @staticmethod
    def get_all_meeting_id():
        file = os.path.join(file_dir, "meeting_data")
        return [i.split(".")[0] for i in os.listdir(file)]

    def __str__(self):
        return self.get_name()

    def get_raw_info(self):
        file = os.path.join(file_dir, "meeting_data", str(self.event_id) + ".json")
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                meeting_info = json.loads(f.read())
                return meeting_info
        else:
            empty_data = {
                "name": "",
                "description": "",
                "host": "",
                "link": "",
                "start_time": "",
                "started": False,
                "notified": False,
                "meeting_record_link": "",
                "absent_members": [["id", "reason"]]
            }
            return empty_data

    def write_raw_info(self, data):
        file = os.path.join(file_dir, "meeting_data", str(self.event_id) + ".json")
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def delete(self):
        file = os.path.join(file_dir, "meeting_data", str(self.event_id) + ".json")
        os.remove(file)

    def archive(self):
        file = os.path.join(file_dir, "meeting_data", str(self.event_id) + ".json")
        if os.path.exists(file):
            shutil.move(file, os.path.join(file_dir, "archived", "meeting", str(self.event_id) + ".json"))
        else:
            raise FileNotFoundError("File not found.")

    def get_name(self):
        meeting_info = self.get_raw_info()
        return meeting_info["name"]

    def set_name(self, name):
        meeting_info = self.get_raw_info()
        meeting_info["name"] = name
        self.write_raw_info(meeting_info)

    def get_description(self):
        meeting_info = self.get_raw_info()
        return meeting_info["description"]

    def set_description(self, description):
        meeting_info = self.get_raw_info()
        meeting_info["description"] = description
        self.write_raw_info(meeting_info)

    def get_host(self):
        meeting_info = self.get_raw_info()
        return meeting_info["host"]

    def set_host(self, host):
        meeting_info = self.get_raw_info()
        meeting_info["host"] = host
        self.write_raw_info(meeting_info)

    def get_link(self):
        meeting_info = self.get_raw_info()
        return meeting_info["link"]

    def set_link(self, link):
        meeting_info = self.get_raw_info()
        meeting_info["link"] = link
        self.write_raw_info(meeting_info)

    def get_start_time(self):
        meeting_info = self.get_raw_info()
        return meeting_info["start_time"]

    def set_start_time(self, start_time):
        meeting_info = self.get_raw_info()
        meeting_info["start_time"] = start_time
        self.write_raw_info(meeting_info)

    def get_absent_members(self):
        meeting_info = self.get_raw_info()
        members = meeting_info["absent_members"]
        del members[0]
        return meeting_info["absent_members"]

    def add_absent_member(self, member_id, reason):
        meeting_info = self.get_raw_info()
        meeting_info["absent_members"].append([member_id, reason])
        self.write_raw_info(meeting_info)

    def get_started(self):
        meeting_info = self.get_raw_info()
        return meeting_info["started"]

    def set_started(self, started: bool):
        meeting_info = self.get_raw_info()
        meeting_info["started"] = started
        self.write_raw_info(meeting_info)

    def get_notified(self):
        meeting_info = self.get_raw_info()
        return meeting_info["notified"]

    def set_notified(self, notified: bool):
        meeting_info = self.get_raw_info()
        meeting_info["notified"] = notified
        self.write_raw_info(meeting_info)

    def get_meeting_record_link(self):
        meeting_info = self.get_raw_info()
        try:
            return meeting_info["meeting_record_link"]
        except KeyError:
            return ""

    def set_meeting_record_link(self, link: str):
        meeting_info = self.get_raw_info()
        meeting_info["meeting_record_link"] = link
        self.write_raw_info(meeting_info)


class Message:
    def __init__(self, message_id):
        self.message_id = message_id

    @staticmethod
    def create_new_message():
        while True:
            random_char_list = [choice(hexdigits) for i in range(5)]
            random_char = "".join(random_char_list)
            file = os.path.join(file_dir, "message_data", random_char + ".json")
            if not os.path.exists(file):
                break
        empty_data = Message(random_char).get_raw_info()
        Message(random_char).write_raw_info(empty_data)
        return random_char

    @staticmethod
    def get_all_message_id():
        file = os.path.join(file_dir, "message_data")
        return [i.split(".")[0] for i in os.listdir(file)]

    def get_raw_info(self):
        file = os.path.join(file_dir, "message_data", str(self.message_id) + ".json")
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                message_info = json.loads(f.read())
                return message_info
        else:
            empty_data = {
                "author": "",
                "time": "",
                "content": "",
                "replied": False,
                "response": ""
            }
            return empty_data

    def write_raw_info(self, data):
        file = os.path.join(file_dir, "message_data", str(self.message_id) + ".json")
        with open(file, "w", encoding="utf-8") as fm:
            json.dump(data, fm, indent=2, ensure_ascii=False)

    def delete(self):
        file = os.path.join(file_dir, "message_data", str(self.message_id) + ".json")
        os.remove(file)

    def get_author(self):
        message_info = self.get_raw_info()
        return message_info["author"]

    def set_author(self, author):
        message_info = self.get_raw_info()
        message_info["author"] = author
        self.write_raw_info(message_info)

    def get_time(self):
        message_info = self.get_raw_info()
        return message_info["time"]

    def set_time(self, time):
        message_info = self.get_raw_info()
        message_info["time"] = time
        self.write_raw_info(message_info)

    def get_content(self):
        message_info = self.get_raw_info()
        return message_info["content"]

    def set_content(self, content):
        message_info = self.get_raw_info()
        message_info["content"] = content
        self.write_raw_info(message_info)

    def get_replied(self) -> bool:
        message_info = self.get_raw_info()
        return message_info["replied"]

    def set_replied(self, replied: bool):
        message_info = self.get_raw_info()
        message_info["replied"] = replied
        self.write_raw_info(message_info)

    def get_response(self):
        message_info = self.get_raw_info()
        return message_info["response"]

    def set_response(self, response):
        message_info = self.get_raw_info()
        message_info["response"] = response
        self.write_raw_info(message_info)
