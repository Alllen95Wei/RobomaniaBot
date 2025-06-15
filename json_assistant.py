# coding=utf-8
import json
import os
import shutil
import datetime
import logging
from string import hexdigits
from random import choice

base_dir = os.path.abspath(os.path.dirname(__file__))


class User:
    INIT_DATA = {
        "real_name": None,
        "total_meeting_time": 0,
        "jobs": [],
        "warning_points": 0.0,
        "warning_history": [["time", "reason", "points", "note"]],
        "email_address": "",
    }

    def __init__(self, user_id: int | str):
        self.user_id = user_id

    # @staticmethod
    # def __index_using_real_name():
    #     index_dict = {}
    #     for user in os.listdir(os.path.join(base_dir, "member_data")):
    #         user_id = user.split(".")[0]
    #         user = User(int(user_id))
    #         index_dict[user.get_real_name()] = user_id
    #     return index_dict
    #
    # @staticmethod
    # def real_name_index():
    #     return User.__index_using_real_name()

    @staticmethod
    def get_all_user_id():
        file = os.path.join(base_dir, "member_data")
        raw_list = [i.split(".")[0] for i in os.listdir(file)]
        raw_list.remove("warning_points_history")
        return raw_list

    @staticmethod
    def convert_big5_to_utf8():
        user_list = User.get_all_user_id()
        for user in user_list:
            try:
                file = os.path.join(base_dir, "member_data", user + ".json")
                with open(file, "r", encoding="big5") as f:
                    raw_data = f.read()
                with open(file, "w", encoding="utf-8") as f:
                    f.write(raw_data)
            except UnicodeDecodeError:
                print(f"Error occurred when converting {user}.json from big5 to utf-8.")

    def get_raw_info(self) -> dict:
        file = os.path.join(base_dir, "member_data", str(self.user_id) + ".json")
        logging.debug(f"Reading {file}")
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                user_info = json.loads(f.read())
                return user_info
        else:
            return self.INIT_DATA

    def write_raw_info(self, data):
        file = os.path.join(base_dir, "member_data", str(self.user_id) + ".json")
        logging.debug(f"Writing {file}")
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

    def get_warning_points(self) -> float | int:
        user_info = self.get_raw_info()
        return user_info["warning_points"]

    def add_warning_points(self, points: float | int, reason: str, note: str = None):
        user_info = self.get_raw_info()
        user_info["warning_points"] += points
        user_info["warning_history"].append(
            [
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                reason,
                points,
                note,
            ]
        )
        self.write_raw_info(user_info)
        self.add_warning_history(self.user_id, points, reason, note)

    def get_raw_warning_history(self) -> list:
        user_info = self.get_raw_info()
        raw_history = user_info["warning_history"]
        del raw_history[0]
        return raw_history

    def get_formatted_str_warning_history(self) -> str:
        raw_history = self.get_raw_warning_history()
        formatted_history = ""
        for i in raw_history:
            i: list[str | int]
            add_or_subtract = "記點" if i[2] > 0 else "銷點"
            if i[3] is None:
                formatted_history += (
                    f"{i[0]}: {add_or_subtract} {abs(i[2])} 點 ({i[1]})\n"
                )
            else:
                formatted_history += (
                    f"{i[0]}: {add_or_subtract} {abs(i[2])} 點 ({i[1]}) - {i[3]}\n"
                )
            formatted_history += "\n"
        return formatted_history

    @staticmethod
    def get_all_warning_history():
        file = os.path.join(base_dir, "member_data", "warning_points_history.json")
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                return json.loads(f.read())
        else:
            return []

    @staticmethod
    def add_warning_history(
        user_id, points: float | int, reason: str, note: str = None
    ):
        file = os.path.join(base_dir, "member_data", "warning_points_history.json")
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                history = json.loads(f.read())
        else:
            history = []
        history.append(
            [
                user_id,
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                reason,
                points,
                note,
            ]
        )
        with open(file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

    def set_email_address(self, email_address: str):
        user_info = self.get_raw_info()
        user_info["email_address"] = email_address
        self.write_raw_info(user_info)

    def get_email_address(self) -> str | None:
        user_info = self.get_raw_info()
        return user_info.get("email_address", None)


class Meeting:
    def __init__(self, event_id):
        self.event_id = event_id

    @staticmethod
    def create_new_meeting():
        while True:
            random_char_list = [choice(hexdigits) for _ in range(5)]
            random_char = "".join(random_char_list)
            file = os.path.join(base_dir, "meeting_data", random_char + ".json")
            if not os.path.exists(file):
                break
        empty_data = Meeting(random_char).get_raw_info()
        Meeting(random_char).write_raw_info(empty_data)
        return random_char

    @staticmethod
    def get_all_meeting_id():
        file = os.path.join(base_dir, "meeting_data")
        return [i.split(".")[0] for i in os.listdir(file)]

    def __str__(self):
        return self.get_name()

    def get_raw_info(self):
        file = os.path.join(base_dir, "meeting_data", str(self.event_id) + ".json")
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
                "start_time": 0,
                "started": False,
                "notified": False,
                "meeting_record_link": "",
                "absent_requests": {"pending": [], "reviewed": []},
            }
            return empty_data

    def write_raw_info(self, data):
        file = os.path.join(base_dir, "meeting_data", str(self.event_id) + ".json")
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def delete(self):
        file = os.path.join(base_dir, "meeting_data", str(self.event_id) + ".json")
        os.remove(file)

    def archive(self):
        file = os.path.join(base_dir, "meeting_data", str(self.event_id) + ".json")
        if os.path.exists(file):
            shutil.move(
                file,
                os.path.join(
                    base_dir, "archived", "meeting", str(self.event_id) + ".json"
                ),
            )
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

    def disable_absent(self, disabled: bool):
        meeting_info = self.get_raw_info()
        if disabled:
            meeting_info["absent_requests"] = "disabled"
        else:
            meeting_info["absent_requests"] = {"pending": [], "reviewed": []}
        self.write_raw_info(meeting_info)

    def get_absent_requests(self) -> dict[str, list[dict]] | None:
        meeting_info = self.get_raw_info()
        members = meeting_info.get(
            "absent_requests", {"pending": [], "reviewed": []}
        )
        if members == "disabled":
            return None
        else:
            return members

    def add_absent_request(self, member_id, timestamp, reason):
        meeting_info = self.get_raw_info()
        members = meeting_info["absent_requests"]
        if members == "disabled":
            raise Exception('"absent_requests" disabled.')
        meeting_info["absent_requests"]["pending"].append(
            {
                "member": member_id,
                "time": timestamp,
                "reason": reason,
                "result": {
                    "time": None,
                    "approved": None,
                    "reviewer": None,
                    "response": "",
                },
            }
        )
        self.write_raw_info(meeting_info)

    def review_absent_request(
        self,
        member_id: int,
        timestamp: int | float,
        reviewer_id: int,
        approved: bool = False,
        response: str = "",
    ):
        meeting_info = self.get_raw_info()
        pending_requests: list[dict] = meeting_info.get(
            "absent_requests", {"pending": [], "reviewed": []}
        ).get("pending", [])
        target_request = None
        target_index = 0
        for request in pending_requests:
            if request["member"] == member_id:
                target_request = request
                break
            target_index += 1
        if target_request is None:
            raise Exception(f"Request from {member_id} not found.")
        target_request["result"] = {
            "time": timestamp,
            "approved": approved,
            "reviewer": reviewer_id,
            "response": response,
        }
        del meeting_info["absent_requests"]["pending"][target_index]
        meeting_info["absent_requests"]["reviewed"].append(target_request)
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
            random_char_list = [choice(hexdigits) for _ in range(5)]
            random_char = "".join(random_char_list)
            file = os.path.join(base_dir, "message_data", random_char + ".json")
            if not os.path.exists(file):
                break
        empty_data = Message(random_char).get_raw_info()
        Message(random_char).write_raw_info(empty_data)
        return random_char

    @staticmethod
    def get_all_message_id():
        file = os.path.join(base_dir, "message_data")
        return [i.split(".")[0] for i in os.listdir(file)]

    def get_raw_info(self):
        file = os.path.join(base_dir, "message_data", str(self.message_id) + ".json")
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
                "response": "",
            }
            return empty_data

    def write_raw_info(self, data):
        file = os.path.join(base_dir, "message_data", str(self.message_id) + ".json")
        with open(file, "w", encoding="utf-8") as fm:
            json.dump(data, fm, indent=2, ensure_ascii=False)

    def delete(self):
        file = os.path.join(base_dir, "message_data", str(self.message_id) + ".json")
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


class Order:
    def __init__(self, order_id: str):
        self.order_id = order_id
        self.file_path = os.path.join(base_dir, "order_data", order_id + ".json")

    @staticmethod
    def generate_order_id():
        while True:
            random_char_list = [choice(hexdigits) for _ in range(5)]
            random_char = "".join(random_char_list)
            file = os.path.join(base_dir, "order_data", random_char + ".json")
            if not os.path.exists(file):
                break
        empty_data = Order(random_char).get_raw_info()
        Order(random_char).write_raw_info(empty_data)
        return random_char

    @staticmethod
    def get_all_order_id():
        file = os.path.join(base_dir, "order_data")
        return [i.split(".")[0] for i in os.listdir(file)]

    def get_raw_info(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, "r") as f:
                user_info = json.loads(f.read())
                return user_info
        else:
            empty_data = {
                "title": "",
                "description": "",
                "menu_link": "",
                "end_time": 0,
                "current_order": {},
                "manager": 0,
                "has_closed": False,
            }
            return empty_data

    def write_raw_info(self, data: dict):
        with open(self.file_path, "w") as f:
            json.dump(data, f, indent=2)

    def delete(self):
        if os.path.exists(self.file_path):
            os.remove(self.file_path)
        else:
            raise FileNotFoundError("Order not found.")

    def get_title(self):
        return self.get_raw_info()["title"]

    def set_title(self, title: str):
        data = self.get_raw_info()
        data["title"] = title
        self.write_raw_info(data)

    def get_description(self):
        return self.get_raw_info()["description"]

    def set_description(self, description: str):
        data = self.get_raw_info()
        data["description"] = description
        self.write_raw_info(data)

    def get_menu_link(self):
        return self.get_raw_info()["menu_link"]

    def set_menu_link(self, menu_link: str):
        data = self.get_raw_info()
        data["menu_link"] = menu_link
        self.write_raw_info(data)

    def get_end_time(self) -> int:
        return self.get_raw_info()["end_time"]

    def set_end_time(self, end_time: int):
        data = self.get_raw_info()
        data["end_time"] = end_time
        self.write_raw_info(data)

    def get_current_order(self) -> dict:
        return self.get_raw_info()["current_order"]

    def get_user_order(self, user_id: int):
        all_order = self.get_current_order()
        try:
            return all_order[str(user_id)]
        except KeyError:
            return []

    def add_order(self, user_id: int, order: list):
        data = self.get_raw_info()
        data["current_order"][str(user_id)] = order
        self.write_raw_info(data)

    def remove_order(self, user_id: int):
        data = self.get_raw_info()
        for i in data["current_order"]:
            if i == user_id:
                data["current_order"].pop(i)
                break
        self.write_raw_info(data)

    def user_has_joined_order(self, user_id: int) -> bool:
        order = self.get_current_order()
        return str(user_id) in order.keys()

    def get_manager(self):
        return self.get_raw_info()["manager"]

    def set_manager(self, manager: int):
        data = self.get_raw_info()
        data["manager"] = manager
        self.write_raw_info(data)

    def order_has_closed(self) -> bool:
        return self.get_raw_info()["has_closed"]

    def set_order_has_closed(self, status: bool):
        data = self.get_raw_info()
        data["has_closed"] = status
        self.write_raw_info(data)


class Reminder:
    def __init__(self, reminder_id: str):
        self.reminder_id = reminder_id

    @staticmethod
    def create_new_reminder():
        while True:
            random_char_list = [choice(hexdigits) for _ in range(5)]
            random_char = "".join(random_char_list)
            file = os.path.join(base_dir, "reminder_data", random_char + ".json")
            if not os.path.exists(file):
                break
        empty_data = Reminder(random_char).get_raw_info()
        Reminder(random_char).write_raw_info(empty_data)
        return random_char

    @staticmethod
    def get_all_reminder_id():
        file = os.path.join(base_dir, "reminder_data")
        return [i.split(".")[0] for i in os.listdir(file)]

    def get_raw_info(self):
        file = os.path.join(base_dir, "reminder_data", str(self.reminder_id) + ".json")
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                reminder_info = json.loads(f.read())
                return reminder_info
        else:
            empty_data = {
                "title": "",
                "description": "",
                "mention_roles": [],
                "progress": 0,
                "sub_tasks": [],
                "author": 0,
                "time": 0,
                "notified": False,
            }
            return empty_data

    def write_raw_info(self, data):
        file = os.path.join(base_dir, "reminder_data", str(self.reminder_id) + ".json")
        with open(file, "w", encoding="utf-8") as fm:
            json.dump(data, fm, indent=2, ensure_ascii=False)

    def get_title(self) -> str:
        reminder_info = self.get_raw_info()
        return reminder_info.get("title", "")

    def set_title(self, title: str):
        reminder_info = self.get_raw_info()
        reminder_info["title"] = title
        self.write_raw_info(reminder_info)

    def get_description(self) -> str:
        reminder_info = self.get_raw_info()
        return reminder_info.get("description", "")

    def set_description(self, description: str):
        reminder_info = self.get_raw_info()
        reminder_info["description"] = description
        self.write_raw_info(reminder_info)

    def get_mention_roles(self) -> list[int]:
        reminder_info = self.get_raw_info()
        return reminder_info.get("mention_roles", [])

    def add_mention_roles(self, roles_to_add: list[int]) -> list[int]:
        reminder_info = self.get_raw_info()
        for role in roles_to_add:
            if role not in reminder_info["mention_roles"]:
                reminder_info["mention_roles"].append(role)
            else:
                roles_to_add.remove(role)
        self.write_raw_info(reminder_info)
        return roles_to_add

    def remove_mention_roles(self, roles_to_remove: list[int]) -> list[int]:
        reminder_info = self.get_raw_info()
        for role in roles_to_remove:
            if role in reminder_info["mention_roles"]:
                reminder_info["mention_roles"].remove(role)
            else:
                roles_to_remove.remove(role)
        self.write_raw_info(reminder_info)
        return roles_to_remove

    def get_progress(self) -> int:
        reminder_info = self.get_raw_info()
        return reminder_info.get("progress", 0)

    def set_progress(self, progress: int):
        if progress < 0 or progress > 100:
            raise ValueError
        reminder_info = self.get_raw_info()
        reminder_info["progress"] = progress
        self.write_raw_info(reminder_info)

    def get_subtasks(self) -> list[dict]:
        reminder_info = self.get_raw_info()
        return reminder_info.get("progress", [])

    def add_subtasks(self, task_name: str, task_progress: float):
        if task_progress < 0 or task_progress > 100:
            raise ValueError
        new_task = {"name": task_name, "progress": task_progress}
        reminder_info = self.get_raw_info()
        reminder_info["sub_tasks"].append(new_task)
        self.write_raw_info(reminder_info)

    def get_author(self) -> int:
        reminder_info = self.get_raw_info()
        return reminder_info.get("author", 0)

    def set_author(self, author: int):
        reminder_info = self.get_raw_info()
        reminder_info["author"] = author
        self.write_raw_info(reminder_info)

    def get_time(self) -> int:
        reminder_info = self.get_raw_info()
        return reminder_info.get("time", 0)

    def set_time(self, time: int):
        reminder_info = self.get_raw_info()
        reminder_info["time"] = time
        self.write_raw_info(reminder_info)

    def get_notified(self) -> bool:
        reminder_info = self.get_raw_info()
        return reminder_info.get("notified", False)

    def set_notified(self, is_notified: bool = True):
        reminder_info = self.get_raw_info()
        reminder_info["notified"] = is_notified
        self.write_raw_info(reminder_info)

    def delete(self):
        file = os.path.join(base_dir, "reminder_data", str(self.reminder_id) + ".json")
        os.remove(file)


class WarnPtsRankRecord:
    INIT_DATA = {"data": []}

    def __init__(self, start_date: datetime.datetime):
        self.start_date = start_date
        self.file_path = os.path.join(
            base_dir,
            "warning_points_record_data",
            self.start_date.strftime("%Y-%m-%d") + ".json",
        )

    def get_raw_info(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, "r", encoding="utf-8") as f:
                warning_points_record = json.loads(f.read())
                return warning_points_record
        else:
            return self.INIT_DATA

    def write_raw_info(self, data: dict):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
